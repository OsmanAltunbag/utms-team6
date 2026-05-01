# UTMS — Architecture Overview

## Architectural Style
**Layered Monolith**: Resource → Service → Repository

```
┌─────────────────────────────────────────────┐
│              Frontend (React 18)             │
│         Vite + TypeScript + Axios            │
└───────────────────┬─────────────────────────┘
                    │ HTTPS
┌───────────────────▼─────────────────────────┐
│        FastAPI (Resource Layer)              │
│   JWT auth middleware • RBAC dependency      │
├─────────────────────────────────────────────┤
│        Service Layer                         │
│  AuthService • ApplicationService           │
│  EvaluationService • RankingService         │
│  NotificationService • AuditService         │
├─────────────────────────────────────────────┤
│        Repository Layer                      │
│  SQLAlchemy 2.0 async • One repo per root   │
├──────────────┬──────────────────────────────┤
│  PostgreSQL  │  Redis       │  MinIO         │
│  (primary)   │  (sessions,  │  (documents)   │
│              │   Celery)    │                │
└──────────────┴──────────────────────────────┘
        ↓ External Adapters
  e-Devlet · YÖKSİS · ÖSYM · UBYS
```

## Application State Machine

```
                    ┌─────────┐
                    │  DRAFT  │
                    └────┬────┘
                         │ submit()
                    ┌────▼────┐
                    │SUBMITTED│
                    └────┬────┘
          correction     │ review()
          resolved  ┌────▼────────────┐
         ┌──────────┤  UNDER_REVIEW   ├──────── reject ──────► REJECTED
         │          └────┬────────────┘
         │               │           │
         │           correction      │
  CORRECTION_REQUESTED◄──┘       english_review()
                              ┌────▼──────────┐
                              │ ENGLISH_REVIEW ├────── reject ──► REJECTED
                              └────┬──────────┘
                                   │ approve_english()
                              ┌────▼──────┐
                              │ DEPT_EVAL ├────────── reject ──► REJECTED
                              └────┬──────┘
                                   │ evaluate()
                              ┌────▼──────┐
                              │  RANKING  ├────────── reject ──► REJECTED
                              └────┬──────┘
                                   │ announce()
                              ┌────▼──────┐
                              │ ANNOUNCED │
                              └───────────┘
```

## External Integration Timeouts

| System | Operation | Timeout | Retry |
|--------|-----------|---------|-------|
| e-Devlet | Identity verify | 7s | No (user retries) |
| YÖKSİS | Academic record | 10s | No |
| ÖSYM | YKS score | 10s | No |
| UBYS | Transcript | 10s | No |
| UBYS | Register accepted | 10s | Yes (Celery, 3x) |

## Key Performance Requirements (from SRS)

| Operation | Requirement |
|-----------|-------------|
| Login | < 5 seconds |
| Document validation | < 5 seconds |
| Status retrieval | < 3 seconds |
| Status update visibility | ≤ 2 minutes without refresh |
| Academic data fetch | ≤ 10 seconds (parallel) |
| Eligibility check | ≤ 3 seconds |
| Bulk notification (1,000) | ≤ 5 minutes |
| RBAC check | < 100 ms |

## Security Requirements

| Requirement | Implementation |
|-------------|----------------|
| JWT algorithm | RS256 |
| JWT delivery | HttpOnly Secure SameSite=Strict cookie |
| Password storage | bcrypt |
| Account lockout | 5 failed attempts → 15 min lock |
| Session revocation | Redis JTI store |
| File storage | MinIO, no public URLs ever |
| Preview URLs | Pre-signed, 5-min TTL |
| KVKK compliance | UUID PKs, soft delete, no personal data in URLs |
| Audit trail | Immutable append-only audit_logs |
| Role enforcement | Middleware + dependency injection |
| DB enumeration | UUID PKs prevent sequential guessing |

---

# UTMS — API Contract Summary

## Auth Endpoints
| Method | Path | Role | Description |
|--------|------|------|-------------|
| POST | /api/auth/register | — | Applicant registration |
| POST | /api/auth/verify-email/{token} | — | Email verification |
| POST | /api/auth/login | — | Login (all roles) |
| POST | /api/auth/logout | Any | Logout |
| POST | /api/auth/refresh | Any | Refresh token |
| POST | /api/auth/forgot-password | — | Request reset |
| POST | /api/auth/reset-password/{token} | — | Reset password |

## Applicant Endpoints
| Method | Path | Role | Description |
|--------|------|------|-------------|
| POST | /api/applications | APPLICANT | Create application |
| GET | /api/applications | APPLICANT/STAFF | List applications |
| GET | /api/applications/{id} | APPLICANT/STAFF | Get application |
| GET | /api/applications/{id}/status | APPLICANT/STAFF | Get status + progress |
| GET | /api/applications/{id}/events | APPLICANT | SSE status stream |
| POST | /api/applications/{id}/fetch-academic-data | APPLICANT | Trigger data fetch |
| POST | /api/applications/{id}/submit | APPLICANT | Submit application |
| GET | /api/applications/{id}/documents | APPLICANT/STAFF | List documents |
| POST | /api/applications/{id}/documents/upload-url | APPLICANT | Get upload URL |
| POST | /api/applications/{id}/documents/confirm | APPLICANT | Confirm upload |
| GET | /api/documents/{id}/preview-url | APPLICANT/STAFF | Get preview URL |

