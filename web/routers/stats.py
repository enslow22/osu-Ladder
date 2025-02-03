from fastapi import APIRouter, status, Query
from typing import Optional, List, Annotated
from database.ORM import ORM
from database.models import RegisteredUser
from database.util import parse_score_filters, parse_mod_filters
from database.userService import get_top_n, get_profile_pp, get_ids_from_tag
from database.leaderboardService import group_leaderboard
from web.apiModels import Filters, Mods, Mode, Metric

router = APIRouter()
orm = ORM()

@router.get('/test')
def get_user(user_id: int):
    """
    Fetches a user from the database from their user_id
    """
    return {"user": orm.session.get(RegisteredUser, user_id)}

@router.get('/top', status_code=status.HTTP_200_OK)
def top_n(user_id: int, mode: Mode = 'osu', filters: str = None, mods: str = None, metric: str = 'pp', desc: bool = True, n: int = 100, unique: bool = True):
    """
    Gets the top n scores from the user (limit 100)
    - **unique:** Return only one score per beatmap
    """
    filters = parse_score_filters(mode, filters)
    mods = parse_mod_filters(mode, mods)
    session = orm.sessionmaker()
    n = min(100, n) # 100 is the max number of maps
    a = get_top_n(session, user_id, mode, filters, mods, metric, n, unique, desc)
    session.close()
    return {"scores": a}

@router.get('/profile_pp', status_code=status.HTTP_200_OK)
def profile_pp(user_id: int, mode: Mode = 'osu', filters: Optional[str] = None, mods: Optional[str] = None, n: int = 100, bonus: bool = True, unique: bool = True):
    """
    Same as top but also returns a profile pp value according to the weightage system at https://osu.ppy.sh/wiki/en/Performance_points
    - **unique:** Return only one score per beatmap
    """
    n = min(100, n)  # 100 is the max number of maps
    scores = top_n(user_id, mode, filters, mods,'pp', True, n, unique)['scores']
    total_pp = get_profile_pp(scores, bonus, n)
    return {"total_pp": total_pp, "scores": scores}

@router.get('/group_leaderboard', status_code=status.HTTP_200_OK)
def get_group_leaderboard(beatmap_id: int, users: Annotated[list[int] | None, Query()] = None, group_tag: str = None, mode: Mode = 'osu', filters: Optional[str] = None, mods: Optional[str] = None,  metric: Annotated[Metric, Query()] = 'pp', desc: bool = True, unique: bool = True):
    """
    Given a beatmap_id and a list of users (or a Tag), construct a leaderboard
    - **unique:** Return only one score per user
    """
    filters = parse_score_filters(mode, filters)
    mods = parse_mod_filters(mode, mods)
    session = orm.sessionmaker()
    if users is None:
        if group_tag is None:
            return {"message": "Supply a group tag or list of users!"}
        users = get_ids_from_tag(session, group_tag)
        if len(users) == 0:
            return {"message": "There are no registered users in %s" % group_tag}

    scores = group_leaderboard(session, users, beatmap_id, mode, filters, mods, metric, unique)
    session.close()
    return {"Leaderboard for %s" % beatmap_id: scores}