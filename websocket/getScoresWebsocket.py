# Thank you MaxOhn for https://github.com/MaxOhn/scores-ws

import asyncio
import os
from database.ORM import ORM
from database.scoreService import insert_scores
from sqlalchemy import select
from database.models import RegisteredUser
from websockets.asyncio.client import connect
import json
import datetime
from ossapi.ossapiv2 import Ossapi, Score

# While `scores-ws` is already running...

async def run():
    # Create the websocket stream
    async with connect("ws://127.0.0.1:7727") as websocket:
        # Send the initial message within 5 seconds of connecting the websocket.
        # Must be either "connect" or a score id to resume from
        await websocket.send("connect")

        # Let's run it for a bit until we disconnect manually
        listening = asyncio.create_task(process_scores(websocket))

        await asyncio.sleep(10)
        listening.cancel()
        try:
            await listening
        except asyncio.CancelledError:
            pass

        # Let the websocket know we are about to disconnect.
        # This is not necessary but will allow us to resume later on.
        await websocket.send("disconnect")

        # As response, we'll receive a score id
        score_id = await websocket.recv()
        await websocket.close()

        await asyncio.sleep(10)

        # If we connect again later on...
        async with connect("ws://127.0.0.1:7727") as websocket:
            # ... we can use that score id. This way we only receive the scores that
            # were fetched in the meanwhile that we don't already know about.
            await websocket.send(score_id)
            await process_scores(websocket)

async def process_scores(websocket):
    try:
        time = datetime.datetime.now()
        orm = ORM()
        stmt = select(RegisteredUser.user_id)
        user_ids = [user_id for user_id in orm.session.execute(stmt).scalars().all()]
        #print(user_ids)
        import dotenv
        ossapi = Ossapi(os.getenv('CLIENT_ID'), os.getenv('CLIENT_SECRET'))

        import time
        oldepoch = time.time()
        def minute_passed():
            return time.time() - oldepoch >= 60

        async for event in websocket:
            score = json.loads(event)
            if score['user_id'] in user_ids:
                print(f'Found a score for {score["user_id"]}')
                new_score = ossapi._instantiate_type(Score, score)
                await insert_scores(orm.session, [new_score])
            # Update registered users every minute.
            if minute_passed():
                oldepoch = time.time()
                user_ids = [user_id for user_id in orm.session.execute(stmt).scalars().all()]


    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(e)

if __name__ == "__main__":

    asyncio.run(run())