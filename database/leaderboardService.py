from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from database.util import get_mode_table, parse_score_filters
from typing import List, Any
from ossapi import Score
from database.models import RegisteredUser



def group_leaderboard(session: Session, users: List[int], beatmap_id: int, mode: str or int, filters: tuple, metric: str, unique: bool = True) -> List[Score]:
    """
    :param users:       The tag. If None, include all users
    :param beatmap_id:  The id of the map to generate the leaderboard
    :param mode:        The mode of the leaderboard
    :param filters:     Any additional filters
    :param metric:      The column to order by
    :param unique:      One score per user?
    :return:            A list of scores in
    """
    if not isinstance(filters, tuple):
        filters = tuple(filters)
    table = get_mode_table(mode)
    stmt = select(table).filter(
        and_(
            getattr(table, 'beatmap_id') == beatmap_id,
            getattr(table, 'user_id').in_(users)
        )
    ).filter(*filters).order_by(getattr(table, metric).desc())
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
def pp_history(session: Session, users: List[int], mode: str or int) -> list[dict[str, Any]]:
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