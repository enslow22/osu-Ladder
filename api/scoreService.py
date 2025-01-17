from util import get_mode_table
from ossapi.models import Score
from osuApi import get_user_scores_on_map, get_user_recent_scores
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
    def fetch_and_insert_score(self, beatmap_id: int, user_id: int, multiple: bool = True, modes: tuple[...] = ()):
        # If converts are specified, get them as well
        # Check for allowed values

        score_infos = []

        # If the default map is standard, there will be converts.
        # Otherwise, there will be no converts
        # If score_infos is [], then that means the user did not have a score on the default difficulty.
        # They might have a score on a convert, so we need to check the converts.
        # so if score_infos is empty or if it contains standard plays, we need to check for other modes
        for mode in modes:
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
    score_service.fetch_and_insert_score(4849275, 10651409, multiple=True, modes=('fruits', 'mania', 'taiko'))