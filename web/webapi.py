import datetime
from fastapi import FastAPI, status, Request, Depends
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse, FileResponse
import requests
from hashlib import sha256
from starlette.staticfiles import StaticFiles
from routers import admin, auth, stats
from dependencies import verify_token, verify_admin, create_access_token, RegisteredUserCompact, has_token
from database.ORM import ORM
from database.userService import get_user_from_apikey, register_user, count_users, set_user_authentication
from database.tagService import count_tags
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

@app.get('/today_summary', status_code=status.HTTP_200_OK)
async def get_today_summary():
    """
    Returns the number of scores submitted in each mode for today
    """
    session = orm.sessionmaker()
    import datetime
    filter_string = 'date>='+datetime.date.today().strftime('%Y-%m-%d')
    data = {}
    for mode in ['osu', 'taiko', 'fruits', 'mania']:
        data[mode] = await count_scores(session, mode, score_filters=parse_score_filters(mode, filter_string))
    session.close()
    return data

@app.get('/database_summary', status_code=status.HTTP_200_OK)
async def get_database_summary():
    """
    Returns the number of scores in the database
    """
    session = orm.sessionmaker()
    num_osu_scores = await count_scores(session, mode='osu')
    num_taiko_scores = await count_scores(session, mode='taiko')
    num_catch_scores = await count_scores(session, mode='fruits')
    num_mania_scores = await count_scores(session, mode='mania')
    num_registered_users = count_users(session)
    num_tags, num_users_tagged = count_tags(session)
    session.close()

    return {'Total Standard Scores': num_osu_scores,
            'Total Taiko Scores': num_taiko_scores,
            'Total Catch Scores': num_catch_scores,
            'Total Mania Scores': num_mania_scores,
            'Total Registered Users': num_registered_users,
            'Total Tags': num_tags,
            'Total Tagged Players': num_users_tagged,}

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