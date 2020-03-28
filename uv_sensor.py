import time
import board
import busio
from adafruit_veml6070 import VEML6070
from datetime import date




with busio.I2C(board.SCL, board.SDA) as i2c:
    uv = VEML6070(i2c,"VEML6070_4_T")
    
    while True:
        uv_raw = uv.uv_raw
        risk_level = uv.get_index(uv_raw)
        print("{0}".format(uv_raw))
        time.sleep(3)
