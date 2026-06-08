"""
Seed script — UC-04-01 YGK Evaluation test fixtures.

Creates 3 applicants with UNDER_REVIEW applications for manual testing:
  TC-1A  Happy path          gpa_4=3.50, yks=420
  TC-1B  Discrepancy / typo  gpa_4=3.90, yks=410  (corrected to 3.09 in UI)
  TC-2A  Foreign/unknown     gpa_4=None, yks=430  → triggers Manual Calculation warning

Idempotent: safe to run multiple times (skips existing rows by email).

Run inside the backend container:
    python -m scripts.seed_ygk_evaluations
"""

import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = _ROOT if os.path.isdir(os.path.join(_ROOT, "app")) else os.path.join(_ROOT, "backend")
sys.path.insert(0, _BACKEND)

from decimal import Decimal

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from scripts._engine import make_session_factory

from app.domain.academic_record import AcademicRecord
from app.domain.application import Application
from app.domain.enums import AppStatus, UserRole
from app.domain.period import ApplicationPeriod
from app.domain.program import Program
from app.domain.user import Applicant, User

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Test-case definitions
# ---------------------------------------------------------------------------

SEED_CASES = [
    {
        "label": "TC-1A (Happy Path)",
        "email": "tc1a.normal@seed.iyte.edu.tr",
        "first_name": "TC1A Normal",
        "last_name": "Applicant",
        "national_id": "99900000001",
        "tracking_number": "APP-2025-99901",
        "gpa_4": Decimal("3.50"),
        "yks_score": Decimal("420.000"),
        "institution": "Ankara University",
        "source": "USER_DECLARED",
    },
    {
        "label": "TC-1B (Discrepancy/Typo)",
        "email": "tc1b.typo@seed.iyte.edu.tr",
        "first_name": "TC1B Typo",
        "last_name": "Applicant",
        "national_id": "99900000002",
        "tracking_number": "APP-2025-99902",
        "gpa_4": Decimal("3.90"),   # will be corrected to 3.09 in the UI
        "yks_score": Decimal("410.000"),
        "institution": "Istanbul Technical University",
        "source": "USER_DECLARED",
    },
    {
        "label": "TC-2A (Foreign/Unknown Scale)",
        "email": "tc2a.foreign@seed.iyte.edu.tr",
        "first_name": "TC2A Foreign Scale",
        "last_name": "Applicant",
        "national_id": "99900000003",
        "tracking_number": "APP-2025-99903",
        "gpa_4": None,              # no 4.0-scale GPA → triggers manual calc warning
        "yks_score": Decimal("430.000"),
        "institution": "Vienna University of Technology (Austria)",
        "source": "MANUAL",
    },
]


async def seed(session: AsyncSession) -> None:
    # ── Resolve program ────────────────────────────────────────────────
    program = await session.scalar(select(Program).where(Program.code == "CENG"))
    if program is None:
        print("  [ERROR] Program with code='CENG' not found. Run the base seed first.")
        return
    print(f"  [ok] Using program: {program.code} — {program.name} (id={program.id})")

    # ── Resolve period ─────────────────────────────────────────────────
    period = await session.scalar(
        select(ApplicationPeriod).where(ApplicationPeriod.label == "2025-2026 Spring")
    )
    if period is None:
        print("  [ERROR] Period '2025-2026 Spring' not found. Run the base seed first.")
        return
    print(f"  [ok] Using period: {period.label} (id={period.id})")

    print()
    seeded_count = 0

    for case in SEED_CASES:
        # ── Idempotency: reset existing application to UNDER_REVIEW ────
        existing_user = await session.scalar(
            select(User).where(User.email == case["email"])
        )
        if existing_user is not None:
            from app.domain.application import Application
            from app.domain.academic_record import AcademicRecord as AR
            existing_app = await session.scalar(
                select(Application).where(Application.tracking_number == case["tracking_number"])
            )
            if existing_app is not None:
                existing_app.status = AppStatus.UNDER_REVIEW
                existing_app.updated_at = datetime.now(timezone.utc)
                existing_record = await session.scalar(
                    select(AR).where(AR.application_id == existing_app.id)
                )
                if existing_record is not None:
                    existing_record.is_locked = False
                    existing_record.gpa_100 = None
                    existing_record.gpa_4 = case["gpa_4"]
                    existing_record.yks_score = case["yks_score"]
                await session.flush()
                print(f"  [reset] {case['label']} — reset to UNDER_REVIEW, is_locked=False")
            else:
                print(f"  [skip] {case['label']} — user exists but no application found")
            continue

        # ── User ───────────────────────────────────────────────────────
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email=case["email"],
            password_hash=pwd_ctx.hash("Test1234!"),
            role=UserRole.APPLICANT,
            first_name=case["first_name"],
            last_name=case["last_name"],
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()

        # ── Applicant profile ──────────────────────────────────────────
        applicant = Applicant(
            id=user_id,
            national_id=case["national_id"],
            date_of_birth=date(1999, 1, 1),
            identity_verified=True,
        )
        session.add(applicant)
        await session.flush()

        # ── Application ────────────────────────────────────────────────
        app_id = uuid.uuid4()
        application = Application(
            id=app_id,
            applicant_id=user_id,
            program_id=program.id,
            period_id=period.id,
            status=AppStatus.UNDER_REVIEW,
            tracking_number=case["tracking_number"],
            submitted_at=datetime.now(timezone.utc),
        )
        session.add(application)
        await session.flush()

        # ── Academic record ────────────────────────────────────────────
        record = AcademicRecord(
            application_id=app_id,
            institution=case["institution"],
            gpa_4=case["gpa_4"],
            gpa_100=None,           # not yet locked/converted — YGK will do this
            yks_score=case["yks_score"],
            source=case["source"],
            is_locked=False,
        )
        session.add(record)
        await session.flush()

        gpa_display = str(case["gpa_4"]) if case["gpa_4"] is not None else "None (foreign scale)"
        print(
            f"  [+] {case['label']}\n"
            f"      email={case['email']}  tracking={case['tracking_number']}\n"
            f"      gpa_4={gpa_display}  yks_score={case['yks_score']}"
        )
        seeded_count += 1

    await session.commit()
    print(f"\n  {seeded_count} new application(s) seeded (skipped already-existing ones).")


async def main() -> None:
    print("UC-04-01 YGK Evaluation Seed")
    print("=" * 40)

    engine, factory = make_session_factory()

    async with factory() as session:
        await seed(session)

    await engine.dispose()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
