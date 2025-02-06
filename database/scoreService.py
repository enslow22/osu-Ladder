from collections.abc import Sequence
from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session
import database.util
from models import Score
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

def get_scores(session: Session, mode: str or int, filters: tuple = (), mod_filters: tuple = (), metric: str = 'lazer_score', desc: bool = True, limit=50):
    """
    Returns a list of scores with the given filters, regardless of beatmap or user.
    """
    table = get_mode_table(mode)
    sort_order = getattr(table, metric)
    if desc:
        sort_order = sort_order.desc()
    stmt = select(table).filter(*filters).filter(*mod_filters).order_by(sort_order).limit(limit)
    return session.scalars(stmt).all()

def get_total_scores(session: Session, mode: str or int, filters: tuple = (), mods: tuple = ()) -> int:
    """
    Returns the total number of scores with the listed filters
    """
    tbl = get_mode_table(mode)
    stmt = select(func.count(getattr(tbl, 'score_id'))).filter(*filters).filter(*mods)

    return session.scalars(stmt).one()

if __name__ == '__main__':

    from ORM import ORM
    orm = ORM()
    filters = database.util.parse_mod_filters('osu', '!HRDTHDCL')
    other_filters = database.util.parse_score_filters('osu', 'date<2024-01-01')
    print(get_total_scores(orm.sessionmaker(), mode=0, filters=other_filters, mods=filters))