"""
Methods in this service access the database about specific users.
Get methods return a resource
Post and registration methods return True or False depending on if the operation was successful
"""
import datetime
import os
from typing import List
from util import get_mode_table
from osuApi import get_user_info
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from database.models import RegisteredUser, RegisteredUserTag, Score

def register_user(session: Session, user_id: int, apikey: str | None = None, access_token: str | None = None, refresh_token: str | None = None, expires_at: datetime.datetime | None = None) -> (bool, RegisteredUser):
    """
    Register a new user to the database
    """
    user = session.get(RegisteredUser, user_id)
    if user:
        return False, user
    user_info = get_user_info(user_id)
    user = RegisteredUser(user_info)
    session.add(user)
    user.apikey = apikey
    user.access_token = access_token
    user.refresh_token = refresh_token
    user.expires_at = expires_at
    session.commit()
    return True, user

def get_user_from_apikey(session: Session, apikey) -> RegisteredUser or None:
    """
    Given an apikey, return the corresponding user
    """
    stmt = select(RegisteredUser).filter(RegisteredUser.apikey == apikey)
    user = session.scalars(stmt).one()
    return user

def update_user_metadata(session: Session, user_id: int) -> bool:
    """
    Given a user_id, update their metadata in the database
    """
    user = session.get(RegisteredUser, user_id)
    if user is None:
        print('User not found')
        return False
    user_info = get_user_info(user_id)
    user.set_all(user_info)
    session.commit()
    return True

def count_users(session: Session) -> int:
    """
    Return the number of registered users
    """
    return session.scalars(func.count(RegisteredUser.user_id)).one()

def get_top_n(session: Session, user_id: int, mode: str or int, filters: tuple, mods: tuple, metric: str = 'pp', number: int = 100, unique: bool = True, desc = True) -> List[Score]:
    """
    For a user, get their top n plays by some metric and filters. Also has the option to return one score per beatmap
    """
    if not isinstance(filters, tuple):
        filters = tuple(filters)
    if not isinstance(mods, tuple):
        mods = tuple(mods)
    table = get_mode_table(mode)

    sort_order = getattr(table, metric)
    if desc:
        sort_order = sort_order.desc()


    if not unique:
        stmt = select(table).filter(table.user_id == user_id).filter(*filters).filter(*mods).order_by(
            sort_order).limit(number)
        res = session.scalars(stmt).all()
        return list(res)
    else:

        # Select the highest pp play for each beatmap
        subq = select(table.beatmap_id, func.max(getattr(table, metric)).label('max_pp')).filter(table.user_id == user_id).filter(*filters).filter(*mods).group_by(table.beatmap_id).subquery()
        stmt = select(table).join(subq, (table.beatmap_id == subq.c.beatmap_id) & (getattr(table, metric) == subq.c.max_pp) ).filter(table.user_id == user_id).filter(*filters).filter(*mods).order_by(sort_order).limit(number)
        res = list(session.scalars(stmt).all())
        return res

def refresh_tokens(session: Session, user: RegisteredUser | int) -> bool:
    """
    Refresh a user's access token
    """
    if isinstance(user, int):
        user = session.get(RegisteredUser, user)
    if user.refresh_token is None:
        return False
    import requests
    headers = {'Accept': 'application/json',
               'Content-Type': 'application/x-www-form-urlencoded'}
    data = {'client_id': os.getenv('WEBCLIENT_ID'),
            'client_secret': os.getenv('WEBCLIENT_SECRET'),
            'grant_type': 'refresh_token',
            'refresh_token': user.refresh_token,
            'scope': 'public'}
    r = requests.post('https://osu.ppy.sh/oauth/token', headers=headers, data=data)
    payload = r.json()
    print(payload)
    if 'access_token' in payload:
        user.refresh_token = payload['refresh_token']
        user.access_token = payload['access_token']
        user.expires_at = datetime.datetime.now() + datetime.timedelta(seconds=payload['expires_in'])
        session.commit()
    return True

def get_profile_pp(scores: List[Score], bonus = True, n = 100) -> int:
    """
    Returns profile pp with only that list of scores considered
    """

    total = 416.666666 if bonus else 0
    scores = scores if n > len(scores) else scores[:n]
    for i, score in enumerate(scores):
        total += score.pp * 0.95**(i-1)
    return total

if __name__ == '__main__':
    from ORM import ORM
    orm = ORM()
    session = orm.sessionmaker()
    refresh_tokens(session, 4991273)