"""
UC-05-01 — Approve English Proficiency (YDYO).

Creates four applicants whose applications are parked in the
ENGLISH_REVIEW stage so the YDYO officer dashboard has something
to act on. Each test case targets a different branch of the use case:

  TC-A  Strong TOEFL iBT 95              → officer should APPROVE → DEPT_EVAL
  TC-B  IELTS 6.5 (borderline)           → officer can APPROVE or REJECT
  TC-C  TOEFL iBT 55 (insufficient)      → officer should REJECT (INSUFFICIENT_SCORE)
  TC-D  YDS 70 from 2020 (expired)       → officer should REJECT (EXPIRED_EXAM)

Idempotent: re-running the script resets each of these four applications
back to ENGLISH_REVIEW (clearing any prior review decision) so the test
can be repeated without manual DB surgery.

Login credentials for every test applicant:

    Password:  Test1234!

To act on them, log in as the YDYO officer seeded by seed_test_roles.py:

    Email:     ydyo@iyte.edu.tr
    Password:  Test1234!

Run inside the backend container:

    docker compose exec backend python -m scripts.seed_uc_05_01_english_review

If the file isn't in the image yet (only backend/app is bind-mounted),
copy it in first:

    docker compose cp backend/scripts/seed_uc_05_01_english_review.py \\
                     backend:/app/scripts/seed_uc_05_01_english_review.py
"""

import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timezone

# Allow `python -m scripts.seed_uc_05_01_english_review` from /app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.application import Application
from app.domain.document import Document
from app.domain.english import EnglishProficiencyReview
from app.domain.enums import AppStatus, DocStatus, DocType, UserRole
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

# Reuse canonical fixtures from the base seed.
PROGRAM_CODE = "CE"
PERIOD_LABEL = "2025-2026 Spring"

# ── Test cases ─────────────────────────────────────────────────────────
# Each case describes a different expected YDYO decision path.

CASES = [
    {
        "label": "TC-A  Strong TOEFL iBT 95         → APPROVE",
        "email": "uc0501.toefl95@seed.iyte.edu.tr",
        "first_name": "Aslı",
        "last_name": "Yılmaz",
        "national_id": "50100000001",
        "tracking_number": "APP-UC0501-A",
        "cert": {
            "exam_type": "TOEFL_IBT",
            "score": 95,
            "issued_on": "2024-09-15",
            "expires_on": "2026-09-15",
            "filename": "toefl_ibt_95_2024.pdf",
        },
    },
    {
        "label": "TC-B  IELTS 6.5 (borderline)      → APPROVE or REJECT",
        "email": "uc0501.ielts65@seed.iyte.edu.tr",
        "first_name": "Burak",
        "last_name": "Demir",
        "national_id": "50100000002",
        "tracking_number": "APP-UC0501-B",
        "cert": {
            "exam_type": "IELTS",
            "score": 6.5,
            "issued_on": "2024-03-10",
            "expires_on": "2026-03-10",
            "filename": "ielts_6_5_2024.pdf",
        },
    },
    {
        "label": "TC-C  TOEFL iBT 55 (insufficient) → REJECT (INSUFFICIENT_SCORE)",
        "email": "uc0501.toefl55@seed.iyte.edu.tr",
        "first_name": "Ceren",
        "last_name": "Koç",
        "national_id": "50100000003",
        "tracking_number": "APP-UC0501-C",
        "cert": {
            "exam_type": "TOEFL_IBT",
            "score": 55,
            "issued_on": "2024-06-01",
            "expires_on": "2026-06-01",
            "filename": "toefl_ibt_55_2024.pdf",
        },
    },
    {
        "label": "TC-D  YDS 70 expired 2020         → REJECT (EXPIRED_EXAM)",
        "email": "uc0501.yds70expired@seed.iyte.edu.tr",
        "first_name": "Deniz",
        "last_name": "Aksoy",
        "national_id": "50100000004",
        "tracking_number": "APP-UC0501-D",
        "cert": {
            "exam_type": "YDS",
            "score": 70,
            "issued_on": "2020-04-12",
            "expires_on": "2025-04-12",  # already in the past
            "filename": "yds_70_2020_expired.pdf",
        },
    },
]


# ── Helpers ────────────────────────────────────────────────────────────


async def _get_program(db: AsyncSession) -> Program:
    program = await db.scalar(select(Program).where(Program.code == PROGRAM_CODE))
    if program is None:
        raise RuntimeError(
            f"Program with code='{PROGRAM_CODE}' not found. "
            f"Run `python -m scripts.seed` first."
        )
    return program


