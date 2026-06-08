"""
UC-06-01 — Approve Transfer Application (Dean's Office Final Decision).

Seeds 23 applicants that match the Figma sidebar counts exactly:

    Pending Review:   12     (status = RANKING)
    Approved:          8     (status = DEAN_APPROVED + DEAN_FINAL_APPROVED audit log)
    Rejected:          3     (status = REJECTED  + DEAN_FINAL_REJECTED audit log)

The first three Pending applicants intentionally use the names visible
in the Figma mockup (Buse Toklu / Tan Aksu / Seda Güven) so the screen
looks identical out of the box.

Idempotent: re-running resets every previously-seeded UC-06-01 applicant
back to their initial state (so you can test Approve/Reject again).

Login as Dean:
    dean@iyte.edu.tr / Test1234!
Each applicant uses:
    Test1234!

Run inside the backend container:
    docker compose exec backend python -m scripts.seed_uc_06_01_dean_review
"""
import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = _ROOT if os.path.isdir(os.path.join(_ROOT, "app")) else os.path.join(_ROOT, "backend")
sys.path.insert(0, _BACKEND)

from passlib.context import CryptContext
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from scripts._engine import make_session_factory

from app.domain.academic_record import AcademicRecord
from app.domain.application import Application
from app.domain.audit import AuditLog
from app.domain.document import Document
from app.domain.enums import AppStatus, DocStatus, DocType, UserRole
from app.domain.period import ApplicationPeriod
from app.domain.program import Program
from app.domain.user import Applicant, User

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


SHARED_PASSWORD = "Test1234!"
PERIOD_LABEL = "2025-2026 Spring"
TRACKING_PREFIX = "APP-2024-"  # APP-2024-001 … APP-2024-023, matches Figma

# Dean officer who "approved/rejected" the historical decisions.
DEAN_EMAIL = "dean@iyte.edu.tr"


def _spec(idx, first, last, national_id, institution, program_code, gpa, target_status):
    """Build a uniform spec dict for an applicant.

    target_status is one of "RANKING" (pending), "DEAN_APPROVED" (approved),
    "REJECTED" (rejected).
    """
    tracking = f"{TRACKING_PREFIX}{idx:03d}"
    return {
        "tracking_number": tracking,
        "email": f"uc0601.{idx:03d}@seed.iyte.edu.tr",
        "first_name": first,
        "last_name": last,
        "national_id": national_id,
        "institution": institution,
        "program_code": program_code,
        "gpa_4": Decimal(str(gpa)),
        "target_status": target_status,
    }


