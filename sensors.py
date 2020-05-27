import plantyErrors
import collections
import asyncio
import websockets
import time
import datetime
import board
import busio
import serial
import decimal
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import adafruit_ads1x15.ads1x15 as ads1x15
from adafruit_veml6070 import VEML6070
import adafruit_bme280
import boto3
import json
from plantyutils import DecimalEncoder
import sys
import RPi.GPIO as GPIO
import itertools

import logging

dynamodb = boto3.resource('dynamodb', region_name='eu-west-1',
                          endpoint_url="https://dynamodb.eu-west-1.amazonaws.com")
plantersMeasurementsTable = dynamodb.Table('PlantersMeasurements')

logger = logging.getLogger('websockets')
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

MY_ID = "e0221623-fb88-4fbd-b524-6f0092463c93"

bufferSize = 20
soilHumidityBuffer = collections.deque([0.0]*bufferSize, bufferSize)
soilHumidityBufferCount = 0
soilHumidity = 0.0

temperatureBuffer = collections.deque([0.0]*bufferSize, bufferSize)
temperatureBufferCount = 0
temperature = 0.0
saveLaps = 60


def setSoilHumidity(value):
    global soilHumidity
    global soilHumidityBufferCount
    if soilHumidityBufferCount < bufferSize:
        soilHumidityBufferCount = soilHumidityBufferCount + 1

    soilHumidityBuffer.append(float(value))
    soilHumidity = sum(soilHumidityBuffer)/soilHumidityBufferCount


def setTemperature(value):
    global temperature
    global temperatureBufferCount
    if temperatureBufferCount < bufferSize:
        temperatureBufferCount = temperatureBufferCount + 1

    temperatureBuffer.append(float(value))
    temperature = sum(temperatureBuffer)/temperatureBufferCount


def saveMeasurementsToDb(ambientTemperatureCelsius, uvIntesity, soilHumidity):
    timeStamp = decimal.Decimal(datetime.datetime.utcnow().timestamp())

    try:
        response = plantersMeasurementsTable.put_item(
            Item={
                'planterId': MY_ID,
                'timeStamp':   timeStamp,
                "uvIntesity": uvIntesity,
                "soilHumidity": decimal.Decimal(str(soilHumidity)),
                "ambientTemperatureCelsius": decimal.Decimal(str(ambientTemperatureCelsius))
            }
        )

        if(response["ResponseMetadata"]["HTTPStatusCode"] == 200):
            print("Saved To Database.")
        else:
            print("Failed To Save")

    except:
        print("Failed To Save")


async def websocket_handler():
    uri = "wss://0xl08k0h22.execute-api.eu-west-1.amazonaws.com/dev"
    global soilHumidity
    global saveLaps
    global retryCounter

    async with websockets.connect(uri, ssl=True) as websocket:
        print("Connected to Websocket")
        retryCounter = 0
        with busio.I2C(board.SCL, board.SDA) as i2c:
            try:
                uv = VEML6070(i2c, "VEML6070_4_T")
                bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, 0x76)
                ads = ADS.ADS1115(i2c, mode=ads1x15.Mode.CONTINUOUS)
                humiditySensor = AnalogIn(ads, ADS.P0)
            except:
                print(f'Failed to initiate Sensor:\n{sys.exc_info()[0]}')
                raise
                # TODO Add Sensors exceptions and implement retry

            maxHumidity = 23150
            minHumidity = 10500

            while True:
                soilHumidityRaw = humiditySensor.value
                sh = (100-float((soilHumidityRaw-minHumidity)
                                * 100 / (maxHumidity-minHumidity)))/100
                setSoilHumidity(sh)

                uv_raw = uv.uv_raw
                t = bme280.temperature
                setTemperature(t)
                airHumidity = bme280.humidity

                print(f'{datetime.datetime.now()} T:{temperature:0.3f}|{t:0.6f} AH:{airHumidity:0.2f} UV:{uv_raw} SH:{soilHumidity:0.3f}|{sh:0.6f}')

                if(saveLaps == 0):
                    try:
                        saveMeasurementsToDb(temperature, uv_raw, soilHumidity)
                    except Exception as e:
                        print("Failed  to save data to DynamoDB.")
                        print(e)

                if(saveLaps % 10 == 0):
                    message = f'{{\"action":"message","message":"FROM_PLANTER;{MY_ID};MEASUREMENTS;T:{temperature};UV:{uv_raw};SH:{soilHumidity};AH:{airHumidity}"}}'

                    await websocket.send(message)

                time.sleep(5)
                pong_awaiter = await websocket.ping()
                await pong_awaiter
                saveLaps = saveLaps+5 if saveLaps < 60 else 0


if __name__ == "__main__":
    retryCounter = 0

    while True and retryCounter < 20:
        try:
            asyncio.get_event_loop().run_until_complete(websocket_handler())
        except websockets.exceptions.ConnectionClosedOK:
            print(f"Connection closed by server.\n Reconnecting. Attempt:{retryCounter}\n")
            time.sleep(15)
            retryCounter = retryCounter+1

        except websockets.exceptions.ConnectionClosedError:
            print(f"Connection closed by server Error.\n Reconnecting. Attempt:{retryCounter}\n")
            time.sleep(15)
            retryCounter = retryCounter+1
        except Exception as e:
            print("Unexpected error:", sys.exc_info()[0])
            print(e)
            GPIO.cleanup()
            raise
        GPIO.cleanup()
