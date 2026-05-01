"""Initial schema — all ENUM types, tables, indexes, constraints, triggers.

Revision ID: 0001
Revises:
Create Date: 2026-05-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 0. Extensions
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ------------------------------------------------------------------
    # 1. ENUM types  (must be created before tables that reference them)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TYPE user_role AS ENUM (
            'APPLICANT', 'STUDENT_AFFAIRS', 'TRANSFER_COMMISSION',
            'YDYO', 'DEAN_OFFICE', 'SYSTEM_ADMIN'
        )
        """
    )
    op.execute(
        """
        CREATE TYPE app_status AS ENUM (
            'DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'ENGLISH_REVIEW',
            'DEPT_EVAL', 'RANKING', 'ANNOUNCED', 'REJECTED', 'CORRECTION_REQUESTED'
        )
        """
    )
    op.execute(
        """
        CREATE TYPE doc_type AS ENUM (
            'TRANSCRIPT', 'YKS_RESULT', 'LANGUAGE_CERT', 'ID_COPY',
            'MILITARY_STATUS', 'DISCIPLINE_RECORD', 'OTHER'
        )
        """
    )
    op.execute(
        """
        CREATE TYPE doc_status AS ENUM (
            'PENDING', 'ACCEPTED', 'REJECTED', 'CORRECTION_REQUESTED'
        )
        """
    )
    op.execute("CREATE TYPE notif_channel AS ENUM ('EMAIL', 'SMS', 'IN_APP')")
    op.execute("CREATE TYPE notif_status AS ENUM ('PENDING', 'SENT', 'FAILED')")
    op.execute("CREATE TYPE rank_status AS ENUM ('DRAFT', 'APPROVED', 'PUBLISHED')")
    op.execute("CREATE TYPE intibak_status AS ENUM ('DRAFT', 'SUBMITTED', 'APPROVED')")

    # ------------------------------------------------------------------
    # 2. Core tables — in FK dependency order
    # ------------------------------------------------------------------

    # users (no FK deps)
    op.execute(
        """
        CREATE TABLE users (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email           VARCHAR(255) UNIQUE NOT NULL,
            password_hash   TEXT NOT NULL,
            role            user_role NOT NULL,
            first_name      VARCHAR(100) NOT NULL,
            last_name       VARCHAR(100) NOT NULL,
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
            failed_attempts INT NOT NULL DEFAULT 0,
            locked_until    TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_users_email ON users(email)")
    op.execute("CREATE INDEX idx_users_role ON users(role)")

    # applicants (→ users)
    op.execute(
        """
        CREATE TABLE applicants (
            id                UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            national_id       VARCHAR(11) UNIQUE NOT NULL,
            date_of_birth     DATE NOT NULL,
            phone             VARCHAR(20),
            identity_verified BOOLEAN NOT NULL DEFAULT FALSE
        )
        """
    )

    # staff (→ users)
    op.execute(
        """
        CREATE TABLE staff (
            id          UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            department  VARCHAR(150),
            title       VARCHAR(100)
        )
        """
    )

    # programs (no FK deps)
    op.execute(
        """
        CREATE TABLE programs (
            id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name      VARCHAR(200) NOT NULL,
            code      VARCHAR(20) UNIQUE NOT NULL,
            faculty   VARCHAR(150) NOT NULL,
            quota     INT NOT NULL DEFAULT 0,
            min_gpa   NUMERIC(4,2),
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
        """
    )

    # application_periods (→ users)
    op.execute(
        """
        CREATE TABLE application_periods (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            label      VARCHAR(100) NOT NULL,
            opens_at   TIMESTAMPTZ NOT NULL,
            closes_at  TIMESTAMPTZ NOT NULL,
            is_active  BOOLEAN NOT NULL DEFAULT FALSE,
            created_by UUID REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # applications (→ applicants, programs, application_periods)
    op.execute(
        """
        CREATE TABLE applications (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            applicant_id     UUID NOT NULL REFERENCES applicants(id),
            program_id       UUID NOT NULL REFERENCES programs(id),
            period_id        UUID NOT NULL REFERENCES application_periods(id),
            status           app_status NOT NULL DEFAULT 'DRAFT',
            tracking_number  VARCHAR(30) UNIQUE,
            submitted_at     TIMESTAMPTZ,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_apps_applicant ON applications(applicant_id)")
    op.execute("CREATE INDEX idx_apps_status ON applications(status)")
    op.execute("CREATE INDEX idx_apps_program ON applications(program_id)")

    # academic_records (→ applications)
    op.execute(
        """
        CREATE TABLE academic_records (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            application_id    UUID NOT NULL UNIQUE REFERENCES applications(id),
            institution       VARCHAR(200),
            gpa_4             NUMERIC(4,2),
            gpa_100           NUMERIC(5,2),
            yks_score         NUMERIC(8,3),
            credits_completed INT,
            fetched_at        TIMESTAMPTZ,
            source            VARCHAR(50)
        )
        """
    )

    # documents (→ applications, users)
    op.execute(
        """
        CREATE TABLE documents (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            application_id  UUID NOT NULL REFERENCES applications(id),
            doc_type        doc_type NOT NULL,
            file_path       TEXT NOT NULL
                                CONSTRAINT chk_file_path_no_url CHECK (file_path NOT LIKE 'http%'),
            file_name       TEXT NOT NULL,
            file_size_bytes BIGINT,
            status          doc_status NOT NULL DEFAULT 'PENDING',
            rejection_note  TEXT,
            uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            reviewed_at     TIMESTAMPTZ,
            reviewed_by     UUID REFERENCES users(id)
        )
        """
    )
    op.execute("CREATE INDEX idx_docs_application ON documents(application_id)")

    # eligibility_checks (→ applications)
    op.execute(
        """
        CREATE TABLE eligibility_checks (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            application_id  UUID NOT NULL REFERENCES applications(id),
            rule_key        VARCHAR(100) NOT NULL,
            passed          BOOLEAN NOT NULL,
            detail          TEXT,
            checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # department_requirements (→ programs)
    op.execute(
        """
        CREATE TABLE department_requirements (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            program_id  UUID NOT NULL REFERENCES programs(id),
            rule_key    VARCHAR(100) NOT NULL,
            rule_value  TEXT NOT NULL,
            description TEXT,
            is_active   BOOLEAN NOT NULL DEFAULT TRUE,
            UNIQUE (program_id, rule_key)
        )
        """
    )

    # department_evaluations (→ applications, users)
    op.execute(
        """
        CREATE TABLE department_evaluations (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            application_id  UUID NOT NULL REFERENCES applications(id),
            evaluator_id    UUID REFERENCES users(id),
            passed          BOOLEAN,
            notes           TEXT,
            evaluated_at    TIMESTAMPTZ
        )
        """
    )

    # english_proficiency_reviews (→ applications, users)
    op.execute(
        """
        CREATE TABLE english_proficiency_reviews (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            application_id  UUID NOT NULL REFERENCES applications(id),
            reviewer_id     UUID REFERENCES users(id),
            approved        BOOLEAN,
            exam_type       VARCHAR(50),
            exam_score      NUMERIC(6,2),
            notes           TEXT,
            reviewed_at     TIMESTAMPTZ
        )
        """
    )

    # rankings (→ programs, application_periods, users)
    op.execute(
        """
        CREATE TABLE rankings (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            program_id   UUID NOT NULL REFERENCES programs(id),
            period_id    UUID NOT NULL REFERENCES application_periods(id),
            status       rank_status NOT NULL DEFAULT 'DRAFT',
            approved_by  UUID REFERENCES users(id),
            approved_at  TIMESTAMPTZ,
            published_at TIMESTAMPTZ,
            UNIQUE (program_id, period_id)
        )
        """
    )

    # ranking_entries (→ rankings, applications)
    op.execute(
        """
        CREATE TABLE ranking_entries (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            ranking_id      UUID NOT NULL REFERENCES rankings(id),
            application_id  UUID NOT NULL REFERENCES applications(id),
            composite_score NUMERIC(8,3) NOT NULL,
            position        INT NOT NULL,
            is_primary      BOOLEAN NOT NULL,
            UNIQUE (ranking_id, application_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_ranking_entries_ranking ON ranking_entries(ranking_id)"
    )

    # intibak_tables (→ applications, users)
    op.execute(
        """
        CREATE TABLE intibak_tables (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            application_id  UUID NOT NULL UNIQUE REFERENCES applications(id),
            prepared_by     UUID REFERENCES users(id),
            status          intibak_status NOT NULL DEFAULT 'DRAFT',
            submitted_at    TIMESTAMPTZ,
            approved_at     TIMESTAMPTZ
        )
        """
    )

    # course_mappings (→ intibak_tables)
    op.execute(
        """
        CREATE TABLE course_mappings (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            intibak_table_id  UUID NOT NULL REFERENCES intibak_tables(id),
            source_course     VARCHAR(200) NOT NULL,
            source_credits    NUMERIC(4,1),
            target_course     VARCHAR(200) NOT NULL,
            target_credits    NUMERIC(4,1),
            equivalence_type  VARCHAR(50) NOT NULL,
            notes             TEXT
        )
        """
    )

    # notifications (→ users, applications)
    op.execute(
        """
        CREATE TABLE notifications (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID NOT NULL REFERENCES users(id),
            application_id  UUID REFERENCES applications(id),
            channel         notif_channel NOT NULL DEFAULT 'EMAIL',
            subject         TEXT,
            body            TEXT NOT NULL,
            status          notif_status NOT NULL DEFAULT 'PENDING',
            retry_count     INT NOT NULL DEFAULT 0,
            max_retries     INT NOT NULL DEFAULT 5,
            sent_at         TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_notif_user ON notifications(user_id)")
    op.execute("CREATE INDEX idx_notif_status ON notifications(status)")

    # audit_logs (→ users)  — IMMUTABLE: never DELETE
    op.execute(
        """
        CREATE TABLE audit_logs (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            actor_id     UUID NOT NULL REFERENCES users(id),
            action       VARCHAR(100) NOT NULL,
            entity_type  VARCHAR(100) NOT NULL,
            entity_id    UUID,
            old_value    JSONB,
            new_value    JSONB,
            ip_address   INET,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_audit_actor ON audit_logs(actor_id)")
    op.execute(
        "CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id)"
    )
    op.execute("CREATE INDEX idx_audit_created ON audit_logs(created_at DESC)")
    op.execute(
        "CREATE INDEX idx_audit_old_val ON audit_logs USING GIN (old_value)"
    )
    op.execute(
        "CREATE INDEX idx_audit_new_val ON audit_logs USING GIN (new_value)"
    )

    # questions (→ applicants, applications)
    op.execute(
        """
        CREATE TABLE questions (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            applicant_id    UUID NOT NULL REFERENCES applicants(id),
            application_id  UUID REFERENCES applications(id),
            subject         VARCHAR(255) NOT NULL,
            body            TEXT NOT NULL,
            is_resolved     BOOLEAN NOT NULL DEFAULT FALSE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # replies (→ questions, users)
    op.execute(
        """
        CREATE TABLE replies (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            question_id  UUID NOT NULL REFERENCES questions(id),
            staff_id     UUID NOT NULL REFERENCES users(id),
            body         TEXT NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # ------------------------------------------------------------------
    # 3. updated_at auto-update trigger (users + applications)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION _utms_set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION _utms_set_updated_at()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_applications_updated_at
        BEFORE UPDATE ON applications
        FOR EACH ROW EXECUTE FUNCTION _utms_set_updated_at()
        """
    )

    # ------------------------------------------------------------------
    # 4. Security — revoke DELETE on audit_logs from all roles
    # ------------------------------------------------------------------
    op.execute("REVOKE DELETE ON TABLE audit_logs FROM PUBLIC")


def downgrade() -> None:
    # Drop triggers first
    op.execute("DROP TRIGGER IF EXISTS trg_applications_updated_at ON applications")
    op.execute("DROP TRIGGER IF EXISTS trg_users_updated_at ON users")
    op.execute("DROP FUNCTION IF EXISTS _utms_set_updated_at()")

    # Drop tables in reverse FK dependency order
    op.execute("DROP TABLE IF EXISTS replies CASCADE")
    op.execute("DROP TABLE IF EXISTS questions CASCADE")
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS notifications CASCADE")
    op.execute("DROP TABLE IF EXISTS course_mappings CASCADE")
    op.execute("DROP TABLE IF EXISTS intibak_tables CASCADE")
    op.execute("DROP TABLE IF EXISTS ranking_entries CASCADE")
    op.execute("DROP TABLE IF EXISTS rankings CASCADE")
    op.execute("DROP TABLE IF EXISTS english_proficiency_reviews CASCADE")
    op.execute("DROP TABLE IF EXISTS department_evaluations CASCADE")
    op.execute("DROP TABLE IF EXISTS department_requirements CASCADE")
    op.execute("DROP TABLE IF EXISTS eligibility_checks CASCADE")
    op.execute("DROP TABLE IF EXISTS documents CASCADE")
    op.execute("DROP TABLE IF EXISTS academic_records CASCADE")
    op.execute("DROP TABLE IF EXISTS applications CASCADE")
    op.execute("DROP TABLE IF EXISTS application_periods CASCADE")
    op.execute("DROP TABLE IF EXISTS programs CASCADE")
    op.execute("DROP TABLE IF EXISTS staff CASCADE")
    op.execute("DROP TABLE IF EXISTS applicants CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")

    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS intibak_status")
    op.execute("DROP TYPE IF EXISTS rank_status")
    op.execute("DROP TYPE IF EXISTS notif_status")
    op.execute("DROP TYPE IF EXISTS notif_channel")
    op.execute("DROP TYPE IF EXISTS doc_status")
    op.execute("DROP TYPE IF EXISTS doc_type")
    op.execute("DROP TYPE IF EXISTS app_status")
    op.execute("DROP TYPE IF EXISTS user_role")
