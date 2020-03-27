import time
import board
import busio
from adafruit_veml6070 import VEML6070
from datetime import date




with busio.I2C(board.SCL, board.SDA) 
as i2c:
    uv = VEML6070(i2c,"VEML6070_4_T")
    # Alternative constructors with parameters
    #uv = VEML6070(i2c, 'VEML6070_1_T')
    #uv = VEML6070(i2c, 'VEML6070_HALF_T', True)

    # take 10 readings
    
    for j in range(60):
        log = open("uv.log","a+")
        uv_raw = uv.uv_raw
        risk_level = uv.get_index(uv_raw)
        #d = date.today().strftime("%Y-%b-%d")
        #log.write('{0} - Reading: {1} | Risk Level: {2}\r\n'.format(d,uv_raw, risk_level))
        print("{0}".format(uv_raw))
        time.sleep(3)
        log.close()