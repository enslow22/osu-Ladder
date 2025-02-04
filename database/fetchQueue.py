import multiprocessing.pool
import time
import datetime
import queue
from database.userService import refresh_tokens, register_user
from database.osuApiAuthService import OsuApiAuthService
from database.scoreService import insert_scores
from database.ORM import ORM
import os
import dotenv

import sqlalchemy.orm

from database.models import RegisteredUser


# A task in this context looks like
# (time_set: int, RegisteredUser: user, catch_converts: bool)

dotenv.load_dotenv('../database/.env')
NUM_THREADS = int(os.getenv('NUM_THREADS'))


class TaskQueue:

    def __init__(self, sessionmaker: sqlalchemy.orm.sessionmaker):
        self.sessionmaker = sessionmaker
        self.q = queue.PriorityQueue()
        self.pool = multiprocessing.pool.ThreadPool(processes=NUM_THREADS)
        self.current = []
        # {'user_id': user.user_id,
        #   'username': user.username,
        #   'catch_converts': catch_converts,
        #   'num_maps': num_maps,}

    def enqueue(self, user_id: int, catch_converts: bool) -> bool:
        session = self.sessionmaker()
        user = session.get(RegisteredUser, user_id)
        session.close()

        user_queue = [x[1].user_id for x in self.q.queue]
        bonus_priority = 1 if catch_converts else 0

        if user is None:
            return False
        if user.last_updated is not None:
            return False
        if user.access_token is None or user.refresh_token is None or user.expires_at is None:
            return False
        for tasks in self.current:
            if tasks['user_id'] == user.user_id:
                return False
        if user.user_id in user_queue:
            return False
        catch_string = ' Also fetching catch converts.' if catch_converts else ''
        print('Adding %s to the fetch queue.%s' % (user.username, catch_string))
        self.q.put((time.time()+bonus_priority*43200, user, catch_converts))
        if len(self.current) < NUM_THREADS and not self.q.empty():
            self.start()
        return True

    def start(self):
        time_set, user, catch_converts = self.q.get()
        self.current.append({'user_id': user.user_id,
                             'username': user.username,
                             'catch_converts': catch_converts,
                             'num_maps': float('nan')})
        self.pool.apply_async(self.process, args=(user, catch_converts))
        #self.pool.apply_async(self.test, args=(user, catch_converts))
        if len(self.current) < NUM_THREADS and not self.q.empty():
            self.start()

    def process(self, user: RegisteredUser, catch_converts: bool):
        for task in self.current:
            if task['user_id'] == user.user_id:
                task['num_maps'] = 'Calculating'

        auth_osu_api = OsuApiAuthService(user.user_id, user.access_token)

        catch_string = ' Also fetching catch converts.' if catch_converts else ''
        print('Starting initial_fetch for %s.%s' % (user.username, catch_string))

        session = self.sessionmaker()
        if user.expires_at < datetime.datetime.now():
            refresh_tokens(session, user)

        print('%s accessed the osu api' % user.username)

        most_played = auth_osu_api.get_all_played_maps()
        most_played = [{'beatmap_id': x.beatmap_id,
                        'beatmapset_id': x.beatmapset.id,
                        'mode': x._beatmap.mode.value,
                        'status': x.beatmapset.status.value} for x in most_played]
        most_played = list(filter(lambda x: x['status'] in [1, 2, 4], most_played))

        for task in self.current:
            if task['user_id'] == user.user_id:
                task['num_maps'] = len(most_played)


        print('Beginning fetch for %s!%s They have %s maps in their most played.' % (
        user.username, catch_string, str(len(most_played))))
        try:

            # For all maps, fetch the user's score on that map
            while len(most_played) > 0:
                beatmap = most_played.pop()

                # Get the default mode score first
                new_scores = auth_osu_api.get_user_scores_on_map(beatmap['beatmap_id'])

                # If the map has converts and the user wants converts, then get those as well.
                if catch_converts and beatmap['mode'] == 'osu':
                    new_scores += auth_osu_api.get_user_scores_on_map(beatmap['beatmap_id'], mode='fruits')
                insert_scores(self.sessionmaker(), new_scores)
                for task in self.current:
                    if task['user_id'] == user.user_id:
                        task['num_maps'] = len(most_played)

            user.last_updated = datetime.datetime.now()
            for task in self.current:
                if task['user_id'] == user.user_id:
                    self.current.remove(task)
            self.start()
        except Exception as e:
            # Also add a flag to know if a user was kicked out in the middle of their initial fetch
            import pickle
            import os
            path = os.path.join(os.getcwd(), 'pickle')
            os.makedirs(path, exist_ok=True)
            with open('pickle/%s.pkl' % user.username, 'wb') as f:
                pickle.dump(self.current, f)
            print(e)

if __name__ == '__main__':
    orm = ORM()
    tq = TaskQueue(orm.sessionmaker)
    session = orm.sessionmaker()

    tq.enqueue(4991273, False)
    tq.enqueue(10651409, False)
    #tq.enqueue(3634152, False)

    while True:
        print(tq.current)
        print(tq.q.queue)
        print('\n')
        time.sleep(5)