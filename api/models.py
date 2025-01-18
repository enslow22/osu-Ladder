import datetime
from sqlalchemy.orm import DeclarativeBase, registry, relationship
from sqlalchemy import Column, String, Integer, Float, Date, Boolean, DateTime, ForeignKey
from sqlalchemy.types import JSON
import enum
from sqlalchemy import Enum
from osuApi import parse_modlist

mapper_registry = registry()

class Base(DeclarativeBase):
    def to_dict(self):
        return {field.name: getattr(self, field.name) for field in self.__table__.c}

'''
class User(Base):
    __tablename__ = 'sample_users'


class BeatmapSet(Base):
    __tablename__ = 'osu_beatmapsets'

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

class PlaymodeEnum(enum.Enum):
    osu = 'osu'
    taiko = 'taiko'
    fruits = 'fruits'
    mania = 'mania'

class Score(Base):
    __abstract__ = True
    score_id = Column(Integer, primary_key=True)
    beatmap_id = Column(Integer)
    user_id = Column(Integer, ForeignKey('registered_users.user_id'))
    stable_score = Column(Integer)
    lazer_score = Column(Integer)
    classic_score = Column(Integer)
    maxcombo = Column(Integer)
    rank = Column(Enum(RankEnum))
    count50 = Column(Integer)
    count100 = Column(Integer)
    count300 = Column(Integer)
    countmiss = Column(Integer)
    perfect = Column(Boolean)
    enabled_mods = Column(Integer) # Comes from https://github.com/tybug/ossapi/blob/master/ossapi/mod.py (only stable)
    enabled_mods_settings = Column(JSON) # This comes from the response
    date = Column(DateTime)
    pp = Column(Float)
    replay = Column(Boolean)

    def set_details(self, info):
        self.score_id = info.id
        self.beatmap_id = info.beatmap_id
        self.user_id = info.user_id
        self.stable_score = info.legacy_total_score
        self.lazer_score = info.total_score
        self.classic_score = info.classic_total_score
        self.maxcombo = info.max_combo
        self.rank = info.rank.value
        self.perfect = info.is_perfect_combo
        self.count50 = int(info.statistics.meh or 0)
        self.count100 = int(info.statistics.ok or 0)
        self.count300 = int(info.statistics.great or 0)
        self.countmiss = int(info.statistics.miss or 0)
        mod_string, mod_settings = parse_modlist(info.mods)
        self.enabled_mods = mod_string
        self.enabled_mods_settings = mod_settings
        self.date = info.ended_at
        self.pp = info.pp
        self.replay = info.replay

class OsuScore(Score):
    __tablename__ = 'registered_scores_osu'

    def set_details(self, info):
        super().set_details(info)

class TaikoScore(Score):
    __tablename__ = 'registered_scores_taiko'

    def set_details(self, info):
        super().set_details(info)

class CatchScore(Score):
    __tablename__ = 'registered_scores_catch'

    def set_details(self, info):
        super().set_details(info)

class ManiaScore(Score):
    __tablename__ = 'registered_scores_mania'

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

    def __init__(self, user_id):
        self.user_id = user_id

    # Given a User object from the osu! api, set all fields on the mapped class
    def set_details(self, info):
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

    # If given a User Object (from the osu api wrapper), it will populate the row with the correct info
    def __init__(self, user_info):
        self.set_all(user_info)

    def set_all(self, user_info):
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

# Takes a list of mods
# If it's a stable (classic) score, it will have the classic mod
# If it's a lazer score, it will not have the classic mod
# If it's a lazer score, then mods may have modifiers
# We could store this as a string. The most important part is that it is invertible.
# I don't think there's a nice way to do this without violating db normalization
# The settings will be stored as a json I guess

