import datetime
from fastapi import FastAPI, status, Query, Response, Request, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse, FileResponse
import requests
from hashlib import sha256

from starlette.staticfiles import StaticFiles

from routers import admin, auth, stats
from pydantic import BaseModel

from dependencies import verify_token, verify_admin, create_access_token, RegisteredUserCompact, has_token

from database.ORM import ORM
from database.fetchQueue import TaskQueue
import database.userService as userService
import dotenv
import os

dotenv.load_dotenv('../database/.env')
webclient_id = os.getenv('WEBCLIENT_ID')
webclient_secret = os.getenv('WEBCLIENT_SECRET')
redirect_uri = os.getenv('REDIRECT_URI')
templates = Jinja2Templates(directory='web/frontend/templates')

orm = ORM()
tq = TaskQueue(orm.sessionmaker)

app = FastAPI(redoc_url=None)
#app = FastAPI()

@app.get("/", response_class=FileResponse)
def main_page(request: Request, authorization: RegisteredUserCompact = Depends(has_token)):
    print(authorization)
    if not authorization:
        return templates.TemplateResponse(request=request, name='index.html', context={})
    else:
        # Get profile data from cookie
        session = orm.sessionmaker()
        user = userService.get_user_from_apikey(session, authorization['apikey'])
        session.close()
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
    r = requests.post(url='https://osu.ppy.sh/oauth/token', data=params, headers=headers).json()

    # If everything is successful, we can generate their database key as described by Haruhime and store that in the database
    if "access_token" in r:
        access_token = r['access_token']
        refresh_token = r['refresh_token']
        expires_in = r['expires_in']

        headers['Authorization'] =  'Bearer %s' % r['access_token']
        r = requests.get('https://osu.ppy.sh/api/v2/me/osu', headers=headers)
        user_data = r.json()
        print('Success! %s has successfully signed in with osu oauth.' % user_data['username'])

        static_secret = os.getenv('APIKEYSECRET')
        apikey = sha256((static_secret + str(user_data['id'])).encode('utf-8')).hexdigest()

        session = orm.sessionmaker()
        user = userService.register_user(session, user_data['id'], apikey, access_token=access_token, refresh_token=refresh_token, expires_at=datetime.datetime.now() + datetime.timedelta(seconds=expires_in))

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
    user_queue = tq.q.queue

    return {'current': copy.deepcopy(tq.current), 'in queue': [{'username': x[1].username,
                                                                'user_id': x[1].user_id,
                                                                'catch_converts': x[2],
                                                                'num_maps': 'nan'} for x in user_queue]}

app.include_router(
    auth.router,
    tags=["auth"],
    #dependencies=[Depends(verify_token)],
    )
app.include_router(
    stats.router,
    prefix="/stats",
    tags=["stats"],
    #dependencies=[Depends(verify_token)],
)
app.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    #dependencies=[Depends(verify_admin)],
)

app.mount("/", StaticFiles(directory="web/frontend", html=True), name="web/frontend")