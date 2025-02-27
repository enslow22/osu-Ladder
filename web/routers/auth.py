import datetime
import fastapi.exceptions
import sqlalchemy.exc
from fastapi import APIRouter, Depends, status, Query
from pydantic import BaseModel
from starlette.responses import RedirectResponse
from typing import Optional, Annotated
from web.dependencies import RegisteredUserCompact, verify_token
from sqlalchemy import select, delete, func, and_
from database.ORM import ORM
from database.models import RegisteredUser, Leaderboard, LeaderboardSpot, LeaderboardMetricEnum
from database.scoreService import get_user_scores
from database.util import parse_score_filters, parse_mod_filters
from database.leaderboardService import recalculate_user
from web.apiModels import Mode

router = APIRouter()
orm = ORM()

@router.post("/logout")
async def logout(token: Annotated[RegisteredUserCompact, Depends(verify_token)]):
    """
    Logs the current user out
    """
    if not token:
        return {"message": "user not logged in"}
    response = RedirectResponse('/', status_code=302)
    response.delete_cookie('session_token', '/')
    return response

@router.get('/users/{user_id}', tags=['auth'])
def get_user(user_id: int):
    """
    Fetches a user from the database from their user_id
    """
    session = orm.sessionmaker()
    return {"user": session.get(RegisteredUser, user_id)}

@router.post("/initial_fetch_self", status_code=status.HTTP_202_ACCEPTED)
def initial_fetch(token: Annotated[RegisteredUserCompact, Depends(verify_token)], catch_converts: Annotated[ bool , Query(description='Fetch ctb converts?')] = False):
    """
    Moved to /fetch/initial_fetch_self
    """
    pass

@router.post("/create_leaderboard", status_code=status.HTTP_201_CREATED)
def create_leaderboard(token: Annotated[RegisteredUserCompact, Depends(verify_token)], leaderboard_name: str,
                       description: str,
                       metric: LeaderboardMetricEnum,
                       unique: bool = True,
                       private: bool = True,
                       mode: Mode = "osu",
                       mod_filters: str = None,
                       score_filters: str = None,
                       beatmap_filters: str = None,
                       beatmapset_filters: str = None,):
    session = orm.sessionmaker()
    try:
        new_leaderboard = Leaderboard()
        new_leaderboard.name = leaderboard_name
        new_leaderboard.creator_id = token["user_id"]
        new_leaderboard.mode = mode
        new_leaderboard.metric = metric
        new_leaderboard.unique = unique
        new_leaderboard.private = private
        new_leaderboard.description = description
        new_leaderboard.mod_filters = mod_filters
        new_leaderboard.score_filters = score_filters
        new_leaderboard.beatmap_filters = beatmap_filters
        new_leaderboard.beatmapset_filters = beatmapset_filters
        session.add(new_leaderboard)
        session.commit()
    except Exception as e:
        print(e)
        return {"message": f"{leaderboard_name} was not created due to an issue. Maybe a leaderboard with that name already exists?"}
    session.close()
    return {"message": f"{leaderboard_name} has been successfully created"}

@router.post("/delete_leaderboard", status_code=status.HTTP_201_CREATED)
def delete_leaderboard(token: Annotated[RegisteredUserCompact, Depends(verify_token)], leaderboard_name: str):
    session = orm.sessionmaker()
    try:
        stmt = select(Leaderboard).filter(and_(
            Leaderboard.name == leaderboard_name,
            Leaderboard.creator_id == token.user_id
        ))
        leaderboard = session.scalars(stmt).one()
        session.delete(leaderboard)
        session.commit()
    except:
        return {"message": f"Either the leaderboard {leaderboard_name} does not exist, or you are not the creator of it"}
    return {"message": f"{leaderboard_name} has been successfully deleted"}

@router.post("/add_users_to_leaderboard", status_code=status.HTTP_201_CREATED)
async def add_user_to_leaderboard(token: Annotated[RegisteredUserCompact, Depends(verify_token)], user_ids: Annotated[list[int] | None, Query()], leaderboard_name: str):
    # Check if leaderboard is public
    session = orm.sessionmaker()
    stmt = select(Leaderboard).filter(Leaderboard.name == leaderboard_name)
    leaderboard = session.scalars(stmt).one()

    if (leaderboard.private and token['user_id'] == leaderboard.creator_id) or not leaderboard.private:

        problem_users = []
        for user_id in user_ids:
            # Check that user is registered
            # If they are not registered, then pass
            user = session.get(RegisteredUser, user_id)

            try:
                new_leaderboard_spot = LeaderboardSpot()
                new_leaderboard_spot.leaderboard_id = leaderboard.leaderboard_id
                new_leaderboard_spot.user_id = user.user_id
                session.add(new_leaderboard_spot)
                await recalculate_user(session, user.user_id, leaderboard_id=new_leaderboard_spot.leaderboard_id)
                session.commit()
            except Exception:
                problem_users.append(user_id)
                session.rollback()
                continue

        if len(problem_users) > 0:
            return {"message": f"Some users ({problem_users}) were not added to {leaderboard_name}. Other users have been added."}
        return {"message": "Success, all users have been added to the leaderboard! "}
    else:
        return {"message": f"You do not have access to add users to {leaderboard_name}"}

@router.post("/remove_users_from_leaderboard", status_code=status.HTTP_202_ACCEPTED)
async def remove_from_leaderboard(token: Annotated[RegisteredUserCompact, Depends(verify_token)], user_ids: Annotated[list[int] | None, Query()], leaderboard_name: str):
    # People can remove themselves from leaderboards
    # The leaderboard owner can remove people from their leaderboard

    pass

@router.post("/edit_leaderboard_data")
async def edit_leaderboard_data(token: Annotated[RegisteredUserCompact, Depends(verify_token)], mode: Mode = None,
                                description: str = None, metric: LeaderboardMetricEnum = None, unique: bool = None, private: bool = None,
                                mod_filters: str = None,
                                score_filters: str = None,
                                beatmap_filters: str = None,
                                beatmapset_filters: str = None):
    pass