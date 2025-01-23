from datetime import timedelta, datetime
from hashlib import sha256

import jwt
import requests
from fastapi import FastAPI, status, Query, Response, Cookie, Request, Depends, HTTPException
from fastapi.params import Header
from fastapi.security import OAuth2PasswordBearer, HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jwt import InvalidTokenError
from pydantic import BaseModel
from typing import Annotated, List, Optional
import dotenv
import os
from requests import session
from starlette.responses import RedirectResponse, FileResponse
from starlette.status import HTTP_200_OK
from ORM import ORM
from scoreService import ScoreService
from fetchQueue import TaskQueue
from models import RegisteredUser
from userService import UserService
from leaderboardService import LeaderboardService
from util import parse_score_filters


orm = ORM()

user_service = UserService(session= orm.sessionmaker())
score_service = ScoreService(session= orm.sessionmaker())
leaderboard_service = LeaderboardService(session=orm.sessionmaker())
tq = TaskQueue(orm.sessionmaker)

templates = Jinja2Templates(directory='api/frontend/templates')

dotenv.load_dotenv('.env')
webclient_id = os.getenv('WEBCLIENT_ID')
webclient_secret = os.getenv('WEBCLIENT_SECRET')
redirect_uri = 'http://localhost:8000/auth'
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class InternalError(Exception):
    pass

class Token(BaseModel):
    access_token: str
    token_type: str

class RegisteredUserCompact(BaseModel):
    user_id: int
    username: str
    avatar_url: str
    apikey: str

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now() + timedelta(weeks=2)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, os.getenv('JWTSECRET'), algorithm="HS256")
    return encoded_jwt

def verify_token(req: Request):
    token = req.cookies.get('session_token')
    if token is None:
        return False
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, os.getenv('JWTSECRET'), algorithms="HS256")
    except InvalidTokenError:
        raise credentials_exception
    return payload

def verify_admin(req: Request):
    token = req.cookies.get('session_token')
    if token is None:
        return False
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, os.getenv('JWTSECRET'), algorithms="HS256")
        admin_ids = os.getenv('ADMINS').split(',')
        if payload['user_id'] not in admin_ids:
            raise InvalidTokenError
    except InvalidTokenError:
        raise credentials_exception
    return payload

app = FastAPI(dependencies=[Depends(verify_token)])

"""
There are three levels of authentication: None, RegisteredUser, Admin
None:
/, /login, /auth, /fetch_queue

RegisteredUser
/logout, /users, /top_n, /scores, /leaderboard, /add_self, /initial_fetch_self, /add_tag_self

Admin
/add_user, /daily_fetch_all, /add_tag
"""

@app.get("/", response_class=FileResponse)
def main_page(request: Request, authorization: RegisteredUserCompact = Depends(verify_token)):
    if not authorization:
        return templates.TemplateResponse(request=request, name='index.html', context={})
    else:
        # Get profile data from cookie
        user = user_service.get_user_from_apikey(authorization['apikey'])
        return templates.TemplateResponse(request=request,
                                          name='authorized.html',
                                          context={'apikey': user.apikey,
                                                   'username': user.username,
                                                   'profile_avatar': user.avatar_url})

@app.get("/login")
async def login_via_osu():
    return RedirectResponse(url='https://osu.ppy.sh/oauth/authorize?client_id=%s&redirect_uri=%s&response_type=code&scope=public' % (webclient_id, redirect_uri))

@app.get("/auth")
async def auth_via_osu(code: str):
    headers = {'Accept': 'application/json',
               'Content-Type': 'application/x-www-form-urlencoded',}
    params = {'client_id': str(webclient_id),
              'client_secret': str(webclient_secret),
              'code': code,
              'grant_type': 'authorization_code',
              'redirect_uri': redirect_uri,}
    r = requests.post(url='https://osu.ppy.sh/oauth/token', data=params, headers=headers)

    # If everything is successful, we can generate their api key as described by Haruhime and store that in the database
    if r.json()['access_token']:
        headers['Authorization'] =  'Bearer %s' % r.json()['access_token']
        r = requests.get('https://osu.ppy.sh/api/v2/me/osu', headers=headers)
        user_data = r.json()
        print('Success! %s has successfully signed in with osu oauth.' % user_data['username'])

        static_secret = os.getenv('apikeysecret')
        apikey = sha256((static_secret + str(user_data['id'])).encode('utf-8')).hexdigest()
        user = user_service.register_user(user_data['id'], apikey)
        access_token = create_access_token({'user_id': user_data['id'], 'username': user.username, 'avatar_url': user.avatar_url, 'apikey': apikey})
        response = RedirectResponse(url='/')
        response.set_cookie(key='session_token', value=access_token, httponly=True, secure=True)

        return response
    return {"message": "Something has gone wrong. Please try again and let enslow know if you continue to have issues!"}

@app.post("/logout")
async def logout(token: Annotated[RegisteredUserCompact, Depends(verify_token)]):
    if not token:
        return {"message": "user not logged in"}
    response = RedirectResponse('/', status_code=302)
    response.delete_cookie('session_token', '/')
    return response

@app.get("/fetch_queue/", status_code=HTTP_200_OK)
def get_fetch_queue():
    """
    :return: the fetch queue
    """
    import copy
    if tq.current is None:
        return {'current': None, 'in queue': None}

    return {'current': copy.deepcopy(tq.current), 'in queue': tq.q.queue}

@app.get("/auth_token")
async def get_user_auth(token: Annotated[RegisteredUserCompact, Depends(verify_token)]):
    if token is None:
        return None
    user = orm.session.get(RegisteredUser, token['user_id'])
    return user

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

@app.post("/initial_fetch_self/", status_code=status.HTTP_202_ACCEPTED)
def initial_fetch(token: Annotated[RegisteredUserCompact, Depends(verify_token)], modes: Annotated[ list[str] | None, Query(description='osu, taiko, fruits, mania')] = None):
    tq.enqueue(('initial_fetch', {'user_id': token['user_id'], 'modes': tuple(modes)}))
    items = {"user_id": token['user_id'],
             "modes": modes,
             "queue": tq.q.queue}
    return items

@app.post("/daily_fetch_user/{user_id}", status_code=status.HTTP_202_ACCEPTED)
def daily_fetch_all(user_id: int):
    tq.enqueue(('daily_fetch', {'user_id': user_id}))
    return get_fetch_queue()

@app.post("/daily_fetch_all/", status_code=status.HTTP_202_ACCEPTED)
def daily_fetch_all(force: bool = False):
    tq.daily_queue_all(force)
    return get_fetch_queue()

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

app.mount("/", StaticFiles(directory="api/frontend", html=True), name="api/frontend")