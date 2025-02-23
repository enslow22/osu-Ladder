import datetime
from typing import List
from sqlalchemy.ext.declarative import AbstractConcreteBase
from sqlalchemy.orm import DeclarativeBase, registry, relationship, Mapped, declared_attr, declarative_base
from sqlalchemy import Column, String, Integer, Float, Date, Boolean, DateTime, ForeignKey
from sqlalchemy.types import JSON
from sqlalchemy.ext.declarative import ConcreteBase
import enum
from sqlalchemy import Enum
import util
from ossapi import Score as OssapiScore, User, Beatmapset

mapper_registry = registry()

class Base(DeclarativeBase):
    def to_dict(self):
        return {field.name: getattr(self, field.name) for field in self.__table__.c}

'''
class User(Base):
    __tablename__ = 'sample_users'



class Beatmap(Base):
    __tablename__ = 'osu_beatmaps'
'''

class RankEnum(enum.Enum):
    A = 'A'
    B = 'B'
    C = 'C'
    D = 'D'
    S = 'S'
    SH = 'SH'
    X = 'X'
    XH = 'XH'

class StatusEnum(enum.Enum):
    graveyard = 'graveyard'
    wip = 'wip'
    pending = 'pending'
    ranked = 'ranked'
    approved = 'approved'
    qualified = 'qualified'
    loved = 'loved'

class PlaymodeEnum(enum.Enum):
    osu = 'osu'
    taiko = 'taiko'
    fruits = 'fruits'
    mania = 'mania'

class Score(AbstractConcreteBase, Base):
    strict_attrs = True
    score_id = Column(Integer, primary_key=True)
    stable_score = Column(Integer)
    lazer_score = Column(Integer)
    classic_score = Column(Integer)
    accuracy = Column(Float)
    maxcombo = Column(Integer)
    rank = Column(Enum(RankEnum))
    count50 = Column(Integer)
    count100 = Column(Integer)
    count300 = Column(Integer)
    countmiss = Column(Integer)
    perfect = Column(Boolean)
    enabled_mods = Column(String) # Comes from https://github.com/tybug/ossapi/blob/master/ossapi/mod.py (only stable)
    enabled_mods_settings = Column(JSON) # This comes from the response
    date = Column(DateTime)
    pp = Column(Float)
    replay = Column(Boolean)

    @declared_attr
    def beatmap_id(cls):
        return Column(Integer, ForeignKey('osu_beatmaps.beatmap_id'))

    @declared_attr
    def user_id(cls):
        return Column(Integer, ForeignKey('registered_users.user_id'))

    @declared_attr
    def beatmap(cls) -> Mapped["Beatmap"]:
        return relationship("Beatmap")

    def set_details(self, info: OssapiScore):
        self.score_id = info.id
        self.beatmap_id = info.beatmap_id
        self.user_id = info.user_id
        self.stable_score = info.legacy_total_score
        self.lazer_score = info.total_score
        self.classic_score = info.classic_total_score
        self.accuracy = info.accuracy
        self.maxcombo = info.max_combo
        self.rank = info.rank.value
        self.perfect = info.is_perfect_combo
        self.count50 = int(info.statistics.meh or 0)
        self.count100 = int(info.statistics.ok or 0)
        self.count300 = int(info.statistics.great or 0)
        self.countmiss = int(info.statistics.miss or 0)
        mod_string, mod_settings = util.parse_modlist(info.mods)
        self.enabled_mods = mod_string
        self.enabled_mods_settings = mod_settings
        self.date = info.ended_at
        self.pp = info.pp
        self.replay = info.replay

class OsuScore(Score):
    __tablename__ = 'registered_scores_osu'

    __mapper_args__ = {"concrete": True, "polymorphic_identity": "osu"}

    def set_details(self, info):
        super().set_details(info)

class TaikoScore(Score):
    __tablename__ = 'registered_scores_taiko'

    __mapper_args__ = {"concrete": True, "polymorphic_identity": "taiko"}

    def set_details(self, info):
        super().set_details(info)

