"""
This is the api for the fetch queue. It does two things: add people to queue and display the queue
This runs in its own container.
"""
from fastapi import FastAPI, Query, status, Depends
from typing import Annotated
from database.ORM import ORM
from database.models import RegisteredUser
from database.osuApiAuthService import OsuApiAuthService
from web.dependencies import verify_token, verify_admin, RegisteredUserCompact
from scores_fetcher.fetchQueue import TaskQueue

fetchapp = FastAPI(docs_url="/docs", redoc_url=None)
orm = ORM()
tq = TaskQueue(orm.sessionmaker)

def enqueue_user(user_id: int, get_non_converts: bool, catch_converts: bool):
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
    if not get_non_converts and not catch_converts:
        return {'message': 'You must queue for something!'}

    if tq.enqueue(user_id, get_non_converts, catch_converts):
        return {'message': 'Success! You have been added to the queue.'}
    return {'message': 'Something went wrong. Relog and try again if your scores have not already been fetched.'}

@fetchapp.get("/queue", status_code=status.HTTP_200_OK)
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

@fetchapp.post("/enqueue_self", status_code=status.HTTP_202_ACCEPTED)
def initial_fetch(token: Annotated[RegisteredUserCompact, Depends(verify_token)], catch_converts: Annotated[ bool , Query(description='Fetch ctb converts?')] = False):
    """
    Adds the authenticated user to the fetch queue
    """
    user_id = token['user_id']
    return enqueue_user(user_id, True, catch_converts)

@fetchapp.post("/enqueue_user", status_code=status.HTTP_202_ACCEPTED)
def initial_fetch_user(token: Annotated[RegisteredUserCompact, Depends(verify_admin)], user_id: int, non_converts: Annotated[ bool , Query(description='Fetch non_converts?')] = False, catch_converts: Annotated[ bool , Query(description='Fetch ctb converts?')] = False):
    """
    Adds any user to the fetch queue
    """
    return enqueue_user(user_id, non_converts, catch_converts)

@fetchapp.post("/remove_from_queue", status_code=status.HTTP_202_ACCEPTED)
def remove_from_queue(token: Annotated[RegisteredUserCompact, Depends(verify_admin)], user_id: int):
    try:
        print(tq.current)
        print(tq.q.queue)
        for task in tq.current:
            if task['user_id'] == user_id:
                tq.current.remove(task)

                if len(tq.q.queue) > 0:
                    tq.start()
                    return {"message": "%s has been removed from the queue" % str(user_id)}

        for task in tq.q.queue:
            if task['user_id'] == user_id:
                tq.q.queue.remove(task)

                if len(tq.q.queue) > 0:
                    tq.start()
                    return {"message": "%s has been removed from the queue" % str(user_id)}
        if len(tq.q.queue) == 0:
            return {"message": "%s has been removed from the queue" % str(user_id)}
        raise Exception
    except Exception as e:
        print(e)
        return {"message": "Something went wrong and %s was not removed" % str(user_id)}