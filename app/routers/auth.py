import hashlib
import os
import secrets
import smtplib
from datetime import timedelta
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..deps import get_current_user
from ..model.models import PasswordReset, User, utcnow
from ..schema.schemas import PasswordResetConfirm, PasswordResetRequest, SignupIn, Token, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _email_reset_link(destination: str, token: str) -> None:
    host = os.getenv("SMTP_HOST")
    sender = os.getenv("EMAIL_FROM")

    if not host or not sender:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Password reset email is not configured. Please contact the event organizer.",
        )

    base_url = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
    message = EmailMessage()
    message["Subject"] = "Reset your EventHub password"
    message["From"] = sender
    message["To"] = destination
    message.set_content(
        f"Use this link within 30 minutes to reset your password:\n\n"
        f"{base_url}/reset-password?token={token}\n\n"
        "If you did not request this, you can ignore this email."
    )

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")

    with smtplib.SMTP(host, port, timeout=10) as client:
        client.ehlo()

        if os.getenv("SMTP_STARTTLS", "true").lower() == "true":
            client.starttls()
            client.ehlo()

        if username:
            client.login(username, password or "")
        client.send_message(message)


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(data: SignupIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.username == data.username)):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Username already taken"
        )
    
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password)
    )

    db.add(user)
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Username already taken"
        )

    return user


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == form.username))

    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect username or password"
        )
    
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/password-reset/request")
def request_password_reset(data: PasswordResetRequest, db: Session = Depends(get_db)):
    if not os.getenv("SMTP_HOST") or not os.getenv("EMAIL_FROM"):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Password reset email is not configured. Please contact the event organizer.",
        )
    
    email = data.email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))

    if not user or not user.email:
        return {"message": "If an account uses that email, reset instructions will be sent."}

    now = utcnow()

    recent = db.scalar(
        select(PasswordReset.id)
        .where(PasswordReset.user_id == user.id, PasswordReset.created_at > now - timedelta(minutes=1))
        .limit(1)
    )

    if recent:
        return {"message": "If an account uses that email, reset instructions will be sent."}

    raw_token = secrets.token_urlsafe(32)
    reset = PasswordReset(
        user_id=user.id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=now + timedelta(minutes=30),
    )

    db.add(reset)

    try:
        _email_reset_link(user.email, raw_token)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as error:
        db.rollback()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "We could not send the reset email. Please try again later.",
        ) from error
    
    return {"message": "If an account uses that email, reset instructions will be sent."}


@router.post("/password-reset/confirm")
def confirm_password_reset(data: PasswordResetConfirm, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(data.token.encode()).hexdigest()
    reset = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == token_hash))
    now = utcnow()

    if not reset or reset.used_at or reset.expires_at <= now:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This reset link is invalid or has expired."
        )

    user = reset.user
    user.hashed_password = hash_password(data.new_password)
    reset.used_at = now

    for other_reset in user.password_resets:
        if other_reset.id != reset.id and not other_reset.used_at:
            other_reset.used_at = now
    
    db.commit()

    return {"message": "Password updated. You can now sign in."}


