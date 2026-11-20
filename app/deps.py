import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .core.database import get_db
from .model.models import User
from .security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        user_id = decode_token(token)
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized
    
    user = db.get(User, user_id)

    if not user:
        raise unauthorized
    
    return user


def require_organizer(user: User = Depends(get_current_user)) -> User:
    if not user.is_organizer:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Organizer access required")
    
    return user
