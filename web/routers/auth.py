from fastapi import APIRouter, Depends, status, Query
from starlette.responses import RedirectResponse
from typing import Optional, Annotated
from web.dependencies import RegisteredUserCompact, verify_token
from database.ORM import ORM
from database.models import RegisteredUser
import database.scoreService as scoreService
from database.util import parse_score_filters

router = APIRouter()
orm = ORM()

@router.post("/logout")
async def logout(token: Annotated[RegisteredUserCompact, Depends(verify_token)]):
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

@router.get('/scores', tags=['auth'])
def get_score(beatmap_id: int, user_id: int, mode: str or int = 'osu', filters: Optional[str] = None, metric: str = 'pp'):
    filters = parse_score_filters(mode, filters)
    """
    Fetches a user's scores on a beatmap
    """
    session = orm.sessionmaker()
    a = scoreService.get_user_scores(session, beatmap_id, user_id, mode, filters, metric)
    session.close()
    return {"scores": a}

@router.post("/initial_fetch_self", status_code=status.HTTP_202_ACCEPTED)
def initial_fetch(token: Annotated[RegisteredUserCompact, Depends(verify_token)], catch_converts: Annotated[ bool , Query(description='Fetch ctb converts?')] = False):
    from web.webapi import tq
    if tq.enqueue(token['user_id'], catch_converts):
        return {'message': 'success'}
    return {'message': 'fail'}