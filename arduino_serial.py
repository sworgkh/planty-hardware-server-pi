import serial
import time

ser = serial.Serial('/dev/ttyUSB0',9600)
while True:
    if(ser.in_waiting > 0): 
        line = str(ser.readline())
        print(line)
    time.sleep(2)
