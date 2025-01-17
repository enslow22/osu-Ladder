import datetime
import os.path
import queue
import types
from datetime import timedelta
from models import RegisteredUser
from osuApi import get_most_played
import threading
from ORM import ORM
from userService import UserService
from scoreService import ScoreService
from sqlalchemy import select, update

UPDATE_INTERVAL_SECONDS = 28800

# TODO: Merge queues together so that all items are in teh same queue.
# TODO: Different tasks have different priority as well.

# You can add people to the queue whenever, but it can only fetch one at a time
class FetchQueue:

    def __init__(self, sessionmaker: types.FunctionType):
        self.q = queue.Queue()
        self.sessionmaker = sessionmaker
        self.user_service = UserService(sessionmaker())
        self.score_service = ScoreService(sessionmaker())
        self.current = None

    def enqueue(self, user_id: int, modes: tuple[str, ...]):
        # Check if user exists and needs to be updated
        user = self.user_service.get_user(user_id)
        if user is None:
            print('%s is not a registered user' % str(user_id))
            return
        if user.last_updated is not None:
            print('%s not added to queue. They do not need to be fetched.' % str(user_id))
            return
        if user in self.q.queue:
            print('%s is already in the queue!' % str(user_id))
            return
        print('Adding %s to the fetch queue for %s' % (user.username, ', '.join(modes)))

        # If no modes were specified, just use the player's default mode
        if modes is None:
            modes = (user.playmode,)

        self.q.put((user_id, modes))
        if self.current is None:
            self.start()

    # This needs to be in its own thread
    def process(self):
        user_id = self.current['user_id']
        username = self.current['username']
        most_played = self.current['maps']
        modes = self.current['modes']

        print('Beginning fetch for %s! They have %s maps in their most played.' % (username, str(len(most_played))))
        try:
            # For all maps, fetch the user's score on that map
            while len(self.current['maps']) > 0:
                count = self.current['num_maps'] - len(self.current['maps'])
                if count % 50 == 0:
                    print('Added %s maps for %s so far!' % (str(count), username), flush=True)
                beatmap = self.current['maps'].pop()
                beatmap_id = beatmap['beatmap_id']
                self.score_service.fetch_and_insert_score(beatmap_id, user_id, multiple=True, modes=modes)
        except Exception as e:
            # Also add a flag to know if a user was kicked out in the middle of their initial fetch
            import pickle
            path = os.path.join(os.getcwd(), 'pickle')
            os.makedirs(path, exist_ok=True)
            with open('pickle/%s.pkl' % username, 'wb') as f:
                pickle.dump(self.current, f)
            print(e)
        finally:
            print('Done with %s' % username)
            self.current = None
            if not self.q.empty():
                self.start()

    def start(self):
        user_id, modes = self.q.get()
        local_user_service = UserService(self.sessionmaker())
        if user_id is None:
            return
        print('Currently grabbing: %s' % str(user_id), flush=True)
        userinfo = local_user_service.get_user(user_id)

        most_played = get_most_played(user_id)
        # Organize all played maps
        most_played = [{'beatmap_id': x.beatmap_id,
                        'beatmapset_id': x.beatmapset.id,
                        'status': x.beatmapset.status.value} for x in most_played]
        most_played = list(filter(lambda x: x['status'] in [1, 2, 4], most_played))
        self.current = {'user_id': user_id, 'username': userinfo.username, 'maps': most_played,
                        'num_maps': len(most_played),
                        'modes': modes}
        t = threading.Thread(target=self.process)
        t.start()

class DailyQueue:

    def __init__(self, sessionmaker: types.FunctionType):
        self.q = queue.Queue()
        self.sessionmaker = sessionmaker
        self.session = sessionmaker()
        self.user_service = UserService(sessionmaker())
        self.score_service = ScoreService(sessionmaker())
        self.current = None

    def enqueue(self, user: RegisteredUser):
        import datetime

        today = datetime.datetime.now()
        time_diff = today - user.last_updated
        if time_diff.total_seconds() < UPDATE_INTERVAL_SECONDS:
            print('User does not need to be updated yet')
            return
        self.q.put(user)

        if self.current is None:
            self.start()

    def process(self):
        try:
            self.score_service.fetch_and_insert_daily_scores(self.current.user_id)
        except Exception as e:
            print(e)
        finally:
            print('Done with %s' % self.current.username)
            self.current.last_updated = datetime.datetime.now()
            self.user_service.session.commit()
            self.current = None
            if not self.q.empty():
                self.start()

    def start(self):
        user = self.q.get()
        self.current = user
        t = threading.Thread(target=self.process)
        t.start()

    def enqueue_all(self):
        today = datetime.datetime.now()
        time_diff = today - timedelta(seconds=UPDATE_INTERVAL_SECONDS)
        session = self.sessionmaker()
        stmt = select(RegisteredUser).filter(RegisteredUser.last_updated < time_diff)
        all_users = session.scalars(stmt).all()
        for user in all_users:
            self.enqueue(user)

if __name__ == '__main__':
    orm = ORM()
    score_service = ScoreService(orm.sessionmaker())
    fq = FetchQueue(orm.sessionmaker)
    dq = DailyQueue(orm.sessionmaker)
    dq.enqueue_all()

    """
    test_data = [(20720260, ('mania',)),
                 (20651411, ('taiko',))]
    fq.enqueue( 20651412, ('osu',) )
    for d in test_data:
        fq.enqueue(*d)
    print(fq.q.queue)
    """
