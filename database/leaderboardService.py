from sqlalchemy import select, and_, func, Date
from sqlalchemy.orm import Session
from database.util import get_mode_table
from typing import List, Any
from ossapi import Score
from database.models import RegisteredUser

def get_beatmap_leaderboard(session: Session, users: List[int], beatmap_id: int, mode: str or int, filters: tuple = (), mods: tuple = (), metric: str = 'lazer_score', unique: bool = True) -> List[Score]:
    """
    Given a beatmap, fetch the beatmap leaderboard. Can also supply a group of users.
    """
    if not isinstance(filters, tuple):
        filters = tuple(filters)
    if not isinstance(mods, tuple):
        mods = tuple(mods)

    table = get_mode_table(mode)
    stmt = select(table).filter(
        and_(
            getattr(table, 'beatmap_id') == beatmap_id,
            getattr(table, 'user_id').in_(users)
        )
    ).filter(*filters).filter(*mods).order_by(getattr(table, metric).desc())
    lb = list(session.scalars(stmt).all())

    if unique:
        # Go through and check that there's only one score per user
        users_found = []
        for i, score in enumerate(lb):
            if score.user_id in users_found:
                lb[i] = None
                continue
            users_found.append(score.user_id)
    return [x for x in lb if x is not None]

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

def top_play_per_day(session: Session, user_id: int, mode: str or int, filters: tuple = (), mods: tuple = (), minimal: bool = True):
    """
    Given a user, fetch their highest pp play for each day.
    """
    if not isinstance(filters, tuple):
        filters = tuple(filters)
    if not isinstance(mods, tuple):
        mods = tuple(mods)

    table = get_mode_table(mode)

    # I think this method messes up very slightly, but only if a person sets the exact same play on the exact same day.
    stmt = (select(getattr(table, 'date').cast(Date).label('date'), func.max(getattr(table, 'pp')).label('max_pp'))
            .filter(getattr(table, 'user_id') == user_id).filter(getattr(table, 'pp').isnot(None))
            .filter(*filters).filter(*mods)
            .group_by(getattr(table, 'date').cast(Date))
            .order_by(getattr(table, 'date').cast(Date)))

    if not minimal:
        subq = stmt.subquery()
        stmt = select(table).join(subq, (getattr(table, 'pp') == subq.c.max_pp) & (getattr(table, 'date').cast(Date) == subq.c.date) ).filter(getattr(table, 'user_id') == user_id).filter(*filters).filter(*mods).order_by(getattr(table, 'date'))
        return [a[0] for a in session.execute(stmt)]
    return [a._mapping for a in session.execute(stmt).all()]

if __name__ == "__main__":
    from database.ORM import ORM
    from database.util import parse_mod_filters
    orm = ORM()
    mods1 = parse_mod_filters(0, '+HDDTHR')
    b = top_play_per_day(orm.sessionmaker(), 20085097, 0, mods=mods1, minimal=True)
    print(b[0]._mapping)