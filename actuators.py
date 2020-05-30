from plantyutils import DecimalEncoder
import asyncio
import websockets
import pathlib
import ssl
import time
from datetime import datetime, timedelta, timezone
import subprocess
import boto3
from boto3.dynamodb.conditions import Key
import json
import decimal
import sys
import psutil
from dynamodb_json import json_util as dynamo_json
import logging
import RPi.GPIO as GPIO
import logging.config
import statistics

logging.config.fileConfig('logging.conf')
# create logger
logger = logging.getLogger('actuators')

retryCounter = 0

GPIO.setmode(GPIO.BCM)

MY_ID = "e0221623-fb88-4fbd-b524-6f0092463c93"
STREAM_PROCCESS_NAME = "kinesis_video_g"

process = None

camera_motor_pins = [4, 17, 27, 22]

for pin in camera_motor_pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, 0)

halfstep_seq_right = [
    [0, 0, 0, 1],
    [0, 0, 1, 1],
    [0, 0, 1, 0],
    [0, 1, 1, 0],
    [0, 1, 0, 0],
    [1, 1, 0, 0],
    [1, 0, 0, 0],
    [1, 0, 0, 1]
]

halfstep_seq_left = [
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
    [1, 0, 0, 1]
]

# GPIO SETUP
# We are using GPIO numbers Instead of Physical PIN numbers.
UV_LAMP_GPIO = 24            # PIN 18
WATER_CONTROL_GPIO = 25      # PIN 22
HEATER_CONTROL_GPIO = 23     # PIN 16
FAN_CONTROL_GPIO = 11        # PIN 23

isUVOn = False

# GPIO.setwarnings(False)
GPIO.setup(UV_LAMP_GPIO, GPIO.OUT, initial=1)
GPIO.setup(WATER_CONTROL_GPIO, GPIO.OUT, initial=1)
GPIO.setup(HEATER_CONTROL_GPIO, GPIO.OUT)
GPIO.setup(FAN_CONTROL_GPIO, GPIO.OUT)

dynamodb = boto3.resource('dynamodb', region_name='eu-west-1',
                          endpoint_url="https://dynamodb.eu-west-1.amazonaws.com")
plantersActionsTable = dynamodb.Table('PlantersActions')

waterAddedTime = datetime(2000, 1, 1)
activeSubPhase = {
    "subPhase": {"name": ""},
    "startTimeStamp": datetime(2000, 1, 1),
    "uvValues": []

}
measurements = {
    "isInitiated": False,
    "timeStamp": datetime.utcnow(),
    "uvIntensity": 0,
    "soilHumidity": 0,
    "ambientTemperature": 0,
    "airHumidity": 0
}


def checkIfProcessRunning(processName):
    for proc in psutil.process_iter():
        try:
            if processName.lower() in proc.name().lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False


def uvOn():
    global isUVOn
    GPIO.output(UV_LAMP_GPIO, 0)
    isUVOn = True
    logger.info("UV On")
    saveActionToDb('UV_LAMP', 'ON')


def uvOff():
    global isUVOn
    GPIO.output(UV_LAMP_GPIO, 1)
    isUVOn = False
    logger.info("UV Off")
    saveActionToDb('UV_LAMP', 'OFF')


def heaterOn():
    GPIO.output(HEATER_CONTROL_GPIO, 0)
    logger.info("HEATER On")
    saveActionToDb('HEATER', 'ON')


def heaterOff():
    GPIO.output(HEATER_CONTROL_GPIO, 0)
    logger.info("HEATER On")
    saveActionToDb('HEATER', 'OFF')


def fanOn():
    GPIO.output(FAN_CONTROL_GPIO, 0)
    logger.info("FAN On")
    saveActionToDb('FAN', 'ON')


def fanOff():
    GPIO.output(FAN_CONTROL_GPIO, 1)
    logger.info("FAN Off")
    saveActionToDb('FAN', 'OFF')


