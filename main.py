# Phase one is to add all users to the database
# It will include all user info present on the website and a last_updated column
import pickle
import time

# There are 101 oregon players
# We need to fetch their user data from the api and put it into osu_user_stats
# We also need to alter that table and include a last updated column
# This will require me to write the base class definition for the osu_user_stats table

# Now that I have all the oregon players in the database, I need to add all their scores
# For each oregon player:
# While they have maps in their most played:
# - Grab 50 of them
# - Fetch their scores for all 50
# - Insert all into Database

# TODO
# Before we can do the above, we need to map the scores response from the api to the mapped class
# Before we do that we need to map the scores table to the orm
# Before we do that we need to disable autoincrement on the scores table
# TODO ADD TIBOM 6172584 ADD ORBITIS 3634152 ADD EVB 4742068 ADD 910DOWII 21368052
# TODO ADD SLEEPTEINER 4781004 ADD HARUHIME 12231334

from ORM import ORM
from osuApi import get_user_info, get_most_played

def test_on_enslow(from_pickle = True):

    orm = ORM()
    if not from_pickle:
        enslow_most_played = get_most_played(10651409)
        enslow_most_played = [{'beatmap_id': x.beatmap_id,
                               'beatmapset_id': x.beatmapset.id,
                               'status': x.beatmapset.status.value} for x in enslow_most_played]
        enslow_most_played = list(filter(lambda x: x['status'] in [1, 2, 4], enslow_most_played))
    else:
        pklfile = open('pkl/enslow.pkl', 'rb')
        enslow_most_played = pickle.load(pklfile)
        pklfile.close()

    completed_ids = []
    problem_ids = []
    try:
        while len(enslow_most_played) > 0:
            beatmap = enslow_most_played.pop()
            if beatmap['status'] not in [1, 2, 4]:
                continue
            #print('Accessing %s for enslow' % beatmap['beatmap_id'])
            if orm.fetch_and_insert_score(beatmap['beatmap_id'], 10651409, multiple=True):
                completed_ids.append(beatmap['beatmap_id'])
            else:
                print('problem with %s' % str(beatmap['beatmap_id']))
                problem_ids.append(beatmap['beatmap_id'])
    except Exception as e:
        print('uh oh')
        print(e)
        pklfile = open('pkl/enslow.pkl', 'wb')
        pickle.dump(enslow_most_played, pklfile)
        pklfile.close()
        with open("enslow.txt", "w") as file:
            # Write the string to the file
            file.write(str(enslow_most_played)+'\n')
            file.write(str(completed_ids)+'\n')
            file.write(str(problem_ids)+'\n')

    #orm.add_users_to_oregon([2504750, 13641450])
    #orm.update_players_stats([2504750, 13641450])
    #oregon_users = orm.get_all_oregon_players()
    #oregon_ids = [user.user_id for user in oregon_users]
    #orm.update_players_stats(oregon_ids)

def initial_fetch(user_id, from_pickle = False):

    user_info = get_user_info(user_id)
    username = user_info.username
    print('Adding %s to the database. Fetching their scores' % username)
    orm = ORM()
    if not from_pickle:
        most_played = get_most_played(user_id)
        most_played = [{'beatmap_id': x.beatmap_id,
                               'beatmapset_id': x.beatmapset.id,
                               'status': x.beatmapset.status.value} for x in most_played]
        most_played = list(filter(lambda x: x['status'] in [1, 2, 4], most_played))
    else:
        pklfile = open('%s.pkl' % username, 'rb')
        most_played = pickle.load(pklfile)
        pklfile.close()

    completed_ids = []
    problem_ids = []
    try:
        while len(most_played) > 0:
            beatmap = most_played.pop()
            if beatmap['status'] not in [1, 2, 4]:
                continue
            if orm.fetch_and_insert_score(beatmap['beatmap_id'], user_id, multiple=True):
                completed_ids.append(beatmap['beatmap_id'])
            else:
                print('problem with %s' % str(beatmap['beatmap_id']))
                problem_ids.append(beatmap['beatmap_id'])
    except Exception as e:
        print('uh oh')
        print(e)
    finally:
        pklfile = open('%s.pkl' % username, 'wb')
        pickle.dump(most_played, pklfile)
        pklfile.close()
        with open("%s.txt" % username, "w") as file:
            # Write the string to the file
            file.write(str(most_played)+'\n')
            file.write(str(completed_ids)+'\n')
            file.write(str(problem_ids)+'\n')

# Get a user's 24hr history and merge all scores into the database
def daily_fetch(user_id):
    orm = ORM()
    orm.fetch_and_insert_daily_scores(user_id)

if __name__ == '__main__':
    start = time.time()
    orm = ORM()
    orm.add_new_registered_users([6172584, 3634152, 4742068, 21368052, 4781004, 12231334])
    end = time.time()
    print("Elapsed time: " + str(end - start))