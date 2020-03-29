import asyncio
import websockets
import time
import datetime
import board
import busio
import serial
import decimal
from adafruit_veml6070 import VEML6070
import adafruit_bme280
import boto3
import json
from plantyutils import DecimalEncoder

dynamodb = boto3.resource('dynamodb', region_name='eu-west-1',
                          endpoint_url="https://dynamodb.eu-west-1.amazonaws.com")
plantersMeasurementsTable = dynamodb.Table('PlantersMeasurements')


MY_ID = "e0221623-fb88-4fbd-b524-6f0092463c93"
soilHumidity = -1
saveLaps = -60


def saveMeasurementsToDb(ambientTemperatureCelsius, uvIntesity, soilHumidity):
    timeStamp = decimal.Decimal(datetime.datetime.utcnow().timestamp())
    try:

        response = plantersMeasurementsTable.put_item(
            Item={
                'planterId': MY_ID,
                'timeStamp':   timeStamp,
                "uvIntesity": uvIntesity,
                "soilHumidity": soilHumidity,
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
        with busio.I2C(board.SCL, board.SDA) as i2c:
            uv = VEML6070(i2c, "VEML6070_4_T")
            bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, 0x76)
            ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
            ser.flush()

            while True:
                if ser.in_waiting > 0:
                    soilHumidity = decimal.Decimal(
                        ser.readline().decode('utf-8').rstrip())

                uv_raw = uv.uv_raw
                temperature = bme280.temperature

                print(
                    f'{datetime.datetime.now()} T:{temperature:0.3f} UV:{uv_raw} SHum:{soilHumidity}')

                if(saveLaps == 0):
                    saveMeasurementsToDb(temperature, uv_raw, soilHumidity)

                if(saveLaps % 10 == 0):
                    message = f'{{\"action":"message","message":"FROM_PLANTER;{MY_ID};MEASUREMENTS;T:{temperature};UV:{uv_raw};SH:{soilHumidity}"}}'
                    await websocket.send(message)

                time.sleep(5)
                saveLaps = saveLaps+5 if saveLaps < 60 else 0


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(websocket_handler())