def addWater(secconds=10):
    subPhase = getSubPhase()
    if measurements["soilHumidity"] >= subPhase["soilHumidity"]["max"]:
        logger.error("Attempt To Over Humidify Soil Blocked.")
        return

    global waterAddedTime
    logger.info("Adding Water")
    GPIO.output(WATER_CONTROL_GPIO, 0)
    time.sleep(secconds)
    GPIO.output(WATER_CONTROL_GPIO, 1)
    waterAddedTime = datetime.utcnow()
    saveActionToDb('WATER', 'ADD')


def moveCameraLeft(isLong):
    print(f'move_left Camera {"Long" if isLong else "Short"}')
    steps = 600 if isLong else 200
    for _ in range(steps):
        for halfstep in range(8):
            for pin in range(4):
                GPIO.output(camera_motor_pins[pin],
                            halfstep_seq_left[halfstep][pin])
            time.sleep(0.001)
    saveActionToDb(f'MOVE_CAMERA_{"LONG" if isLong else "SHORT"}', 'LEFT')


def moveCameraRight(isLong):
    print(f'move_right Camera {"Long" if isLong else "Short"}')
    steps = 600 if isLong else 200
    for _ in range(steps):
        for halfstep in range(8):
            for pin in range(4):
                GPIO.output(camera_motor_pins[pin],
                            halfstep_seq_right[halfstep][pin])
            time.sleep(0.001)
    saveActionToDb(f'MOVE_CAMERA_{"LONG" if isLong else "SHORT"}', 'RIGHT')


def cameraMove(direction, isLong):
    if direction == "R":
        moveCameraRight(isLong)
    elif direction == "L":
        moveCameraLeft(isLong)
    else:
        print("Bad Camera Direction: {0}".format(direction))


def videoStreamOn():
    global process
    process = subprocess.Popen('/home/pi/Desktop/run_video',
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, shell=True)
    saveActionToDb('VIDEO_STREAM', 'ON')


def videoStreamOff():
    global process
    process.kill()
    subprocess.call("killall kinesis_video_g", shell=True)
    saveActionToDb('VIDEO_STREAM', 'OFF')


def saveActionToDb(actionType, actionValue):
    timeStamp = decimal.Decimal(datetime.utcnow().timestamp())
    response = plantersActionsTable.put_item(
        Item={
            'planterId': MY_ID,
            'timeStamp':    timeStamp,
            'type': actionType,
            'value': actionValue
        }
    )

    if(response["ResponseMetadata"]["HTTPStatusCode"] == 200):
        print(f"Saved {actionType}_{actionValue} To Database.")
    else:
        print(f"Failed To Save {actionType}_{actionValue}")


def load_growth_plan():
    client = boto3.client('dynamodb')
    try:
        response = client.get_item(TableName='Test_Planters', Key={
                                   'UUID': {'S': str(MY_ID)}})
        r = dynamo_json.loads(response)

        global GROWTH_PLAN
        GROWTH_PLAN = r
        # time_activated = r['Item']['TimeActivated']
        # local_time = time.ctime(time_activated)
        # print("Local time:", local_time)
        # current_time = time.time()
        # current_time = str(current_time)
        # needed_day = float(current_time) - float(time_activated)
        # needed_day = int(needed_day / 86400)
        # phases = r['Item']['activeGrowthPlan']['phases']
        # for phase in phases:
        #     if int(phase['fromDay']) <= needed_day < int(phase['toDay']):
        # print(phase)

    except Exception:
        print('Error loading growth plan')


def getSubPhase():
    time_activated = GROWTH_PLAN['Item']['TimeActivated']
    current_time = datetime.utcnow().timestamp()
    current_time = str(current_time)
    needed_day = float(current_time) - float(time_activated)
    needed_day = int(needed_day / 86400)
    phases = GROWTH_PLAN['Item']['activeGrowthPlan']['phases']
    for phase in phases:
        if int(phase['fromDay']) <= needed_day < int(phase['toDay']):
            now = datetime.utcnow()
            for subphase in phase['subPhases']:
                if int(subphase['fromHour']) <= now.hour < int(subphase['toHour']):
                    return subphase


