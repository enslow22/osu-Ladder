from typing import List
from sqlalchemy import select, and_
from models import Score, RegisteredUser
from util import get_mode_table

class LeaderboardService:

    def __init__(self, session):
        self.session = session

    def group_leaderboard(self, users: List[int], beatmap_id: int, mode: str or int, filters: tuple | None, metric: str) -> List[Score]:
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
        lb = self.session.scalars(stmt).all()
        return lb

    def pp_history(self, users: List[int], mode: str or int) -> List[Score]:
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


if __name__ == '__main__':
    from ORM import ORM
    orm = ORM()
    leaderboard_service = LeaderboardService(orm.sessionmaker())
    from userService import UserService
    user_service = UserService(orm.sessionmaker())
    ids = user_service.get_ids_from_tag('OR')
    dataset = leaderboard_service.pp_history(ids, 'osu')


    import tabulate
    header = dataset[0].keys()
    rows = [x.values() for x in dataset]
    print(tabulate.tabulate(rows, header))

    """
    from util import parse_score_filters
    filterstr = 'date<2025-01-01, rank=A'
    filters = parse_score_filters('osu', filterstr)

    a = leaderboard_service.group_leaderboard(None, 1768177, 'osu', filters, 'pp')
    print(a)"""

