"""
Seed script — UC-03-02 (Notify Transfer Results)
Creates an APPROVED ranking ready for publication testing.

Run inside the backend container:
  docker exec utms-team6-backend-1 python /scripts/seed_ranking_for_notify.py
"""

import asyncio
import sys
import uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── DB connection (inside-container URL) ────────────────────────────────────
DATABASE_URL = "postgresql+asyncpg://utms:utms@db:5432/utms"

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# ── App imports (available because this runs inside the backend image) ───────
from app.core.security import hash_password
from app.domain.user import User, Applicant
from app.domain.program import Program
from app.domain.period import ApplicationPeriod
from app.domain.application import Application
from app.domain.ranking import Ranking, RankingEntry
from app.domain.enums import UserRole, AppStatus, RankStatus


# ── Helpers ──────────────────────────────────────────────────────────────────

async def get_or_create_program(db: AsyncSession) -> Program:
    # Use the canonical CE program that already exists in the DB
    result = await db.execute(select(Program).where(Program.code == "CE"))
    program = result.scalar_one_or_none()
    if program:
        print(f"  [program]  reusing existing → {program.id}  ({program.code} — {program.name})")
        return program

    # Fallback: create only if CE doesn't exist yet
    program = Program(
        name="Computer Engineering",
        code="CE",
        faculty="Faculty of Engineering",
        quota=5,
        min_gpa=Decimal("2.50"),
        is_active=True,
    )
    db.add(program)
    await db.flush()
    print(f"  [program]  created → {program.id}")
    return program


async def get_or_create_period(db: AsyncSession) -> ApplicationPeriod:
    # Prefer the canonical Spring period; fall back to creating a seed period
    result = await db.execute(
        select(ApplicationPeriod).where(ApplicationPeriod.label == "2025-2026 Spring")
    )
    period = result.scalar_one_or_none()
    if period:
        print(f"  [period]   reusing existing → {period.id}  ({period.label})")
        return period

    result = await db.execute(
        select(ApplicationPeriod).where(ApplicationPeriod.label == "2026 Fall — Seed")
    )
    period = result.scalar_one_or_none()
    if period:
        print(f"  [period]   reusing existing → {period.id}  ({period.label})")
        return period

    now = datetime.now(timezone.utc)
    period = ApplicationPeriod(
        label="2026 Fall — Seed",
        opens_at=now - timedelta(days=30),
        closes_at=now + timedelta(days=30),
        is_active=True,
    )
    db.add(period)
    await db.flush()
    print(f"  [period]   created → {period.id}")
    return period


