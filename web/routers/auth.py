from fastapi import APIRouter, Depends, status, Query
from starlette.responses import RedirectResponse
from typing import Optional, Annotated
from web.dependencies import RegisteredUserCompact, verify_token
from database.ORM import ORM
from database.models import RegisteredUser
from database.scoreService import get_user_scores
from database.tagService import create_tag
from database.util import parse_score_filters
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

@router.get('/scores', tags=['auth'])
def get_score(beatmap_id: int, user_id: int, mode: Mode = 'osu', filters: Optional[str] = None, metric: str = 'pp'):
    """
    Fetches a user's scores on a beatmap
    """
    filters = parse_score_filters(mode, filters)
    session = orm.sessionmaker()
    a = get_user_scores(session, beatmap_id, user_id, mode, filters, metric)
    session.close()
    return {"scores": a}

@router.post("/initial_fetch_self", status_code=status.HTTP_202_ACCEPTED)
def initial_fetch(token: Annotated[RegisteredUserCompact, Depends(verify_token)], catch_converts: Annotated[ bool , Query(description='Fetch ctb converts?')] = False):
    """
    Adds the authenticated user to the fetch queue
    """
    from web.webapi import tq

    # See if they have 2 days on catch playtime
    if token['catch_playtime'] < 172800:
        catch_converts = False
    if tq.enqueue(token['user_id'], catch_converts):
        return {'message': 'Success! You have been added to the queue.'}
    return {'message': 'Something went wrong. Relog and try again if your scores have not already been fetched.'}

# TODO: Add the tag amount check in the api logic, not at the operation layer.
@router.post("/create_new_tag", status_code=status.HTTP_201_CREATED)
def create_new_tag(token: Annotated[RegisteredUserCompact, Depends(verify_token)], tag_name: str):
    session = orm.sessionmaker()
    success = create_tag(session, token['user_id'], tag_name)
    session.close()
    if success:
        return {"message": "Success!"}
    return {"message": "Something went wrong. Maybe the tag already exists or you have more than 4 tags."}

# TODO
@router.post("/delete_tag", status_code=status.HTTP_202_ACCEPTED)
def delete_tag(token: Annotated[RegisteredUserCompact, Depends(verify_token)], tag_name: str):
    pass

# TODO
@router.post("/add_users_to_tag", status_code=status.HTTP_201_CREATED)
def add_users_to_tag(token: Annotated[RegisteredUserCompact, Depends(verify_token)], tag_name: str, user_ids: Annotated[list[int] | None, Query()]):
    pass

# TODO
@router.post("/remove_users_from_tag", status_code=status.HTTP_202_ACCEPTED)
def remove_users_from_tag(token: Annotated[RegisteredUserCompact, Depends(verify_token)], tag_name: str, user_ids: Annotated[list[int] | None, Query()]):
    pass

# TODO
@router.post("/add_tag_mods", status_code=status.HTTP_202_ACCEPTED)
def add_mods_to_tag(token: Annotated[RegisteredUserCompact, Depends(verify_token)], tag_name: str, user_ids: Annotated[list[int] | None, Query()]):
    pass

# TODO
@router.post("/remove_tag_mods", status_code=status.HTTP_202_ACCEPTED)
def add_mods_to_tag(token: Annotated[RegisteredUserCompact, Depends(verify_token)], tag_name: str, user_ids: Annotated[list[int] | None, Query()]):
    pass