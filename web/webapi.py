import datetime
import time
import timeit

from fastapi import FastAPI, status, Request, Depends
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse, FileResponse
from sqlalchemy import select, func
import requests
from hashlib import sha256
from starlette.staticfiles import StaticFiles

from database.models import Leaderboard, LeaderboardSpot, RegisteredUser, BeatmapSet, Beatmap, OsuScore, TaikoScore, \
    CatchScore, ManiaScore
from routers import admin, auth, stats
from dependencies import verify_token, verify_admin, create_access_token, RegisteredUserCompact, has_token
from database.ORM import ORM
from database.userService import get_user_from_apikey, register_user, count_users, set_user_authentication
from database.scoreService import count_scores
from database.util import parse_score_filters
import dotenv
import os

dotenv.load_dotenv('../database/.env')
webclient_id = os.getenv('WEBCLIENT_ID')
webclient_secret = os.getenv('WEBCLIENT_SECRET')
redirect_uri = os.getenv('REDIRECT_URI')
templates = Jinja2Templates(directory='web/frontend/templates')

orm = ORM()

tags_metadata = [
    {
        "name": "default",
        "description": "Methods that anyone can access."
    },
    {
        "name": "auth",
        "description": "Methods that require osu! oauth authentication from the end user.",
    },
    {
        "name": "stats",
        "description": "Methods for data retrieval and analysis. Requires auth.",
    },
    {
        "name": "admin",
        "description": "Methods for administrative tasks. Must have administrative access",
    }
]

with open("web/description.md", 'r') as f:
    description = f.read(-1)

app = FastAPI(redoc_url=None, openapi_tags=tags_metadata, description=description)

@app.get("/", response_class=FileResponse)
def main_page(request: Request, authorization: RegisteredUserCompact = Depends(has_token)):
    """
    Returns the home page
    """
    if not authorization:
        return templates.TemplateResponse(request=request, name='index.html', context={})
    else:
        # Get profile data from cookie
        session = orm.sessionmaker()
        user = get_user_from_apikey(session, authorization['apikey'])
        session.close()
        return templates.TemplateResponse(request=request,
                                          name='authorized.html',
                                          context={'apikey': user.apikey,
                                                   'username': user.username,
                                                   'profile_avatar': user.avatar_url})

@app.get("/login", status_code=status.HTTP_200_OK)
async def login_via_osu(req: Request):
    """
    Sends user to the osu oauth page
    """
    if os.getenv('APISUBDOMAIN') in req.headers['referer']:
        url = 'https://osu.ppy.sh/oauth/authorize?client_id=%s&redirect_uri=%s&response_type=code&scope=public' % (
        webclient_id, redirect_uri)
    else:
        url = 'https://osu.ppy.sh/oauth/authorize?client_id=%s&redirect_uri=%s&response_type=code&scope=public' % (
        webclient_id, os.getenv('REDIRECT_URI_FRONT'))
    return RedirectResponse(url=url)

@app.get("/auth_front", status_code=status.HTTP_200_OK)
async def auth_to_front(code: str):
    return await auth_via_osu(code, os.getenv('FRONTDOMAIN'))

@app.get("/auth", status_code=status.HTTP_200_OK)
async def auth_via_osu(code: str, override_redirect: str or None = None):
    """
    The callback for osu oauth
    """
    if override_redirect:
        callback_url = os.getenv('REDIRECT_URI_FRONT')
    else:
        callback_url = redirect_uri
    headers = {'Accept': 'application/json',
               'Content-Type': 'application/x-www-form-urlencoded',}
    params = {'client_id': str(webclient_id),
              'client_secret': str(webclient_secret),
              'code': code,
              'grant_type': 'authorization_code',
              'redirect_uri': callback_url,}
    r = requests.post(url='https://osu.ppy.sh/oauth/token', data=params, headers=headers).json()

    # If everything is successful, we can generate their database key as described by Haruhime and store that in the database
    if "access_token" in r:
        access_token = r['access_token']
        refresh_token = r['refresh_token']
        expires_in = r['expires_in']

        headers['Authorization'] =  'Bearer %s' % r['access_token']
        r = requests.get('https://osu.ppy.sh/api/v2/me/fruits', headers=headers)
        user_data = r.json()
        print('Success! %s has successfully signed in with osu oauth.' % user_data['username'])

        static_secret = os.getenv('APIKEYSECRET')
        apikey = sha256((static_secret + str(user_data['id'])).encode('utf-8')).hexdigest()

        session = orm.sessionmaker()
        success, user = register_user(session, user_data['id'])
        set_user_authentication(session, user_data['id'], apikey, access_token, refresh_token, datetime.datetime.now() + datetime.timedelta(seconds=expires_in))

        access_token = create_access_token({'user_id': user_data['id'], 'username': user.username, 'avatar_url': user.avatar_url, 'apikey': apikey, 'catch_playtime': user_data['statistics']['play_time']})

        if override_redirect:
            response = RedirectResponse(url=os.getenv('FRONTDOMAIN'))
        else:
            response = RedirectResponse(url='/')
        response.set_cookie(key='session_token', value=access_token, httponly=True, secure=True, domain=os.getenv("DOMAIN"))

        return response
    return {"message": "Something has gone wrong. Please try again and let enslow know if you continue to have issues!"}

