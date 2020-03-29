import board
import busio
import adafruit_bme280
import time
import datetime


i2c = busio.I2C(board.SCL, board.SDA)
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c,0x76)
while True:
    temperature = bme280.temperature
    print(f'{datetime.datetime.now()}> Temperature: {temperature:0.3f} C')
    time.sleep(5)