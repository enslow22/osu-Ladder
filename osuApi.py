from ossapi import Ossapi
from dotenv import load_dotenv
import os
from ratelimit import limits, sleep_and_retry

ONE_MINUTE = 60
CALLS = 100

load_dotenv()
client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')
osu_api = Ossapi(client_id, client_secret)

# Gets a list of all ranked, approved, and loved maps a user has played
# The user_beatmaps endpoint can grab 100 at a time.
# The way we do this correctly is to grab 100, then offset by 100. and repeat until all beatmaps have been grabbed
# We know all beatmaps have been grabbed when the length of the response is less than 100

@sleep_and_retry
@limits(calls=CALLS, period=ONE_MINUTE)
def get_user_maps(user_id, offset, limit):
    return osu_api.user_beatmaps(user_id, "most_played", limit=limit, offset=offset)

def get_most_played(user_id):
    map_list = []
    offset = 0
    limit = 100
    while b := get_user_maps(user_id, offset, limit):
        if offset % 1000 == 0:
            print(str(offset) + ' maps found')
        map_list += b
        offset += 100
    print(str(len(map_list)) + ' total maps found')
    return map_list

@sleep_and_retry
@limits(calls=CALLS, period=ONE_MINUTE)
def get_user_info(user_id):
    return osu_api.user(user_id)

@sleep_and_retry
@limits(calls=CALLS, period=ONE_MINUTE)
def get_score_info(score_id):
    return osu_api.score(score_id)

def parse_modlist(modlist):
    if not modlist:
        return '', None
    string = ''
    for mod in modlist:
        string += mod.acronym

    # Figure out if classic
    if modlist[-1].acronym == 'CL':
        return string, None
    else:
        newmodlist = []
        for mod in modlist:
            newmodlist.append((mod.acronym, mod.settings))
        tup = (string, newmodlist)
        return tup

    # If it's classic, return a string of mods

    # Otherwise, return a tuple (a, b) where a is a string of mods and b is list of settings
    # Example: ('HDDT', 'DT: {speed_change: 1.3}')

@sleep_and_retry
@limits(calls=CALLS, period=ONE_MINUTE)
def get_user_scores_on_map(beatmap_id, user_id, multiple = True):
    try:
        if multiple:
            score_infos = osu_api.beatmap_user_scores(beatmap_id, user_id)
        else:
            score_infos = [osu_api.beatmap_user_score(beatmap_id, user_id).score]
    except ValueError as ve:
        print(ve)
        print('map is unranked probably')
        return None
    return score_infos

@sleep_and_retry
@limits(calls=CALLS, period=ONE_MINUTE)
def get_user_recent_scores(user_id):
    scores = []
    offset = 0
    limit = 5
    while b := osu_api.user_scores(user_id, 'recent', offset=offset, limit=limit):
        scores += b
        offset += limit
    return scores
