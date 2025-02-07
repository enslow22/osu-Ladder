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
from database.fetchQueue import TaskQueue
from database.userService import get_user_from_apikey, register_user, count_users
from database.tagService import count_tags
from database.scoreService import get_total_scores
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

description = """
## osu!lb api documentation

osu!lb is a scores database. It stores all modes, and only excludes taiko and mania converts. You can register yourself to get your scores fetched by the api. Once you're registered, osu!lb will constantly update itself will all your new scores. 

---

### Mods:

You have three options for filtering scores by mods:
- Exact
    - Start the mod string with '!', and osu!lb will find all scores with that __exact__ mod combination.
    - Note that 'CL' is a mod, so nomod plays should have the string 'CL' if set on stable or '' if set on lazer.
    - Example: 'mods=!HDHRDT', 'mods=!EZHTHD'.
- Including
    - Start the string of mods to be included with '+'. osu!lb will return all scores that include those mods.
    - Example: 'mods=+HRHD', 'mods=+EZ+HD+RX'
- Excluding
    - Start the string of mods to be excluded with '-'. osu!lb will return all scores that exclude those mods.
    - Example: 'mods=-HD', 'mods=-DT-HT-RC'

You can combine including and excluding mod filters as well.
For example, the string 'mods=+HR-HDDT' will return all scores that have HR, except the ones that also have HD or DT    

---

### General Filters:

osu!lb stores the following data for every score in the database:

| Column Name   | Type                                           | Description                                                                                    |
|---------------|------------------------------------------------|------------------------------------------------------------------------------------------------|
| user_id       | int                                            | The user who set the play                                                                      |
| date          | datetime                                       | The date and time the score was submitted in UTC. Formatted as "YYYY-MM-DD HH:MM:SS"           |
| pp            | float                                          | The pp value of the score.                                                                     |
| rank          | Enum('XH', 'X', 'SH', 'S', 'A', 'B', 'C', 'D') | The awarded rank of the score.                                                                 |
| perfect       | bool                                           | If the score has perfect combo                                                                 |
| max_combo     | int                                            | The highest combo achieved in the score                                                        |
| replay        | bool                                           | Does a replay exist on bancho? (This information may be out of date as bancho deletes replays) |
| stable_score  | int                                            | The score amount on stable. (Will be 0 for scores set on lazer)                                |
| lazer_score   | int                                            | The score amount on lazer.                                                                     |
| classic_score | int                                            | The score amount on lazer classic scoring. (Will be -1 for some scores)                        |
| count_miss    | int                                            | The number of misses                                                                           |
| count_50      | int                                            | The number of 50s                                                                              |
| count_100     | int                                            | The number of 100s                                                                             |
| count_300     | int                                            | The number of 300s                                                                             |

- You can filter through these with operators: (=, !=, >, <, <=, >=, /)
- / represents the contains operator and it is used only for rank. The string rank/(XHSH) will only return scores that are hidden S or hidden SS
- For dates, you can also compare with the format "YYYY-MM-DD" (e.g. date<2024-07-27 will return all scores older than July 27th 2024, 00:00:00)
- You can add multiple filters by separating them with withspace or commas (e.g. pp<1000 pp>800 date<2023-01-01 will return all scores earlier than 2023 with pp values between 800 and 1000)

### Metrics:

Metrics are how the returned data is sorted. You can sort the data by pp, stable_score, lazer_score, classic_score, accuracy, or date. 

You can also sort by descending (default) or ascending
"""

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
async def login_via_osu():
    """
    Sends user to the osu oauth page
    """
    return RedirectResponse(url='https://osu.ppy.sh/oauth/authorize?client_id=%s&redirect_uri=%s&response_type=code&scope=public' % (webclient_id, redirect_uri))

@app.get("/auth", status_code=status.HTTP_200_OK)
async def auth_via_osu(code: str):
    """
    The callback for osu oauth
    """
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
        r = requests.get('https://osu.ppy.sh/api/v2/me/fruits', headers=headers)
        user_data = r.json()
        print('Success! %s has successfully signed in with osu oauth.' % user_data['username'])

        static_secret = os.getenv('APIKEYSECRET')
        apikey = sha256((static_secret + str(user_data['id'])).encode('utf-8')).hexdigest()

        session = orm.sessionmaker()
        success, user = register_user(session, user_data['id'], apikey, access_token=access_token, refresh_token=refresh_token, expires_at=datetime.datetime.now() + datetime.timedelta(seconds=expires_in))

        access_token = create_access_token({'user_id': user_data['id'], 'username': user.username, 'avatar_url': user.avatar_url, 'apikey': apikey, 'catch_playtime': user_data['statistics']['play_time']})
        response = RedirectResponse(url='/')
        response.set_cookie(key='session_token', value=access_token, httponly=True, secure=True)

        return response
    return {"message": "Something has gone wrong. Please try again and let enslow know if you continue to have issues!"}

@app.get("/fetch_queue", status_code=status.HTTP_200_OK)
def get_fetch_queue():
    """
    Moved to /fetch/fetch_queue
    """
    pass

@app.get('/today_summary', status_code=status.HTTP_200_OK)
def get_today_summary():
    """
    Returns the number of scores submitted in each mode for today
    """
    session = orm.sessionmaker()
    import datetime
    filter_string = 'date>='+datetime.date.today().strftime('%Y-%m-%d')
    data = {}
    for mode in ['osu', 'taiko', 'fruits', 'mania']:
        data[mode] = get_total_scores(session, mode, filters=parse_score_filters(mode, filter_string))
    session.close()
    return data

@app.get('/database_summary', status_code=status.HTTP_200_OK)
async def get_database_summary():
    """
    Returns the number of scores in the database
    """
    session = orm.sessionmaker()
    num_osu_scores = get_total_scores(session, mode='osu')
    num_taiko_scores = get_total_scores(session, mode='taiko')
    num_catch_scores = get_total_scores(session, mode='fruits')
    num_mania_scores = get_total_scores(session, mode='mania')
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