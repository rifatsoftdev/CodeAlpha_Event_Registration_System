from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..deps import get_current_user, require_organizer
from ..model.models import Event, Registration, User, utcnow
from ..schema.schemas import (EventCreate, EventOut, EventUpdate, RegistrationForm, RegistrationOut)



router = APIRouter(prefix="/events", tags=["events"])


def _with_spots(db: Session, events: List[Event]) -> List[Event]:
    """Attach `spots_left` (capacity - confirmed registrations) to each event."""
    if not events:
        return events
    
    rows = db.execute(
        select(Registration.event_id, func.count())
        .where(Registration.event_id.in_([e.id for e in events]),
               Registration.status == Registration.CONFIRMED)
        .group_by(Registration.event_id)
    ).all()

    taken = dict(rows)

    for e in events:
        e.spots_left = max(e.capacity - taken.get(e.id, 0), 0)

    return events


def _get_event_or_404(db: Session, event_id: int) -> Event:
    event = db.get(Event, event_id)

    if not event:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Event not found"
        )
    
    return event


def _owned_event(db: Session, event_id: int, user: User) -> Event:
    event = _get_event_or_404(db, event_id)

    if event.organizer_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You can only manage your own events"
        )
    
    return event


# ---------- public ----------
@router.get("", response_model=List[EventOut])
def list_events(
    upcoming: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = select(Event).order_by(Event.start_time)
    if upcoming:
        q = q.where(Event.start_time >= utcnow())

    return _with_spots(db, list(db.scalars(q.offset(skip).limit(limit))))


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    return _with_spots(db, [_get_event_or_404(db, event_id)])[0]


# ---------- registration form ----------
@router.post("/{event_id}/register", response_model=RegistrationOut, status_code=status.HTTP_201_CREATED)
def register(
    event_id: int,
    form: RegistrationForm,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Row lock (PostgreSQL) so two people can't grab the last spot at once.
    event = db.scalar(select(Event).where(Event.id == event_id).with_for_update())

    if not event:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Event not found"
        )
    
    if event.start_time <= utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This event has already started")

    reg = db.scalar(select(Registration).where(
        Registration.user_id == user.id,
        Registration.event_id == event_id)
    )

    if reg and reg.status == Registration.CONFIRMED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "You are already registered for this event"
        )

    confirmed = db.scalar(select(func.count()).select_from(Registration).where(
        Registration.event_id == event_id, Registration.status == Registration.CONFIRMED))
    
    if confirmed >= event.capacity:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This event is full"
        )

    if reg:  # re-registering after a cancellation
        reg.full_name, reg.phone, reg.notes = form.full_name, form.phone, form.notes
        reg.status, reg.cancelled_at = Registration.CONFIRMED, None
    else:
        reg = Registration(user_id=user.id, event_id=event_id, **form.model_dump())
        db.add(reg)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "You are already registered for this event"
        )
    
    return reg


# ---------- event owner management ----------
@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(data: EventCreate, user: User = Depends(require_organizer), db: Session = Depends(get_db)):
    event = Event(**data.model_dump(), organizer_id=user.id)
    db.add(event)
    db.commit()

    return _with_spots(db, [event])[0]


@router.patch("/{event_id}", response_model=EventOut)
def update_event(
    event_id: int,
    data: EventUpdate,
    user: User = Depends(require_organizer),
    db: Session = Depends(get_db)
):
    event = _owned_event(db, event_id, user)

    updates = data.model_dump(exclude_unset=True)

    if "capacity" in updates:
        confirmed = db.scalar(
            select(func.count()).select_from(Registration).where(
                Registration.event_id == event_id,
                Registration.status == Registration.CONFIRMED,
            )
        )
        if updates["capacity"] < confirmed:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"capacity cannot be less than the {confirmed} confirmed registrations",
            )

    for k, v in updates.items():
        setattr(event, k, v)

    if event.end_time <= event.start_time:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "end_time must be after start_time"
        )
    
    db.commit()

    return _with_spots(db, [event])[0]


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, user: User = Depends(require_organizer), db: Session = Depends(get_db)):
    db.delete(_owned_event(db, event_id, user))
    db.commit()


@router.get("/{event_id}/registrations", response_model=List[RegistrationOut])
def event_attendees(
    event_id: int,
    user: User = Depends(require_organizer),
    db: Session = Depends(get_db)
):
    _owned_event(db, event_id, user)

    return list(
        db.scalars(select(Registration).where(
            Registration.event_id == event_id
        ).order_by(Registration.created_at)))
