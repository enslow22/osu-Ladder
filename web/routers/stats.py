from fastapi import APIRouter, status, Query, Request
from typing import Optional, Annotated, Dict, List
from pydantic import BaseModel
from sqlalchemy import select

from database.ORM import ORM
from database.models import RegisteredUser
from database.util import parse_score_filters, parse_mod_filters, parse_beatmap_filters, parse_beatmapset_filters, \
    parse_user_filters
from database.userService import get_profile_pp, top_play_per_day
from database.scoreService import get_top_n, get_scores, compact_scores_list
from web.apiModels import Mode, Metric, ScoreGroupBy, ScoreReturnFormat

router = APIRouter()
orm = ORM()

ScoreFilter = Query(default=None, description='Score Filters', example='rank/ABC pp>400 date>2020-04-24 perfect=1 replay=1')
ModFilter = Query(default=None, description='Mod Filters', example='')
BeatmapFilter = Query(default=None, description='Beatmap Filters')
BeatmapsetFilter = Query(default=None, description='Beatmapset Filters')

@router.get('/get_scores')
async def get_user_scores_with_filters(users: Annotated[list[int] | None, Query()], mode: Mode = 'osu', metric: Metric = 'lazer-score', desc: bool = True, limit: Annotated[int, Query(le=100)] = 100,
               mod_filters: str = None,
               score_filters: str = None,
               beatmap_filters: str = None,
               beatmapset_filters: str = None, return_format: ScoreReturnFormat = 'readable'):
    """
    Find scores based on parameters.
    Must specify a list of users.
    """
    session = orm.sessionmaker()

    user_filter = parse_user_filters(mode, users)
    parsed_mods_filters = parse_mod_filters(mode, mod_filters)
    parsed_score_filters = parse_score_filters(mode, score_filters)
    parsed_beatmap_filters = parse_beatmap_filters(beatmap_filters)
    parsed_beatmapset_filters = parse_beatmapset_filters(beatmapset_filters)

    scores = await get_scores(session, mode, metric, desc, limit, parsed_mods_filters, parsed_score_filters+user_filter, parsed_beatmap_filters, parsed_beatmapset_filters)

    if return_format == 'minimal':
        scores = compact_scores_list(scores, metric)
    elif return_format == 'verbose':
        users =  session.query(RegisteredUser.user_id, RegisteredUser.username, RegisteredUser.avatar_url).filter(RegisteredUser.user_id.in_(users)).all()
        users = [{"user id": x[0], "username": x[1], "avatar_url": x[2]} for x in users]
        scores = [x.to_dict() | {'beatmap': x.beatmap.to_dict()} for x in scores]
    elif return_format == 'none':
        scores = []
    else:
        scores = [{"title" : x.beatmap.beatmapset.title, "difficulty name": x.beatmap.version} | x.to_dict()  for x in scores]
    session.close()

    return {
        "users": users,
        "mode": "mode",
        "metric": metric,
        "desc": desc,
        "mod_filters": mod_filters,
        "score_filters": score_filters,
        "beatmap_filters": beatmap_filters,
        "beatmapset_filters": beatmapset_filters,
        "scores": scores}

@router.get('/top', status_code=status.HTTP_200_OK)
async def top_n(user_id: int, mode: Mode = 'osu', metric: Metric = 'pp', desc: bool = True, limit: Annotated[int, Query(le=100)] = 100, unique: bool = True,
                mod_filters: str = None,
                score_filters: str = None,
                beatmap_filters: str = None,
                beatmapset_filters: str = None,
                return_format: ScoreReturnFormat = 'readable'):
    """
    Gets the top n pp scores from the user (limit 100) based on a set of filters
    - **unique:** Return only one score per beatmap
    """
    parsed_mods_filters = parse_mod_filters(mode, mod_filters)
    parsed_score_filters = parse_score_filters(mode, score_filters)
    parsed_beatmap_filters = parse_beatmap_filters(beatmap_filters)
    parsed_beatmapset_filters = parse_beatmapset_filters(beatmapset_filters)

    session = orm.sessionmaker()
    limit = min(100, limit) # 100 is the max number of maps
    top_plays = await get_top_n(session, user_id, mode, metric, desc, limit, unique, parsed_mods_filters, parsed_score_filters, parsed_beatmap_filters, parsed_beatmapset_filters)

    if return_format == 'minimal':
        top_plays = compact_scores_list(top_plays, metric)
    elif return_format == 'verbose':
        top_plays = [x.to_dict() | {'beatmap': x.beatmap.to_dict()} for x in top_plays]
    elif return_format == 'none':
        top_plays = []
    else:
        top_plays = [{"title" : x.beatmap.beatmapset.title, "difficulty name": x.beatmap.version} | x.to_dict()  for x in top_plays]

    session.close()
    return {'user_id': user_id,
            'mode': mode.name,
            'metric': metric.name,
            'desc': desc,
            'mods': mod_filters,
            'score filters': score_filters,
            'beatmap filters': beatmap_filters,
            'beatmapset filters': beatmapset_filters,
            'limit': limit,
            'top plays': top_plays}

@router.get('/profile_pp', status_code=status.HTTP_200_OK)
async def profile_pp(user_id: int, mode: Mode = 'osu', metric: Metric = 'pp', desc: bool = True, limit: Annotated[int, Query(le=100)] = 100, unique: bool = True, bonus: bool = True,
                mod_filters: str = None,
                score_filters: str = None,
                beatmap_filters: str = None,
                beatmapset_filters: str = None,
                return_format: ScoreReturnFormat = 'readable'):
    """
    Same as top but also returns a profile pp value according to the weightage system at [https://osu.ppy.sh/wiki/en/Performance_points](https://osu.ppy.sh/wiki/en/Performance_points)
    - **unique:** Return only one score per beatmap
    - **n:** Number of scores to return (limit 100)
    - **bonus:** Whether to include max bonus pp in the calculation
    """
    limit = min(100, limit)  # 100 is the max number of maps
    parsed_mods_filters = parse_mod_filters(mode, mod_filters)
    parsed_score_filters = parse_score_filters(mode, score_filters)
    parsed_beatmap_filters = parse_beatmap_filters(beatmap_filters)
    parsed_beatmapset_filters = parse_beatmapset_filters(beatmapset_filters)

    session = orm.sessionmaker()
    scores = await get_top_n(session, user_id, mode, metric, desc, limit, unique, parsed_mods_filters,
                                parsed_score_filters, parsed_beatmap_filters, parsed_beatmapset_filters)

    total_pp = get_profile_pp(scores, bonus, limit)
    return {'user_id': user_id,
            'mode': mode.name,
            'metric': metric.name,
            'desc': desc,
            'mods': mod_filters,
            'score filters': score_filters,
            'beatmap filters': beatmap_filters,
            'beatmapset filters': beatmapset_filters,
            'limit': limit,
            'unique': unique,
            'total pp': total_pp,
            'top plays': compact_scores_list(scores, 'pp')}

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