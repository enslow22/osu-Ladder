"""
Methods in this service access the database about specific users.
Get methods return a resource
Post and registration methods return True or False depending on if the operation was successful
"""

from typing import List
from util import get_mode_table
import osuApi
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from models import RegisteredUser, RegisteredUserTag, Score, OsuScore


class UserService:

    def __init__(self, session):
        self.session = session

    def get_user(self, user_id: int) -> RegisteredUser or None:
        """
        Get a user

        :param user_id: a user_id
        :return: a RegisteredUser object
        """
        try:
            stmt = select(RegisteredUser).filter(RegisteredUser.user_id == user_id)
            user = self.session.scalars(stmt).one()
            return user
        except Exception as e:
            return None

    def register_user(self, user_id: int):
        """
        Register a new user

        :param user_id: a user_id
        :return: True for success, False for failure
        """
        a = self.get_user(user_id)
        if a is not None:
            print('%s, user id: %s already exists in the database' % (a.username, str(a.user_id)))
            return False
        user_info = osuApi.get_user_info(user_id)
        new_user = RegisteredUser(user_info)
        self.session.add(new_user)
        self.session.commit()
        return True

    def update_user_metadata(self, user_id: int):
        """
        Update a user's metadata

        :param user_id: a user id
        :return: True for success, False for failure
        """
        user = self.get_user(user_id)
        if user is None:
            print('User not found')
            return False
        user_info = osuApi.get_user_info(user_id)
        user.set_all(user_info)
        self.session.commit()
        return True

    def add_tags(self, user_ids: List[int], tag:str):
        """
        Assign a tag to a list of users

        :param user_ids: a list of user ids, can also be a single user id as an int
        :param tag: the tag to assign to all supplied users
        :return: True for success, False for failure
        """
        if isinstance(user_ids, int):
            user_ids = [user_ids]

        registered_profiles = self.session.query(RegisteredUser).filter(RegisteredUser.user_id.in_(user_ids)).all()
        registered_ids = [user.user_id for user in registered_profiles]

        not_registered = list(set(user_ids) - set(registered_ids))

        if len(not_registered) > 0:
            print('The user_ids: [%s] are not registered' % ', '.join(str(x) for x in not_registered))
            print('No action taken')
            return False

        new_tags = []
        try:
            for user_id in user_ids:
                new_tags.append(RegisteredUserTag(user_id=user_id, tag=tag))
            self.session.add_all(new_tags)
            self.session.commit()
            return True
        except IntegrityError as e:
            print(e.orig)
            print('No action taken')
            return False

    def get_top_n(self, user_id: int, mode: str or int, filters: tuple, metric: str = 'pp', number: int = 100) -> List[Score]:
        """
        Runs (SELECT * FROM (table) WHERE user_id = user_id AND (filters) LIMIT (n) ORDER BY (metric) DESC)

        :param user_id: a user id
        :param mode:    integer representation of a game mode
        :param filters: a tuple of filters
        :param metric:  a column to order by
        :param number:  the number of scores to return
        :return:        The top n scores matching the provided filters for the specified player
        """
        if not isinstance(filters, tuple):
            filters = tuple(filters)
        table = get_mode_table(mode)
        stmt = select(table).filter(getattr(table, 'user_id') == user_id).filter(*filters).limit(number).order_by(getattr(table, metric).desc())
        res = self.session.scalars(stmt).all()

        return res

    def get_ids_from_tag(self, group: str or List[int]) -> List[int] or None:
        # List of user_ids
        if isinstance(group, list):
            return group
        stmt = select(RegisteredUserTag.user_id)
        if isinstance(group, str):
            stmt = stmt.filter(RegisteredUserTag.tag == group)
        return self.session.scalars(stmt).all()

    @staticmethod
    def get_profile_pp(scores: List[Score], bonus = True, n = 100) -> int:
        """
        Returns profile pp with only that list of scores considered
        :param n:       number of scores to truncate to (ignored if n > len(scores))
        :param bonus:   include max bonus pp or not
        :param scores:  A list of score objects
        :return:        Profile pp
        """

        total = 416.666666 if bonus else 0
        scores = scores if n > len(scores) else scores[:n]
        for i, score in enumerate(scores):
            total += score.pp * 0.95**(i-1)
        return total


if __name__ == '__main__':
    from ORM import ORM
    orm = ORM()
    user_service = UserService(orm.sessionmaker())
    a = user_service.session.scalars(select(RegisteredUser)).all()


    """
    c = user_service.get_user(10651409)
    d = user_service.get_ids_from_tag('OR')
    e = user_service.get_ids_from_tag(None)
    #user_service.add_tags([10651409, 4830687], 'aaaaaaaaa')
    a = user_service.get_top_n(10651409, 0, ( OsuScore.rank.in_(['B', 'C', 'D']) ,), 'pp', 100)
    b = user_service.get_top_n(20085097, 0, (OsuScore.rank.in_(['B', 'C', 'D']),), 'pp', 100)
    print(user_service.get_profile_pp(a))
    print(user_service.get_profile_pp(b))"""
