import asyncio
import websockets
import logging
logger = logging.getLogger('websockets')
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


async def websocket_handler():
    uri = "wss://0xl08k0h22.execute-api.eu-west-1.amazonaws.com/dev"
    async with websockets.connect(uri, ssl = True) as websocket:
        answer = input('{{\"action":"message","message":"FROM_PLANTER;e0221623-fb88-4fbd-b524-6f0092463c93;{0}"}}'.format("TEST"))
        await websocket.send(answer)



if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(websocket_handler())
   