# def getNeededTemp():
#     subphase = getSubPhase()
#     return subphase['temperature']['min'], subphase['temperature']['max']


# def getNeededUV():
#     subphase = getSubPhase()
#     return subphase['uvIntensity']['min'], subphase['uvIntensity']['max']


# def getNeededHumid():
#     subphase = getSubPhase()
#     return subphase['soilHumidity']['min'], subphase['soilHumidity']['max']

def getMeasurementsForCurrentSubphase(subPhase):
    table = dynamodb.Table('PlantersMeasurements')

    utcNow = datetime.utcnow()
    now = decimal.Decimal(utcNow.timestamp())
    subPhaseStart = decimal.Decimal(
        datetime(utcNow.year, utcNow.month, utcNow.day,
                 subPhase["fromHour"], 0, 0,tzinfo=timezone.utc).timestamp()
    )

    try:
        response = table.query(KeyConditionExpression=Key('planterId').eq(
            MY_ID) & Key('timeStamp').between(subPhaseStart, now))

        items = response["Items"]
        for m in items:
            activeSubPhase["uvValues"].append(m["uvIntesity"])
        logger.info("Loaded UV values for Current Phase")

    except:
        logger.critical("Failed to load SubPhase Measurements till now")
        raise


def setMeasurements(command):
    measurements["timeStamp"] = datetime.utcnow()
    measurements["ambientTemperature"] = (float)((command[3]).split(":")[1])
    measurements["uvIntensity"] = (int)((command[4]).split(":")[1])
    activeSubPhase["uvValues"].append(measurements["uvIntensity"])
    measurements["soilHumidity"] = (float)((command[5]).split(":")[1])
    measurements["airHumidity"] = (float)((command[6]).split(":")[1])
    measurements["isInitiated"] = True


def on_message(message):
    global MY_ID, STREAM_PROCCESS_NAME
    global isUVOn
    global UV_LAMP_GPIO
    command = (str)(message).split(";")
    logger.info(f'{command[2]} <<< {command[0]}')
    if command[1] != MY_ID:
        return "Ignore"

    if command[0] == "FROM_PLANTER":
        if command[2] == "MEASUREMENTS":
            setMeasurements(command)
        return "Ignore"

    if command[2] == "PING":
        return "PONG"

    if command[2] == "UV_LAMP_ON" and not isUVOn:
        uvOn()
        return "UV_LAMP_IS_ON"

    if command[2] == "UV_LAMP_OFF" and isUVOn:
        uvOff()
        return "UV_LAMP_IS_OFF"

    if command[2] == "ADD_WATER":
        addWater()
        return "WATER_ADDED"

    if command[2] == "MOVE_CAMERA_RIGHT":
        cameraMove("R", False)
        return "CAMERA_MOVED_RIGHT"

    if command[2] == "MOVE_CAMERA_LEFT":
        cameraMove("L", False)
        return "CAMERA_MOVED_LEFT"

    if command[2] == "MOVE_CAMERA_RIGHT_LONG":
        cameraMove("R", True)
        return "CAMERA_MOVED_RIGHT_LONG"

    if command[2] == "MOVE_CAMERA_LEFT_LONG":
        cameraMove("L", True)
        return "CAMERA_MOVED_LEFT_LONG"

    if command[2] == "VIDEO_STREAM_ON":
        videoStreamOn()
        return "STREAM_STARTED"

    if command[2] == "VIDEO_STREAM_OFF":
        videoStreamOff()
        return "STREAM_STOPPED"

    if command[2] == "VIDEO_STREAM_STATUS":
        return "STREAM_ON" if checkIfProcessRunning(STREAM_PROCCESS_NAME) else "STREAM_OFF"

    if command[2] == "UV_LAMP_STATUS":
        return "LAMP_IS_ON" if isUVOn else "LAMP_IS_OFF"

    if command[2] == "RELOAD_GROWTH_PLAN":
        load_growth_plan()
        return "GROWTH_PLAN_RELOADED"

    logger.info(f"Unknown Command: {command}")
    return "FAILED"


