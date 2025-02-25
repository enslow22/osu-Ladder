"""
Does stuff relating to Score Objects
Includes:
    - Fetching Scores based on filters
    - Calculating Metrics for users based on their Scores (weighted_sum_pp, group by count scores, etc.)
"""

from collections.abc import Sequence
from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session
from database.models import Beatmap, Score, BeatmapSet
from database.util import parse_user_filters
from util import get_mode_table
from typing import List
from ossapi import Score as ossapiScore

def insert_scores(session: Session, scores: List[ossapiScore]) -> bool:
    if not scores:
        return False
    try:
        for score in scores:
            new_score = get_mode_table(score.ruleset_id)()
            new_score.set_details(score)
            session.merge(new_score)
        session.commit()
        return True
    except Exception as e:
        print(e)
        for score in scores:
            print(str(score))
        return False

def get_user_scores(session: Session, beatmap_id: int, user_id: int, mode: str or int, filters: tuple = (), mods: tuple = (), metric: str = 'lazer_score') -> Sequence[Score]:
    """
    Given a user and a beatmap, get all the user's scores on that beatmap. Can also specify filters and metrics to sort by
    """
    table = get_mode_table(mode)
    stmt = select(table).filter(
        and_(
            getattr(table, 'beatmap_id') == beatmap_id,
            getattr(table, 'user_id') == user_id
        )
    ).filter(*filters).filter(*mods).order_by(getattr(table, metric).desc())
    return session.scalars(stmt).all()

async def get_scores(session: Session, mode: str or int, metric: str = 'lazer_score', desc: bool = True,
               limit=100,
               mod_filters: tuple = (),
               score_filters: tuple = (),
               beatmap_filters: tuple = None,
               beatmapset_filters: tuple = None,
               ) -> Sequence[Score]:
    """
    Select a list of scores based on some criteria
    """

    # Get mode
    score_type_table = get_mode_table(mode)

    # Parse order and metric
    sort_order = getattr(score_type_table, metric)
    if desc:
        sort_order = sort_order.desc()

    # Apply filters
    stmt = select(score_type_table).filter(*score_filters).filter(*mod_filters)
    if beatmap_filters:
        stmt = stmt.join(Beatmap, score_type_table.beatmap_id == Beatmap.beatmap_id).filter(*beatmap_filters)
    if beatmapset_filters:
        if not beatmap_filters:
            stmt = stmt.join(Beatmap, score_type_table.beatmap_id == Beatmap.beatmap_id)
        stmt = stmt.join(BeatmapSet, Beatmap.beatmapset_id == BeatmapSet.beatmapset_id).filter(*beatmapset_filters)

    # Order and limit results
    stmt = stmt.order_by(sort_order).limit(limit)

    return session.scalars(stmt).all()

async def count_scores(session: Session, mode: str or int, group_by: str | None = None, desc: bool = True, limit = 1000,
                         mod_filters: tuple = (),
                         score_filters: tuple = (),
                         beatmap_filters: tuple = None,
                         beatmapset_filters: tuple = None) -> List[dict]:
        """
        Returns the number of scores with the given filters
        If group by is None, do not group by anything and instead just count the total.
        """

        score_type_table = get_mode_table(mode)

        sort_order = func.count(getattr(score_type_table, 'score_id'))
        if desc:
            sort_order = func.count(getattr(score_type_table, 'score_id')).desc()

        # Choose group by
        if group_by:
            stmt = select(getattr(score_type_table, group_by), func.count(score_type_table.score_id))
        else:
            stmt = select(func.count(score_type_table.score_id))

        # Apply all WHERE clauses
        stmt = stmt.filter(*score_filters).filter(*mod_filters)
        if beatmap_filters:
            stmt = stmt.join(Beatmap, score_type_table.beatmap_id == Beatmap.beatmap_id).filter(*beatmap_filters)
        if beatmapset_filters:
            if not beatmap_filters:
                stmt = stmt.join(Beatmap, score_type_table.beatmap_id == Beatmap.beatmap_id)
            stmt = stmt.join(BeatmapSet, Beatmap.beatmapset_id == BeatmapSet.beatmapset_id).filter(*beatmapset_filters)

        # Group by field and sort
        if group_by:
            stmt = stmt.group_by(getattr(score_type_table, group_by)).order_by(sort_order)
        else:
            stmt = stmt.order_by(sort_order)

        # Limit results
        stmt = stmt.limit(limit)

        # Parse and format response
        res = list(session.execute(stmt).fetchall())
        if group_by:
            return [{group_by: x[0], "count": x[1]} for x in res]
        else:
            return res[0][0]

