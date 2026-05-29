"""
Seed script — populates the database with dev/test data for local SPEC-006 testing.

Run from the repo root (Docker):
    docker compose exec backend python -m scripts.seed

Or from backend/ (local Python with deps installed):
    python -m scripts.seed

Requires DATABASE_URL env var (or .env file). MinIO must be running for mock documents.
"""

import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

# Allow running as `python -m scripts.seed` from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.storage import MinIOClient
from app.domain.academic_record import AcademicRecord
from app.domain.application import Application
from app.domain.document import Document
from app.domain.eligibility import EligibilityCheck
from app.domain.enums import AppStatus, DocStatus, DocType, RankStatus, UserRole
from app.domain.period import ApplicationPeriod
from app.domain.program import Program
from app.domain.ranking import Ranking, RankingEntry
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

TEST_OFFICER = {
    "email": "officer@iyte.edu.tr",
    "password": "Officer1234!",
    "first_name": "ÖİDB",
    "last_name": "Officer",
    "role": UserRole.STUDENT_AFFAIRS,
    "department": "Student Affairs (ÖİDB)",
    "title": "Document Verification Officer",
}

TEST_APPLICANT = {
    "email": "applicant@iyte.edu.tr",
    "password": "Applicant1234!",
    "first_name": "Ayşe",
    "last_name": "Yılmaz",
    "national_id": "12345678901",
    "date_of_birth": date(2002, 6, 15),
    "phone": "+905551234567",
}

MOCK_TRACKING_NUMBER = "APP-MOCK-00001"

# Minimal valid PDF for in-browser preview during officer review.
_MOCK_PDF_BYTES = b"""%PDF-1.4
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /MediaBox [0 0 612 792] /Parent 2 0 R >>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer<< /Size 4 /Root 1 0 R >>
startxref
190
%%EOF"""


def _upload_mock_pdf(storage: MinIOClient, object_key: str) -> None:
    storage.put_object(object_key, _MOCK_PDF_BYTES, "application/pdf")


async def _seed_mock_submitted_application(session: AsyncSession) -> None:
    """Create a verified applicant with a SUBMITTED application for SPEC-006."""
    existing_app = await session.scalar(
        select(Application).where(Application.tracking_number == MOCK_TRACKING_NUMBER)
    )
    if existing_app:
        print(f"  [skip] Mock application {MOCK_TRACKING_NUMBER} already exists")
        return

    program = await session.scalar(select(Program).where(Program.code == "CE"))
    period = await session.scalar(
        select(ApplicationPeriod).where(ApplicationPeriod.label == "2025-2026 Spring")
    )
    if program is None or period is None:
        print("  [!] Skipping mock application — run seed again after programs/period exist")
        return

    applicant_user = await session.scalar(
        select(User).where(User.email == TEST_APPLICANT["email"])
    )
    if applicant_user is None:
        applicant_id = uuid.uuid4()
        applicant_user = User(
            id=applicant_id,
            email=TEST_APPLICANT["email"],
            password_hash=pwd_ctx.hash(TEST_APPLICANT["password"]),
            role=UserRole.APPLICANT,
            first_name=TEST_APPLICANT["first_name"],
            last_name=TEST_APPLICANT["last_name"],
            is_active=True,
            is_verified=True,
        )
        session.add(applicant_user)
        await session.flush()

        applicant = Applicant(
            id=applicant_id,
            national_id=TEST_APPLICANT["national_id"],
            date_of_birth=TEST_APPLICANT["date_of_birth"],
            phone=TEST_APPLICANT["phone"],
            identity_verified=True,
        )
        session.add(applicant)
        await session.flush()
        print(
            f"  [+] Mock applicant: {TEST_APPLICANT['email']} "
            f"(password: {TEST_APPLICANT['password']})"
        )
    else:
        print(f"  [skip] Mock applicant {TEST_APPLICANT['email']} already exists")

    now = datetime.now(timezone.utc)
    app_id = uuid.uuid4()
    application = Application(
        id=app_id,
        applicant_id=applicant_user.id,
        program_id=program.id,
        period_id=period.id,
        status=AppStatus.SUBMITTED,
        tracking_number=MOCK_TRACKING_NUMBER,
        submitted_at=now,
    )
    session.add(application)
    await session.flush()

    session.add(
        AcademicRecord(
            application_id=app_id,
            institution="Ege University",
            gpa_4=Decimal("3.45"),
            yks_score=Decimal("412.500"),
            credits_completed=98,
            fetched_at=now,
            source="UBYS+OSYM",
        )
    )
    session.add(
        EligibilityCheck(
            application_id=app_id,
            rule_key="GPA_MIN",
            passed=True,
            detail=f"GPA 3.45 >= minimum {program.min_gpa}",
        )
    )

    storage = MinIOClient()
    required_docs = [
        (DocType.TRANSCRIPT, "transcript.pdf"),
        (DocType.YKS_RESULT, "yks_result.pdf"),
        (DocType.ID_COPY, "id_copy.pdf"),
    ]
    for doc_type, file_name in required_docs:
        object_key = f"applications/{app_id}/{doc_type.value}/{uuid.uuid4()}.pdf"
        try:
            _upload_mock_pdf(storage, object_key)
        except Exception as exc:
            print(f"  [!] MinIO upload failed for {doc_type.value}: {exc}")
            print("      Mock application created without previewable files.")
            object_key = f"applications/{app_id}/{doc_type.value}/missing.pdf"

        session.add(
            Document(
                application_id=app_id,
                doc_type=doc_type,
                file_path=object_key,
                file_name=file_name,
                file_size_bytes=len(_MOCK_PDF_BYTES),
                status=DocStatus.PENDING,
                extracted_data={"source": "mock_seed", "verified": True},
                extraction_confirmed=True,
            )
        )

    print(f"  [+] Mock SUBMITTED application: {MOCK_TRACKING_NUMBER} (Computer Engineering)")
    print(f"      Officer queue → filter: Submitted → review as officer@iyte.edu.tr")


