"""
Contains helper functions which will be used in more than one service
"""
import datetime
import operator as op

modes = ['osu', 'taiko', 'fruits', 'mania']

def get_mode_table(mode: str or int):
    from .models import OsuScore, TaikoScore, CatchScore, ManiaScore
    match mode:
        case 'osu' | 0:
            return OsuScore
        case 'taiko' | 1:
            return TaikoScore
        case 'fruits' | 2:
            return CatchScore
        case 'mania' | 3:
            return ManiaScore

def parse_modlist(modlist: list):
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

def parse_score_filters(mode: str or int, filters: str):
    """
    Builds a query object based on a bunch of filters as a string
    The list of filters available:
    stable_score, lazer_score, classic_score, maxcombo, rank, count50, count100, count300, countmiss, perfect,
    enabled_mods, enabled_mods_settings, date, pp, replay

    An example would be 'date<2010-12-12 pp>100 replay=1'
    This should return a 3-tuple (OsuScore.date<'2010-12-12', OsuScore.pp>100, OsuScore.replay==1)

    :param mode     the game mode
    :param kwargs:  filters
    :return:
    """

    if filters is None:
        return ()

    import re

    table = get_mode_table(mode)

    all_filters = re.split(r',|\s', filters)
    all_filters = [x.strip() for x in all_filters]
    all_filters = [re.split('([<>=!])+', x) for x in all_filters]

    op_map = {
    "=": op.eq,
    "!=": op.ne,
    ">": op.gt,
    "<": op.lt,
    "<=": op.le,
    ">=": op.ge,
    }

    field_map = {
        "date": table.date,
        "pp": table.pp,
        "rank": table.rank,
        "perfect": table.perfect,
        "max_combo": table.maxcombo
    }

    # We can check that things are properly formatted and change them if they aren't
    # TODO: this
    formats = {
        "date": lambda x: datetime.datetime.strftime(x, "%Y-%m-%d"),
        "pp": lambda x: float(x),
        "rank": lambda x: x,
        "perfect": lambda x: int(x),
        "max_combo": lambda x: int(x)
    }

    r = []
    for f in all_filters:
        r.append(op_map[f[1]](field_map[f[0]], f[2]))
        #print(formats[f[0]](f[2]))
    return tuple(r)

if __name__ == '__main__':

    a = parse_score_filters('osu', 'date<2024-10-10')
    #parse_score_filters('osu', 'date<2024-12-31 rank=S')
