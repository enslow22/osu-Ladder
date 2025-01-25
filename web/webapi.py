from fastapi import FastAPI, status, Query, Response, Request, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse, FileResponse
import requests
from hashlib import sha256

from starlette.staticfiles import StaticFiles

from .routers import admin, auth, stats
from pydantic import BaseModel

from .dependencies import verify_token, verify_admin, create_access_token, RegisteredUserCompact, has_token

from database.ORM import ORM
from database.scoreService import ScoreService
from database.fetchQueue import TaskQueue
from database.models import RegisteredUser
from database.userService import UserService
from database.leaderboardService import LeaderboardService
from database.util import parse_score_filters
import dotenv
import os

dotenv.load_dotenv('../database/.env')
webclient_id = os.getenv('WEBCLIENT_ID')
webclient_secret = os.getenv('WEBCLIENT_SECRET')
redirect_uri = os.getenv('REDIRECT_URI')
templates = Jinja2Templates(directory='web/frontend/templates')

orm = ORM()

user_service = UserService(session= orm.sessionmaker())
score_service = ScoreService(session= orm.sessionmaker())
leaderboard_service = LeaderboardService(session=orm.sessionmaker())
tq = TaskQueue(orm.sessionmaker)

app = FastAPI()

@app.get("/", response_class=FileResponse)
def main_page(request: Request, authorization: RegisteredUserCompact = Depends(has_token)):
    print(authorization)
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

@app.get("/login", status_code=status.HTTP_200_OK)
async def login_via_osu():
    return RedirectResponse(url='https://osu.ppy.sh/oauth/authorize?client_id=%s&redirect_uri=%s&response_type=code&scope=public' % (webclient_id, redirect_uri))

@app.get("/auth", status_code=status.HTTP_200_OK)
async def auth_via_osu(code: str):
    headers = {'Accept': 'application/json',
               'Content-Type': 'application/x-www-form-urlencoded',}
    params = {'client_id': str(webclient_id),
              'client_secret': str(webclient_secret),
              'code': code,
              'grant_type': 'authorization_code',
              'redirect_uri': redirect_uri,}
    r = requests.post(url='https://osu.ppy.sh/oauth/token', data=params, headers=headers)

    # If everything is successful, we can generate their database key as described by Haruhime and store that in the database
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

@app.get("/fetch_queue", status_code=status.HTTP_200_OK)
def get_fetch_queue():
    """
    :return: the fetch queue
    """
    import copy
    if tq.current is None:
        return {'current': None, 'in queue': None}

    return {'current': copy.deepcopy(tq.current), 'in queue': tq.q.queue}

app.include_router(
    auth.router,
    tags=["auth"],
    dependencies=[Depends(verify_token)],
    ),
app.include_router(
    stats.router,
    prefix="/stats",
    tags=["stats"],
    dependencies=[Depends(verify_token)]
)
app.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin)],
    responses={418: {"description": "I'm a teapot"}},
)

app.mount("/", StaticFiles(directory="web/frontend", html=True), name="web/frontend")