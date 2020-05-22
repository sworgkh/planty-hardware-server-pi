import plantyErrors
import asyncio
import websockets
import time
import datetime
import sys

import logging

logger = logging.getLogger('websockets')
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


async def websocket_handler():
    uri = "wss://0xl08k0h22.execute-api.eu-west-1.amazonaws.com/dev"

    try:
        async with websockets.connect(uri, ssl=True) as websocket:
            print("Connected to Websocket")
            message = f'{{\"action":"message","message":"TEST"}}'
            await websocket.send(message)
            time.sleep(5)
            x = input('pres to resend')
    except:
        print(f'Unexpected Error:\n{sys.exc_info()[0]}')
        raise


if __name__ == "__main__":
    while True:
        try:
            asyncio.get_event_loop().run_until_complete(websocket_handler())
        except websockets.exceptions.ConnectionClosedOK:
            print("Connection closed by server.\n Reconnecting.\n")
        except websockets.exceptions.ConnectionClosedError:
            print("Connection closed by server error.\n Reconnecting.\n")
        except Exception as e:
            print("Unexpected error:", sys.exc_info()[0])
            print(e)
            raise
