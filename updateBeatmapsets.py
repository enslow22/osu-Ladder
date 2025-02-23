"""
This script will be started by a cron job, and when run, it will update the beatmapsets database
This script finds the latest beatmap ranked date and then will search for beatmaps that were ranked after it.
"""
import time
from ossapi import Ossapi, BeatmapsetSearchSort
import os
import dotenv
from database.models import Beatmap, BeatmapSet
from database.beatmapsetService import get_beatmapset
from sqlalchemy import select
from database.ORM import ORM

dotenv.load_dotenv('database/.env')
osu_api = Ossapi(int(os.getenv("CLIENT_ID")), os.getenv("CLIENT_SECRET"))

orm = ORM()
session = orm.sessionmaker()

stmt = select(BeatmapSet).order_by(BeatmapSet.approved_date.desc()).limit(1)
last_beatmapset = session.scalars(stmt).first()
last_approved_date = last_beatmapset.approved_date.strftime("%Y-%m-%d")

res = osu_api.search_beatmapsets(query=f"ranked>={last_approved_date}", sort=BeatmapsetSearchSort.RANKED_ASCENDING)

while last_beatmapset.beatmapset_id != res.beatmapsets[-1].id:

    for beatmapset in res.beatmapsets:
        # Check if beatmapset exists in database
        if get_beatmapset(session, beatmapset.id):
            continue

        # search_beatmapsets does not return genre and language id
        temp_beatmapset = osu_api.beatmapset(beatmapset.id)

        new_beatmapset = BeatmapSet()
        new_beatmapset.set_details(temp_beatmapset)
        last_beatmapset = new_beatmapset
        session.add(new_beatmapset)

        for beatmap in temp_beatmapset.beatmaps:
            new_beatmap = Beatmap()
            new_beatmap.set_details(beatmap)
            session.add(new_beatmap)

        session.commit()

    time.sleep(5)
    print(res.beatmapsets[-1].title)
    res = osu_api.search_beatmapsets(query=f"ranked>={last_approved_date}", sort=BeatmapsetSearchSort.RANKED_ASCENDING, cursor=res.cursor)

print('fin')