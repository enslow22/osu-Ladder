from typing import Union
from fastapi import FastAPI, status
from ORM import ORM
from models import RegisteredUser

app = FastAPI()
orm = ORM()

class InternalError(Exception):
    pass


@app.get("/users/{user_id}", status_code=status.HTTP_200_OK)
def get_user(user_id: int):
    """
    Fetches a user from the database

    :param user_id: same as osu! user id
    :return: the corresponding RegisteredUser object in the database
    """
    return {"user": orm.session.get(RegisteredUser, user_id)}

@app.get("/scores/", status_code=status.HTTP_200_OK)
def get_score(b: int, u: int, m: int = 0, **kwargs):
    """
    Fetches a list of scores

    :param b: id of a beatmap
    :param u: id of a user
    :param m: ruleset (0 - osu!, 1 - taiko, 2 - catch, 3 - mania)
    :param kwargs: extra filters
    :return: Score[] containing all the user's scores on the specified beatmap
    """
    return {"score": orm.fetch_user_scores_on_beatmap(b, u, m, **kwargs)}

@app.get("/leaderboard/", status_code=status.HTTP_200_OK)
def get_group_leaderboard(g: str, b: int, m: int, **kwargs):
    """
    Generate a leaderboard given a group name and a beatmap

    :param g: group name
    :param b: id of a beatmap
    :param m: ruleset (0 - osu!, 1 - taiko, 2 - catch, 3 - mania)
    :param kwargs: extra filters
    :return: Score[] containing all the high scores of players in the group, on the specified beatmap
    """
    return {"leaderboard": orm.get_group_leaderboard(g, b, m, **kwargs)}

@app.post("/add_user/{user_id}", status_code=status.HTTP_201_CREATED)
def add_registered_user(user_id: int):
    """
    Register a new user

    :param user_id: user to be registered
    :return: None
    """
    if orm.add_new_registered_users(user_ids=user_id):
        return {"message": "%s registered to database" % str(user_id)}
    else:
        raise InternalError('Something went wrong')

@app.post("/initial_fetch/{user_id}", status_code=status.HTTP_202_ACCEPTED)
def initial_fetch(user_id: int):
    """
    Begin the fetch process for the specified user

    :param user_id: user who's scored to be fetched
    :return: None
    """
    if orm.initial_fetch_user(user_id=user_id):
        return {"message": "%s added to fetch queue" % str(user_id)}
    else:
        raise InternalError('Something went wrong')

@app.post("/add_tag/", status_code=status.HTTP_201_CREATED)
def add_tag(user_id: int, tag: str):
    """
    Give a user a new tag (add a user to a new group)

    :param user_id: user to be updated
    :param tag: new tag to be added
    :return: None
    """
    if orm.assign_tags_to_users(user_ids=user_id, tag=tag):
        return {"message": "Tags added to user %s" % str(user_id)}
    else:
        raise InternalError('Something went wrong')