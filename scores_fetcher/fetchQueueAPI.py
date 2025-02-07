"""
This is the api for the fetch queue. It does two things: add people to queue and display the queue
This runs in its own container.
"""
from fastapi import FastAPI, Query, status, Depends
from typing import Annotated
from database.ORM import ORM
from database.models import RegisteredUser
from database.osuApiAuthService import OsuApiAuthService
from web.dependencies import verify_token, RegisteredUserCompact
from scores_fetcher.fetchQueueTest import TaskQueue

app = FastAPI()
orm = ORM()
tq = TaskQueue(orm.sessionmaker)

app.get("/")
def main():
    return {"message": "You are at the fetch queue!"}

@app.get("/queue", status_code=status.HTTP_200_OK)
def get_fetch_queue():
    """
    Returns the fetch queue
    """
    import copy
    if tq.current is None:
        return {'current': None, 'in queue': None}
    user_queue = tq.q.queue

    return {'current': copy.deepcopy(tq.current), 'in queue': [{'username': x[1].username,
                                                                'user_id': x[1].user_id,
                                                                'catch_converts': x[2],
                                                                'num_maps': 'Calculating',
                                                                'total_map': 'Calculating'} for x in user_queue]}

@app.post("/enqueue_me", status_code=status.HTTP_202_ACCEPTED)
def initial_fetch(token: Annotated[RegisteredUserCompact, Depends(verify_token)], catch_converts: Annotated[ bool , Query(description='Fetch ctb converts?')] = False):
    """
    Adds the authenticated user to the fetch queue
    """
    user_id = token['user_id']

    # Verify that the user can be fetched
    user_queue = [x[1].user_id for x in tq.q.queue]
    session = orm.sessionmaker()
    user = session.get(RegisteredUser, user_id)

    if user.last_updated is not None:
        return {'message': 'You have been calculated in the past. You have not been added to the queue.'}
    if user is None:
        return {'message': 'You are not registered. You have not been added to the queue.'}
    for tasks in tq.current:
        if tasks['user_id'] == user.user_id:
            return {'message': 'You are already in the queue.'}
    if user.user_id in user_queue:
        return {'message': 'You are already in the queue.'}
    auth_client = OsuApiAuthService(user.user_id, user.access_token)
    if not auth_client.auth_client_works():
        return {'message': 'Auth credentials out of date, try relogging'}


    if tq.enqueue(user_id, catch_converts):
        return {'message': 'Success! You have been added to the queue.'}
    return {'message': 'Something went wrong. Relog and try again if your scores have not already been fetched.'}
