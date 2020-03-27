
import asyncio
import websockets
import pathlib
import ssl
import json
import time
import subprocess

import logging
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)


process = None
logger = logging.getLogger('websockets')
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

camera_motor_pins = [4,17,27,22]

for pin in camera_motor_pins:
  GPIO.setup(pin, GPIO.OUT)
  GPIO.output(pin, 0)

halfstep_seq_right = [
  [1,0,0,0],
  [1,1,0,0],
  [0,1,0,0],
  [0,1,1,0],
  [0,0,1,0],
  [0,0,1,1],
  [0,0,0,1],
  [1,0,0,1]
]
halfstep_seq_left = [
  [0,0,0,1],
  [0,0,1,1],
  [0,0,1,0],
  [0,1,1,0],
  [0,1,0,0],
  [1,1,0,0],
  [1,0,0,0],
  [1,0,0,1]
]

#GPIO SETUP
UV_LAMP_PIN = 24
WATER_CONTROL_PIN = 25
HEATER_CONTROL_PIN = 5
FAN_CONTROL_PIN = 6

isUVOn = False

#GPIO.setwarnings(False)
GPIO.setup(UV_LAMP_PIN, GPIO.OUT, initial = 1)
GPIO.setup(WATER_CONTROL_PIN, GPIO.OUT, initial = 1)
#GPIO.setup(HEATER_CONTROL_PIN, GPIO.OUT)
#GPIO.setup(FAN_CONTROL_PIN, GPIO.OUT)

#GPIO.output(HEATER_CONTROL_PIN, GPIO.LOW)
#GPIO.output(FAN_CONTROL_PIN, GPIO.LOW)

def uvOn():
    print("UV On")
    GPIO.output(UV_LAMP_PIN, 0)

def uvOff():
    print("UV Off")
    GPIO.output(UV_LAMP_PIN, 1)

def addWater():
    print("Adding Water")
    GPIO.output(WATER_CONTROL_PIN, 0)
    time.sleep(3)
    GPIO.output(WATER_CONTROL_PIN, 1)

def moveCameraLeft():
    print('move_left Camera')
    for i in range(100):
        for halfstep in range(8):
            for pin in range(4):
                GPIO.output(camera_motor_pins[pin], halfstep_seq_left[halfstep][pin])
            time.sleep(0.001)
    pass


def moveCameraRight():
    print('move_right Camera')
    for i in range(100):
        for halfstep in range(8):
            for pin in range(4):
                GPIO.output(camera_motor_pins[pin], halfstep_seq_right[halfstep][pin])
            time.sleep(0.001)
    pass

def cameraMove(direction):
    if direction=="R": moveCameraRight()
    elif direction=="L": moveCameraLeft()
    else : print("Bad Camera Direction: {0}".format(direction))

def videoStreamOn():
    global process
    process = subprocess.Popen('/home/pi/Desktop/run_video',
                     stdout=subprocess.PIPE, 
                     stderr=subprocess.PIPE,shell=True)
def videoStreamOff():
    global process
    process.kill()
    subprocess.call("killall run_video",shell=True)                     

def on_message(message):
    global isUVOn
    global UV_LAMP_PIN
    command = (str)(message)
    print(command)
    
    if command=="UV_LAMP_ON": uvOn()
    elif command=="UV_LAMP_OFF": uvOff()
    elif command=="ADD_WATER": addWater()
    elif command=="MOVE_CAMERA_RIGHT": cameraMove("R")
    elif command=="MOVE_CAMERA_LEFT": cameraMove("L")
    elif command=="VIDEO_STREAM_ON": videoStreamOn()
    elif command=="VIDEO_STREAM_OFF": videoStreamOff()
    else:
        print("Unknown Command: {0}".format(command))

def on_error(ws, error):
    print(error)

def on_close(ws):
    print("### closed ###")


async def websocket_handler():
    uri = "wss://0xl08k0h22.execute-api.eu-west-1.amazonaws.com/dev"
    async with websockets.connect(uri, ssl = True) as websocket:
        while True:
            message = await websocket.recv()
            on_message(message)


if __name__ == "__main__":
    try:
        set_all_off()
        asyncio.get_event_loop().run_until_complete(websocket_handler())
    finally:
        GPIO.cleanup()
    
    