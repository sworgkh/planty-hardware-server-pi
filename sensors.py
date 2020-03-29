import time
import board
import busio
from adafruit_veml6070 import VEML6070
import adafruit_bme280
import datetime




with busio.I2C(board.SCL, board.SDA) as i2c:
    uv = VEML6070(i2c,"VEML6070_4_T")
    
    while True:
        uv_raw = uv.uv_raw
        risk_level = uv.get_index(uv_raw)
        print(f'{}{uv_raw})
        time.sleep(3)
