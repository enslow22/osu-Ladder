from fastapi import APIRouter, status, Response
from database.ORM import ORM
from database.userService import UserService
from database.models import RegisteredUser


router = APIRouter()
orm = ORM()
user_service = UserService(orm.sessionmaker())

@router.post("/add_user/{user_id}", status_code=status.HTTP_201_CREATED)
async def add_registered_user(user_id: int, response: Response):
    """
    Register a new user
    """
    if user_service.register_user(user_id=user_id, apikey=None):
        return {"message": "%s registered to database" % str(user_id)}
    else:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": "%s is already registered to the database" % str(user_id)}

@router.post("/initial_fetch_user/{user_id}", status_code=status.HTTP_202_ACCEPTED)
async def initial_fetch_user(user_id: int, catch_converts: bool | None):
    from ..webapi import tq
    session = orm.sessionmaker()
    a = session.get(RegisteredUser, user_id)
    session.close()
    if a is None:
        return {"message": "user is not registered"}
    if catch_converts is None:
        catch_converts = False
    data = ('initial_fetch', {'user_id': a.user_id, 'catch_converts': catch_converts})
    tq.enqueue(data)
    items = {"user_id": a.user_id,
             "catch_converts": catch_converts,
             "queue": tq.q.queue}
    return items

@router.get("/test", status_code=status.HTTP_200_OK)
def test():
    return {"message": "hello from /admin/test (hopefully)"}