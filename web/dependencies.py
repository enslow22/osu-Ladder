import os
from datetime import timedelta, datetime
from typing import Annotated

from fastapi import Request, HTTPException, status, Header
from pydantic import BaseModel
import jwt

class RegisteredUserCompact(BaseModel):
    user_id: int
    username: str
    avatar_url: str
    apikey: str

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now() + timedelta(weeks=2)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, os.getenv('JWTSECRET'), algorithm="HS256")
    return encoded_jwt

def has_token(req: Request) -> RegisteredUserCompact | bool:
    token = req.cookies.get('session_token')
    if token is None:
        return False
    try:
        payload = jwt.decode(token, os.getenv('JWTSECRET'), algorithms="HS256")
    except jwt.InvalidTokenError:
        raise credentials_exception
    return payload

def verify_token(req: Request) -> RegisteredUserCompact:
    if req.headers.get('X-Authorization') == os.getenv('HARUHIME_KEY'):
        from database.ORM import ORM
        from database.models import RegisteredUser
        orm = ORM()
        haruhime = orm.session.get(RegisteredUser, 12231334)
        return {'user_id': haruhime.user_id, 'username': haruhime.username, 'avatar_url': haruhime.avatar_url, 'apikey': haruhime.apikey, 'catch_playtime': 172800}
    token = req.cookies.get('session_token')
    if token is None:
        raise credentials_exception
    try:
        payload = jwt.decode(token, os.getenv('JWTSECRET'), algorithms="HS256")
    except jwt.InvalidTokenError:
        raise credentials_exception
    return payload

def verify_admin(req: Request) -> RegisteredUserCompact:
    token = req.cookies.get('session_token')
    if token is None:
        raise credentials_exception
    try:
        payload = jwt.decode(token, os.getenv('JWTSECRET'), algorithms="HS256")
        admin_ids = os.getenv('ADMINS').split(',')
        if str(payload['user_id']) not in admin_ids:
            raise jwt.InvalidTokenError
    except jwt.InvalidTokenError:
        raise credentials_exception
    return payload