# Interleaved tracking numbers — the first 3 mirror the Figma rows exactly
# (Buse Toklu / Tan Aksu / Seda Güven). After that the rows alternate
# pending → approved → rejected naturally so the dean dashboard looks
# realistic when scrolled.
ALL_CASES = [
    # APP-2024-001..003 — exact Figma rows
    _spec(  1, "Buse",    "Toklu",      "60100000001", "Ege University",                  "CE",   3.8, "RANKING"),
    _spec(  2, "Tan",     "Aksu",       "60100000002", "Dokuz Eylül University",          "EEE",  3.9, "RANKING"),
    _spec(  3, "Seda",    "Güven",      "60100000003", "Ankara University",               "CHME", 3.7, "DEAN_APPROVED"),

    # Remaining Pending (10 more → total 12)
    _spec(  4, "Mert",    "Karaca",     "60100000004", "Boğaziçi University",             "ME",   3.5, "RANKING"),
    _spec(  5, "Selin",   "Aydın",      "60100000005", "Istanbul Technical University",   "CIVE", 3.6, "RANKING"),
    _spec(  6, "Emre",    "Demir",      "60100000006", "METU",                            "CE",   3.7, "RANKING"),
    _spec(  7, "Zeynep",  "Yıldız",     "60100000007", "Hacettepe University",            "CHME", 3.4, "RANKING"),
    _spec(  8, "Onur",    "Çelik",      "60100000008", "Bilkent University",              "MSE",  3.5, "RANKING"),
    _spec(  9, "Ayça",    "Kara",       "60100000009", "Ankara University",               "EEE",  3.3, "RANKING"),
    _spec( 10, "Kerem",   "Polat",      "60100000010", "Gazi University",                 "ME",   3.6, "RANKING"),
    _spec( 11, "İrem",    "Şahin",      "60100000011", "Yıldız Technical University",     "CE",   3.8, "RANKING"),
    _spec( 12, "Doruk",   "Korkmaz",    "60100000012", "Sabancı University",              "PHYS", 3.4, "RANKING"),
    _spec( 13, "Naz",     "Ergin",      "60100000013", "Çankaya University",              "MATH", 3.2, "RANKING"),

    # Remaining Approved (7 more → total 8)
    _spec( 14, "Berk",    "Aslan",      "60100000014", "Marmara University",              "CE",   3.9, "DEAN_APPROVED"),
    _spec( 15, "Defne",   "Yalçın",     "60100000015", "Koç University",                  "EEE",  3.8, "DEAN_APPROVED"),
    _spec( 16, "Cem",     "Öztürk",     "60100000016", "Boğaziçi University",             "ME",   3.6, "DEAN_APPROVED"),
    _spec( 17, "Pınar",   "Doğan",      "60100000017", "Eskişehir Osmangazi University",  "MSE",  3.7, "DEAN_APPROVED"),
    _spec( 18, "Mehmet",  "Sarı",       "60100000018", "Trakya University",               "CIVE", 3.5, "DEAN_APPROVED"),
    _spec( 19, "Elif",    "Çetin",      "60100000019", "Akdeniz University",              "PHYS", 3.6, "DEAN_APPROVED"),
    _spec( 20, "Yusuf",   "Arı",        "60100000020", "Erciyes University",              "CHEM", 3.4, "DEAN_APPROVED"),

    # Rejected (3 total)
    _spec( 21, "Hakan",   "Tunç",       "60100000021", "Süleyman Demirel University",     "CE",   2.4, "REJECTED"),
    _spec( 22, "Burcu",   "Acar",       "60100000022", "Karadeniz Technical University",  "EEE",  2.3, "REJECTED"),
    _spec( 23, "Tolga",   "Güneş",      "60100000023", "Pamukkale University",            "ME",   2.5, "REJECTED"),
]


async def _get_period(db: AsyncSession) -> ApplicationPeriod:
    pe = await db.scalar(select(ApplicationPeriod).where(ApplicationPeriod.label == PERIOD_LABEL))
    if pe is None:
        raise RuntimeError(
            f"Period '{PERIOD_LABEL}' not found. Run `python -m scripts.seed` first."
        )
    return pe


async def _get_program_by_code(db: AsyncSession, code: str) -> Program:
    p = await db.scalar(select(Program).where(Program.code == code))
    if p is None:
        raise RuntimeError(
            f"Program code {code} not found. Run `python -m scripts.seed` first."
        )
    return p


async def _get_dean_user(db: AsyncSession) -> User:
    u = await db.scalar(select(User).where(User.email == DEAN_EMAIL))
    if u is None:
        raise RuntimeError(
            f"Dean user '{DEAN_EMAIL}' not found. Run `python -m scripts.seed_test_roles` first."
        )
    return u


async def _upsert_user(db: AsyncSession, spec: dict) -> Applicant:
    user = await db.scalar(select(User).where(User.email == spec["email"]))
    if user is not None:
        # Re-seeds may reassign a tracking-number slot to a different name
        # (e.g. APP-2024-003 swapped from Mert → Seda); keep the user row
        # consistent so the dashboard shows the current spec.
        user.first_name = spec["first_name"]
        user.last_name = spec["last_name"]
        await db.flush()
        return await db.scalar(select(Applicant).where(Applicant.id == user.id))

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


