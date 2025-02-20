from fastapi import APIRouter, status, Query, Request
from typing import Optional, Annotated, Dict
from database.ORM import ORM
from database.models import RegisteredUser
from database.util import parse_score_filters, parse_mod_filters
from database.userService import get_top_n, get_profile_pp
from database.tagService import get_ids_from_tag
from database.leaderboardService import get_beatmap_leaderboard, top_play_per_day
from database.scoreService import get_total_scores
from web.apiModels import Mode, Metric, ScoreGroupBy

router = APIRouter()
orm = ORM()

@router.get('/test')
def get_user(req: Request, user_id: int):
    """
    Fetches a user from the database from their user_id
    """
    return {"user": orm.session.get(RegisteredUser, user_id).username, "headers_given": req.headers}

@router.get('/top', status_code=status.HTTP_200_OK)
async def top_n(user_id: int, mode: Mode = 'osu', filter_string: str = None, mod_string: str = None, metric: Annotated[Metric, Query()] = 'pp', desc: bool = True, n: int = 100, unique: bool = True):
    """
    Gets the top n scores from the user (limit 100)
    - **unique:** Return only one score per beatmap
    """
    filters = parse_score_filters(mode, filter_string)
    mods = parse_mod_filters(mode, mod_string)
    session = orm.sessionmaker()
    n = min(100, n) # 100 is the max number of maps
    a = get_top_n(session, user_id, mode, filters, mods, metric, n, unique, desc)
    session.close()
    return {'user_id': user_id, 'mode': mode.name, 'filters': filter_string, 'mods': mod_string, 'metric': metric.name, 'unique': unique, 'top plays': a}

@router.get('/profile_pp', status_code=status.HTTP_200_OK)
async def profile_pp(user_id: int, mode: Mode = 'osu', filter_string: Optional[str] = None, mod_string: Optional[str] = None, n: int = 100, bonus: bool = True, unique: bool = True):
    """
    Same as top but also returns a profile pp value according to the weightage system at [https://osu.ppy.sh/wiki/en/Performance_points](https://osu.ppy.sh/wiki/en/Performance_points)
    - **unique:** Return only one score per beatmap
    - **n:** Number of scores to return (limit 100)
    - **bonus:** Whether to include max bonus pp in the calculation
    """
    n = min(100, n)  # 100 is the max number of maps
    scores = await top_n(user_id, mode, filter_string, mod_string, Metric.pp, True, n, unique)
    scores = scores['top plays']
    total_pp = get_profile_pp(scores, bonus, n)
    return {'user_id': user_id, 'mode': mode.name, 'filters': filter_string, 'mods': mod_string, 'unique': unique, 'total pp': total_pp, 'top plays': scores}

@router.get('/group_leaderboard', status_code=status.HTTP_200_OK)
async def get_group_leaderboard(beatmap_id: int, users: Annotated[list[int] | None, Query()] = None, group_tag: str or int = None, mode: Mode = 'osu', filter_string: Optional[str] = None, mod_string: Optional[str] = None,  metric: Annotated[Metric, Query()] = 'pp', desc: bool = True, unique: bool = True):
    """
    Given a beatmap_id and a list of users (or a Tag), construct a leaderboard
    - **unique:** Return only one score per user
    """

    filters = parse_score_filters(mode, filter_string)
    mods = parse_mod_filters(mode, mod_string)
    session = orm.sessionmaker()
    if users is None:
        if group_tag is None:
            return {"message": "Supply a group tag or list of users!"}
        users = get_ids_from_tag(session, group_tag)
        if len(users) == 0:
            return {"message": "There are no registered users in %s" % group_tag}

    scores = get_beatmap_leaderboard(session, users, beatmap_id, mode, filters, mods, metric, unique)
    session.close()
    return {"group": str(group_tag), "users": users, "mode": mode.name, "filters": filter_string, "mods": mod_string, "metric": metric.name, "scores": scores}

@router.get('/score_history', status_code=status.HTTP_200_OK)
async def get_score_history(user_id: int, mode: Mode = 'osu', filter_string: Optional[str] = None, mod_string: Optional[str] = None, minimal: bool = True):
    """
    Returns the player's month-to-month performance. This includes the highest pp play every month and the number of plays set per month
    """
    filters = parse_score_filters(mode, filter_string)
    mods = parse_mod_filters(mode, mod_string)
    session = orm.sessionmaker()
    scores = top_play_per_day(session, user_id, mode, filters, mods, minimal)
    session.close()
    return {"length": len(scores), "user_id": user_id, "mode": mode.name, "filters": filter_string, "mods": mod_string, "minimal": minimal, "scores": scores}

@router.get('/total_scores', status_code=status.HTTP_200_OK)
async def total_scores(mode: Mode = 'osu', filter_string: Optional[str] = None, mod_string: Optional[str] = None, group_by: ScoreGroupBy = None) -> Dict:
    """
    Returns the number of scores that match the filters
    """

    session = orm.sessionmaker()
    filters = parse_score_filters(mode, filter_string)
    mod_filters = parse_mod_filters(mode, mod_string)
    scores = get_total_scores(session, mode, filters, mod_filters, group_by=group_by)
    group_by_str = "None" if group_by is None else group_by.name
    return {"mode": mode.name, "filters": filter_string, "mods": mod_string, "grouping by": group_by_str, "scores": scores}