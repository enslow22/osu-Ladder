import datetime
import os.path
import queue
from models import RegisteredUser
from osuApi import get_most_played
import threading
from ORM import ORM
from userService import UserService
from scoreService import ScoreService
from sqlalchemy import select

UPDATE_INTERVAL_SECONDS = 28800

class TaskQueue:

    # The order of this list determines priority order from lowest to highest
    # Tasks queued with higher priority will always go before tasks with lower priority
    all_types = ['daily_fetch', 'initial_fetch']

    def __init__(self, sessionmaker):
        self.sessionmaker = sessionmaker
        self.q = queue.PriorityQueue()
        self.current = None

    def enqueue(self, task: tuple[str, dict]):
        # Verify task first
        task_type = task[0]
        data = task[1]

        if task_type not in self.all_types:
            return
        session = self.sessionmaker()

        if task_type == 'daily_fetch':
            import datetime
            today = datetime.datetime.now()
            user = session.get(RegisteredUser, data['user_id'])
            if user is None:
                print('User %s not registered' % data['user_id'])
                return
            if user.last_updated is None:
                print('Please do an initial fetch for %s first' % user.username)
                return
            time_diff = today - user.last_updated
            if time_diff.total_seconds() < UPDATE_INTERVAL_SECONDS:
                print('User %s does not need to be updated yet' % user.username)
                return
            if user in self.q.queue:
                print('%s is already in the queue!' % user.username)
                return
            print('Adding %s to the daily fetch queue' % user.username)
        elif task_type == 'initial_fetch':
            user = session.get(RegisteredUser, data['user_id'])
            if user is None:
                print('User %s not registered' % data['user_id'])
                return
            if user.last_updated is not None:
                print('User %s does not need to be fetched.' % user.username)
                return
            if user in self.q.queue:
                print('%s is already in the queue!' % user.username)
                return

            # If no modes were specified, just use the player's default mode
            if data['modes'] is None:
                data['modes'] = (user.playmode,)
            print('Adding %s to the fetch queue for %s' % (user.username, ', '.join(data['modes'])))
        session.close()
        import time
        self.q.put((self.all_types.index(task_type)+1, time.time(), task_type, data))
        if self.current is None:
            self.start()
        return

    def start(self):
        prio, time_enqueued, task_type, data = self.q.get()
        self.current = (task_type, data)
        t = threading.Thread(target=self.process)
        t.start()

    def process(self):
        # Based on the type of task in self.current, do something
        task_type = self.current[0]
        data = self.current[1]
        session = self.sessionmaker()

        if task_type == 'daily_fetch':
            user = session.get(RegisteredUser, data['user_id'])
            print('Starting daily_fetch for %s' % user.username)
            try:
                score_service = ScoreService(session)
                score_service.fetch_and_insert_daily_scores(data['user_id'])
                print('Finished fetching %s\'s daily scores.\n' % user.username)
                user.last_updated = datetime.datetime.now()
            except Exception as e:
                print(e)

        elif task_type == 'initial_fetch':
            user = session.get(RegisteredUser, data['user_id'])
            modes = data['modes']
            score_service = ScoreService(session)

            print('Starting initial_fetch for %s on %s' % (user.username, ', '.join(modes)))
            most_played = get_most_played(user.user_id)
            most_played = [{'beatmap_id': x.beatmap_id,
                            'beatmapset_id': x.beatmapset.id,
                            'status': x.beatmapset.status.value} for x in most_played]
            most_played = list(filter(lambda x: x['status'] in [1, 2, 4], most_played))
            num_maps = len(most_played)
            print('Beginning fetch for %s! They have %s maps in their most played.' % (user.username, str(len(most_played))))
            try:
                # For all maps, fetch the user's score on that map
                while len(most_played) > 0:
                    count = num_maps - len(most_played)
                    if count % 50 == 0:
                        print('Added %s maps for %s so far!' % (str(count), user.username))
                    beatmap = most_played.pop()
                    score_service.fetch_and_insert_score(beatmap['beatmap_id'], user.user_id, multiple=True, modes=modes)
                user.last_updated = datetime.datetime.now()
            except Exception as e:
                # Also add a flag to know if a user was kicked out in the middle of their initial fetch
                import pickle
                path = os.path.join(os.getcwd(), 'pickle')
                os.makedirs(path, exist_ok=True)
                with open('pickle/%s.pkl' % user.username, 'wb') as f:
                    pickle.dump(self.current, f)
                print(e)

        session.commit()
        self.current = None
        if not self.q.empty():
            self.start()

    def get_priority(self, task_type: str):
        return self.all_types.index(task_type)

    def daily_queue_all(self):
        from datetime import timedelta
        today = datetime.datetime.now()
        time_diff = today - timedelta(seconds=UPDATE_INTERVAL_SECONDS)
        session = self.sessionmaker()
        stmt = select(RegisteredUser).filter(RegisteredUser.last_updated < time_diff)
        all_users = session.scalars(stmt).all()
        for user in all_users:
            self.enqueue(('daily_fetch', {'user_id': user.user_id}))

if __name__ == '__main__':

    orm = ORM()
    tq = TaskQueue(orm.sessionmaker)
    us = UserService(orm.sessionmaker())
    tq.daily_queue_all()

    print(tq.q.queue)
    """
    score_service = ScoreService(orm.sessionmaker())
    fq = FetchQueue(orm.sessionmaker)
    dq = DailyQueue(orm.sessionmaker)
    dq.enqueue_all()

    test_data = [(20720260, ('mania',)),
                 (20651411, ('taiko',))]
    fq.enqueue( 20651412, ('osu',) )
    for d in test_data:
        fq.enqueue(*d)
    print(fq.q.queue)
    """
