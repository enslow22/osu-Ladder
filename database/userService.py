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
from sqlalchemy.exc import IntegrityError
from database.models import RegisteredUser, RegisteredUserTag, Score


# TODO: hash the apikey before saving to db
def register_user(session: Session, user_id: int, apikey: str | None = None, access_token: str | None = None, refresh_token: str | None = None, expires_at: datetime.datetime | None = None) -> RegisteredUser:
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

def get_user_from_apikey(session: Session, apikey) -> RegisteredUser or None:
    stmt = select(RegisteredUser).filter(RegisteredUser.apikey == apikey)
    user = session.scalars(stmt).one()
    return user

def update_user_metadata(session: Session, user_id: int) -> bool:
    user = session.get(RegisteredUser, user_id)
    if user is None:
        print('User not found')
        return False
    user_info = get_user_info(user_id)
    user.set_all(user_info)
    session.commit()
    return True

# TODO: implement this on the database end as well. Will also need an orm mapped class in models.py
def create_tag(session: Session, owner: int, tag: str) -> bool:
    """

    :param owner:   Who has management controls over the tag
    :param tag:     String representation of the group name
    :return:
    """
    # Check if tag exists

    # Check if user owns more than 4 groups

    # Make new tag and assign incremental id
    return True

def add_tags(session: Session, user_ids: List[int], tag:str) -> bool:
    if isinstance(user_ids, int):
        user_ids = [user_ids]

    stmt = select(RegisteredUser.user_id).filter(RegisteredUser.user_id.in_(user_ids))
    registered_ids = session.execute(stmt).scalars().all()
    #registered_profiles = session.query(RegisteredUser).filter(RegisteredUser.user_id.in_(user_ids)).all()
    #registered_ids = [user.user_id for user in registered_profiles]

    not_registered = list(set(user_ids) - set(registered_ids))
    if len(not_registered) > 0:
        print('The user_ids: [%s] are not registered' % ', '.join(str(x) for x in not_registered))
        print('No action taken')
        return False

    try:
        for user_id in user_ids:
            session.merge(RegisteredUserTag(user_id=user_id, tag=tag))
        session.commit()
        return True
    except IntegrityError as e:
        session.commit()
        print(e.orig)
        print('No action taken')
        return False

# TODO unique has not been implemented yet
def get_top_n(session: Session, user_id: int, mode: str or int, filters: tuple, mods: tuple, metric: str = 'pp', number: int = 100, unique: bool = True, desc = True) -> List[Score]:
    """
    Runs (SELECT * FROM (table) WHERE user_id = user_id AND (filters) LIMIT (n) ORDER BY (metric) DESC)

    :param user_id: a user id
    :param mode:    integer representation of a game mode
    :param filters: a tuple of filters
    :param mods:    a tuple of mod filters
    :param metric:  a column to order by
    :param number:  the number of scores to return
    :param unique:  Only pick one score per beatmap
    :param desc:    returns in descending metric if true, ascending if false
    :return:        The top n scores matching the provided filters for the specified player
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
        stmt = select(table).filter(getattr(table, 'user_id') == user_id).filter(*filters).filter(*mods).order_by(
            sort_order).limit(number)
        res = session.scalars(stmt).all()
        return list(res)
    else:
        stmt = select(table).filter(getattr(table, 'user_id') == user_id).filter(*filters).filter(*mods).order_by(
            sort_order).limit(number) # i hate subqueries im sorry i cant deal with this rn
        res = session.scalars(stmt).all()
        # I think i should make this a stored procedure.
        return list(res)

def get_ids_from_tag(session: Session, group: str or List[int]) -> List[int] or None:
    # List of user_ids
    if isinstance(group, list):
        return group
    stmt = select(RegisteredUserTag.user_id)
    if isinstance(group, str):
        stmt = stmt.filter(RegisteredUserTag.tag == group)
    return session.scalars(stmt).all()

def refresh_tokens(session: Session, user: RegisteredUser | int) -> bool:
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
    refresh_tokens(session, 4991273)