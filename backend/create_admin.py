import os
from getpass import getpass

from backend.db.database import SessionLocal
from backend.models import User
from backend.auth.security import hash_password


def create_admin():
    db = SessionLocal()

    try:
        username = input("Admin username: ").strip()
        email = input("Admin email: ").strip()
        password = getpass("Admin password: ")
        confirm_password = getpass("Confirm password: ")

        if len(username) < 3:
            print("Username must contain at least 3 characters.")
            return

        if len(password) < 8 or len(password.encode("utf-8")) > 72:
            print("Password must be at least 8 characters and at most 72 bytes.")
            return

        if password != confirm_password:
            print("Passwords do not match.")
            return

        existing = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing:
            print("Username or email already exists.")
            return

        admin = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
        )

        db.add(admin)
        db.commit()

        print(f"Admin account '{username}' created successfully.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()