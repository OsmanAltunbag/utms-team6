"""
Seed script — creates one test user for every role so each dashboard
in the UI can be exercised end-to-end.

All accounts share the same password (so testing is painless):

    Password:  Test1234!

Run inside the backend container:

    docker compose exec backend python -m scripts.seed_test_roles

Idempotent — re-running just skips already-existing users.
"""

import asyncio
import os
import sys
import uuid
from datetime import date

# Allow running as `python -m scripts.seed_test_roles` from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.enums import UserRole
from app.domain.user import Applicant, Staff, User

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://utms:utms@localhost:5432/utms"
)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

SHARED_PASSWORD = "Test1234!"

# One user per role. Staff roles also get a Staff profile row.
TEST_USERS = [
    {
        "email": "applicant@iyte.edu.tr",
        "first_name": "Test",
        "last_name": "Applicant",
        "role": UserRole.APPLICANT,
        "applicant": {
            "national_id": "10000000001",
            "date_of_birth": date(2000, 1, 1),
            "identity_verified": True,
        },
    },
    {
        "email": "studentaffairs@iyte.edu.tr",
        "first_name": "Student",
        "last_name": "Affairs",
        "role": UserRole.STUDENT_AFFAIRS,
        "staff": {"department": "Student Affairs", "title": "Officer"},
    },
    {
        "email": "commission@iyte.edu.tr",
        "first_name": "Transfer",
        "last_name": "Commission",
        "role": UserRole.TRANSFER_COMMISSION,
        "staff": {"department": "Computer Engineering", "title": "Commission Member"},
    },
    {
        "email": "ydyo@iyte.edu.tr",
        "first_name": "YDYO",
        "last_name": "Officer",
        "role": UserRole.YDYO,
        "staff": {"department": "School of Foreign Languages", "title": "English Coordinator"},
    },
    {
        "email": "dean@iyte.edu.tr",
        "first_name": "Dean",
        "last_name": "Office",
        "role": UserRole.DEAN_OFFICE,
        "staff": {"department": "Faculty of Engineering", "title": "Dean"},
    },
    {
        "email": "admin2@iyte.edu.tr",
        "first_name": "Second",
        "last_name": "Admin",
        "role": UserRole.SYSTEM_ADMIN,
        "staff": {"department": "IT", "title": "System Administrator"},
    },
]


async def seed(session: AsyncSession) -> None:
    print(f"\nShared password for every account: {SHARED_PASSWORD}\n")

    for spec in TEST_USERS:
        existing = await session.scalar(select(User).where(User.email == spec["email"]))
        if existing:
            print(f"  [skip] {spec['role'].value:<22} {spec['email']}")
            continue

        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email=spec["email"],
            password_hash=pwd_ctx.hash(SHARED_PASSWORD),
            role=spec["role"],
            first_name=spec["first_name"],
            last_name=spec["last_name"],
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()

        if "applicant" in spec:
            session.add(Applicant(id=user_id, **spec["applicant"]))
        if "staff" in spec:
            session.add(Staff(id=user_id, **spec["staff"]))

        await session.flush()
        print(f"  [+]    {spec['role'].value:<22} {spec['email']}")

    await session.commit()


async def main() -> None:
    print("UTMS — Test Role Seed")
    print("=====================")

    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        await seed(session)

    await engine.dispose()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
