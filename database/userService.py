"""
Methods in this service access the database about specific users.
Get methods return a resource
Post and registration methods return True or False depending on if the operation was successful
"""
import datetime
import os
from typing import List
from database.util import get_mode_table
from database.osuApi import get_user_info
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database.models import RegisteredUser, RegisteredUserTag, Score


# TODO: hash the apikey before saving to db
def register_user(session: Session, user_id: int, apikey: str | None, access_token: str | None = None, refresh_token: str | None = None, expires_at: datetime.datetime | None = None):
    user = session.get(RegisteredUser, user_id)
    if user is None:
        user_info = get_user_info(user_id)
        user = RegisteredUser(user_info)
        session.add(user)
    user.apikey = apikey
    user.access_token = access_token
    user.refresh_token = refresh_token
    user.expires_at = expires_at
    session.commit()
    return user

def get_user_from_apikey(session: Session, apikey):
    stmt = select(RegisteredUser).filter(RegisteredUser.apikey == apikey)
    user = session.scalars(stmt).one()
    return user

def update_user_metadata(session: Session, user_id: int):
    user = session.get(RegisteredUser, user_id)
    if user is None:
        print('User not found')
        return False
    user_info = osu_api.get_user_info(user_id)
    user.set_all(user_info)
    session.commit()
    return True

def add_tags(session: Session, user_ids: List[int], tag:str):
    if isinstance(user_ids, int):
        user_ids = [user_ids]

    # TODO: This should be rewritten using select rather than query
    registered_profiles = session.query(RegisteredUser).filter(RegisteredUser.user_id.in_(user_ids)).all()
    registered_ids = [user.user_id for user in registered_profiles]

    not_registered = list(set(user_ids) - set(registered_ids))
    if len(not_registered) > 0:
        print('The user_ids: [%s] are not registered' % ', '.join(str(x) for x in not_registered))
        print('No action taken')
        return False

    new_tags = []
    try:
        for user_id in user_ids:
            new_tags.append(RegisteredUserTag(user_id=user_id, tag=tag))
        session.add_all(new_tags)
        session.commit()
        return True
    except IntegrityError as e:
        session.commit()
        print(e.orig)
        print('No action taken')
        return False

def get_top_n(session: Session, user_id: int, mode: str or int, filters: tuple, metric: str = 'pp', number: int = 100) -> List[Score]:
    """
    Runs (SELECT * FROM (table) WHERE user_id = user_id AND (filters) LIMIT (n) ORDER BY (metric) DESC)

    :param user_id: a user id
    :param mode:    integer representation of a game mode
    :param filters: a tuple of filters
    :param metric:  a column to order by
    :param number:  the number of scores to return
    :return:        The top n scores matching the provided filters for the specified player
    """
    if not isinstance(filters, tuple):
        filters = tuple(filters)
    table = get_mode_table(mode)
    stmt = select(table).filter(getattr(table, 'user_id') == user_id).filter(*filters).limit(number).order_by(getattr(table, metric).desc())
    res = session.scalars(stmt).all()

    return res

def get_ids_from_tag(session: Session, group: str or List[int]) -> List[int] or None:
    # List of user_ids
    if isinstance(group, list):
        return group
    stmt = select(RegisteredUserTag.user_id)
    if isinstance(group, str):
        stmt = stmt.filter(RegisteredUserTag.tag == group)
    return session.scalars(stmt).all()

def refresh_tokens(session: Session, user: RegisteredUser | int):
    if isinstance(user, int):
        user = session.get(RegisteredUser, user)
    if user.refresh_token is None:
        return
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
    if 'access_token' in payload:
        user.refresh_token = payload['refresh_token']
        user.access_token = payload['access_token']
        user.expires_at = datetime.datetime.now() + datetime.timedelta(seconds=payload['expires_in'])
        session.commit()

def get_profile_pp(scores: List[Score], bonus = True, n = 100) -> int:
    """
    Returns profile pp with only that list of scores considered
    :param n:       number of scores to truncate to (ignored if n > len(scores))
    :param bonus:   include max bonus pp or not
    :param scores:  A list of score objects
    :return:        Profile pp
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
    refresh_tokens(session, 10651409)