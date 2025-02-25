import multiprocessing.pool
import time
import datetime
import queue
from database.userService import refresh_tokens
from database.osuApiAuthService import OsuApiAuthService
from database.scoreService import insert_scores
from database.ORM import ORM
import os
import dotenv
from database.models import RegisteredUser

dotenv.load_dotenv('../database/.env')
NUM_THREADS = int(os.getenv('NUM_THREADS'))

class TaskQueue:

    def __init__(self, sessionmaker, bypass_user_auth=False):
        self.sessionmaker = sessionmaker
        self.q = queue.PriorityQueue()
        self.pool = multiprocessing.pool.ThreadPool(processes=NUM_THREADS)
        self.bypass_user_auth = bypass_user_auth
        self.current = []
        # {'user_id': user.user_id,
        #   'username': user.username,
        #   'catch_converts': catch_converts,
        #   'num_maps': num_maps,}

    def enqueue(self, user_id: int, get_non_converts: bool, get_converts: bool):
        """
        Add them to the queue
        1. Get user info from db
        2. Assign bonus priority if fetching catch converts
        3. Add them to the queue and start the worker.
        """
        try:
            session = self.sessionmaker()
            user = session.get(RegisteredUser, user_id)
            bonus_priority = get_converts and get_non_converts
            self.q.put((time.time() + bonus_priority * 43200, user, get_non_converts, get_converts))
            session.close()
            self.start()
        except Exception as e:
            print(e)
            return False
        return True

    def start(self):
        """
        Starts the worker and fills the threadpool with tasks
        """
        while len(self.current) < NUM_THREADS and not self.q.empty():
            time_set, user, non_converts, converts = self.q.get()
            self.current.append({'user_id': user.user_id,
                                 'username': user.username,
                                 'non_converts': non_converts,
                                 'catch_converts': converts,
                                 'num_maps': 'Calculating',
                                 'total_maps': 'Calculating'})
            self.pool.apply_async(self.process, args=(user, non_converts, converts))

    def process(self, user: RegisteredUser, non_converts: bool, converts: bool):

        session = self.sessionmaker()
        try:
            print('Starting initial_fetch for %s. Fetching non converts: %s. Fetching catch converts: %s' % (user.username, non_converts, converts))

            # Check refresh tokens
            if user.expires_at < datetime.datetime.now():
                success = refresh_tokens(session, user)
                session.close()
                if not success:
                    print('Something went wrong with %s' % user.username)
                    raise Exception

            # Try to connect to auth client
            auth_osu_api = OsuApiAuthService(user.user_id, user.access_token, override=self.bypass_user_auth)
            print('%s accessed the osu api successfully' % user.username)

            # Get most played
            most_played = auth_osu_api.get_all_played_maps()

            # Get relevant info and filter for only ranked, loved, and approved maps
            most_played = [{'beatmap_id': x.beatmap_id,
                            'beatmapset_id': x.beatmapset.id,
                            'mode': x._beatmap.mode.value,
                            'status': x.beatmapset.status.value} for x in most_played]
            most_played = list(filter(lambda x: x['status'] in [1, 2, 4], most_played))

            # Update current with the new values
            for task in self.current:
                if task['user_id'] == user.user_id:
                    task['num_maps'] = len(most_played)
                    task['total_maps'] = len(most_played)

            print('Beginning fetch for %s! They have %s maps in their most played.' % (user.username, len(most_played)))

            while len(most_played) > 0:
                # Check to see that user is still in current (They may have been removed)
                ids = [x['user_id'] for x in self.current]
                if user.user_id not in ids:
                    raise Exception

                beatmap = most_played.pop()

                new_scores = []
                # Get the default mode score first
                if not non_converts:
                    new_scores += auth_osu_api.get_user_scores_on_map(beatmap['beatmap_id'])

                # If the map has converts and the user wants converts, then get those as well.
                if converts and beatmap['mode'] == 'osu':
                    new_scores += auth_osu_api.get_user_scores_on_map(beatmap['beatmap_id'], mode='fruits')
                temp_session = self.sessionmaker()
                insert_scores(temp_session, new_scores)
                temp_session.close()

                # Update the task
                for task in self.current:
                    if task['user_id'] == user.user_id:
                        task['num_maps'] = len(most_played)

            session = self.sessionmaker()
            new_user = session.get(RegisteredUser, user.user_id)
            new_user.last_updated = datetime.datetime.now()
            session.close()
            # Task finished

        except Exception as e:
            session.close()
            print('Exception raised in fetch for %s' % user.username)
            print('User is probably not authenticated or was removed from queue')
            print(e)

        finally:
            for task in self.current:
                if task['user_id'] == user.user_id:
                    self.current.remove(task)
                    return
            self.start()

if __name__ == '__main__':
    orm = ORM()
    tq = TaskQueue(orm.sessionmaker)
    tq.start()
    tq.enqueue(10651409, True, True)
    #tq.enqueue(84841, True, True)
    #tq.enqueue(617104, True, True)
    #tq.enqueue(7720423, True, True)

    while True:
        print(tq.current)
        print(tq.q.queue)
        print('\n')
        time.sleep(5)