@app.get("/fetch_queue", status_code=status.HTTP_301_MOVED_PERMANENTLY)
def get_fetch_queue():
    """
    Moved to /fetch/fetch_queue
    """
    return {"message": "Moved to /fetch/fetch_queue"}

@app.get('/recent_scores', status_code=status.HTTP_200_OK)
async def get_recent_scores(n: int=10):
    n = min(n, 10)
    now = time.time()
    session = orm.sessionmaker()
    osu_scores = session.scalars(select(OsuScore).order_by(OsuScore.score_id.desc()).limit(n)).all()
    taiko_scores = session.scalars(select(TaikoScore).order_by(TaikoScore.score_id.desc()).limit(n)).all()
    catch_scores = session.scalars(select(CatchScore).order_by(CatchScore.score_id.desc()).limit(n)).all()
    mania_scores = session.scalars(select(ManiaScore).order_by(ManiaScore.score_id.desc()).limit(n)).all()
    scores_list = osu_scores+taiko_scores+catch_scores+mania_scores

    scores_list = [x.to_dict() | {"mode": x.get_mode()} for x in scores_list]

    scores_list.sort(key=lambda x: x['date'], reverse=True)
    later = time.time()
    print(later - now)
    return scores_list[:n]

@app.get('/recent_summary', status_code=status.HTTP_200_OK)
async def get_recent_summary(days: int = 1):
    """
    Returns the number of scores fetched in each mode for the past n days. (max 7 days)
    """
    days = min(7, days)
    session = orm.sessionmaker()
    import datetime

    one_day = datetime.timedelta(days=1)
    today = datetime.date.today()
    data = []
    for day in range(days):
        row = {'date': (today - day*one_day).strftime('%Y-%m-%d')}
        filter_string = f'date>={(today - day*one_day).strftime('%Y-%m-%d')} date<={(today - (day-1)*one_day).strftime('%Y-%m-%d')}'
        for mode in ['osu', 'taiko', 'fruits', 'mania']:
            row[mode] = await count_scores(session, mode, score_filters=parse_score_filters(mode, filter_string))
        data.append(row)
    session.close()
    return data

@app.get('/database_summary', status_code=status.HTTP_200_OK)
async def get_database_summary():
    """
    Returns the number of scores in the database
    """
    session = orm.sessionmaker()
    data = {'num_users': session.query(func.count(RegisteredUser)).scalar(),
            'num_beatmapsets': session.query(func.count(BeatmapSet)).scalar(),
            'num_beatmaps': session.query(func.count(Beatmap)).scalar(),
            'num_leaderboards': session.query(func.count(Leaderboard.leaderboard_id)).scalar(),
            'num_leaderboardspots': session.query(func.count(LeaderboardSpot)).scalar(),
            }

    for mode in ['osu', 'taiko', 'fruits', 'mania']:
        data[mode] = await count_scores(session, mode=mode)
    session.close()

    return data

@app.get('/user_summary')
async def get_user_summary():
    """
    SELECT r.username, r.last_updated, s.user_id, COUNT(*) FROM all_modes s  LEFT JOIN registered_users r on r.user_id = s.user_id GROUP BY s.user_id
    :return:
    """
    pass

app.include_router(
    auth.router,
    tags=["auth"],
    dependencies=[Depends(verify_token)],
)
app.include_router(
    stats.router,
    prefix="/stats",
    tags=["stats"],
    dependencies=[Depends(verify_token)],
)
app.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin)],
)

app.mount("/", StaticFiles(directory="web/frontend", html=True), name="web/frontend")