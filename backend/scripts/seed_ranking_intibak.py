"""
Seed — Ranking + Intibak end-to-end test fixtures.

Creates 3 applicants under the ENGT program (2025-2026 Spring period)
with a fully-approved ranking, then verifies intibak preconditions:

  Fixture A  seed.intibak.a@test.iyte.edu.tr  — HAS transcript  → intibak table creation SUCCEEDS
  Fixture B  seed.intibak.b@test.iyte.edu.tr  — NO  transcript  → EX-01 fires ("Missing transcript data")
  Fixture C  seed.intibak.c@test.iyte.edu.tr  — yedek / waitlist (no transcript)

Idempotent — safe to re-run.  On each run:
  • Existing seed users / applications are updated, not duplicated.
  • The seed ranking entries are rebuilt from scratch.
  • Fixture B's TRANSCRIPT document is removed if it somehow appeared.

Run:
    docker compose exec backend python -m scripts.seed_ranking_intibak
"""

import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from scripts._engine import make_session_factory

from app.domain.academic_record import AcademicRecord
from app.domain.application import Application
from app.domain.document import Document
from app.domain.enums import AppStatus, DocStatus, DocType, RankStatus, UserRole
from app.domain.period import ApplicationPeriod
from app.domain.program import Program
from app.domain.ranking import Ranking, RankingEntry
from app.domain.user import Applicant, User
from app.services.evaluation_service import calculate_transfer_score

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

SHARED_PASSWORD = "Test1234!"
PROGRAM_CODE    = "ENGT"
PERIOD_LABEL    = "2025-2026 Spring"

# ---------------------------------------------------------------------------
# Fixture definitions
# ---------------------------------------------------------------------------

FIXTURES = [
    {
        "label":          "Fixture A — Happy Path",
        "email":          "seed.intibak.a@test.iyte.edu.tr",
        "first_name":     "SeedA",
        "last_name":      "Intibak",
        "national_id":    "88800000001",
        "tracking":       "SEED-INTIBAK-001",
        "gpa_4":          Decimal("3.50"),
        "gpa_100":        Decimal("85.00"),
        "yks_score":      Decimal("420.000"),
        "has_transcript": True,   # intibak must SUCCEED
    },
    {
        "label":          "Fixture B — Negative (EX-01 expected)",
        "email":          "seed.intibak.b@test.iyte.edu.tr",
        "first_name":     "SeedB",
        "last_name":      "NoTranscript",
        "national_id":    "88800000002",
        "tracking":       "SEED-INTIBAK-002",
        "gpa_4":          Decimal("3.20"),
        "gpa_100":        Decimal("78.00"),
        "yks_score":      Decimal("400.000"),
        "has_transcript": False,  # intibak must FAIL with EX-01
    },
    {
        "label":          "Fixture C — Yedek (waitlist)",
        "email":          "seed.intibak.c@test.iyte.edu.tr",
        "first_name":     "SeedC",
        "last_name":      "Yedek",
        "national_id":    "88800000003",
        "tracking":       "SEED-INTIBAK-003",
        "gpa_4":          Decimal("2.90"),
        "gpa_100":        Decimal("70.00"),
        "yks_score":      Decimal("380.000"),
        "has_transcript": False,
    },
]

