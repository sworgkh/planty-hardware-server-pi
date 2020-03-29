from plantyutils import DecimalEncoder
import asyncio
import websockets
import pathlib
import ssl
import time
import datetime
import subprocess
import boto3
import json
import decimal

import logging
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
MY_ID = "e0221623-fb88-4fbd-b524-6f0092463c93"

process = None
logger = logging.getLogger('websockets')
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

camera_motor_pins = [4, 17, 27, 22]

for pin in camera_motor_pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, 0)

halfstep_seq_right = [
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
    [1, 0, 0, 1]
]
halfstep_seq_left = [
    [0, 0, 0, 1],
    [0, 0, 1, 1],
    [0, 0, 1, 0],
    [0, 1, 1, 0],
    [0, 1, 0, 0],
    [1, 1, 0, 0],
    [1, 0, 0, 0],
    [1, 0, 0, 1]
]

# GPIO SETUP
UV_LAMP_PIN = 24
WATER_CONTROL_PIN = 25
HEATER_CONTROL_PIN = 5
FAN_CONTROL_PIN = 6

isUVOn = False

# GPIO.setwarnings(False)
GPIO.setup(UV_LAMP_PIN, GPIO.OUT, initial=1)
GPIO.setup(WATER_CONTROL_PIN, GPIO.OUT, initial=1)
#GPIO.setup(HEATER_CONTROL_PIN, GPIO.OUT)
#GPIO.setup(FAN_CONTROL_PIN, GPIO.OUT)

dynamodb = boto3.resource('dynamodb', region_name='eu-west-1',
                          endpoint_url="https://dynamodb.eu-west-1.amazonaws.com")
plantersActionsTable = dynamodb.Table('PlantersActions')


def uvOn():
    print("UV On")
    GPIO.output(UV_LAMP_PIN, 0)
    saveActionToDb('UV_LAMP', 'ON')


def uvOff():
    print("UV Off")
    GPIO.output(UV_LAMP_PIN, 1)
    saveActionToDb('UV_LAMP', 'OFF')


def addWater():
    print("Adding Water")
    GPIO.output(WATER_CONTROL_PIN, 0)
    time.sleep(3)
    GPIO.output(WATER_CONTROL_PIN, 1)
    saveActionToDb('WATER', 'ADD')


def moveCameraLeft():
    print('move_left Camera')
    for i in range(100):
        for halfstep in range(8):
            for pin in range(4):
                GPIO.output(camera_motor_pins[pin],
                            halfstep_seq_left[halfstep][pin])
            time.sleep(0.001)
    saveActionToDb('MOVE_CAMERA', 'LEFT')


def moveCameraRight():
    print('move_right Camera')
    for i in range(100):
        for halfstep in range(8):
            for pin in range(4):
                GPIO.output(camera_motor_pins[pin],
                            halfstep_seq_right[halfstep][pin])
            time.sleep(0.001)
    saveActionToDb('MOVE_CAMERA', 'RIGHT')


def cameraMove(direction):
    if direction == "R":
        moveCameraRight()
    elif direction == "L":
        moveCameraLeft()
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
    subprocess.call("killall run_video", shell=True)
    saveActionToDb('VIDEO_STREAM', 'OFF')


def saveActionToDb(actionType, actionValue):
    timeStamp = decimal.Decimal(datetime.datetime.utcnow().timestamp())
    response = plantersActionsTable.put_item(
        Item={
            'planterId': MY_ID,
            'timeStamp':    timeStamp,
            'type': actionType,
            'value': actionValue
        }
    )

    print(json.dumps(response, indent=4, cls=DecimalEncoder))


def on_message(message):
    global MY_ID
    global isUVOn
    global UV_LAMP_PIN
    command = (str)(message).split(";")
    print(command)
    print(f'<<< {command[2]}')
    if command[0] == "FROM_PLANTER" or command[1] != MY_ID:
        return "Ignore"

    if command[2] == "UV_LAMP_ON":
        uvOn()
        return "UV_LAMP_IS_ON"

    elif command[2] == "UV_LAMP_OFF":
        uvOff()
        return "UV_LAMP_IS_OFF"

    elif command[2] == "ADD_WATER":
        addWater()
        return "WATER_ADDED"

    elif command[2] == "MOVE_CAMERA_RIGHT":
        cameraMove("R")
        return "CAMERA_MOVED_RIGHT"

    elif command[2] == "MOVE_CAMERA_LEFT":
        cameraMove("L")
        return "CAMERA_MOVED_LEFT"

    elif command[2] == "VIDEO_STREAM_ON":
        videoStreamOn()
        return "STREAM_STARTED"

    elif command[2] == "VIDEO_STREAM_OFF":
        videoStreamOff()
        return "STREAM_STOPPED"

    else:
        print("Unknown Command: {0}".format(command))
        return "FAILED"


async def websocket_handler():
    uri = "wss://0xl08k0h22.execute-api.eu-west-1.amazonaws.com/dev"
    async with websockets.connect(uri, ssl=True) as websocket:
        while True:
            message = await websocket.recv()
            semicolonCount = sum(map(lambda x: 1 if ';' in x else 0, message))
            if semicolonCount != 2 and semicolonCount != 5:
                print(message)
                print("Bad Command")
                answer = '{{\"action":"message","message":"FROM_PLANTER;e0221623-fb88-4fbd-b524-6f0092463c93;BAD_COMMAND"}}'
                await websocket.send(answer)
                continue
            result = on_message(message)
            if result == "Ignore":
                print('Ignore')
                continue

            answer = f'{{\"action":"message","message":"FROM_PLANTER;e0221623-fb88-4fbd-b524-6f0092463c93;{result}"}}'
            await websocket.send(answer)
            print(f'>>> {result}')


if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(websocket_handler())
    finally:
        GPIO.cleanup()
