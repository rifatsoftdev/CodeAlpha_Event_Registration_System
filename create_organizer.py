"""Create a new organizer or promote an existing account interactively."""
from getpass import getpass

from sqlalchemy import select

from app.core.database import Base, SessionLocal, engine
from app.model.models import User
from app.security import hash_password


def main() -> None:
    Base.metadata.create_all(bind=engine)
    username = input("Organizer username: ").strip()

    if not username:
        raise SystemExit("Username cannot be empty.")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))

        if user:
            if user.is_organizer:
                print(f"'{username}' is already an organizer.")
                return
            
            confirm = input(f"Promote existing user '{username}' to organizer? [y/N]: ").strip().lower()

            if confirm not in {"y", "yes"}:
                print("No changes made.")
                return
            
            user.is_organizer = True
            db.commit()
            print(f"Promoted '{username}' to organizer.")
            return

        email = input("Organizer email: ").strip().lower()

        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            raise SystemExit("Enter a valid email address.")

        password = getpass("Password (at least 8 characters): ")

        if len(password) < 8:
            raise SystemExit("Password must be at least 8 characters.")
        
        confirmation = getpass("Confirm password: ")

        if password != confirmation:
            raise SystemExit("Passwords do not match.")

        db.add(User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            is_organizer=True,
        ))
        
        db.commit()
        print(f"Organizer account '{username}' created.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("\nCancelled.")