# Fake course list stored in Document.extracted_data (JSONB).
# Format matches what transcript_parser.parse_transcript() returns.
FAKE_TRANSCRIPT_DATA = {
    "parser_strategy": "table",
    "warnings": [],
    "courses": [
        {"course_code": "MAT101",  "course_name": "Calculus I",          "credits": 4.0, "grade": "AA", "semester": "2022-2023 Fall"},
        {"course_code": "PHY101",  "course_name": "Physics I",           "credits": 4.0, "grade": "BB", "semester": "2022-2023 Fall"},
        {"course_code": "ENG101",  "course_name": "English I",           "credits": 3.0, "grade": "AA", "semester": "2022-2023 Fall"},
        {"course_code": "CENG101", "course_name": "Introduction to CS",  "credits": 4.0, "grade": "AA", "semester": "2022-2023 Fall"},
        {"course_code": "MAT102",  "course_name": "Calculus II",         "credits": 4.0, "grade": "BA", "semester": "2022-2023 Spring"},
        {"course_code": "PHY102",  "course_name": "Physics II",          "credits": 4.0, "grade": "CB", "semester": "2022-2023 Spring"},
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _upsert_user(db: AsyncSession, spec: dict) -> User:
    user = await db.scalar(select(User).where(User.email == spec["email"]))
    if user is None:
        uid = uuid.uuid4()
        user = User(
            id=uid,
            email=spec["email"],
            password_hash=pwd_ctx.hash(SHARED_PASSWORD),
            role=UserRole.APPLICANT,
            first_name=spec["first_name"],
            last_name=spec["last_name"],
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.flush()

        db.add(Applicant(
            id=uid,
            national_id=spec["national_id"],
            date_of_birth=date(2000, 6, 1),
            identity_verified=True,
        ))
        await db.flush()
        print(f"      [+] user created")
    else:
        print(f"      [=] user exists")
    return user


async def _upsert_application(
    db: AsyncSession,
    user: User,
    program: Program,
    period: ApplicationPeriod,
    spec: dict,
) -> Application:
    app = await db.scalar(
        select(Application).where(Application.tracking_number == spec["tracking"])
    )
    if app is None:
        app = Application(
            applicant_id=user.id,
            program_id=program.id,
            period_id=period.id,
            status=AppStatus.DEPT_EVAL,
            tracking_number=spec["tracking"],
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(app)
        await db.flush()
        print(f"      [+] application created ({spec['tracking']})")
    else:
        app.status     = AppStatus.DEPT_EVAL
        app.program_id = program.id
        app.period_id  = period.id
        await db.flush()
        print(f"      [=] application reset → DEPT_EVAL ({spec['tracking']})")
    return app


async def _upsert_academic_record(
    db: AsyncSession,
    app: Application,
    spec: dict,
) -> None:
    rec = await db.scalar(
        select(AcademicRecord).where(AcademicRecord.application_id == app.id)
    )
    if rec is None:
        db.add(AcademicRecord(
            application_id=app.id,
            institution="Seed Test University",
            gpa_4=spec["gpa_4"],
            gpa_100=spec["gpa_100"],
            yks_score=spec["yks_score"],
            source="MANUAL",
            is_locked=False,
        ))
        print(f"      [+] academic_record created (gpa_100={spec['gpa_100']}, yks={spec['yks_score']})")
    else:
        rec.gpa_4      = spec["gpa_4"]
        rec.gpa_100    = spec["gpa_100"]
        rec.yks_score  = spec["yks_score"]
        rec.is_locked  = False
        print(f"      [=] academic_record updated")
    await db.flush()


async def _sync_transcript_doc(
    db: AsyncSession,
    app: Application,
    spec: dict,
) -> None:
    existing = await db.scalar(
        select(Document).where(
            Document.application_id == app.id,
            Document.doc_type == DocType.TRANSCRIPT,
        )
    )
    if spec["has_transcript"]:
        if existing is None:
            db.add(Document(
                application_id=app.id,
                doc_type=DocType.TRANSCRIPT,
                file_path=f"applications/{app.id}/TRANSCRIPT/transcript_seed.pdf",
                file_name="transcript_seed.pdf",
                file_size_bytes=2048,
                status=DocStatus.ACCEPTED,
                extracted_data=FAKE_TRANSCRIPT_DATA,
                extraction_confirmed=True,
            ))
            await db.flush()
            print(f"      [+] TRANSCRIPT doc added ({len(FAKE_TRANSCRIPT_DATA['courses'])} courses in extracted_data)")
        else:
            existing.status               = DocStatus.ACCEPTED
            existing.extracted_data       = FAKE_TRANSCRIPT_DATA
            existing.extraction_confirmed = True
            await db.flush()
            print(f"      [=] TRANSCRIPT doc updated")
    else:
        if existing is not None:
            await db.delete(existing)
            await db.flush()
            print(f"      [!] removed TRANSCRIPT doc (negative fixture — EX-01 must fire)")
        else:
            print(f"      [ok] no TRANSCRIPT doc (negative fixture confirmed)")


# ---------------------------------------------------------------------------
# Main seed
# ---------------------------------------------------------------------------

async def seed(db: AsyncSession) -> None:
    # ── Resolve shared dependencies ────────────────────────────────────
    program = await db.scalar(select(Program).where(Program.code == PROGRAM_CODE))
    if program is None:
        print(f"[ERROR] Program '{PROGRAM_CODE}' not found — run base seed first.")
        return

    period = await db.scalar(
        select(ApplicationPeriod).where(ApplicationPeriod.label == PERIOD_LABEL)
    )
    if period is None:
        print(f"[ERROR] Period '{PERIOD_LABEL}' not found — run base seed first.")
        return

    ygk_user = await db.scalar(
        select(User).where(User.email == "ygk_member@iyte.edu.tr")
    )
    if ygk_user is None:
        print("[ERROR] ygk_member@iyte.edu.tr not found — run base seed first.")
        return

    print(f"[ok] program={program.code}  quota={program.quota}  min_gpa={program.min_gpa}")
    print(f"[ok] period={period.label}")
    print(f"[ok] approver={ygk_user.email}")
    print()

    # ── Create / update applicants ─────────────────────────────────────
    created: list[tuple[dict, Application]] = []

    for spec in FIXTURES:
        print(f"  {spec['label']}")
        user = await _upsert_user(db, spec)
        app  = await _upsert_application(db, user, program, period, spec)
        await _upsert_academic_record(db, app, spec)
        await _sync_transcript_doc(db, app, spec)
        created.append((spec, app))
        print()

    # ── Upsert Ranking row ─────────────────────────────────────────────
    ranking = await db.scalar(
        select(Ranking).where(
            Ranking.program_id == program.id,
            Ranking.period_id  == period.id,
        )
    )
    if ranking is None:
        ranking = Ranking(
            program_id=program.id,
            period_id=period.id,
            status=RankStatus.DRAFT,
        )
        db.add(ranking)
        await db.flush()
        print(f"  [+] Created Ranking row for {program.code}")
    else:
        print(f"  [=] Using existing Ranking {ranking.id}")

    # ── Rebuild ranking entries for seed applicants ────────────────────
    seed_app_ids = {app.id for _, app in created}

    stale = await db.execute(
        select(RankingEntry).where(
            RankingEntry.ranking_id     == ranking.id,
            RankingEntry.application_id.in_(seed_app_ids),
        )
    )
    for entry in stale.scalars().all():
        await db.delete(entry)
    await db.flush()

    # Score and sort descending (mirrors ranking_service.generate_ranking)
    base_score = float(program.min_gpa) * 25 if program.min_gpa else 400.0
    scored = []
    for spec, app in created:
        score = calculate_transfer_score(
            float(spec["yks_score"]),
            base_score,
            float(spec["gpa_100"]),
        )
        scored.append((spec, app, score))
    scored.sort(key=lambda t: -t[2])

    # Count non-seed entries already in this ranking to offset position numbering
    existing_count_result = await db.execute(
        select(RankingEntry).where(
            RankingEntry.ranking_id.in_([ranking.id]),
            RankingEntry.application_id.not_in(seed_app_ids),
        )
    )
    offset = len(list(existing_count_result.scalars().all()))

    quota = program.quota
    entry_rows: list[tuple[dict, Application, float, bool, int]] = []
    for i, (spec, app, score) in enumerate(scored):
        position   = offset + i + 1
        is_primary = position <= quota
        db.add(RankingEntry(
            ranking_id=ranking.id,
            application_id=app.id,
            composite_score=Decimal(str(round(score, 3))),
            position=position,
            is_primary=is_primary,
        ))
        entry_rows.append((spec, app, score, is_primary, position))
    await db.flush()

    # ── Approve the ranking ────────────────────────────────────────────
    ranking.status      = RankStatus.APPROVED
    ranking.approved_by = ygk_user.id
    ranking.approved_at = datetime.now(timezone.utc)
    await db.flush()

    # ── Advance seed applications to RANKING status ────────────────────
    for spec, app, score, is_primary, position in entry_rows:
        app.status     = AppStatus.RANKING
        app.updated_at = datetime.now(timezone.utc)
    await db.flush()

    await db.commit()

    # ── Print summary ──────────────────────────────────────────────────
    sep = "=" * 68
    print()
    print(sep)
    print("  SEED COMPLETE")
    print(sep)
    print(f"  Program : {program.code} — {program.name}")
    print(f"  Period  : {period.label}")
    print(f"  Ranking : {ranking.id}  [APPROVED, quota={quota}]")
    print()
    print("  Staff credentials (password: Test1234!)")
    print("    YGK / Transfer Commission : ygk_member@iyte.edu.tr")
    print("    Dean's Office             : dean@iyte.edu.tr")
    print()
    print("  Applicants (password: Test1234!)")
    print()
    for spec, app, score, is_primary, position in entry_rows:
        tier      = "ASIL  (primary)" if is_primary else "YEDEK (waitlist)"
        transcript = "✓ HAS transcript — intibak POST /applications/{id}/intibak → 201" \
                     if spec["has_transcript"] \
                     else "✗ NO  transcript — intibak POST /applications/{id}/intibak → 422 EX-01"
        print(f"  [{tier}]  #{position}")
        print(f"    email    : {spec['email']}")
        print(f"    password : {SHARED_PASSWORD}")
        print(f"    app_id   : {app.id}")
        print(f"    tracking : {spec['tracking']}")
        print(f"    score    : {score:.3f}  (yks={spec['yks_score']}, gpa_100={spec['gpa_100']})")
        print(f"    intibak  : {transcript}")
        print()
    print(sep)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    print("Ranking + Intibak Seed")
    print("=" * 68)
    engine, factory = make_session_factory()
    async with factory() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
