"""
Seed script — populates the database with default programs and a test system admin.
Run from the backend/ directory:

    python -m scripts.seed

Requires DATABASE_URL env var (or .env file).
"""

import asyncio
import os
import sys
import uuid

# Allow running as `python -m scripts.seed` from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.enums import UserRole
from app.domain.program import Program
from app.domain.user import Applicant, Staff, User

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://utms:utms@localhost:5432/utms"
)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

DEFAULT_PROGRAMS = [
    {
        "name": "Computer Engineering",
        "code": "CE",
        "faculty": "Faculty of Engineering",
        "quota": 5,
        "min_gpa": "2.50",
    },
    {
        "name": "Electrical and Electronics Engineering",
        "code": "EEE",
        "faculty": "Faculty of Engineering",
        "quota": 5,
        "min_gpa": "2.50",
    },
    {
        "name": "Mechanical Engineering",
        "code": "ME",
        "faculty": "Faculty of Engineering",
        "quota": 5,
        "min_gpa": "2.50",
    },
    {
        "name": "Civil Engineering",
        "code": "CIVE",
        "faculty": "Faculty of Engineering",
        "quota": 5,
        "min_gpa": "2.50",
    },
    {
        "name": "Chemical Engineering",
        "code": "CHME",
        "faculty": "Faculty of Engineering",
        "quota": 5,
        "min_gpa": "2.50",
    },
    {
        "name": "Materials Science and Engineering",
        "code": "MSE",
        "faculty": "Faculty of Engineering",
        "quota": 3,
        "min_gpa": "2.50",
    },
    {
        "name": "Physics",
        "code": "PHYS",
        "faculty": "Faculty of Science",
        "quota": 3,
        "min_gpa": "2.00",
    },
    {
        "name": "Chemistry",
        "code": "CHEM",
        "faculty": "Faculty of Science",
        "quota": 3,
        "min_gpa": "2.00",
    },
    {
        "name": "Mathematics",
        "code": "MATH",
        "faculty": "Faculty of Science",
        "quota": 3,
        "min_gpa": "2.00",
    },
]

TEST_ADMIN = {
    "email": "admin@iyte.edu.tr",
    "password": "Admin1234!",
    "first_name": "System",
    "last_name": "Admin",
    "role": UserRole.SYSTEM_ADMIN,
}


async def seed(session: AsyncSession) -> None:
    # ── Programs ──────────────────────────────────────────────────────
    for prog_data in DEFAULT_PROGRAMS:
        existing = await session.scalar(
            select(Program).where(Program.code == prog_data["code"])
        )
        if existing:
            print(f"  [skip] Program {prog_data['code']} already exists")
            continue

        program = Program(
            name=prog_data["name"],
            code=prog_data["code"],
            faculty=prog_data["faculty"],
            quota=prog_data["quota"],
            min_gpa=prog_data.get("min_gpa"),
        )
        session.add(program)
        print(f"  [+] Program: {prog_data['code']} — {prog_data['name']}")

    await session.flush()

    # ── Test System Admin ─────────────────────────────────────────────
    existing_admin = await session.scalar(
        select(User).where(User.email == TEST_ADMIN["email"])
    )
    if existing_admin:
        print(f"  [skip] Admin user {TEST_ADMIN['email']} already exists")
    else:
        admin_id = uuid.uuid4()
        admin_user = User(
            id=admin_id,
            email=TEST_ADMIN["email"],
            password_hash=pwd_ctx.hash(TEST_ADMIN["password"]),
            role=TEST_ADMIN["role"],
            first_name=TEST_ADMIN["first_name"],
            last_name=TEST_ADMIN["last_name"],
            is_active=True,
            is_verified=True,
        )
        session.add(admin_user)
        await session.flush()

        admin_staff = Staff(id=admin_id, department="IT", title="System Administrator")
        session.add(admin_staff)
        print(f"  [+] Admin user: {TEST_ADMIN['email']} (password: {TEST_ADMIN['password']})")

    await session.commit()


async def main() -> None:
    print("UTMS Seed Script")
    print("================")

    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        await seed(session)

    await engine.dispose()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
