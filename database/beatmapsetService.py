from database.models import BeatmapSet
from ossapi.models import Beatmapset as OssapiBeatmapSet
from sqlalchemy import select, and_, func, Date
from sqlalchemy.orm import Session

# Fetch a beatmapset from the database
def get_beatmapset(session: Session, beatmapset_id: int) -> BeatmapSet | None:
    return session.get(BeatmapSet, beatmapset_id)

# Insert a new beatmapset into the database
def insert_beatmapset(session: Session, beatmapset: BeatmapSet) -> None:
    return