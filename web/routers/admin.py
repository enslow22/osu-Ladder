from typing import Annotated
from fastapi import APIRouter, Query, status, Response
from database.ORM import ORM
import database.userService as userService
from database.models import RegisteredUser
from database.tagService import add_tags

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

@router.post("/add_tags_to_users/", status_code=status.HTTP_202_ACCEPTED)
async def add_tags_to_users(user_ids: Annotated[list[int] | None, Query()], tag: str):
    if not add_tags(orm.sessionmaker(), user_ids, tag):
        return {"message": "An error occurred. Make sure all users are registered."}

@router.get("/test", status_code=status.HTTP_200_OK)
def test():
    return {"message": "hello from /admin/test (hopefully)"}