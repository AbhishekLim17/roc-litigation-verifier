"""Command-line admin tasks.

Usage (from backend/, with the virtual environment active):
    python -m app.cli create-user --email admin@example.com --name "Admin" --role admin

The password is typed at a hidden prompt, so it never appears in shell history.
"""

import argparse
import getpass
import sys

from sqlalchemy import select

from app.database.session import get_session_factory
from app.models import User, UserRole
from app.security.passwords import hash_password, password_problems
from app.services.audit import record_audit


def create_user(email: str, full_name: str, role: UserRole, password: str) -> User:
    email = email.strip().lower()
    problems = password_problems(password)
    if problems:
        raise ValueError("Password " + "; ".join(problems))
    with get_session_factory()() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise ValueError(f"A user with email {email} already exists")
        user = User(
            email=email, full_name=full_name, role=role, password_hash=hash_password(password)
        )
        db.add(user)
        db.flush()
        record_audit(
            db,
            "user.created",
            entity_type="user",
            entity_id=str(user.id),
            details={"email": email, "role": role.value, "via": "cli"},
        )
        db.commit()
        return user


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-user", help="Create an application user")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--role", choices=[r.value for r in UserRole], default="analyst")
    args = parser.parse_args(argv)

    if args.command == "create-user":
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match.", file=sys.stderr)
            return 1
        try:
            user = create_user(args.email, args.name, UserRole(args.role), password)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Created {user.role.value} user {user.email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
