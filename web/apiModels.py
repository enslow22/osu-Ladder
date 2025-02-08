from typing import Literal

from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

filter_names = [
    "date",
    "pp",
    "rank",
    "perfect",
    "max_combo",
    "replay",
    "stable_score",
    "lazer_score",
    "classic_score",
    "count_50",
    "count_100",
    "count_300",
    "count_miss",
    "perfect_combo"]
operation_names = [
    "=",
    "!=",
    ">",
    "<",
    "<=",
    ">="]
filters = '|'.join(filter_names)
operations = '|'.join(operation_names)
filters_regex = r"(%s){1}(%s){1}(\d{4}-\d{2}-\d{2}|\d*|\w*)" % (filters, operations)

class Mode(str or int, Enum):
    osu = 'osu' or 0
    taiko = 'taiko' or 1
    fruits = 'fruits' or 2
    mania = 'mania' or 3

class Metric(str, Enum):
    pp = 'pp'
    stable_score = 'stable_score'
    lazer_score = 'lazer_score'
    classic_score = 'classic_score'
    accuracy = 'accuracy'
    date = 'date'

class ScoreGroupBy(str, Enum):
    user_id = 'user_id'
    beatmap_id = 'beatmap_id'
    rank = 'rank'

class Mods(BaseModel):
    #model_config = ConfigDict(regex_engine='python-re'
    mods: str = Field('a', description='A list of mods as a string')

class Filters(BaseModel):
    filters: str = Field(pattern=filters_regex) #  maybe this doesnt need to exist

class SortBy(BaseModel):
    metric: Metric = Field('pp')
    descending: bool = Field(True)

class FilterParams(BaseModel):
    limit: int = Field(100, gt=0, le=100)
    offset: int = Field(0, ge=0)
    order_by: Literal["created_at", "updated_at"] = "created_at"