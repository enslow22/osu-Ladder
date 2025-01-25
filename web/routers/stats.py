from fastapi import APIRouter
from database.ORM import ORM
from database.models import RegisteredUser

router = APIRouter()
orm = ORM()

@router.get('/', tags=['auth'])
def get_user(user_id: int):
    """
    Fetches a user from the database from their user_id
    """
    return {"user": orm.session.get(RegisteredUser, user_id)}