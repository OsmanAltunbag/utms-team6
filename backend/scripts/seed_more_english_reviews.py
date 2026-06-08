"""
Additional UC-05-01 fixtures — 8 fresh English-proficiency applications
parked in ENGLISH_REVIEW so the YDYO officer always has something to act
on. Use this whenever the original UC-05-01 batch has been exhausted by
previous test runs.

Each applicant arrives with a LANGUAGE_CERT document whose extracted_data
mirrors what an OCR pipeline would produce, so the YDYO certificate panel
renders meaningful values immediately.

Decision-path coverage:

  E  TOEFL iBT 92 (2024)             → APPROVE (clear pass, ≥ 80)
  F  TOEFL iBT 78 (2024)             → MUST TAKE EXAM (just below 80)
  G  IELTS 7.5 (2024)                → APPROVE (clear pass, ≥ 6.5)
  H  IELTS 5.5 (2024)                → REJECT  (INSUFFICIENT_SCORE)
  I  YDS 85   (2024)                 → APPROVE (≥ 65)
  J  YDS 60   (2024)                 → MUST TAKE EXAM (just below 65)
  K  YOKDIL 75 (2024)                → APPROVE (≥ 65)
  L  TOEFL iBT 88 issued 2021        → REJECT  (EXPIRED_EXAM, > 2 yrs old)

Idempotent: re-running resets each of these eight applications back to
ENGLISH_REVIEW with all review flags cleared so they reappear as
'Pending Verification' on the YDYO dashboard.

Login:
    YDYO officer:  ydyo@iyte.edu.tr / Test1234!
    Each applicant: Test1234!

Run inside the backend container:
    docker compose exec backend python -m scripts.seed_more_english_reviews
"""

import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = _ROOT if os.path.isdir(os.path.join(_ROOT, "app")) else os.path.join(_ROOT, "backend")
sys.path.insert(0, _BACKEND)

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from scripts._engine import make_session_factory

from app.domain.academic_record import AcademicRecord
from app.domain.application import Application
from app.domain.document import Document
from app.domain.english import EnglishProficiencyReview
from app.domain.enums import AppStatus, DocStatus, DocType, UserRole
from app.domain.period import ApplicationPeriod
from app.domain.program import Program
from app.domain.user import Applicant, User

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


SHARED_PASSWORD = "Test1234!"
PROGRAM_CODE = "CE"
PERIOD_LABEL = "2025-2026 Spring"

def _academic(institution: str, gpa_4: float, yks: float | None = None, credits: int = 90):
    return {
        "institution": institution,
        "gpa_4": Decimal(str(gpa_4)),
        "yks_score": Decimal(str(yks)) if yks is not None else None,
        "credits_completed": credits,
    }


