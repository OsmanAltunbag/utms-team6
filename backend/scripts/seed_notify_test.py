"""
Notification E2E Test Seed — seeds 2 DEAN_APPROVED applications
whose applicant email is osmanaltunbag@std.iyte.edu.tr so that
clicking "Notify Results" in the Student Affairs dashboard sends
a real email to that inbox.

Run inside the backend container:
    docker compose exec backend python -m scripts.seed_notify_test

Idempotent: re-running resets both applications back to DEAN_APPROVED.

Login as Student Affairs:
    studentaffairs@iyte.edu.tr / Test1234!
"""
import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from scripts._engine import make_session_factory

from app.domain.academic_record import AcademicRecord
from app.domain.application import Application
from app.domain.audit import AuditLog
from app.domain.enums import AppStatus, UserRole
from app.domain.period import ApplicationPeriod
from app.domain.program import Program
from app.domain.user import Applicant, User

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


TARGET_EMAIL = "osmanaltunbag@std.iyte.edu.tr"
SHARED_PASSWORD = "Test1234!"
PERIOD_LABEL = "2025-2026 Spring"

APPLICATIONS = [
    {
        "tracking_number": "NOTIFY-TEST-001",
        "first_name": "Osman",
        "last_name": "Altunbag",
        "national_id": "99900000001",
        "institution": "Ege University",
        "program_code": "CENG",
        "gpa_4": Decimal("3.75"),
    },
    {
        "tracking_number": "NOTIFY-TEST-002",
        "first_name": "Osman",
        "last_name": "Altunbag",
        "national_id": "99900000001",
        "institution": "Ege University",
        "program_code": "EEE",
        "gpa_4": Decimal("3.60"),
    },
]


async def seed(db: AsyncSession) -> None:
    print("Notification E2E Test Seed")
    print("=" * 50)

    period = await db.scalar(
        select(ApplicationPeriod).where(ApplicationPeriod.label == PERIOD_LABEL)
    )
    if period is None:
        raise RuntimeError(
            f"Period '{PERIOD_LABEL}' not found. Run `python -m scripts.seed` first."
        )
    print(f"Period: {period.label}")

    # Upsert applicant user with the target email
    user = await db.scalar(select(User).where(User.email == TARGET_EMAIL))
    if user is None:
        uid = uuid.uuid4()
        user = User(
            id=uid,
            email=TARGET_EMAIL,
            password_hash=pwd_ctx.hash(SHARED_PASSWORD),
            role=UserRole.APPLICANT,
            first_name="Osman",
            last_name="Altunbag",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.add(
            Applicant(
                id=uid,
                national_id="99900000001",
                date_of_birth=date(2000, 6, 6),
                identity_verified=True,
            )
        )
        await db.flush()
        print(f"[+] Created applicant: {TARGET_EMAIL}")
    else:
        print(f"[skip] Applicant {TARGET_EMAIL} already exists")

    applicant = await db.scalar(select(Applicant).where(Applicant.id == user.id))

    base_time = datetime.now(timezone.utc) - timedelta(days=15)

    for i, spec in enumerate(APPLICATIONS):
        program = await db.scalar(
            select(Program).where(Program.code == spec["program_code"])
        )
        if program is None:
            print(f"  [skip] Program {spec['program_code']} not found — run seed.py first")
            continue

        app = await db.scalar(
            select(Application).where(
                Application.tracking_number == spec["tracking_number"]
            )
        )
        if app is None:
            app = Application(
                applicant_id=applicant.id,
                program_id=program.id,
                period_id=period.id,
                status=AppStatus.DEAN_APPROVED,
                tracking_number=spec["tracking_number"],
                submitted_at=base_time + timedelta(days=i),
            )
            db.add(app)
            await db.flush()
            print(f"[+] Created application: {spec['tracking_number']} → {program.code} (DEAN_APPROVED)")
        else:
            app.status = AppStatus.DEAN_APPROVED
            app.program_id = program.id
            await db.flush()
            print(f"[reset] Application {spec['tracking_number']} reset to DEAN_APPROVED")

        # Remove any existing RESULT_ANNOUNCED audit rows so re-seed works
        await db.execute(
            delete(AuditLog).where(
                AuditLog.entity_id == app.id,
                AuditLog.action == "RESULT_ANNOUNCED",
            )
        )
        await db.flush()

        rec = await db.scalar(
            select(AcademicRecord).where(AcademicRecord.application_id == app.id)
        )
        if rec is None:
            db.add(
                AcademicRecord(
                    application_id=app.id,
                    institution=spec["institution"],
                    gpa_4=spec["gpa_4"],
                    source="MANUAL",
                    is_locked=False,
                )
            )
        else:
            rec.institution = spec["institution"]
            rec.gpa_4 = spec["gpa_4"]
        await db.flush()

    await db.commit()

    print()
    print("─" * 50)
    print("DONE. Two DEAN_APPROVED applications ready.")
    print()
    print("To trigger the email notification:")
    print("  1. Log in as:  studentaffairs@iyte.edu.tr / Test1234!")
    print("  2. Go to:      Student Affairs dashboard → 'Announcement Queue' tab")
    print("  3. Click:      'Notify Results' next to NOTIFY-TEST-001 or NOTIFY-TEST-002")
    print()
    print(f"  Email will be sent to: {TARGET_EMAIL}")


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