class CatchScore(Score):
    __tablename__ = 'registered_scores_catch'

    __mapper_args__ = {"concrete": True, "polymorphic_identity": "fruits"}

    def set_details(self, info):
        super().set_details(info)

class ManiaScore(Score):
    __tablename__ = 'registered_scores_mania'

    __mapper_args__ = {"concrete": True, "polymorphic_identity": "mania"}

    def set_details(self, info):
        super().set_details(info)

class UserStats(Base):
    __tablename__ = 'osu_user_stats'
    user_id = Column(Integer, primary_key=True)
    count300 = Column(Integer)
    count100 = Column(Integer)
    count50 = Column(Integer)
    countMiss = Column(Integer)
    accuracy_total = Column(Integer)
    accuracy_count = Column(Integer)
    accuracy = Column(Float)
    playcount = Column(Integer)
    ranked_score = Column(Integer)
    total_score = Column(Integer)
    x_rank_count = Column(Integer)
    xh_rank_count = Column(Integer)
    s_rank_count = Column(Integer)
    sh_rank_count = Column(Integer)
    a_rank_count = Column(Integer)
    rank = Column(Integer)
    level = Column(Float)
    replay_popularity = Column(Integer)
    fail_count = Column(Integer)
    exit_count = Column(Integer)
    max_combo = Column(Integer)
    country_acronym = Column(String)
    rank_score = Column(Float) # I think this is pp
    rank_score_index = Column(Integer)
    rank_score_exp = Column(Float)
    rank_score_index_exp = Column(Integer)
    accuracy_new = Column(Float)
    last_update = Column(Date)
    last_played = Column(Date)
    total_seconds_played = Column(Integer)

    def __init__(self, user_id: int):
        self.user_id = user_id

    # Given a User object from the osu! database, set all fields on the mapped class
    def set_details(self, info: User):
        stats = info.statistics
        self.count300 = stats.count_300
        self.count100 = stats.count_100
        self.count50 = stats.count_50
        self.countMiss = stats.count_miss
        #self.accuracy_total = Column(Integer) # WHAT IS THIS
        #self.accuracy_count = Column(Integer) # WHAT IS THIS
        #self.accuracy = Column(Float) # WHAT IS THIS
        self.playcount = stats.play_count
        self.ranked_score = stats.ranked_score
        self.total_score = stats.total_score
        self.x_rank_count = stats.grade_counts.ss
        self.xh_rank_count = stats.grade_counts.ssh
        self.s_rank_count = stats.grade_counts.s
        self.sh_rank_count = stats.grade_counts.sh
        self.a_rank_count = stats.grade_counts.a
        #self.rank = Column(Integer) # WHAT IS THIS
        self.level = stats.level.current + stats.level.progress / 100
        self.replay_popularity = stats.replays_watched_by_others
        #self.fail_count = Column(Integer) # NOT GIVEN
        #self.exit_count = Column(Integer) # NOT GIVEN
        self.max_combo = stats.maximum_combo
        self.country_acronym = info.country_code
        self.rank_score = stats.pp
        self.rank_score_index = stats.global_rank # This is rank
        #self.rank_score_exp = Column(Float) # WHAT IS THIS
        #self.rank_score_index_exp = Column(Integer) # WHAT IS THIS
        self.accuracy_new = stats.hit_accuracy
        self.last_update = datetime.datetime.now()
        self.last_played = info.last_visit
        self.total_seconds_played = stats.play_time

class RegisteredUser(Base):
    __tablename__ = 'registered_users'
    user_id = Column(Integer, primary_key=True)
    username = Column(String)
    country = Column(String)
    discord = Column(String)
    profile_hue = Column(Integer)
    avatar_url = Column(String)
    playmode = Column(Enum(PlaymodeEnum))
    last_updated = Column(DateTime)
    #fetched_catch_converts = Column(Boolean)
    track_osu = Column(Boolean)
    track_taiko = Column(Boolean)
    track_fruits = Column(Boolean)
    track_mania = Column(Boolean)
    apikey = Column(String)
    access_token = Column(String)
    refresh_token = Column(String)
    expires_at = Column(DateTime)

    # If given a User Object (from the osu database wrapper), it will populate the row with the correct info
    def __init__(self, user_info):
        self.set_all(user_info)

    def set_all(self, user_info: User):
        self.user_id = user_info.id
        self.username = user_info.username
        self.country = user_info.country_code
        self.discord = user_info.discord
        self.profile_hue = user_info.profile_hue
        self.avatar_url = user_info.avatar_url
        self.playmode = user_info.playmode