async def _get_period(db: AsyncSession) -> ApplicationPeriod:
    period = await db.scalar(
        select(ApplicationPeriod).where(ApplicationPeriod.label == PERIOD_LABEL)
    )
    if period is None:
        raise RuntimeError(
            f"Period '{PERIOD_LABEL}' not found. "
            f"Run `python -m scripts.seed` first."
        )
    return period


async def _upsert_user(
    db: AsyncSession, email: str, first_name: str, last_name: str, national_id: str
) -> Applicant:
    user = await db.scalar(select(User).where(User.email == email))
    if user is not None:
        applicant = await db.scalar(select(Applicant).where(Applicant.id == user.id))
        return applicant

    user_id = uuid.uuid4()
    db.add(
        User(
            id=user_id,
            email=email,
            password_hash=pwd_ctx.hash(SHARED_PASSWORD),
            role=UserRole.APPLICANT,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_verified=True,
        )
    )
    db.add(
        Applicant(
            id=user_id,
            national_id=national_id,
            date_of_birth=date(2000, 1, 1),
            identity_verified=True,
        )
    )
    await db.flush()
    return await db.scalar(select(Applicant).where(Applicant.id == user_id))


async def _upsert_application(
    db: AsyncSession,
    applicant: Applicant,
    program: Program,
    period: ApplicationPeriod,
    tracking_number: str,
) -> Application:
    app = await db.scalar(
        select(Application).where(Application.tracking_number == tracking_number)
    )
    if app is not None:
        # Reset to a clean ENGLISH_REVIEW state for repeatability
        app.status = AppStatus.ENGLISH_REVIEW
        app.updated_at = datetime.now(timezone.utc)
        # Wipe any previous decision so the dashboard shows an undecided row
        review = await db.scalar(
            select(EnglishProficiencyReview).where(
                EnglishProficiencyReview.application_id == app.id
            )
        )
        if review is not None:
            review.approved = None
            review.exam_type = None
            review.exam_score = None
            review.notes = None
            review.reviewer_id = None
            review.reviewed_at = None
            review.must_take_exam = False
        await db.flush()
        return app

    app = Application(
        applicant_id=applicant.id,
        program_id=program.id,
        period_id=period.id,
        status=AppStatus.ENGLISH_REVIEW,
        tracking_number=tracking_number,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(app)
    await db.flush()
    return app


async def _upsert_language_cert(
    db: AsyncSession, application: Application, cert: dict
) -> None:
    existing = await db.scalar(
        select(Document).where(
            Document.application_id == application.id,
            Document.doc_type == DocType.LANGUAGE_CERT,
        )
    )
    if existing is not None:
        existing.extracted_data = cert
        existing.extraction_confirmed = True
        return

    db.add(
        Document(
            application_id=application.id,
            doc_type=DocType.LANGUAGE_CERT,
            # file_path is a MinIO object key, NOT a URL (CHECK constraint).
            file_path=f"applications/{application.id}/{cert['filename']}",
            file_name=cert["filename"],
            file_size_bytes=128 * 1024,
            status=DocStatus.ACCEPTED,
            extracted_data=cert,
            extraction_confirmed=True,
        )
    )
    await db.flush()


# ── Driver ─────────────────────────────────────────────────────────────


async def seed(db: AsyncSession) -> None:
    print("UC-05-01 — Approve English Proficiency (YDYO) seed")
    print("=" * 60)
    print(f"Shared applicant password: {SHARED_PASSWORD}")
    print(f"Log in as YDYO:            ydyo@iyte.edu.tr / {SHARED_PASSWORD}")
    print()

    program = await _get_program(db)
    period = await _get_period(db)
    print(f"Using program: {program.code} — {program.name}")
    print(f"Using period:  {period.label}")
    print()

    for spec in CASES:
        print(f"→ {spec['label']}")
        applicant = await _upsert_user(
            db,
            email=spec["email"],
            first_name=spec["first_name"],
            last_name=spec["last_name"],
            national_id=spec["national_id"],
        )
        app = await _upsert_application(
            db, applicant, program, period, spec["tracking_number"]
        )
        await _upsert_language_cert(db, app, spec["cert"])
        print(f"    email     : {spec['email']}")
        print(f"    tracking  : {spec['tracking_number']}")
        print(f"    cert      : {spec['cert']['exam_type']} "
              f"score={spec['cert']['score']} "
              f"(expires {spec['cert']['expires_on']})")
        print()

    await db.commit()
    print("Done. Visit the YDYO dashboard to see these in ENGLISH_REVIEW.")


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
