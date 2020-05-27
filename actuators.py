from plantyutils import DecimalEncoder
import asyncio
import websockets
import pathlib
import ssl
import time
from datetime import datetime, timedelta
import subprocess
import boto3
import json
import decimal
import sys
import psutil
from dynamodb_json import json_util as dynamo_json
import logging
import RPi.GPIO as GPIO


GPIO.setmode(GPIO.BCM)

MY_ID = "e0221623-fb88-4fbd-b524-6f0092463c93"
STREAM_PROCCESS_NAME = "kinesis_video_g"

process = None

logger = logging.getLogger('websockets')
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

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
measurements = {
    "isInitiated": False,
    "timeStamp": datetime.utcnow(),
    "uvIntensity": 0,
    "soilHumidity": 0,
    "ambientTemperature": 0,
    "airHumidity": 0
}


def log(text):
    print(f'{datetime.now()} {text}')


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
    print("UV On")
    saveActionToDb('UV_LAMP', 'ON')


def uvOff():
    global isUVOn
    GPIO.output(UV_LAMP_GPIO, 1)
    isUVOn = False
    print("UV Off")
    saveActionToDb('UV_LAMP', 'OFF')


def heaterOn():
    GPIO.output(HEATER_CONTROL_GPIO, 0)
    print("HEATER On")
    saveActionToDb('HEATER', 'ON')


def heaterOff():
    GPIO.output(HEATER_CONTROL_GPIO, 0)
    print("HEATER On")
    saveActionToDb('HEATER', 'OFF')


def fanOn():
    GPIO.output(FAN_CONTROL_GPIO, 0)
    print("FAN On")
    saveActionToDb('FAN', 'ON')


def fanOff():
    GPIO.output(FAN_CONTROL_GPIO, 1)
    print("FAN Off")
    saveActionToDb('FAN', 'OFF')


def addWater(secconds=10):
    global waterAddedTime
    print("Adding Water")
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
    current_time = time.time()
    current_time = str(current_time)
    needed_day = float(current_time) - float(time_activated)
    needed_day = int(needed_day / 86400)
    phases = GROWTH_PLAN['Item']['activeGrowthPlan']['phases']
    for phase in phases:
        if int(phase['fromDay']) <= needed_day < int(phase['toDay']):
            now = datetime.now()
            for subphase in phase['subPhases']:
                if int(subphase['fromHour']) <= now.hour < int(subphase['toHour']):
                    return subphase


def getNeededTemp():
    subphase = getSubPhase()
    return subphase['temperature']['min'], subphase['temperature']['max']


def getNeededUV():
    subphase = getSubPhase()
    return subphase['uvIntensity']['min'], subphase['uvIntensity']['max']


def getNeededHumid():
    subphase = getSubPhase()
    return subphase['soilHumidity']['min'], subphase['soilHumidity']['max']


def setMeasurements(command):
    measurements["timeStamp"] = datetime.utcnow()
    measurements["ambientTemperature"] = (float)((command[3]).split(":")[1])
    measurements["uvIntensity"] = (int)((command[4]).split(":")[1])
    measurements["soilHumidity"] = (float)((command[5]).split(":")[1])
    measurements["airHumidity"] = (float)((command[6]).split(":")[1])
    measurements["isInitiated"] = True


def on_message(message):
    global MY_ID, STREAM_PROCCESS_NAME
    global isUVOn
    global UV_LAMP_GPIO
    command = (str)(message).split(";")
    log(f'{command[2]} <<< {command[0]}')
    # print(command)
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

    log("Unknown Command: {0}".format(command))
    return "FAILED"


def waterAddedSeccondsAgo():
    global waterAddedTime
    now = datetime.utcnow()
    return now - waterAddedTime


def handleGrowthPlantSoilHumidity(subPhase):
    hNow = measurements["soilHumidity"]
    hMin = subPhase["soilHumidity"]["min"]
    print(f'Soil Humidity Check now: {hNow:0.3f} | min: {hMin:0.3f}')
    if hNow < hMin:
        if waterAddedSeccondsAgo().total_seconds() > 5*60:
            addWater(20)


def applyGrowthPlan():
    if measurements["isInitiated"]:
        subPhase = getSubPhase()
        handleGrowthPlantSoilHumidity(subPhase)


async def websocket_handler():
    uri = "wss://0xl08k0h22.execute-api.eu-west-1.amazonaws.com/dev"
    async with websockets.connect(uri, ssl=True) as websocket:
        log("Connected to Websocket\n")
        while True:
            message = await websocket.recv()
            semicolonCount = sum(map(lambda x: 1 if ';' in x else 0, message))
            if semicolonCount != 2 and semicolonCount != 5 and semicolonCount != 6:
                log(message)
                log("Bad Command")
                answer = '{{\"action":"message","message":"FROM_PLANTER;e0221623-fb88-4fbd-b524-6f0092463c93;BAD_COMMAND"}}'
                await websocket.send(answer)
                continue
            result = on_message(message)
            applyGrowthPlan()
            if result == "Ignore":
                log('Ignore')
                continue

            answer = f'{{\"action":"message","message":"FROM_PLANTER;e0221623-fb88-4fbd-b524-6f0092463c93;{result}"}}'
            await websocket.send(answer)
            log(f'>>> {result}')


if __name__ == "__main__":
    retryCounter = 0
    load_growth_plan()
    while True and retryCounter < 20:
        try:
            asyncio.get_event_loop().run_until_complete(websocket_handler())
        except websockets.exceptions.ConnectionClosedOK:
            log("Connection closed by server.\n Reconnecting.\n")
            time.sleep(15)
            retryCounter = retryCounter+1

        except websockets.exceptions.ConnectionClosedError:
            log("Connection closed by server error.\n Reconnecting.\n")
            time.sleep(15)
            retryCounter = retryCounter+1
        except:
            print("Unexpected error:", sys.exc_info()[0])
            GPIO.cleanup()
            raise

    GPIO.cleanup()