## Student Affairs Endpoints
| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | /api/staff/applications | STUDENT_AFFAIRS | List for review |
| GET | /api/staff/applications/{id} | STUDENT_AFFAIRS | Get detail |
| POST | /api/staff/applications/{id}/approve-verification | STUDENT_AFFAIRS | Approve |
| POST | /api/staff/applications/{id}/request-correction | STUDENT_AFFAIRS | Request correction |
| POST | /api/staff/applications/{id}/reject | STUDENT_AFFAIRS | Reject |
| GET | /api/staff/results/{period_id}/{program_id} | STUDENT_AFFAIRS | View results |
| POST | /api/staff/results/{period_id}/{program_id}/publish | STUDENT_AFFAIRS | Publish results |

## Transfer Commission (YGK) Endpoints
| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | /api/ygk/applications | TRANSFER_COMMISSION | List for evaluation |
| GET | /api/ygk/applications/{id}/evaluation | TRANSFER_COMMISSION | Evaluation detail |
| POST | /api/ygk/applications/{id}/verify-scores | TRANSFER_COMMISSION | Verify & convert |
| POST | /api/ygk/applications/{id}/evaluate-conditions | TRANSFER_COMMISSION | Dept evaluation |
| POST | /api/ygk/rankings/generate | TRANSFER_COMMISSION | Generate ranking |
| GET | /api/ygk/rankings/{id} | TRANSFER_COMMISSION | Get ranking |
| POST | /api/ygk/rankings/{id}/approve | TRANSFER_COMMISSION | Approve ranking |
| POST | /api/ygk/rankings/{id}/return | TRANSFER_COMMISSION | Return for correction |
| POST | /api/ygk/rankings/{id}/promote-waitlisted | TRANSFER_COMMISSION | Promote waitlist |
| POST | /api/ygk/applications/{id}/intibak | TRANSFER_COMMISSION | Create intibak table |
| POST | /api/ygk/intibak/{id}/mappings | TRANSFER_COMMISSION | Add course mapping |
| POST | /api/ygk/intibak/{id}/submit | TRANSFER_COMMISSION | Submit intibak |

## YDYO Endpoints
| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | /api/ydyo/applications | YDYO | List for English review |
| POST | /api/ydyo/applications/{id}/approve-english | YDYO | Approve English |
| POST | /api/ydyo/applications/{id}/reject-english | YDYO | Reject English |
| POST | /api/ydyo/exam-results | YDYO | Bulk exam results |

## Dean's Office Endpoints
| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | /api/dean/applications | DEAN_OFFICE | List for final decision |
| POST | /api/dean/applications/{id}/approve | DEAN_OFFICE | Final approval |
| POST | /api/dean/applications/{id}/reject | DEAN_OFFICE | Final rejection |

## Admin Endpoints
| Method | Path | Role | Description |
|--------|------|------|-------------|
| POST | /api/admin/staff | SYSTEM_ADMIN | Create staff |
| GET | /api/admin/staff | SYSTEM_ADMIN | List staff |
| PATCH | /api/admin/staff/{id}/role | SYSTEM_ADMIN | Update role |
| DELETE | /api/admin/staff/{id} | SYSTEM_ADMIN | Deactivate (soft) |
| POST | /api/admin/periods | SYSTEM_ADMIN | Create period |
| GET | /api/admin/periods | SYSTEM_ADMIN | List periods |
| PATCH | /api/admin/periods/{id}/activate | SYSTEM_ADMIN | Activate period |
| PATCH | /api/admin/periods/{id}/deactivate | SYSTEM_ADMIN | Deactivate period |

## Q&A Endpoints
| Method | Path | Role | Description |
|--------|------|------|-------------|
| POST | /api/questions | APPLICANT | Submit question |
| GET | /api/questions | APPLICANT/STUDENT_AFFAIRS | List questions |
| POST | /api/questions/{id}/reply | STUDENT_AFFAIRS | Reply |
| PATCH | /api/questions/{id}/resolve | STUDENT_AFFAIRS | Mark resolved |

## Global Error Response Schema
```json
{
  "detail": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "field_errors": [
    { "field": "email", "message": "Invalid format" }
  ]
}
```

HTTP Status Codes used:
- `200` OK
- `201` Created
- `204` No Content
- `400` Bad Request
- `401` Unauthorized (not authenticated)
- `403` Forbidden (authenticated but wrong role)
- `404` Not Found
- `409` Conflict
- `410` Gone (expired token)
- `422` Unprocessable Entity (validation error)
- `423` Locked (account locked)
- `503` Service Unavailable (external system down)

---

# UTMS — Data Model Summary

## Core Entity Relationships

```
ApplicationPeriod ──< Application >── Program
                           │
               ┌──────────┼──────────────┐
               │           │              │
            Document  AcademicRecord  EligibilityCheck
                           │
               ┌───────────┼───────────┐
               │           │           │
      EnglishReview  DeptEvaluation  IntibakTable
                                          │
                                    CourseMapping
                                          
Ranking ──< RankingEntry >── Application
User ──< Notification
User ──< AuditLog
Applicant ──< Question ──< Reply
```

## User Inheritance

```
users (base)
 ├── applicants  (role=APPLICANT)
 └── staff       (role=STUDENT_AFFAIRS | TRANSFER_COMMISSION | YDYO | DEAN_OFFICE | SYSTEM_ADMIN)
```

## Application Status → Responsible Role

| Status | Who can transition FROM here |
|--------|------------------------------|
| DRAFT | Applicant (submit) |
| SUBMITTED | Student Affairs (review/reject) |
| UNDER_REVIEW | Student Affairs (approve/correct/reject) |
| CORRECTION_REQUESTED | Applicant (re-upload → triggers back to UNDER_REVIEW) |
| ENGLISH_REVIEW | YDYO (approve/reject) |
| DEPT_EVAL | Transfer Commission (evaluate/reject) |
| RANKING | Dean's Office (approve/reject) |
| ANNOUNCED | Terminal state |
| REJECTED | Terminal state |
