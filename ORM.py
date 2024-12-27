import datetime
import os
from sqlalchemy import create_engine, select
from dotenv import load_dotenv
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Session
from models import RegisteredUser, UserStats, OsuScore, TaikoScore, CatchScore, ManiaScore, RegisteredUserTag
from osuApi import osu_api, get_user_info, get_user_scores_on_map, get_user_recent_scores, get_most_played
from ossapi import User
import pickle

class ORM:

    def __init__(self):
        load_dotenv()
        user = os.getenv('DB_USER')
        password = os.getenv('DB_PASS')
        host = os.getenv('DB_HOST')
        port = os.getenv('db_port')
        dbname = os.getenv('DB_NAME')
        connection_string = "mysql+mysqldb://%s:%s@%s:%s/%s" % (user, password, host, port, dbname)
        engine = create_engine(connection_string, echo=False)
        self.session = Session(engine)

    #
    # USER FUNCTIONS
    #

    # Adds a user's id and username to the registered players table
    def add_new_registered_users(self, user_ids):
        if isinstance(user_ids, int):
            user_ids = [user_ids]
        user_objs = []
        # Check if users are in the database already
        stmt = select(RegisteredUser).where(RegisteredUser.user_id.in_(user_ids))
        a = self.session.scalars(stmt).first()
        if a:
            print('Erm someone is already here')
            return
        for user_id in user_ids:
            user_info = get_user_info(user_id)
            user_objs.append(RegisteredUser(user_id = user_id, username=user_info.username))
            # We don't merge here because these should be new users.
        self.session.add_all(user_objs)
        self.session.commit()

    # Takes a list of users and give them all a tag
    def assign_tags_to_users(self, user_ids, tag):
        if isinstance(user_ids, int):
            user_ids = [user_ids]
        # Fetch all matching users from registered_users (We do this to prevent user ids existing when not registered)
        # For each of them, create a new record in registered_user_tags: (user_id, tag)
        stmt = select(RegisteredUser).where(RegisteredUser.user_id.in_(user_ids))
        for user in self.session.scalars(stmt):
            self.session.merge(RegisteredUserTag(user_id = user.user_id, tag = tag))
        self.session.commit()

    def add_users_to_oregon(self, user_ids):
        self.add_users_with_tag(user_ids, 'OR')

    def get_all_oregon_players(self):
        stmt = select(RegisteredUser).where(RegisteredUserTag.tag.in_(['OR']))
        users = []
        for user in self.session.scalars(stmt):
            users.append(user)
        return users

    # Given a user id, update their stats in the database
    # If they are not currently in the database, add them to the database
    def update_players_stats(self, user_ids):
        if isinstance(user_ids, int):
            user_ids = [user_ids]

        stmt = select(UserStats).where(UserStats.user_id.in_(user_ids))
        all_users = self.session.scalars(stmt)

        for user in all_users:
            user_info = get_user_info(user.user_id)
            user.set_details(user_info)
            self.session.commit()
            user_ids.remove(user.user_id)

        # Users who are not already in the database will be left over.
        # We can insert them here
        for user_id in user_ids:
            user_info = get_user_info(user_id)
            new_user = UserStats(user_id)
            new_user.set_details(user_info)
            self.session.add(new_user)
            self.session.commit()

    #
    # SCORE FUNCTIONS
    #

    # Insert a list of scores into the database
    # Returns true if successful
    def insert_scores(self, scores):
        if not scores:
            return False
        try:
            for score in scores:
                # Check the ruleset first
                match score.ruleset_id:
                    case 0:
                        new_score = OsuScore()
                    case 1:
                        new_score = TaikoScore()
                    case 2:
                        new_score = CatchScore()
                    case 3:
                        new_score = ManiaScore()
                new_score.set_details(score)
                self.session.merge(new_score)
            #print('Added %s score(s) for %s' % (str(len(scores)), str(scores[0].beatmap_id)))
            self.session.commit()
            return True
        except Exception as e:
            print(e)
            for score in scores:
                print(str(score))
            return False

    # Given a user and beatmap id, insert that user's highest score into the database
    def fetch_and_insert_score(self, beatmap_id, user_id, multiple = True):
        score_infos = get_user_scores_on_map(beatmap_id, user_id, multiple)
        return self.insert_scores(score_infos)

    def fetch_and_insert_daily_scores(self, user_id):
        scores = get_user_recent_scores(user_id)
        if len(scores) == 0:
            return None, None
        return len(scores), self.insert_scores(scores)

    def daily_update_all(self):
        #TODO Only update those who are more than 24 hrs without an update
        today = datetime.datetime.now()
        statement = select(RegisteredUser)
        all_users = self.session.scalars(statement).all()

        summary = []

        for user in all_users:
            print('Updating %s' % user.user_id)
            num_scores, res = self.fetch_and_insert_daily_scores(user.user_id)
            if num_scores is None:
                continue
            elif not res:
                summary.append((user.user_id, 'Issue'))
            else:
                summary.append((user.user_id, num_scores))
        return summary

    def initial_fetch_all(self):
        statement = select(RegisteredUser).where(RegisteredUser.last_updated is None)
        all_users = self.session.scalars(statement).all()
        for user in all_users:
            if user.last_updated is not None:
                continue
            self.initial_fetch_user(user.user_id)
            user.last_updated = datetime.datetime.now()
            self.session.merge(user)
            self.session.commit()
        pass

    def initial_fetch_user(self, user_id, from_pickle = False):
        user_info = get_user_info(user_id)
        username = user_info.username
        print('Adding %s to the database. Fetching their scores' % username)
        if not from_pickle:
            most_played = get_most_played(user_id)
            most_played = [{'beatmap_id': x.beatmap_id,
                            'beatmapset_id': x.beatmapset.id,
                            'status': x.beatmapset.status.value} for x in most_played]
            most_played = list(filter(lambda x: x['status'] in [1, 2, 4], most_played))
        else:
            pklfile = open('pkl/%s.pkl' % username, 'rb')
            most_played = pickle.load(pklfile)
            pklfile.close()
        try:
            count = 0
            while len(most_played) > 0:
                beatmap = most_played.pop()
                if beatmap['status'] not in [1, 2, 4]:
                    continue
                self.fetch_and_insert_score(beatmap['beatmap_id'], user_id, multiple=True)
                count += 1
                if count % 100 == 0:
                    print('Added %s maps for %s so far!' % (count, username))
        except Exception as e:
            print('uh oh')
            print(e)
        finally:
            pklfile = open('pkl/%s.pkl' % username, 'wb')
            pickle.dump(most_played, pklfile)
            pklfile.close()

if __name__ == '__main__':
    orm = ORM()
    orm.initial_fetch_all()