class RegisteredUserTag(Base):
    __tablename__ = 'registered_user_tags'
    user_id = Column(Integer, primary_key=True)
    tag = Column(String, primary_key=True)
    mod = Column(Boolean)
    date_added = Column(DateTime)

class Tags(Base):
    __tablename__ = 'group_tags'

    tag_id = Column(Integer, primary_key=True, autoincrement=True)
    tag_name = Column(String, primary_key=True)
    tag_owner = Column(Integer, ForeignKey('registered_users.user_id'))
    date_created = Column(DateTime)


# Write a function to add a beatmapset into the database. (This will be a helper function that should be run uhhh idk when)
# The easiest thing to do is just run it every hour or something, and then have a fallback on the front end for beatmaps not found
#   This is the best idea I think. We can run a sql query that right joins the scores and beatmaps tables. If the length
#   of the result does not match the length of scores, then we can search the results for missing beatmap(s) and snurp them.
#   I should make a beatmapService.

# Another thing you can do is whenever a new score is found, just snurp that beatmap into the database. This might be expensive though.
# Write a script to scan for all new ranked, loved, or approved beatmapset ids (This script will be a cron job that runs every 4 hours)

class BeatmapSet(Base):
    __tablename__ = 'osu_beatmapsets'

    beatmapset_id = Column(Integer, primary_key=True)
    owner_id = Column(Integer)
    artist = Column(String)
    artist_unicode = Column(String)
    title = Column(String)
    title_unicode = Column(String)
    tags = Column(String)

    bpm = Column(Float)
    versions_available = Column(Integer)
    approved = Column(Integer) # TODO make enum
    approved_date = Column(DateTime)
    submit_date = Column(DateTime)
    last_update = Column(DateTime)
    genre_id = Column(Integer)
    language_id = Column(Integer)
    nsfw = Column(Boolean)

    beatmaps: Mapped[List["Beatmap"]] = relationship()

    def set_details(self, info: Beatmapset):
        self.beatmapset_id = info.id
        self.owner_id = info.user_id
        self.artist = info.artist
        self.artist_unicode = info.artist_unicode
        self.title = info.title
        self.title_unicode = info.title_unicode
        self.tags = info.tags

        self.bpm = info.bpm
        self.versions_available = len(info.beatmaps)
        self.approved = info.status.value # TODO test this
        self.approved_date = info.ranked_date
        self.submit_date = info.submitted_date
        self.last_update = info.last_updated
        self.genre_id = info.genre
        self.language_id = info.language
        self.nsfw = info.nsfw

class Beatmap(Base):
    __tablename__ = "osu_beatmaps"

    beatmap_id = Column(Integer, primary_key=True)
    beatmapset_id = Column(Integer, ForeignKey('osu_beatmapsets.beatmapset_id'))
    mapper_id = Column(Integer)
    checksum = Column(String)
    version = Column(String)
    total_length = Column(Integer)
    hit_length = Column(Integer)
    count_total = Column(Integer)
    count_normal = Column(Integer)
    count_slider = Column(Integer)
    count_spinner = Column(Integer)
    hp = Column(Float)
    cs = Column(Float)
    od = Column(Float)
    ar = Column(Float)
    playmode = Column(Enum(PlaymodeEnum))
    approved = Column(Integer) # TODO make enum# 1 ranked, 2 approved, 4 loved
    last_update = Column(DateTime)
    stars = Column(Float)
    max_combo = Column(Integer)
    bpm = Column(Float)

    scores: Mapped[List["Score"]] = relationship(back_populates="beatmap")
    beatmapset: Mapped["BeatmapSet"] = relationship(back_populates="beatmaps")

    # TODO write set_details