async def _upsert_application(
    db: AsyncSession,
    applicant: Applicant,
    program: Program,
    period: ApplicationPeriod,
    spec: dict,
    submitted_at: datetime,
) -> Application:
    app = await db.scalar(
        select(Application).where(Application.tracking_number == spec["tracking_number"])
    )
    target_status = AppStatus[spec["target_status"]]

    if app is None:
        app = Application(
            applicant_id=applicant.id,
            program_id=program.id,
            period_id=period.id,
            status=target_status,
            tracking_number=spec["tracking_number"],
            submitted_at=submitted_at,
        )
        db.add(app)
        await db.flush()
    else:
        app.status = target_status
        app.program_id = program.id
        app.submitted_at = submitted_at
        await db.flush()

    # Academic record (institution + GPA) — used for the Figma card body.
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

    # Stub TRANSCRIPT document — required for intibak table creation (UC-04-02).
    # The file_path points to a placeholder object key; no real PDF is needed for
    # backend logic tests (intibak create_table only checks doc existence).
    existing_transcript = await db.scalar(
        select(Document).where(
            Document.application_id == app.id,
            Document.doc_type == DocType.TRANSCRIPT,
        )
    )
    if existing_transcript is None:
        db.add(
            Document(
                application_id=app.id,
                doc_type=DocType.TRANSCRIPT,
                file_path=f"applications/{app.id}/transcript_stub.pdf",
                file_name="transcript_stub.pdf",
                file_size_bytes=0,
                status=DocStatus.ACCEPTED,
            )
        )
        await db.flush()

    return app


async def _reset_dean_audit_logs(db: AsyncSession, app_ids: list[uuid.UUID]) -> None:
    """Wipe any previous DEAN_FINAL_* audit rows for these apps so a fresh
    seed run doesn't accumulate ghost decisions."""
    if not app_ids:
        return
    await db.execute(
        delete(AuditLog).where(
            AuditLog.entity_id.in_(app_ids),
            AuditLog.action.in_(["DEAN_FINAL_APPROVED", "DEAN_FINAL_REJECTED"]),
        )
    )
    await db.flush()


async def _stamp_dean_decision(
    db: AsyncSession,
    app: Application,
    dean_id: uuid.UUID,
    *,
    approved: bool,
) -> None:
    db.add(
        AuditLog(
            actor_id=dean_id,
            action="DEAN_FINAL_APPROVED" if approved else "DEAN_FINAL_REJECTED",
            entity_type="Application",
            entity_id=app.id,
            old_value={"status": AppStatus.RANKING.value},
            new_value={
                "status": (AppStatus.DEAN_APPROVED.value if approved else AppStatus.REJECTED.value),
                "routed_to": "STUDENT_AFFAIRS" if approved else None,
                "ip_address": "seed",
                "decided_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    )
    await db.flush()


async def seed(db: AsyncSession) -> None:
    print("UC-06-01 — Dean's Office Final Decision")
    print("=" * 60)

    period = await _get_period(db)
    dean = await _get_dean_user(db)
    print(f"Using period: {period.label}")
    print(f"Dean officer: {dean.email}")
    print()

    base_submit = datetime.now(timezone.utc) - timedelta(days=20)

    pending_apps: list[Application] = []
    approved_apps: list[Application] = []
    rejected_apps: list[Application] = []

    for spec in ALL_CASES:
        applicant = await _upsert_user(db, spec)
        program = await _get_program_by_code(db, spec["program_code"])
        # Stagger submitted_at so the list looks realistic
        submitted_at = base_submit + timedelta(days=int(spec["tracking_number"].split("-")[-1]))
        app = await _upsert_application(db, applicant, program, period, spec, submitted_at)
        if spec["target_status"] == "RANKING":
            pending_apps.append(app)
        elif spec["target_status"] == "DEAN_APPROVED":
            approved_apps.append(app)
        else:
            rejected_apps.append(app)

    # Reset prior dean audit logs for these apps, then re-stamp.
    all_ids = [a.id for a in approved_apps + rejected_apps]
    await _reset_dean_audit_logs(db, all_ids)

    for app in approved_apps:
        await _stamp_dean_decision(db, app, dean.id, approved=True)
    for app in rejected_apps:
        await _stamp_dean_decision(db, app, dean.id, approved=False)

    await db.commit()

    print(f"Pending Review : {len(pending_apps):>3}")
    print(f"Approved       : {len(approved_apps):>3}")
    print(f"Rejected       : {len(rejected_apps):>3}")
    print()
    print("Open the Dean's Office dashboard (log in as dean@iyte.edu.tr / Test1234!)")
    print("to review and decide on the 12 pending applications.")


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