CASES = [
    {
        "label": "E  TOEFL iBT 92                       → APPROVE",
        "email": "uc0501.batch2.toefl92@seed.iyte.edu.tr",
        "first_name": "Ece",
        "last_name": "Yıldırım",
        "national_id": "50100000010",
        "tracking_number": "APP-UC0501-E",
        "cert": {
            "exam_type": "TOEFL_IBT", "score": 92,
            "issued_on": "2024-08-20", "expires_on": "2026-08-20",
            "filename": "toefl_ibt_92_2024.pdf",
        },
        "academic": _academic("Boğaziçi University", 3.7, 478.2, 105),
    },
    {
        "label": "F  TOEFL iBT 78 (just below 80)       → MUST TAKE EXAM",
        "email": "uc0501.batch2.toefl78@seed.iyte.edu.tr",
        "first_name": "Furkan",
        "last_name": "Öz",
        "national_id": "50100000011",
        "tracking_number": "APP-UC0501-F",
        "cert": {
            "exam_type": "TOEFL_IBT", "score": 78,
            "issued_on": "2024-10-05", "expires_on": "2026-10-05",
            "filename": "toefl_ibt_78_2024.pdf",
        },
        "academic": _academic("Hacettepe University", 3.2, 432.5, 84),
    },
    {
        "label": "G  IELTS 7.5                          → APPROVE",
        "email": "uc0501.batch2.ielts75@seed.iyte.edu.tr",
        "first_name": "Gizem",
        "last_name": "Aksu",
        "national_id": "50100000012",
        "tracking_number": "APP-UC0501-G",
        "cert": {
            "exam_type": "IELTS", "score": 7.5,
            "issued_on": "2024-05-12", "expires_on": "2026-05-12",
            "filename": "ielts_7_5_2024.pdf",
        },
        "academic": _academic("Koç University", 3.85, 491.0, 120),
    },
    {
        "label": "H  IELTS 5.5 (insufficient)           → REJECT",
        "email": "uc0501.batch2.ielts55@seed.iyte.edu.tr",
        "first_name": "Hasan",
        "last_name": "Kaya",
        "national_id": "50100000013",
        "tracking_number": "APP-UC0501-H",
        "cert": {
            "exam_type": "IELTS", "score": 5.5,
            "issued_on": "2024-04-18", "expires_on": "2026-04-18",
            "filename": "ielts_5_5_2024.pdf",
        },
        "academic": _academic("Gazi University", 2.7, 388.9, 60),
    },
    {
        "label": "I  YDS 85                             → APPROVE",
        "email": "uc0501.batch2.yds85@seed.iyte.edu.tr",
        "first_name": "İrem",
        "last_name": "Doğan",
        "national_id": "50100000014",
        "tracking_number": "APP-UC0501-I",
        "cert": {
            "exam_type": "YDS", "score": 85,
            "issued_on": "2024-09-01", "expires_on": "2029-09-01",
            "filename": "yds_85_2024.pdf",
        },
        "academic": _academic("Ankara University", 3.6, 461.4, 96),
    },
    {
        "label": "J  YDS 60 (just below 65)             → MUST TAKE EXAM",
        "email": "uc0501.batch2.yds60@seed.iyte.edu.tr",
        "first_name": "Jale",
        "last_name": "Çelik",
        "national_id": "50100000015",
        "tracking_number": "APP-UC0501-J",
        "cert": {
            "exam_type": "YDS", "score": 60,
            "issued_on": "2024-04-15", "expires_on": "2029-04-15",
            "filename": "yds_60_2024.pdf",
        },
        "academic": _academic("Yıldız Technical University", 3.05, 412.3, 75),
    },
    {
        "label": "K  YÖKDİL 75                          → APPROVE",
        "email": "uc0501.batch2.yokdil75@seed.iyte.edu.tr",
        "first_name": "Kerem",
        "last_name": "Aydın",
        "national_id": "50100000016",
        "tracking_number": "APP-UC0501-K",
        "cert": {
            "exam_type": "YOKDIL", "score": 75,
            "issued_on": "2024-07-22", "expires_on": "2029-07-22",
            "filename": "yokdil_75_2024.pdf",
        },
        "academic": _academic("Sabancı University", 3.4, 445.7, 105),
    },
    {
        "label": "L  TOEFL iBT 88 issued 2021 (expired) → REJECT (EXPIRED_EXAM)",
        "email": "uc0501.batch2.toefl88expired@seed.iyte.edu.tr",
        "first_name": "Leyla",
        "last_name": "Şahin",
        "national_id": "50100000017",
        "tracking_number": "APP-UC0501-L",
        "cert": {
            "exam_type": "TOEFL_IBT", "score": 88,
            "issued_on": "2021-06-10", "expires_on": "2023-06-10",
            "filename": "toefl_ibt_88_2021_expired.pdf",
        },
        "academic": _academic("Marmara University", 3.55, 458.9, 102),
    },
]


# ── Helpers (identical pattern to seed_uc_05_01_english_review.py) ─────


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
        # Refresh display name in case a re-seed swapped specs.
        user.first_name = first_name
        user.last_name = last_name
        await db.flush()
        return await db.scalar(select(Applicant).where(Applicant.id == user.id))

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
        app.status = AppStatus.ENGLISH_REVIEW
        app.updated_at = datetime.now(timezone.utc)
        review = await db.scalar(
            select(EnglishProficiencyReview).where(
                EnglishProficiencyReview.application_id == app.id
            )
        )
        if review is not None:
            # Reset every prior decision flag so the row shows up as
            # 'Pending Verification' on the YDYO dashboard again.
            review.approved = None
            review.exam_type = None
            review.exam_score = None
            review.notes = None
            review.reviewer_id = None
            review.reviewed_at = None
            review.must_take_exam = False
            review.exam_date = None
            review.published_at = None
            review.published_by = None
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


async def _upsert_academic_record(
    db: AsyncSession, application: Application, spec: dict
) -> None:
    rec = await db.scalar(
        select(AcademicRecord).where(AcademicRecord.application_id == application.id)
    )
    if rec is None:
        db.add(
            AcademicRecord(
                application_id=application.id,
                institution=spec["institution"],
                gpa_4=spec["gpa_4"],
                yks_score=spec.get("yks_score"),
                credits_completed=spec.get("credits_completed"),
                source="USER_DECLARED",
                is_locked=False,
            )
        )
    else:
        rec.institution = spec["institution"]
        rec.gpa_4 = spec["gpa_4"]
        rec.yks_score = spec.get("yks_score")
        rec.credits_completed = spec.get("credits_completed")
    await db.flush()


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
        existing.file_name = cert["filename"]
        existing.file_path = f"applications/{application.id}/{cert['filename']}"
        return

    db.add(
        Document(
            application_id=application.id,
            doc_type=DocType.LANGUAGE_CERT,
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
    print("UC-05-01 — Extra YDYO English-review fixtures (batch 2)")
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
        await _upsert_academic_record(db, app, spec["academic"])
        await _upsert_language_cert(db, app, spec["cert"])

    await db.commit()
    print()
    print(f"Done. {len(CASES)} fresh applications now in ENGLISH_REVIEW.")
    print("Open the YDYO English Proficiency tab and click each card.")


async def main() -> None:
    engine, factory = make_session_factory()
    async with factory() as session:
        try:
            await seed(session)
        except Exception:
            await session.rollback()
            raise
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
