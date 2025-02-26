from typing import Annotated
from fastapi import APIRouter, Query, status, Response
from sqlalchemy import select
from database.ORM import ORM
import database.userService as userService
from database.models import RegisteredUser, LeaderboardSpot
from database.leaderboardService import recalculate_user

router = APIRouter()
orm = ORM()

@router.post("/add_user/{user_id}", status_code=status.HTTP_201_CREATED)
async def add_registered_user(user_id: int, response: Response):
    """
    Register a new user
    """
    success, user = userService.register_user(orm.sessionmaker(), user_id)
    if success:
        return {"message": "%s registered to database" % str(user_id)}
    else:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "%s is already registered to the database" % str(user_id)}

@router.post("/initial_fetch_user/{user_id}", status_code=status.HTTP_301_MOVED_PERMANENTLY)
async def initial_fetch_user(user_id: int, catch_converts: bool | None):
    """
    Moved to /fetch/initial_fetch_user
    """
    return {"message": "Moved to /fetch/initial_fetch_user"}

@router.get("/test", status_code=status.HTTP_200_OK)
def test():
    return {"message": "hello from /admin/test (hopefully)"}

@router.post("/update_player")
async def update_players(user_ids: Annotated[list[int] | None, Query()]):
    session = orm.sessionmaker()

    for user_id in user_ids:
        # Get all leaderboards user is in
        stmt = select(LeaderboardSpot).filter(LeaderboardSpot.user_id == user_id)
        leaderboard_spots = session.scalars(stmt).all()
        for leaderboard_spot in leaderboard_spots:
            await recalculate_user(session, user_id, leaderboard_spot.leaderboard_id)
    return {"message": "Success"}