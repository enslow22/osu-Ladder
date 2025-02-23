from database.models import BeatmapSet, Beatmap
from sqlalchemy import select, and_, func, Date
from sqlalchemy.orm import Session
from ossapi.models import Beatmap as OssapiBeatmap

def get_beatmap(session: Session, beatmap_id: int) -> Beatmap | None:
    return session.get(Beatmap, beatmap_id)

def insert_beatmap(session: Session, beatmap: OssapiBeatmap) -> None:
    return