def waterAddedSeccondsAgo():
    global waterAddedTime
    now = datetime.utcnow()
    return now - waterAddedTime


def handleGrowthPlantSoilHumidity(subPhase):
    if(subPhase["soilHumidity"] == None or subPhase["soilHumidity"]["min"] == None):
        logger.error(
            "Failed To read Subphase Soil Humidity values. Skipping Soil Humidity check.")
        return

    hNow = measurements["soilHumidity"]
    hMin = subPhase["soilHumidity"]["min"]
    logger.info(f'Soil Humidity Check [ now: {hNow:0.3f} | min: {hMin:0.3f} ]')
    if hNow < hMin:
        if waterAddedSeccondsAgo().total_seconds() > 7*60:
            addWater(20)


def handleGrowthPlantUvAverage(subPhase):
    if(subPhase["uvIntensity"] == None or subPhase["uvIntensity"]["min"] == None):
        logger.error("Failed To read Subphase UV values. Skipping UV check.")
        return

    uvAvgNow = statistics.mean(activeSubPhase["uvValues"])
    uvNow = measurements["uvIntensity"]
    uvMin = subPhase["uvIntensity"]["min"]
    logger.info(
        f'UV Check [ now: {uvNow:0} | mean {uvAvgNow:0.3f} | min: {uvMin:0} ]')

    if uvAvgNow <= uvMin and uvNow <= uvMin and not isUVOn:
        uvOn()
    elif isUVOn:
        uvOff()


def applyGrowthPlan():
    if measurements["isInitiated"]:
        subPhase = getSubPhase()
        if(subPhase == None):
            logger.error("Failed To read Subphase values. Skipping check.")
            return
        if(activeSubPhase["subPhase"]["name"] != subPhase["name"]):
            activeSubPhase["subPhase"] = subPhase

        handleGrowthPlantSoilHumidity(subPhase)
        handleGrowthPlantUvAverage(subPhase)


async def websocket_handler():
    global retryCounter
    uri = "wss://0xl08k0h22.execute-api.eu-west-1.amazonaws.com/dev"
    async with websockets.connect(uri, ssl=True) as websocket:
        logger.info("Connected to Websocket")
        retryCounter = 0
        while True:
            message = await websocket.recv()
            semicolonCount = sum(map(lambda x: 1 if ';' in x else 0, message))
            if semicolonCount != 2 and semicolonCount != 5 and semicolonCount != 6:
                logger.warning("Bad Command")
                logger.warning(message)
                answer = '{{\"action":"message","message":"FROM_PLANTER;e0221623-fb88-4fbd-b524-6f0092463c93;BAD_COMMAND"}}'
                await websocket.send(answer)
                continue
            result = on_message(message)
            applyGrowthPlan()
            if result == "Ignore":
                continue

            answer = f'{{\"action":"message","message":"FROM_PLANTER;e0221623-fb88-4fbd-b524-6f0092463c93;{result}"}}'
            await websocket.send(answer)
            logging.info(f'>>> {result}')


if __name__ == "__main__":
    logger.info('Actuators Started!')
    load_growth_plan()
    activeSubPhase["subPhase"] = getSubPhase()
    getMeasurementsForCurrentSubphase(activeSubPhase["subPhase"])

    while True and retryCounter < 20:
        try:
            asyncio.get_event_loop().run_until_complete(websocket_handler())
        except websockets.exceptions.ConnectionClosedOK:
            logger.warning(
                f"Connection closed by server.Reconnecting. Retry:{retryCounter}")
            time.sleep(15)
            retryCounter = retryCounter+1

        except websockets.exceptions.ConnectionClosedError:
            logger.warning(
                f"Connection closed by server error. Reconnecting. Retry:{retryCounter}")
            time.sleep(15)
            retryCounter = retryCounter+1
        except:
            logger.critical(sys.exc_info()[0])
            GPIO.cleanup()
            raise

    GPIO.cleanup()
