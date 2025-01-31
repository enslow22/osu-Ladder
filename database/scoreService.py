from collections.abc import Sequence
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
import database.models
from util import get_mode_table
from typing import List
from ossapi import Score

def insert_scores(session: Session, scores: List[Score]) -> bool:
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

def get_user_scores(session: Session, beatmap_id: int, user_id: int, mode: str or int, filters: tuple, metric: str) -> Sequence[database.models.Score]:
    table = get_mode_table(mode)
    stmt = select(table).filter(
        and_(
            getattr(table, 'beatmap_id') == beatmap_id,
            getattr(table, 'user_id') == user_id
        )
    ).filter(*filters).order_by(getattr(table, metric).desc())
    return session.scalars(stmt).all()