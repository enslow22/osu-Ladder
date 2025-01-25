from database.userService import UserService
from .util import get_mode_table
from .osuApi import get_user_scores_on_map, get_user_recent_scores
from ossapi.models import Score
from typing import List
from sqlalchemy import select, and_

class ScoreService:

    def __init__(self, session):
        self.session = session

    def insert_scores(self, scores: List[Score]):
        if not scores:
            return False
        try:
            for score in scores:
                new_score = get_mode_table(score.ruleset_id)()
                new_score.set_details(score)
                self.session.merge(new_score)
            self.session.commit()
            return True
        except Exception as e:
            print(e)
            for score in scores:
                print(str(score))
            return False

    # Given a user and beatmap id, insert that user's highest score into the database
    def fetch_and_insert_score(self, beatmap_id: int, user_id: int, multiple: bool = True, modes: tuple[...] = (), default_mode: str = None):
        # If converts are specified, get them as well
        # Check for allowed values

        score_infos = []

        # See if the beatmap default was specified.
        # If not, just fetch for all specified modes
        # If so, fetch the default mode first. If the default mode was not osu, then there are converts, and you can
        # safely continue. However, if the default mode was osu, we need to check for converts.
        if default_mode is None:
            for mode in modes:
                score_infos += get_user_scores_on_map(beatmap_id, user_id, multiple, mode=mode)
        else:
            score_infos += get_user_scores_on_map(beatmap_id, user_id, multiple)
            if default_mode == 'osu':
                for mode in modes:
                    if mode == 'osu':
                        continue
                    score_infos += get_user_scores_on_map(beatmap_id, user_id, multiple, mode=mode)

        return self.insert_scores(score_infos)

    def get_user_scores(self, beatmap_id: int, user_id: int, mode: str or int, filters: tuple, metric: str):
        table = get_mode_table(mode)
        stmt = select(table).filter(
            and_(
                getattr(table, 'beatmap_id') == beatmap_id,
                getattr(table, 'user_id') == user_id
            )
        ).filter(*filters).order_by(getattr(table, metric).desc())
        return self.session.scalars(stmt).all()

    def fetch_and_insert_daily_scores(self, user_id):
        scores = get_user_recent_scores(user_id)
        if len(scores) == 0:
            return True
        return self.insert_scores(scores)

if __name__ ==  '__main__':
    from ORM import ORM
    orm = ORM()
    score_service = ScoreService(orm.sessionmaker())
    #score_service.fetch_and_insert_score(4849275, 10651409, multiple=True, modes=('fruits', 'mania', 'taiko'))
    user_service = UserService(orm.sessionmaker())
    user = user_service.get_user(10651409)
    setattr(user, 'track_%s' % 'fruits', True)