async def get_or_create_applicant(
    db: AsyncSession,
    email: str,
    first_name: str,
    last_name: str,
    national_id: str,
) -> Applicant:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        result2 = await db.execute(select(Applicant).where(Applicant.id == user.id))
        applicant = result2.scalar_one_or_none()
        if applicant:
            print(f"  [user]     reusing {email} → {user.id}")
            return applicant

    user = User(
        email=email,
        password_hash=hash_password("Test1234!"),
        role=UserRole.APPLICANT,
        first_name=first_name,
        last_name=last_name,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()

    applicant = Applicant(
        id=user.id,
        national_id=national_id,
        date_of_birth=date(2000, 1, 1),
        identity_verified=True,
    )
    db.add(applicant)
    await db.flush()
    print(f"  [user]     created {email} → {user.id}")
    return applicant


async def get_or_create_application(
    db: AsyncSession,
    applicant: Applicant,
    program: Program,
    period: ApplicationPeriod,
    tracking_suffix: str,
) -> Application:
    result = await db.execute(
        select(Application).where(
            Application.applicant_id == applicant.id,
            Application.program_id == program.id,
            Application.period_id == period.id,
        )
    )
    app = result.scalar_one_or_none()
    if app:
        # Ensure it's in RANKING status
        if app.status != AppStatus.RANKING:
            app.status = AppStatus.RANKING
            await db.flush()
        print(f"  [app]      reusing → {app.id}  status={app.status.value}")
        return app

    app = Application(
        applicant_id=applicant.id,
        program_id=program.id,
        period_id=period.id,
        status=AppStatus.RANKING,
        tracking_number=f"TRK-SEED-{tracking_suffix}",
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(app)
    await db.flush()
    print(f"  [app]      created → {app.id}  status={app.status.value}")
    return app


async def seed(db: AsyncSession) -> None:
    print("\n=== UTMS — UC-03-02 Seed Script ===\n")

    # 1. Base data
    print("→ Program & Period")
    program = await get_or_create_program(db)
    period = await get_or_create_period(db)

    # 2. Applicants
    print("\n→ Applicants")
    app1_user = await get_or_create_applicant(
        db,
        email="osmanaltunbag@std.iyte.edu.tr",
        first_name="Osman",
        last_name="Altunbag",
        national_id="11111111111",
    )
    app2_user = await get_or_create_applicant(
        db,
        email="test2@iyte.edu.tr",
        first_name="Test",
        last_name="Two",
        national_id="22222222222",
    )
    app3_user = await get_or_create_applicant(
        db,
        email="test3@iyte.edu.tr",
        first_name="Test",
        last_name="Three",
        national_id="33333333333",
    )

    # 3. Applications (all in RANKING status)
    print("\n→ Applications")
    app1 = await get_or_create_application(db, app1_user, program, period, "001")
    app2 = await get_or_create_application(db, app2_user, program, period, "002")
    app3 = await get_or_create_application(db, app3_user, program, period, "003")

    # 4. Ranking
    print("\n→ Ranking")
    result = await db.execute(
        select(Ranking).where(
            Ranking.program_id == program.id,
            Ranking.period_id == period.id,
        )
    )
    ranking = result.scalar_one_or_none()

    if ranking:
        if ranking.status != RankStatus.APPROVED:
            ranking.status = RankStatus.APPROVED
            ranking.approved_at = datetime.now(timezone.utc)
            await db.flush()
        print(f"  [ranking]  reusing → {ranking.id}  status={ranking.status.value}")
    else:
        ranking = Ranking(
            program_id=program.id,
            period_id=period.id,
            status=RankStatus.APPROVED,
            approved_at=datetime.now(timezone.utc),
        )
        db.add(ranking)
        await db.flush()
        print(f"  [ranking]  created → {ranking.id}  status={ranking.status.value}")

    # 5. Ranking entries  (upsert-style: skip if already exists)
    print("\n→ Ranking Entries")
    entries_spec = [
        (app1.id, Decimal("88.750"), 1, True,  "Applicant 1 (osmanaltunbag) — PRIMARY"),
        (app2.id, Decimal("82.300"), 2, True,  "Applicant 2 (test2)         — PRIMARY"),
        (app3.id, Decimal("76.500"), 1, False, "Applicant 3 (test3)         — WAITLISTED"),
    ]

    for app_id, score, position, is_primary, label in entries_spec:
        result = await db.execute(
            select(RankingEntry).where(
                RankingEntry.ranking_id == ranking.id,
                RankingEntry.application_id == app_id,
            )
        )
        entry = result.scalar_one_or_none()
        if entry:
            print(f"  [entry]    reusing {label}")
        else:
            entry = RankingEntry(
                ranking_id=ranking.id,
                application_id=app_id,
                composite_score=score,
                position=position,
                is_primary=is_primary,
            )
            db.add(entry)
            await db.flush()
            print(f"  [entry]    created {label}")

    await db.commit()

    # ── Final output ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SEED COMPLETE — paste these UUIDs into the frontend UI")
    print("=" * 60)
    print(f"  period_id  : {period.id}")
    print(f"  program_id : {program.id}")
    print("=" * 60)
    print("\n  Ranking status : APPROVED  (ready to publish)")
    print("  Primary list   : osmanaltunbag@std.iyte.edu.tr (pos 1, score 88.75)")
    print("                   test2@iyte.edu.tr              (pos 2, score 82.30)")
    print("  Waitlist       : test3@iyte.edu.tr              (pos 1, score 76.50)")
    print()


async def main() -> None:
    async with SessionLocal() as db:
        try:
            await seed(db)
        except Exception as exc:
            await db.rollback()
            print(f"\n[ERROR] Seed failed: {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    asyncio.run(main())
