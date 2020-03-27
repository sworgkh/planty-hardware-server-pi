import boto3
import RPi.GPIO as GPIO
import time
#import cv2
import datetime
import json


GPIO.setmode(GPIO.BOARD)
control_pins = [7,11,13,15]

for pin in control_pins:
  GPIO.setup(pin, GPIO.OUT)
  GPIO.output(pin, 0)

halfstep_seq_left = [
  [1,0,0,0],
  [1,1,0,0],
  [0,1,0,0],
  [0,1,1,0],
  [0,0,1,0],
  [0,0,1,1],
  [0,0,0,1],
  [1,0,0,1]
]
halfstep_seq_right = [
  [0,0,0,1],
  [0,0,1,1],
  [0,0,1,0],
  [0,1,1,0],
  [0,1,0,0],
  [1,1,0,0],
  [1,0,0,0],
  [1,0,0,1]
]

client = boto3.client('sqs', 'eu-west-1')


def recieve_message():
    response = client.receive_message(
        # QueueUrl='https://sqs.eu-west-1.amazonaws.com/321366177529/userActions.fifo',
        QueueUrl='https://sqs.eu-west-1.amazonaws.com/321366177529/test',
        # QueueUrl="https://sqs.eu-west-1.amazonaws.com/321366177529/test.fifo",
        AttributeNames=[
            'All'],
        # MessageAttributeNames=[
        #     'string',
        # ],
        MaxNumberOfMessages=1,
        VisibilityTimeout=10,
        WaitTimeSeconds=1,
        # ReceiveRequestAttemptId='string'
    )
    if response:
        try:
            message = response['Messages']
            # print(message[0]['Body'])
            if message[0]['Body'] == 'left':
                move_left()
            if message[0]['Body'] == 'right':
                move_right()
            if message[0]['Body'].startswith('picture'):
                take_pic(message[0]['Body'])
        except Exception:
            print('No messages')
            return
        if message:
            response = client.delete_message_batch(
                # QueueUrl='https://sqs.eu-west-1.amazonaws.com/321366177529/userActions.fifo',
                QueueUrl='https://sqs.eu-west-1.amazonaws.com/321366177529/test',
                Entries=[
                    {
                        'Id': message[0]['MessageId'],
                        'ReceiptHandle': message[0]['ReceiptHandle']
                    },
                ]
            )
            print(response)

    # print(response['Messages'])


def move_left():
    print('move_left Camera')
    for i in range(100):
        for halfstep in range(8):
            for pin in range(4):
                GPIO.output(control_pins[pin], halfstep_seq_left[halfstep][pin])
            time.sleep(0.001)
    pass


def move_right():
    print('move_right Camera')
    for i in range(100):
        for halfstep in range(8):
            for pin in range(4):
                GPIO.output(control_pins[pin], halfstep_seq_right[halfstep][pin])
            time.sleep(0.001)
    pass


def take_pic(body):
    print('Taking Pic')
    print(body)
    values = str(body).split('+')
    try:
        get_frame(values[1],values[2],values[3])
    except Exception:
            print('Failed getting frame')
            return    


def get_frame(username, planter,stream_url):
    ts = int(datetime.datetime.now().timestamp())
    print(ts)

    url = stream_url
    # vidcap = cv2.VideoCapture('C0001.mp4')
    vidcap = cv2.VideoCapture(url)
    success, image = vidcap.read()
    cv2.imwrite('kang.jpg', image)

    # count = 0
    bucket = 'pictures-bucket-planty165521-planty'

    if success:
        # s3.upload_fileobj(image, bucket, "asdasdasd")
        s3.upload_file('kang.jpg', bucket, 'public/' + username + '/' + planter + '/camera_capture' + str(ts) + '.jpg')


    


while True:
    recieve_message()
