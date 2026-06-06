"""
UC-05-02 — Announce English Proficiency Exam Results (YDYO).

Creates five applicants whose proficiency-exam scores have already been
entered into the system but are still in 'Pending Publication' state, so
the YDYO Exam Results page has rows ready for the officer to publish


    APP-2024-020  Elif Yılmaz      score 75  → Pass (≥ 70)
    APP-2024-021  Can Demir        score 65  → Fail
    APP-2024-022  Ayşe Kaya        score 82  → Pass
    APP-2024-023  Mehmet Öz        score 68  → Fail
    APP-2024-024  Zeynep Arslan    score 78  → Pass

State after seeding (per applicant):
    application.status      = ENGLISH_REVIEW
    review.must_take_exam   = TRUE
    review.exam_score       = <as above>
    review.exam_date        = 2024-11-20
    review.published_at     = NULL   ← still pending publication

Idempotent: re-running unsets any prior publication and resets the
scores back to the values above. Safe to run between test cycles.

Login:
    YDYO officer:  ydyo@iyte.edu.tr / Test1234!
    Each applicant uses password: Test1234!

Run inside the backend container:
    docker compose exec backend python -m scripts.seed_uc_05_02_exam_publication

If the file is not yet in the image (only backend/app is bind-mounted),
copy it in first:
    docker compose cp backend/scripts/seed_uc_05_02_exam_publication.py \\
                     backend:/app/scripts/seed_uc_05_02_exam_publication.py
"""

import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.application import Application
from app.domain.english import EnglishProficiencyReview
from app.domain.enums import AppStatus, UserRole
from app.domain.period import ApplicationPeriod
from app.domain.program import Program
from app.domain.user import Applicant, User

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://utms:utms@localhost:5432/utms"
)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

SHARED_PASSWORD = "Test1234!"
PROGRAM_CODE = "CE"
PERIOD_LABEL = "2025-2026 Spring"
EXAM_DATE = date(2024, 11, 20)
EXAM_TYPE = "IZTECH_EXAM"

# Names + scores mirror the Figma mockup.
CASES = [
    {"tracking_number": "APP-2024-020", "email": "uc0502.elif@seed.iyte.edu.tr",   "first_name": "Elif",   "last_name": "Yılmaz",  "national_id": "50200000001", "score": 75},
    {"tracking_number": "APP-2024-021", "email": "uc0502.can@seed.iyte.edu.tr",    "first_name": "Can",    "last_name": "Demir",   "national_id": "50200000002", "score": 65},
    {"tracking_number": "APP-2024-022", "email": "uc0502.ayse@seed.iyte.edu.tr",   "first_name": "Ayşe",   "last_name": "Kaya",    "national_id": "50200000003", "score": 82},
    {"tracking_number": "APP-2024-023", "email": "uc0502.mehmet@seed.iyte.edu.tr", "first_name": "Mehmet", "last_name": "Öz",      "national_id": "50200000004", "score": 68},
    {"tracking_number": "APP-2024-024", "email": "uc0502.zeynep@seed.iyte.edu.tr", "first_name": "Zeynep", "last_name": "Arslan",  "national_id": "50200000005", "score": 78},
]


async def _get_program(db: AsyncSession) -> Program:
    p = await db.scalar(select(Program).where(Program.code == PROGRAM_CODE))
    if p is None:
        raise RuntimeError(f"Program {PROGRAM_CODE} not found. Run `python -m scripts.seed` first.")
    return p


async def _get_period(db: AsyncSession) -> ApplicationPeriod:
    pe = await db.scalar(select(ApplicationPeriod).where(ApplicationPeriod.label == PERIOD_LABEL))
    if pe is None:
        raise RuntimeError(f"Period '{PERIOD_LABEL}' not found. Run `python -m scripts.seed` first.")
    return pe


async def _upsert_user(db: AsyncSession, spec: dict) -> Applicant:
    user = await db.scalar(select(User).where(User.email == spec["email"]))
    if user is not None:
        applicant = await db.scalar(select(Applicant).where(Applicant.id == user.id))
        return applicant

    uid = uuid.uuid4()
    db.add(
        User(
            id=uid,
            email=spec["email"],
            password_hash=pwd_ctx.hash(SHARED_PASSWORD),
            role=UserRole.APPLICANT,
            first_name=spec["first_name"],
            last_name=spec["last_name"],
            is_active=True,
            is_verified=True,
        )
    )
    db.add(
        Applicant(
            id=uid,
            national_id=spec["national_id"],
            date_of_birth=date(2001, 1, 1),
            identity_verified=True,
        )
    )
    await db.flush()
    return await db.scalar(select(Applicant).where(Applicant.id == uid))


async def _upsert_application_and_review(
    db: AsyncSession,
    applicant: Applicant,
    program: Program,
    period: ApplicationPeriod,
    spec: dict,
) -> None:
    app = await db.scalar(
        select(Application).where(Application.tracking_number == spec["tracking_number"])
    )
    if app is None:
        app = Application(
            applicant_id=applicant.id,
            program_id=program.id,
            period_id=period.id,
            status=AppStatus.ENGLISH_REVIEW,
            tracking_number=spec["tracking_number"],
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(app)
        await db.flush()
    else:
        app.status = AppStatus.ENGLISH_REVIEW

    review = await db.scalar(
        select(EnglishProficiencyReview).where(
            EnglishProficiencyReview.application_id == app.id
        )
    )
    if review is None:
        review = EnglishProficiencyReview(application_id=app.id)
        db.add(review)

    review.reviewer_id = None
    review.approved = None
    review.must_take_exam = True
    review.exam_type = EXAM_TYPE
    review.exam_score = Decimal(str(spec["score"]))
    review.exam_date = EXAM_DATE
    review.notes = "Routed to YDYO proficiency exam — score recorded, pending publication."
    review.reviewed_at = datetime.now(timezone.utc)
    review.published_at = None
    review.published_by = None
    await db.flush()


async def seed(db: AsyncSession) -> None:
    print("UC-05-02 — Announce English Proficiency Exam Results")
    print("=" * 60)

    program = await _get_program(db)
    period = await _get_period(db)
    print(f"Using program: {program.code} — {program.name}")
    print(f"Using period:  {period.label}")
    print()
    print("Seeding 5 applicants in 'Pending Publication' state:")

    for spec in CASES:
        applicant = await _upsert_user(db, spec)
        await _upsert_application_and_review(db, applicant, program, period, spec)
        print(f"  [+] {spec['tracking_number']:14} {spec['first_name']:8} {spec['last_name']:8}  score={spec['score']}")

    await db.commit()
    print()
    print("Done. Open the YDYO Exam Results tab to preview and publish.")
    print("Log in as YDYO:  ydyo@iyte.edu.tr / Test1234!")


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        try:
            await seed(session)
        except Exception:
            await session.rollback()
            raise
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