async def get_top_n(session: Session, user_id: int, mode: str or int, metric: str = 'pp', desc = True, limit: int = 100, unique: bool = True,
              mod_filters: tuple = (),
              score_filters: tuple = (),
              beatmap_filters: tuple = None,
              beatmapset_filters: tuple = None) -> Sequence[Score]:
    """
    For a user, get their top n plays by some metric and filters. Also has the option to return one score per beatmap
    """

    score_type_table = get_mode_table(mode)

    sort_order = getattr(score_type_table, metric)
    if desc:
        sort_order = sort_order.desc()
    user_filter = parse_user_filters(mode, user_id)

    if not unique:
        return await get_scores(session, mode, metric, desc, limit, mod_filters, user_filter + score_filters, beatmap_filters, beatmapset_filters)
    else:
        # Select the highest pp play for each beatmap
        subq = select(score_type_table.beatmap_id, func.max(getattr(score_type_table, metric)).label('max_metric')).filter(*user_filter).filter(*mod_filters).filter(*score_filters).group_by(score_type_table.beatmap_id).subquery()
        stmt = select(score_type_table).join(subq, (score_type_table.beatmap_id == subq.c.beatmap_id) & (getattr(score_type_table, metric) == subq.c.max_metric) ).filter(*user_filter).order_by(sort_order).limit(limit)

        if beatmap_filters:
            stmt = stmt.join(Beatmap, score_type_table.beatmap_id == Beatmap.beatmap_id).filter(*beatmap_filters)
        if beatmapset_filters:
            if not beatmap_filters:
                stmt = stmt.join(Beatmap, score_type_table.beatmap_id == Beatmap.beatmap_id)
            stmt = stmt.join(BeatmapSet, Beatmap.beatmapset_id == BeatmapSet.beatmapset_id).filter(*beatmapset_filters)

        return session.scalars(stmt).all()

def compact_scores_list(scores: List[Score] or Score, metric: str = 'lazer_score'):
    scores = [{"user id": x.user_id,
               "score id": x.score_id,
               "beatmap id": x.beatmap_id,
               "beatmap_title": x.beatmap.beatmapset.title,
               "difficulty name": x.beatmap.version,
               "date": x.date,
               "mods": x.enabled_mods,
               "mods settings": x.enabled_mods_settings,
               metric: getattr(x, metric),
               } for x in scores]
    return scores

def format_scores_list(scores: List[Score] or Score, metric: str = 'lazer_score'):

    for score in scores:
        print(score.to_dict())
    return scores

def weighted_pp_sum(scores: List[Score]) -> int:
    """
    Returns profile pp for the top 100 scores.
    """
    n = 100
    total = 416.666666
    scores = scores if n > len(scores) else scores[:n]
    for i, score in enumerate(scores):
        total += score.pp * 0.95**(i-1)
    return total

if __name__ == '__main__':

    from ORM import ORM
    orm = ORM()
    session = orm.sessionmaker()

    from util import parse_beatmap_filters, parse_beatmapset_filters, parse_score_filters, parse_mod_filters
    from sqlalchemy.dialects import mysql

    mods = parse_mod_filters('osu', '+EZ')
    sf = parse_score_filters('osu', 'replay=1')
    bmf = parse_beatmap_filters("stars>5")
    bmsf = parse_beatmapset_filters("language_id=2")

    #a = get_scores(session, 'osu', 'lazer_score',True, 1000, mod_filters=mods, score_filters=sf, beatmap_filters=bmf, beatmapset_filters=bmsf)
    #b = format_scores_list(a, 'lazer_score')
    #a = get_top_n(session, 124493, 'osu', 'pp', True, 100, True, beatmapset_filters=bmsf, mod_filters=mods)

