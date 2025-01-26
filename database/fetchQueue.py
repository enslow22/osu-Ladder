import datetime
import os.path
import queue
from .models import RegisteredUser
from .osuApiAuthService import OsuApiAuthService
import threading
import database.scoreService as scoreService
from sqlalchemy import select

# TODO rewrite basically all of this and learn how to use the background tasks functionality in fastapi
# TODO this function should use the authenticated user's access token and not my own. Then we can fetch multiple people at once

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
        user_queue = [x[3]['user_id'] for x in self.q.queue]
        bonus_priority = 0
        if task_type == 'daily_fetch':
            import datetime
            user = session.get(RegisteredUser, data['user_id'])
            session.close()
            if user is None:
                print('User %s not registered' % data['user_id'])
                return
            if user.last_updated is None:
                print('Please do an initial fetch for %s first' % user.username)
                return
            if user in self.q.queue:
                print('%s is already in the queue!' % user.username)
                return
            print('Adding %s to the daily fetch queue' % user.username)
        elif task_type == 'initial_fetch':
            user = session.get(RegisteredUser, data['user_id'])
            session.close()
            bonus_priority = 1 if data['catch_converts'] else 0
            if user is None:
                print('User %s not registered' % data['user_id'])
                return
            if user.last_updated is not None:
                print('User %s does not need to be fetched.' % user.username)
                return
            if self.current is not None:
                if self.current[1]['user_id'] == user.user_id:
                    print('%s is already in the queue!' % user.username)
                    return
            if user.user_id in user_queue:
                print('%s is already in the queue!' % user.username)
                return
            catch_string = ' Also fetching catch converts.' if data['catch_converts'] else ''
            print('Adding %s to the fetch queue.%s'% (user.username, catch_string))
        import time
        self.q.put((self.all_types.index(task_type)+1, time.time()+bonus_priority*3600, task_type, data))
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
                # TODO rewrite this
                #score_service = ScoreService(session)
                #score_service.fetch_and_insert_daily_scores(data['user_id'])
                print('Finished fetching %s\'s daily scores.\n' % user.username)
                user.last_updated = datetime.datetime.now()
            except Exception as e:
                print(e)
        elif task_type == 'initial_fetch':
            user = session.get(RegisteredUser, data['user_id'])
            catch_converts = data['catch_converts']
            catch_string = ' Also fetching catch converts.' if catch_converts else ''
            modes = ('osu', 'fruits') if catch_converts else ('osu',)

            print('Starting initial_fetch for %s' % user.username)

            # TODO: Check that access token is not expired

            auth_osu_api = OsuApiAuthService(user.user_id, user.access_token)

            most_played = auth_osu_api.get_all_played_maps()
            most_played = [{'beatmap_id': x.beatmap_id,
                            'beatmapset_id': x.beatmapset.id,
                            'status': x.beatmapset.status.value} for x in most_played]
            most_played = list(filter(lambda x: x['status'] in [1, 2, 4], most_played))
            num_maps = len(most_played)
            print('Beginning fetch for %s!%s They have %s maps in their most played.' % (user.username, catch_string, str(len(most_played))))

            try:
                # For all maps, fetch the user's score on that map
                while len(most_played) > 0:
                    count = num_maps - len(most_played)
                    if count % 50 == 0:
                        print('Added %s maps for %s so far!' % (str(count), user.username))
                    beatmap = most_played.pop()
                    for mode in modes:
                        new_scores = auth_osu_api.get_user_scores_on_map(beatmap['beatmap_id'], mode=mode)
                        scoreService.insert_scores(self.sessionmaker(), new_scores)
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

    def daily_queue_all(self, force: bool = False):
        from datetime import timedelta
        today = datetime.datetime.now()
        time_diff = today - timedelta(seconds=UPDATE_INTERVAL_SECONDS)
        session = self.sessionmaker()
        stmt = select(RegisteredUser)
        if not force:
            stmt = stmt.filter(RegisteredUser.last_updated < time_diff)
        all_users = session.scalars(stmt).all()
        session.close()
        for user in all_users:
            self.enqueue(('daily_fetch', {'user_id': user.user_id}))

if __name__ == '__main__':
    pass
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
