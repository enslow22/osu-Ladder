"""
Methods in this service access the database about specific users.
Get methods return a resource
Post and registration methods return True or False depending on if the operation was successful
"""
import datetime
import os
from typing import Sequence
from osuApi import get_user_info
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from database.models import RegisteredUser, Score

def register_user(session: Session, user_id: int) -> (bool, RegisteredUser):
    """
    Register a new user to the database
    """
    user = session.get(RegisteredUser, user_id)
    if user:
        return False, user
    user_info = get_user_info(user_id)
    user = RegisteredUser(user_info)
    session.add(user)
    session.commit()
    return True, user

def set_user_authentication(session: Session, user_id: int,  apikey: str, access_token: str, refresh_token: str , expires_at: datetime.datetime) -> bool:
    user = session.get(RegisteredUser, user_id)
    if user is None:
        return False
    user.apikey = apikey
    user.access_token = access_token
    user.refresh_token = refresh_token
    user.expires_at = expires_at
    session.commit()
    return True

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
            'scope': 'public+identify'}
    r = requests.post('https://osu.ppy.sh/oauth/token', headers=headers, data=data)
    payload = r.json()
    print(payload)
    if 'access_token' in payload:
        user.refresh_token = payload['refresh_token']
        user.access_token = payload['access_token']
        user.expires_at = datetime.datetime.now() + datetime.timedelta(seconds=payload['expires_in'])
        session.commit()
        return True
    return False

def get_profile_pp(scores: Sequence[Score], bonus = True, n = 100) -> int:
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