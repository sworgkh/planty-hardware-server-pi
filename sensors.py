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

dynamodb = boto3.resource('dynamodb', region_name='eu-west-1',
                          endpoint_url="https://dynamodb.eu-west-1.amazonaws.com")
plantersMeasurementsTable = dynamodb.Table('PlantersMeasurements')


MY_ID = "e0221623-fb88-4fbd-b524-6f0092463c93"
soilHumidity = 331
saveLaps = 60


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

    async with websockets.connect(uri, ssl=True) as websocket:
        print("Connected to Websocket")
        with busio.I2C(board.SCL, board.SDA) as i2c:
            uv = VEML6070(i2c, "VEML6070_4_T")
            bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, 0x76)
            
            ads = ADS.ADS1115(i2c, mode = ads1x15.Mode.CONTINUOUS)
            humiditySensor = AnalogIn(ads, ADS.P0)
            
            maxHumidity = 23150
            minHumidity = 10500


            while True:
                soilHumidityRaw = humiditySensor.value
                print(f'H_Raw:{soilHumidityRaw}\n')
                soilHumidity = (100-float((soilHumidityRaw-minHumidity) * 100 / (maxHumidity-minHumidity)))/100

                uv_raw = uv.uv_raw
                temperature = bme280.temperature
                airHumidity = bme280.humidity

                print(
                    f'{datetime.datetime.now()} T:{temperature:0.3f} AH:{airHumidity:0.2f} UV:{uv_raw} SHum:{soilHumidity:0.3f}')

                if(saveLaps == 0):
                    try:
                        saveMeasurementsToDb(temperature, uv_raw, soilHumidity)
                    except Exception as e:
                        print("Failed  to save data to DynamoDB.")
                        print(e)

                if(saveLaps % 10 == 0):
                    message = f'{{\"action":"message","message":"FROM_PLANTER;{MY_ID};MEASUREMENTS;T:{temperature};UV:{uv_raw};SH:{soilHumidity}"}}'
                    try:
                        await websocket.send(message)
                    except websockets.exceptions.ConnectionClosedOK:
                        print("Disconnected.\n Trying to reconnet.\n")
                        raise
                    except Exception as e:
                        print("Websocket Unexpected error:", sys.exc_info()[0])
                        raise

                time.sleep(5)
                saveLaps = saveLaps+5 if saveLaps < 60 else 0


if __name__ == "__main__":
    try:
        while True:
            try:
                asyncio.get_event_loop().run_until_complete(websocket_handler())
            except websockets.exceptions.ConnectionClosedOK:
                print("Connection closed by server.\n Reconnecting.\n")
            except Exception as e:
                print("Unexpected error:", sys.exc_info()[0])
                print(e)
                GPIO.cleanup()
                raise
    finally:
        GPIO.cleanup()
