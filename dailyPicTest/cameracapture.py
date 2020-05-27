import picamera
import boto3
from botocore.exceptions import ClientError
from datetime import datetime

import asyncio
import websockets
import pathlib
import ssl
import time
import subprocess
import json
import decimal
import sys

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

        camera = picamera.PiCamera()
        
        #camera.start_preview()
        camera.capture('snapshot.jpg',resize=(800, 600))
        #camera.stop_preview()
        
        objectName = 'public/Test/Lopez/cam_capture'
        dateTimeObj = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        
        objectName = objectName + '/capture-' + dateTimeObj + '.jpg'
        print('Saving ',objectName)
        
        
        with open('snapshot.jpg', "rb") as f:
            
            res = upload_file('snapshot.jpg', "pictures-bucket-planty165521-planty", objectName)
            if res:
                print('File was saved')
                #send to socket
                #'FROM_PLANTER;' + this.state.item.UUID +';CHECK_IMAGE;' + objectName, 
                # websocket_send(result)   
                return objectName
            else:
                print('Save failed,will try in 1 day')   
                return None 
        
    except:
        print('Unable to open camera')

    

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

    print("UpdateItem succeeded:")
    sys.exit()



def on_message(message):
    command = (str)(message).split(";")
    print(f'<<< {command[2]}')
    print(command)

    if command[2] == "IMAGE_STATUS" and command[4] == "sick":
        save_to_dynamo_db()
    

    if command[2] == "IMAGE_STATUS" and command[4] == "healthy":
        sys.exit()
     
    
async def websocket_handler():
    picName = take_pic()
    file1 = open('log.txt', 'w') 
    if picName == None:
        s = "Failed to take picture\n"
        
        # Writing a string to file 
        file1.write(s) 
        
        
        # Closing file 
        
    
        file1.close() 
        sys.exit()
    picName = picName.replace('public/','') 
    s = "Took picture "+ picName +"\n"
        
    # Writing a string to file 
    file1.write(s)
    file1.close() 

    uri = "wss://0xl08k0h22.execute-api.eu-west-1.amazonaws.com/dev"
    async with websockets.connect(uri, ssl=True) as websocket:
        print("Connected to Websocket\n")
        i = 0
        msg = f'{{\"action":"message","message":"FROM_PLANTER;PI;CHECK_IMAGE;{picName};;"}}'
        await websocket.send(msg)
        while True:
            message = await websocket.recv()
            semicolonCount = sum(map(lambda x: 1 if ';' in x else 0, message))
            if semicolonCount != 4:
                print(message)
                print("Bad Command")
                answer = '{{\"action":"message","message":"FROM_PLANTER;e0221623-fb88-4fbd-b524-6f0092463c93;BAD_COMMAND"}}'
                await websocket.send(answer)
                continue
            on_message(message)


            if i == 0:
                msg = f'{{\"action":"message","message":"FROM_PLANTER;PI;CHECK_IMAGE;{picName};;"}}'
                await websocket.send(msg)
                i = 1
    

if __name__ == "__main__":
    retryCounter = 0

    while True and retryCounter < 20:
        try:
            asyncio.get_event_loop().run_until_complete(websocket_handler())
        except websockets.exceptions.ConnectionClosedOK:
            print("Connection closed by server.\n Reconnecting.\n")
        except websockets.exceptions.ConnectionClosedError:
            print("Connection closed by server error.\n Reconnecting.\n")
            retryCounter = retryCounter+1
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise
           
