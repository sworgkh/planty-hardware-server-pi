import sys
sys.path = ['', '/usr/lib/python37.zip', '/usr/lib/python3.7', '/usr/lib/python3.7/lib-dynload',
            '/home/pi/.local/lib/python3.7/site-packages', '/usr/local/lib/python3.7/dist-packages', '/usr/lib/python3/dist-packages']

import picamera
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import signal
import asyncio
import websockets
import pathlib
import ssl
import time
import subprocess
import json
import decimal
import logging
import logging.config
import psutil

class CheckComplete(Exception):
    pass

class CheckFailedToCaptureImage(Exception):
    pass


logging.config.fileConfig('/home/pi/Desktop/python/dailyPicTest/logging.conf')
logger = logging.getLogger('camcapture')

STREAM_PROCCESS_NAME = "kinesis_video_g"

def checkIfProcessRunning(processName):
    for proc in psutil.process_iter():
        try:
            if processName.lower() in proc.name().lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False


def upload_file(file_name, bucket, object_name=None):
    """Upload a file to an S3 bucket
    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(file_name, bucket, object_name)
    except ClientError as e:
        return False

    return True


def take_pic():
    try:
        with picamera.PiCamera() as camera:
            camera.capture('snapshot.jpg', resize=(800, 600))

            objectName = 'public/Test/Lopez/cam_capture'
            dateTimeObj = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

            objectName = objectName + '/capture-' + dateTimeObj + '.jpg'
            logger.info('Saving ', objectName)
            res = upload_file('snapshot.jpg', "pictures-bucket-planty165521-planty", objectName)
            if res:
                logger.info('File was saved')
                return objectName
            else:
                logger.info('Save failed,will try in 1 day')
                return None

    except:
        logger.error('Unable to open camera')


def save_to_dynamo_db():
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.Table('Test_Planters')
    response = table.update_item(
        Key={
            'UUID': 'e0221623-fb88-4fbd-b524-6f0092463c93',
        },
        UpdateExpression="set sickPlantDetected = :r,",
        ExpressionAttributeValues={
            ':r': True,
        },
        ReturnValues="UPDATED_NEW"
    )

    logger.info("UpdateItem succeeded:")
    sys.exit()


def on_message(message):
    command = (str)(message).split(";")
    if command[2] == "IMAGE_STATUS" and command[4] == "sick":
        save_to_dynamo_db()
        logger.warning("Plant is Sick! :(")
        raise CheckComplete

    if command[2] == "IMAGE_STATUS" and command[4] == "healthy":
        logger.info("Plant is Healthy! :)")
        raise CheckComplete


async def websocket_handler():
    global STREAM_PROCCESS_NAME
    uri = "wss://0xl08k0h22.execute-api.eu-west-1.amazonaws.com/dev"

    async with websockets.connect(uri, ssl=True) as websocket:
        logger.info("Connected to Websocket\n")
        
        if not checkIfProcessRunning(STREAM_PROCCESS_NAME):
            picName = take_pic()
        else:
            raise CheckFailedToCaptureImage

        if picName == None:
            raise CheckFailedToCaptureImage
        
        picName = picName.replace('public/', '')
        logger.info(f'Took picture "{picName}""')
        
        isMessageSent = False

        msg = f'{{\"action":"message","message":"FROM_PLANTER;PI;CHECK_IMAGE;{picName};;"}}'
        await websocket.send(msg)
        while True:
            message = await websocket.recv()
            semicolonCount = sum(map(lambda x: 1 if ';' in x else 0, message))
            if semicolonCount != 2 and semicolonCount != 5 and semicolonCount != 6 and semicolonCount != 4:
                logger.warning(message)
                logger.warning("Bad Command")
                answer = '{{\"action":"message","message":"FROM_PLANTER;e0221623-fb88-4fbd-b524-6f0092463c93;BAD_COMMAND"}}'
                await websocket.send(answer)
                continue

            on_message(message)

            if not isMessageSent:
                msg = f'{{\"action":"message","message":"FROM_PLANTER;PI;CHECK_IMAGE;{picName};;"}}'
                await websocket.send(msg)
                isMessageSent = True


if __name__ == "__main__":
    retryCounter = 0

    while True and retryCounter < 20:
        try:
            asyncio.get_event_loop().run_until_complete(websocket_handler())
        except websockets.exceptions.ConnectionClosedOK:
            logger.warning("Connection closed by server.\n Reconnecting.\n")
        except websockets.exceptions.ConnectionClosedError:
            logger.warning(
                "Connection closed by server error.\n Reconnecting.\n")
            retryCounter = retryCounter+1
        except CheckComplete:
            retryCounter = 100
            logger.info("Image Check Complete")
        except CheckFailedToCaptureImage:
            logger.error("Failed to capture image.")
            raise
        except:
            logger.critical("Unexpected error:", sys.exc_info()[0])
            raise