async def _seed_mock_ranking_for_spec007(session: AsyncSession) -> None:
    """Prepare APPROVED ranking + RANKING-status app for SPEC-007 publication."""
    program = await session.scalar(select(Program).where(Program.code == "CE"))
    period = await session.scalar(
        select(ApplicationPeriod).where(ApplicationPeriod.label == "2025-2026 Spring")
    )
    application = await session.scalar(
        select(Application).where(Application.tracking_number == MOCK_TRACKING_NUMBER)
    )
    if program is None or period is None or application is None:
        print("  [!] Skipping mock ranking — need program, period, and mock application")
        return

    existing_ranking = await session.scalar(
        select(Ranking).where(
            Ranking.program_id == program.id,
            Ranking.period_id == period.id,
        )
    )
    if existing_ranking is None:
        officer = await session.scalar(
            select(User).where(User.email == TEST_OFFICER["email"])
        )
        now = datetime.now(timezone.utc)
        ranking = Ranking(
            program_id=program.id,
            period_id=period.id,
            status=RankStatus.APPROVED,
            approved_by=officer.id if officer else None,
            approved_at=now,
        )
        session.add(ranking)
        await session.flush()

        session.add(
            RankingEntry(
                ranking_id=ranking.id,
                application_id=application.id,
                composite_score=Decimal("87.250"),
                position=1,
                is_primary=True,
            )
        )
        print("  [+] Mock APPROVED ranking (Asil list) for CE / 2025-2026 Spring")
    else:
        print("  [skip] Mock ranking already exists for CE / 2025-2026 Spring")

    if application.status != AppStatus.RANKING:
        application.status = AppStatus.RANKING
        print(f"  [+] Mock application {MOCK_TRACKING_NUMBER} set to RANKING (ready to publish)")


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

    # ── Test Student Affairs Officer (UC-03-01) ───────────────────────
    existing_officer = await session.scalar(
        select(User).where(User.email == TEST_OFFICER["email"])
    )
    if existing_officer:
        print(f"  [skip] Officer user {TEST_OFFICER['email']} already exists")
    else:
        officer_id = uuid.uuid4()
        officer_user = User(
            id=officer_id,
            email=TEST_OFFICER["email"],
            password_hash=pwd_ctx.hash(TEST_OFFICER["password"]),
            role=TEST_OFFICER["role"],
            first_name=TEST_OFFICER["first_name"],
            last_name=TEST_OFFICER["last_name"],
            is_active=True,
            is_verified=True,
        )
        session.add(officer_user)
        await session.flush()

        officer_staff = Staff(
            id=officer_id,
            department=TEST_OFFICER["department"],
            title=TEST_OFFICER["title"],
        )
        session.add(officer_staff)
        print(
            f"  [+] Student Affairs officer: {TEST_OFFICER['email']} "
            f"(password: {TEST_OFFICER['password']})"
        )

    # ── Application Period ────────────────────────────────────────────
    existing_period = await session.scalar(
        select(ApplicationPeriod).where(ApplicationPeriod.label == "2025-2026 Spring")
    )
    if existing_period:
        print(f"  [skip] Period '2025-2026 Spring' already exists — id: {existing_period.id}")
    else:
        now = datetime.now(timezone.utc)
        period = ApplicationPeriod(
            label="2025-2026 Spring",
            opens_at=now - timedelta(days=1),
            closes_at=now + timedelta(days=60),
            is_active=True,
        )
        session.add(period)
        await session.flush()
        print(f"  [+] Period: 2025-2026 Spring — id: {period.id}")

    # ── Mock applicant + SUBMITTED application (SPEC-006) ───────────────
    await _seed_mock_submitted_application(session)

    # ── Mock APPROVED ranking for results publication (SPEC-007) ────────
    await _seed_mock_ranking_for_spec007(session)

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
