"""
Methods in here access, create, and update tag information.
"""
import datetime
from typing import List
from sqlalchemy import select, func, exists
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database.models import RegisteredUser, RegisteredUserTag, Tags

def create_tag(session: Session, owner: int, tag: str) -> bool:
    """
    Creates a new record in the database that represents a tag
    """
    try:
        new_tag = Tags(tag_name=tag, tag_owner=owner, date_created=datetime.datetime.now())
        session.add(new_tag)
    except Exception as e:
        print(e)
        print("SOMETHING WENT WRONG IN TAGS")
        return False

    new_user_tag = RegisteredUserTag(user_id=owner, tag=tag, mod=True, date_added=datetime.datetime.now())
    session.merge(new_user_tag)
    session.commit()
    return True

# TODO
def delete_tag(session: Session, tag: str) -> bool:
    """
    Deletes a record in the Tags table
    """
    pass

def add_tags(session: Session, user_ids: List[int], tag: str) -> bool:
    """
    Assign tags to a list of users
    """
    if isinstance(user_ids, int):
        user_ids = [user_ids]

    stmt = select(RegisteredUser.user_id).filter(RegisteredUser.user_id.in_(user_ids))
    registered_ids = session.execute(stmt).scalars().all()
    #registered_profiles = session.query(RegisteredUser).filter(RegisteredUser.user_id.in_(user_ids)).all()
    #registered_ids = [user.user_id for user in registered_profiles]

    not_registered = list(set(user_ids) - set(registered_ids))
    if len(not_registered) > 0:
        print('The user_ids: [%s] are not registered' % ', '.join(str(x) for x in not_registered))
        print('No action taken')
        return False

    try:
        for user_id in user_ids:
            session.merge(RegisteredUserTag(user_id=user_id, tag=tag, mod=False, date_added=datetime.datetime.now()))
        session.commit()
        return True
    except IntegrityError as e:
        session.commit()
        print(e.orig)
        print('No action taken')
        return False

# TODO
def remove_tags(session: Session, user_ids: List[int], tag: str) -> bool:
    """
    Removes the specified tag from a list of users
    """
    pass

# Add moderators to a tag
def add_moderators(session: Session, user_ids: List[int], tag: str) -> bool:
    """
    Adds moderators to a list of users for a tag
    """
    stmt = select(RegisteredUserTag).filter(RegisteredUserTag.tag == tag).filter(RegisteredUserTag.user_id.in_(user_ids))
    user_tags = session.scalars(stmt).all()

    for user in user_tags:
        user.mod = True
    session.commit()
    return True

def get_ids_from_tag(session: Session, group: str or List[int]) -> List[int] or None:
    """
    Given a tag, return all user_ids in that tag
    """
    if isinstance(group, list):
        return group
    stmt = select(RegisteredUserTag.user_id)
    if isinstance(group, str):
        stmt = stmt.filter(RegisteredUserTag.tag == group)
    return session.scalars(stmt).all()

# Returns the number of tags and the number of people in tags
def count_tags(session: Session):
    """
    Return the number of tags and the number of tag->user relationships
    """
    stmt = select(func.count(Tags.tag_name))
    stmt2 = select(func.count(RegisteredUserTag.user_id))
    return session.scalars(stmt).one(), session.scalars(stmt2).one()

if __name__ == '__main__':
    from database.ORM import ORM
    orm = ORM()
    # create_tag(orm.sessionmaker(), owner=10651409, tag='OR')
    add_moderators(orm.sessionmaker(), user_ids=[617104], tag='OR')