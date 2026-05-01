# UTMS — Project Context for AI Implementation

## Project
**Undergraduate Transfer Management System (UTMS)**
A web platform that automates the horizontal transfer (yatay geçiş) process at İzmir Institute of Technology (IZTECH).

## Tech Stack
- **Backend:** Python 3.11 + FastAPI
- **ORM:** SQLAlchemy 2.0 (async)
- **Database:** PostgreSQL 16
- **Cache / Session:** Redis 7
- **Task Queue:** Celery 5 + Redis broker
- **Object Storage:** MinIO (S3-compatible)
- **Auth:** RS256-signed JWT via `python-jose`; HttpOnly Secure cookies
- **Password Hashing:** bcrypt (via `passlib`)
- **Frontend:** React 18 + TypeScript + Vite
- **Containerisation:** Docker Compose (dev), Kubernetes (prod)

## Architecture
Layered Monolith: `Resource → Service → Repository`
- **Resource layer:** FastAPI routers (HTTP, request/response DTOs via Pydantic v2)
- **Service layer:** Business logic, state machine, external calls
- **Repository layer:** SQLAlchemy async sessions; one repository per aggregate root

## Folder Structure
```
backend/
  app/
    api/            # FastAPI routers (resources)
    services/       # Business logic services
    repositories/   # DB access layer
    domain/         # Domain models / entities (SQLAlchemy ORM)
    schemas/        # Pydantic v2 schemas (DTOs)
    external/       # External API adapters (YÖKSİS, ÖSYM, e-Devlet, UBYS)
    workers/        # Celery task definitions
    core/           # Config, security, dependencies
    migrations/     # Alembic migration files
  tests/
    unit/
    integration/
frontend/
  src/
    pages/
    components/
    hooks/
    api/            # Axios API client
    types/
```

## Key Domain Rules
1. `Application` is the **central aggregate root**. All status transitions go through `ApplicationService.change_status()`.
2. Application lifecycle: `DRAFT → SUBMITTED → UNDER_REVIEW → ENGLISH_REVIEW → DEPT_EVAL → RANKING → ANNOUNCED / REJECTED`
3. `AuditLog` is **immutable append-only** — never DELETE from it.
4. All datetime columns use **TIMESTAMPTZ**.
5. Primary keys are **UUIDs** (`gen_random_uuid()`).
6. Soft delete only — never hard DELETE users, staff, or department conditions.
7. Documents stored in MinIO; only the **object key** is persisted in the DB. Pre-signed URLs are generated on demand (5-min TTL).
8. Bulk notifications go through **Celery workers** — never inline SMTP.
9. Ranking approval uses **SERIALIZABLE isolation + SELECT FOR UPDATE**.

## External Systems (mock in tests)
- `e-Devlet` — identity verification during registration
- `YÖKSİS` — academic records
- `ÖSYM` — YKS exam scores
- `UBYS` — internal university information system

## Security Rules
- Passwords: bcrypt-hashed, never stored plain
- JWT: RS256, delivered via HttpOnly Secure cookie
- RBAC enforced at middleware level; role check must complete in < 100 ms
- Account lockout after 5 consecutive failed login attempts
- KVKK compliance: no public URLs for personal documents

## Testing Rules
- All external APIs must be mocked in tests
- Use AAA pattern (Arrange / Act / Assert)
- Unit tests for services; integration tests for repositories + API routes
- Repositories are tested against a real PostgreSQL test DB (Docker)
