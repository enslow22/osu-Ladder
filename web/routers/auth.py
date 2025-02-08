import datetime
import sqlalchemy.exc
from fastapi import APIRouter, Depends, status, Query
from starlette.responses import RedirectResponse
from typing import Optional, Annotated
from web.dependencies import RegisteredUserCompact, verify_token
from sqlalchemy import select, delete, func
from database.ORM import ORM
from database.models import RegisteredUser, Tags, RegisteredUserTag
from database.scoreService import get_user_scores
from database.tagService import create_tag
from database.util import parse_score_filters, parse_mod_filters
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
def get_score(beatmap_id: int, user_id: int, mode: Mode = 'osu', filters: Optional[str] = None, mods: Optional[str] = None, metric: str = 'pp'):
    """
    Fetches a user's scores on a beatmap
    """
    filters = parse_score_filters(mode, filters)
    mods = parse_mod_filters(mode, filters)
    session = orm.sessionmaker()
    a = get_user_scores(session, beatmap_id, user_id, mode, filters, mods, metric)
    session.close()
    return {"scores": a}

@router.post("/initial_fetch_self", status_code=status.HTTP_202_ACCEPTED)
def initial_fetch(token: Annotated[RegisteredUserCompact, Depends(verify_token)], catch_converts: Annotated[ bool , Query(description='Fetch ctb converts?')] = False):
    """
    Moved to /fetch/initial_fetch_self
    """
    pass

@router.post("/create_new_tag", status_code=status.HTTP_201_CREATED)
def create_new_tag(token: Annotated[RegisteredUserCompact, Depends(verify_token)], tag_name: str):
    session = orm.sessionmaker()
    stmt = select(Tags).filter(Tags.tag_name == tag_name)
    a = session.execute(stmt).first()
    # Tag already exists
    if a:
        return {"message": "The tag %s already exists!" % tag_name}

    # User has max tags
    stmt = select(func.count(Tags.tag_name)).filter(Tags.tag_owner == token['user_id'])
    if session.scalar(stmt) >= 4:
        return {"message": "You may have up to 4 tags. Please contact enslow if you need more"}
    success = create_tag(session, token['user_id'], tag_name)
    session.close()

    if success:
        return {"message": "Success! %s has been created" % tag_name}
    return {"message": "Something went wrong, and I am not sure what it is."}

@router.post("/delete_tag", status_code=status.HTTP_202_ACCEPTED)
def delete_tag(token: Annotated[RegisteredUserCompact, Depends(verify_token)], tag_name: str):
    # Delete the tag
    stmt = select(Tags).where(token['user_id'] == Tags.tag_owner).filter(tag_name==Tags.tag_name)

    session = orm.sessionmaker()
    tag_object = session.scalar(stmt)
    if not tag_object:
        return {"message": "%s does not exist" % tag_name}
    session.delete(tag_object)
    # If no tags were deleted, we can stop here
    if len(list(session.deleted)) == 0:
        return {"message": "%s has not been deleted. You are not the owner of %s" % (tag_name, tag_name)}
    session.commit()

    return {"message": "%s has been deleted" % tag_name}

@router.post("/add_users_to_tag", status_code=status.HTTP_201_CREATED)
def add_users_to_tag(token: Annotated[RegisteredUserCompact, Depends(verify_token)], tag_name: str, user_ids: Annotated[list[int] | None, Query()]):
    # Check if the user is a moderator
    session = orm.sessionmaker()
    a = session.get(RegisteredUserTag, (token['user_id'], tag_name))
    if not a or not a.mod:
        return {"message": "You must be a moderator of the group to add members."}

    now = datetime.datetime.now()
    num_added = 0
    already_in_tag = []
    # Add the users to the tag
    for user_id in user_ids:
        try:
            new_tag = RegisteredUserTag(user_id=user_id, tag=tag_name, mod=False, date_added=now)
            session.add(new_tag)
            session.commit()
        except sqlalchemy.exc.IntegrityError:
            already_in_tag.append(str(user_id))
            session.rollback()
            continue
        num_added += 1
    session.close()

    info_str = '' if len(already_in_tag) == 0 else " The users %s were not added because they are not registered or because they are already in the tag." % (str(already_in_tag))
    return {"message": "Added %s users to %s.%s" % (str(num_added), tag_name, info_str)}

@router.post("/remove_users_from_tag", status_code=status.HTTP_202_ACCEPTED)
def remove_users_from_tag(token: Annotated[RegisteredUserCompact, Depends(verify_token)], tag_name: str, user_ids: Annotated[list[int] | None, Query()]):
    # Check if the user is a moderator
    session = orm.sessionmaker()
    a = session.get(RegisteredUserTag, (token['user_id'], tag_name))
    if not a or not a.mod:
        return {"message": "You must be a moderator of the group to remove members."}

    stmt = select(func.count(RegisteredUserTag.user_id)).where(RegisteredUserTag.tag == tag_name).where(RegisteredUserTag.user_id.in_(user_ids)).where(RegisteredUserTag.mod == False)
    number_users = session.execute(stmt).scalar()
    stmt = delete(RegisteredUserTag).where(RegisteredUserTag.tag == tag_name).where(RegisteredUserTag.user_id.in_(user_ids)).where(RegisteredUserTag.mod == False)
    session.execute(stmt)
    session.commit()
    session.close()
    return {"message": "%s users were deleted from %s" % (str(number_users), tag_name)}

@router.post("/add_tag_mods", status_code=status.HTTP_202_ACCEPTED)
def add_mods_to_tag(token: Annotated[RegisteredUserCompact, Depends(verify_token)], tag_name: str, user_ids: Annotated[list[int] | None, Query()]):
    # Check if user is the owner of the tag
    session = orm.sessionmaker()
    stmt = select(Tags).filter(tag_name==Tags.tag_name).filter(token['user_id'] == Tags.tag_owner)
    if not session.execute(stmt).first():
        return {"message: You are not the owner of %s, or it does not exist" % tag_name}
    # Add mods to the tag here.

    num_updated = 0
    not_in_tag = []
    for user_id in user_ids:
        user_tag = session.get(RegisteredUserTag, (user_id, tag_name))
        if user_tag:
            if user_tag.mod:
                continue
            user_tag.mod = True
            num_updated += 1
        else:
            not_in_tag.append(str(user_id))
    session.commit()
    session.close()
    info_str = '' if len(not_in_tag) == 0 else " To add %s, add them to the group first." % ' '.join(not_in_tag)
    return {"message": "Success %s have been given mod for %s.%s" % (str(num_updated), tag_name, info_str)}

@router.post("/remove_tag_mods", status_code=status.HTTP_202_ACCEPTED)
def remove_mods_from_tag(token: Annotated[RegisteredUserCompact, Depends(verify_token)], tag_name: str, user_ids: Annotated[list[int] | None, Query()]):
    # Check if user is the owner of the tag
    session = orm.sessionmaker()
    stmt = select(Tags).filter(tag_name == Tags.tag_name).filter(token['user_id'] == Tags.tag_owner)
    if not session.execute(stmt).first():
        return {"message": "You are not the owner of %s, or it does not exist" % tag_name}

    if token['user_id'] in user_ids:
        return {"message": "You can not remove yourself as mod."}

    stmt = select(RegisteredUserTag).filter(RegisteredUserTag.user_id.in_(user_ids)).filter(RegisteredUserTag.mod)
    remove_mods = session.scalars(stmt).all()

    num_removed = 0
    for user in remove_mods:
        session.delete(user)
        num_removed += 1
    session.commit()
    session.close()
    return {"message": "Success %s users have been removed as mod for %s" % (str(num_removed), tag_name)}