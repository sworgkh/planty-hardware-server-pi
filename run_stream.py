import subprocess
import time
process = subprocess.Popen('/home/pi/Desktop/run_video',
                     stdout=subprocess.PIPE, 
                     stderr=subprocess.PIPE,shell=True)

time.sleep(30)                     
process.kill()