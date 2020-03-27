#!/usr/bin/python
import RPi.GPIO as GPIO
import time
 
#GPIO SETUP
pin = 24
GPIO.setmode(GPIO.BCM)
GPIO.setup(pin, GPIO.OUT)

def blink():
    for i in range(10):
        print("On")
        GPIO.output(pin, GPIO.LOW) # out
        time.sleep(1)
        print("Off")
        GPIO.output(pin, GPIO.HIGH) # on
        time.sleep(1)


try:
    blink()
finally:
    GPIO.cleanup()
 