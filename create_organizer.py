"""Create an organizer account or promote one: python create_organizer.py <username> <password> [email]"""
import sys

from sqlalchemy import select

from app.core.database import Base, SessionLocal, engine
from app.model.models import User
from app.security import hash_password

Base.metadata.create_all(bind=engine)

if len(sys.argv) == 3 and sys.argv[1] == "--promote":
    username = sys.argv[2]

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        
        if not user:
            sys.exit(f"User '{username}' not found")
        if user.is_organizer:
            print(f"User '{username}' is already an organizer")
        else:
            user.is_organizer = True
            db.commit()
            print(f"Promoted existing user '{username}' to organizer")
elif len(sys.argv) < 3:
    sys.exit(__doc__)
else:
    with SessionLocal() as db:
        username, password = sys.argv[1], sys.argv[2]
        email = sys.argv[3] if len(sys.argv) > 3 else ""
        user = db.scalar(select(User).where(User.username == username))
        if user:
            user.is_organizer = True
            print(f"Promoted existing user '{username}' to organizer")
        else:
            db.add(User(username=username, email=email, hashed_password=hash_password(password), is_organizer=True))
            print(f"Created organizer '{username}'")
        db.commit()
