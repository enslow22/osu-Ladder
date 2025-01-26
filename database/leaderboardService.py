from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from .util import get_mode_table
from typing import List, Any
from ossapi import Score
from models import RegisteredUser


def group_leaderboard(session: Session, users: List[int], beatmap_id: int, mode: str or int, filters: tuple | None, metric: str) -> List[Score]:
    """
    :param users:       The tag. If None, include all users
    :param beatmap_id:  The id of the map to generate the leaderboard
    :param mode:        The mode of the leaderboard
    :param filters:     Any additional filters
    :param metric:      The column to order by
    :return:            A list of scores in
    """
    table = get_mode_table(mode)
    stmt = select(table).filter(
        and_(
            getattr(table, 'beatmap_id') == beatmap_id,
            getattr(table, 'user_id').in_(users)
        )
    ).filter(*filters).order_by(getattr(table, metric).desc())
    lb = session.scalars(stmt).all()

    # TODO Address this
    return lb

def pp_history(self, users: List[int], mode: str or int) -> list[dict[str, Any]]:
    """

    :param users:   List of users to calculate the pp history
    :param mode:    The mode
    :return:        A list of scores
    """
    table = get_mode_table(mode)
    # For one hundred players, this loads about 100mb worth of data into memory
    stmt = select(table.date, table.pp, table.score_id).filter(
        and_(
            getattr(table, 'pp').is_not(None),
            getattr(table, 'user_id').in_(users)
        )
    ).order_by(getattr(table, 'date'))

    scores = self.session.execute(stmt).all()

    pp_record = 0
    pp_records = []
    for score in scores:
        if score[1] >= pp_record:
            pp_records.append(score[2])
            pp_record = score[1]

    stmt = select(table, RegisteredUser).join_from(table, RegisteredUser, RegisteredUser.user_id == table.user_id).filter(table.score_id.in_(pp_records))

    pp_history = []
    for row in self.session.execute(stmt):
        pp_history.append({
            'username': row[1].username,
            'score': row[0].to_dict()
        })
    return pp_history