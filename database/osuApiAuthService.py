from ossapi import Ossapi, Grant
import dotenv
import os
from ratelimit import limits, sleep_and_retry

CALLS = 60
ONE_MINUTE = 60

# I think each instance of this can have its own rate limiter.
# This service should only fetch from the osu api. It should not touch the database.
class OsuApiAuthService:

    # Note that instantiating this with override will cause problems most likely im sorgy so just don't use it unless youre testing something
    def __init__(self, user_id: int, access_token: str, override=False):
        dotenv.load_dotenv('.env')
        self.user_id = user_id
        if override:
            self.api = Ossapi(int(os.getenv('CLIENT_ID')),
                              os.getenv('CLIENT_SECRET'),)
        else:
            self.api = Ossapi(int(os.getenv('WEBCLIENT_ID')),
                              os.getenv('WEBCLIENT_SECRET'),
                              grant=Grant.AUTHORIZATION_CODE,
                              redirect_uri=os.getenv('REDIRECT_URI'),
                              access_token=access_token,)

    def get_all_played_maps(self):
        map_list = []
        offset = 0
        limit = 100
        while b := self.get_user_maps(offset, limit):
            if offset % 1000 == 0:
                print(str(offset) + ' maps found')
            map_list += b
            offset += 100
        print(str(len(map_list)) + ' total maps found')
        return map_list

    @sleep_and_retry
    @limits(calls=CALLS, period=ONE_MINUTE)
    def get_user_maps(self, offset, limit):
        return self.api.user_beatmaps(self.user_id, "most_played", limit=limit, offset=offset)

    @sleep_and_retry
    @limits(calls=CALLS, period=ONE_MINUTE)
    def get_user_scores_on_map(self, beatmap_id, multiple=True, mode=None):
        try:
            if multiple:
                score_infos = self.api.beatmap_user_scores(beatmap_id, self.user_id, mode=mode)
            else:
                score_infos = [self.api.beatmap_user_score(beatmap_id, self.user_id, mode=mode).score]
        except ValueError as ve:
            print(ve)
            print('Map probably has an issue or has no leaderboard')
            return []
        return score_infos

if __name__ == '__main__':
    pass