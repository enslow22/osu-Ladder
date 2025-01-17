from typing import List
from sqlalchemy import select, and_
from models import Score, RegisteredUserTag
from util import get_mode_table

class LeaderboardService:

    def __init__(self, session):
        self.session = session

    def group_leaderboard(self, users: List[int], beatmap_id: int, mode: str, filters: tuple | None, metric: str) -> List[Score]:
        """
        :param users:       The tag. If None, include all users
        :param beatmap_id:  The id of the map to generate the leaderboard
        :param mode:        The mode of the leaderboard
        :param filters:     Any additional filters
        :param metric:      The column to order by
        :return:            A list of scores in
        """
        all_user_ids = users
        table = get_mode_table(mode)
        stmt = select(table).filter(
            and_(
                getattr(table, 'beatmap_id') == beatmap_id,
                getattr(table, 'user_id').in_(all_user_ids)
            )
        ).filter(*filters).order_by(getattr(table, metric).desc())
        lb = self.session.scalars(stmt).all()
        return lb


if __name__ == '__main__':
    from ORM import ORM
    orm = ORM()
    leaderboard_service = LeaderboardService(orm.sessionmaker())

    from util import parse_score_filters
    filterstr = 'date<2025-01-01, rank=A'
    filters = parse_score_filters('osu', filterstr)

    a = leaderboard_service.group_leaderboard(None, 1768177, 'osu', filters, 'pp')
    print(a)