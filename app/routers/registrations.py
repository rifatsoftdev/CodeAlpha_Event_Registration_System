from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..deps import get_current_user
from ..model.models import Registration, User, utcnow
from ..schema.schemas import RegistrationOut


router = APIRouter(prefix="/registrations", tags=["registrations"])


def _mine_or_404(db: Session, reg_id: int, user: User) -> Registration:
    reg = db.get(Registration, reg_id)
    
    if not reg or reg.user_id != user.id:  # don't reveal other users' registrations
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Registration not found"
        )
    
    return reg


@router.get("/me", response_model=List[RegistrationOut])
def my_registrations(
    status_filter: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    q = select(Registration).where(Registration.user_id == user.id).order_by(Registration.created_at.desc())
    
    if status_filter:
        q = q.where(Registration.status == status_filter)

    return list(db.scalars(q))


@router.get("/{reg_id}", response_model=RegistrationOut)
def get_registration(reg_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _mine_or_404(db, reg_id, user)


@router.delete("/{reg_id}", response_model=RegistrationOut)
def cancel_registration(reg_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Cancel (soft delete): keeps the record, frees the spot."""
    reg = _mine_or_404(db, reg_id, user)

    if reg.status == Registration.CANCELLED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Registration is already cancelled"
        )
    
    reg.status, reg.cancelled_at = Registration.CANCELLED, utcnow()
    db.commit()

    return reg

