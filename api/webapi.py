from fastapi import FastAPI, status, Query, Response
from typing import Annotated, List, Optional
from starlette.status import HTTP_200_OK
from ORM import ORM
from scoreService import ScoreService
from fetchQueue import TaskQueue, daily_queue_all
from models import RegisteredUser
from userService import UserService
from leaderboardService import LeaderboardService
from util import parse_score_filters

app = FastAPI()
orm = ORM()
user_service = UserService(session= orm.sessionmaker())
score_service = ScoreService(session= orm.sessionmaker())
leaderboard_service = LeaderboardService(session=orm.sessionmaker())
tq = TaskQueue(orm.sessionmaker)

class InternalError(Exception):
    pass

@app.get("/users/{user_id}", status_code=status.HTTP_200_OK)
def get_user(user_id: int):
    """
    Fetches a user from the database from their user_id
    """
    return {"user": orm.session.get(RegisteredUser, user_id)}

@app.get("/top_n/", status_code=status.HTTP_200_OK)
def get_top_100(user_id: int, mode: str = 'osu', n: int = 100, filters: Optional[str] = None, metric: str = 'pp'):
    filters = parse_score_filters(mode, filters)
    return {"top %s" % str(n): user_service.get_top_n(user_id=user_id, mode=mode, filters=filters, metric=metric, number=n)}

@app.get("/scores/", status_code=status.HTTP_200_OK)
def get_score(beatmap_id: int, user_id: int, mode: str = 'osu', filters: Optional[str] = None, metric: str = 'pp'):
    filters = parse_score_filters(mode, filters)
    """
    Fetches a user's scores on a beatmap
    """
    return {"score": score_service.get_user_scores(beatmap_id, user_id, mode, filters, metric)}

@app.get("/leaderboard/", status_code=status.HTTP_200_OK)
def get_group_leaderboard(beatmap_id: int, mode: str = 'osu', group: Optional[str] | Optional[List[int]] = None, filters: Optional[str] = None, metric: Optional[str] = 'pp'):
    """
    Generates a Leaderboard for a provided tag. Can also
    """
    filters = parse_score_filters(mode, filters)
    users = user_service.get_ids_from_tag(group)
    return {"leaderboard": leaderboard_service.group_leaderboard(users=users, beatmap_id=beatmap_id, mode=mode, filters=filters, metric=metric)}

@app.post("/add_user/{user_id}", status_code=status.HTTP_201_CREATED)
async def add_registered_user(user_id: int, response: Response):
    """
    Register a new user
    """
    if user_service.register_user(user_id=user_id):
        return {"message": "%s registered to database" % str(user_id)}
    else:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "%s is already registered to the database" % str(user_id)}

@app.get("/fetch_queue/", status_code=HTTP_200_OK)
def get_fetch_queue():
    """
    :return: the fetch queue
    """
    import copy
    if tq.current is None:
        return {'current': None, 'in queue': None}

    return {'current': copy.deepcopy(tq.current), 'in queue': tq.q.queue}

@app.post("/initial_fetch/{user_id}", status_code=status.HTTP_202_ACCEPTED)
def initial_fetch(user_id: int, modes: Annotated[ list[str] | None, Query(description='osu, taiko, fruits, mania')] = None):
    """
    Add the user to the fetch queue

    NOTE: This request does not need a body

    :param user_id: user who's scored to be fetched
    :param modes:   a list of modes for which to fetch the user's scores (includes converts)
    :return: None
    """
    tq.enqueue(('initial_fetch', {'user_id': user_id, 'modes': tuple(modes)}))
    items = {"user_id": user_id,
             "modes": modes,
             "queue": tq.q.queue}
    return items

@app.post("/daily_fetch_all/", status_code=status.HTTP_202_ACCEPTED)
def daily_fetch_all():
    tq.daily_queue_all()
    return {"message": "added all users to queue"}

@app.post("/add_tag/", status_code=status.HTTP_201_CREATED)
def add_tag(user_id: Annotated[ list[int], Query(description='list of ids')], tag: str):
    """
    Give a user a new tag (add a user to a new group)

    :param user_id: user to be updated
    :param tag: new tag to be added
    :return: None
    """
    if user_service.add_tags(user_ids=user_id, tag=tag):
        return {"message": "Tags added to user(s) %s" % str(user_id)}
    else:
        raise InternalError('Something went wrong')