"""
SELECT distinct t.beatmap_id FROM registered_scores_osu t
LEFT JOIN osu_beatmaps tl ON t.beatmap_id = tl.beatmap_id
WHERE tl.beatmap_id IS NULL
"""
import time

from database.ORM import ORM
from ossapi import Ossapi
from sqlalchemy import text
import os
import dotenv
from database.models import Beatmap

orm = ORM()
dotenv.load_dotenv('database/.env')
osu_api = Ossapi(int(os.getenv("CLIENT_ID")), os.getenv("CLIENT_SECRET"))
session = orm.sessionmaker()

# Not the nicest code ive ever written but it works
for mode in ['osu', 'taiko', 'catch', 'mania']:
    stmt = text(f"""
    SELECT distinct t.beatmap_id FROM registered_scores_{mode} t
    LEFT JOIN osu_beatmaps tl ON t.beatmap_id = tl.beatmap_id
    WHERE tl.beatmap_id IS NULL
    """)
    for i, beatmap_id in enumerate(session.scalars(stmt).all()):
        try:
            beatmap_info = osu_api.beatmap(beatmap_id)
        except ValueError:
            continue
        print(beatmap_id)
        print(beatmap_info.version)
        new_beatmap = Beatmap()
        new_beatmap.set_details(beatmap_info)
        session.add(new_beatmap)
        session.commit()
        if (i+1) % 60 == 0:
            time.sleep(20)