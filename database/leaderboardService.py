import datetime

from sqlalchemy import select, and_, func, Date
from sqlalchemy.orm import Session
from database.util import get_mode_table, parse_score_filters, parse_beatmap_filters, parse_beatmapset_filters, parse_user_filters, parse_mod_filters
from typing import List, Any
from ossapi import Score
from database.models import RegisteredUser, Leaderboard, LeaderboardSpot, LeaderboardMetricEnum
from database.scoreService import get_scores, count_scores, get_top_n, weighted_pp_sum


# Probably shouldn't have this as a route, but we will see.
def pp_record_history(session: Session, users: List[int], mode: str or int) -> List[dict[str, Any]]:
    """
    Given a list of users, calculate the pp history.
    """
    table = get_mode_table(mode)
    # For one hundred players, this loads about 100mb worth of data into memory
    stmt = select(table.date, table.pp, table.score_id).filter(
        and_(
            getattr(table, 'pp').is_not(None),
            getattr(table, 'user_id').in_(users)
        )
    ).order_by(getattr(table, 'date'))

    scores = session.execute(stmt).all()

    pp_record = 0
    pp_records = []
    for score in scores:
        if score[1] >= pp_record:
            pp_records.append(score[2])
            pp_record = score[1]

    stmt = select(table, RegisteredUser).join_from(table, RegisteredUser, RegisteredUser.user_id == table.user_id).filter(table.score_id.in_(pp_records))

    pp_history = []
    for row in session.execute(stmt):
        pp_history.append({
            'username': row[1].username,
            'score': row[0].to_dict()
        })
    return pp_history

async def recalculate_user(session: Session, user_id: int, leaderboard_id: int = None, leaderboard_name: str = None):
    """
    Given a leaderboard and a user, update LeaderboardSpot.value
    """
    if not leaderboard_id and not leaderboard_name:
        return False

    if leaderboard_id:
        stmt = select(Leaderboard).filter(Leaderboard.leaderboard_id == leaderboard_id)
    else:
        stmt = select(Leaderboard).filter(Leaderboard.name == leaderboard_name)
    leaderboard = session.scalars(stmt).one()

    leaderboard_spot = list(filter(lambda x: x.user_id == user_id, leaderboard.leaderboard_spots))[0]

    mode = leaderboard.mode.name
    mod_filters = parse_mod_filters(mode, leaderboard.mod_filters)
    score_filters = parse_score_filters(mode, leaderboard.score_filters)
    beatmap_filters = parse_beatmap_filters(leaderboard.beatmap_filters)
    beatmapset_filters = parse_beatmapset_filters(leaderboard.beatmapset_filters)

    new_value = 0

    if leaderboard.metric.name == LeaderboardMetricEnum.weighted_pp.name:
        scores_list = await get_top_n(session, user_id, mode, 'pp', True, 100, True, mod_filters, score_filters, beatmap_filters, beatmapset_filters)
        new_value = weighted_pp_sum(list(scores_list))
        leaderboard_spot.value = new_value
    elif leaderboard.metric.name == LeaderboardMetricEnum.count_unique_beatmaps:
        user_filter = parse_user_filters(mode, leaderboard_spot.user_id)
        new_value = count_scores(session, mode, 'beatmap_id', True, 1, mod_filters, score_filters+user_filter, beatmap_filters, beatmapset_filters)
        leaderboard_spot.value = new_value
    leaderboard_spot.last_updated = datetime.datetime.now()
    session.commit()
    return new_value

if __name__ == "__main__":
    from database.ORM import ORM
    from database.util import parse_mod_filters
    orm = ORM()
    import asyncio
    session = orm.sessionmaker()

    asyncio.run(recalculate_user(session, 10651409, 1))