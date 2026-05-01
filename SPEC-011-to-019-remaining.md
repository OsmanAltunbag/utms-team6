# SPEC-011 — Transfer Commission: Course Equivalency (Intibak)

## Goal
YGK prepares course equivalency (intibak) tables mapping applicant's previous courses to IZTECH curriculum. Tables are lockable; submitted tables forwarded electronically to Dean's Office.

## Depends On
SPEC-010

---

## Tasks

### Task 1 — IntibakService
File: `backend/app/services/intibak_service.py`

```python
class IntibakService:
    async def create_table(self, application_id: UUID, preparer_id: UUID) -> IntibakTable
    async def add_course_mapping(
        self, table_id: UUID, mapping: CourseMappingCreate
    ) -> CourseMapping
    async def save_draft(self, table_id: UUID) -> IntibakTable
    async def submit_table(self, table_id: UUID, submitter_id: UUID) -> IntibakTable
    # submit: status → SUBMITTED, locked (no further edits), forward to Dean
```

### Task 2 — Intibak API
File: `backend/app/api/intibak.py`

```
POST /api/ygk/applications/{id}/intibak
  Auth: TRANSFER_COMMISSION
  Response: 201 IntibakTable

POST /api/ygk/intibak/{table_id}/mappings
  Auth: TRANSFER_COMMISSION
  Body: { source_course, source_credits, target_course, target_credits, equivalence_type, notes }
  Response: 201 CourseMapping

PUT /api/ygk/intibak/{table_id}/mappings/{mapping_id}
  Auth: TRANSFER_COMMISSION
  Response: 200 CourseMapping
  Error: 422 if table already submitted

POST /api/ygk/intibak/{table_id}/submit
  Auth: TRANSFER_COMMISSION
  Response: 200 { status: "SUBMITTED" }
```

---

## Acceptance Criteria
- Submitted intibak tables are read-only (status=SUBMITTED blocks all edits)
- Submission written to audit_logs

---
---

# SPEC-012 — Transfer Commission: Process Waitlisted Applicants

## Goal
When a primary (asil) candidate withdraws or fails to enroll, the system promotes the next waitlisted applicant automatically.

## Depends On
SPEC-010

---

## Tasks

### Task 1 — Waitlist Promotion Logic
File: `backend/app/services/ranking_service.py` (extension)

```python
async def promote_next_waitlisted(
    self, ranking_id: UUID, withdrawn_application_id: UUID, actor_id: UUID
) -> RankingEntry | None
# 1. Mark withdrawn_application REJECTED
# 2. Find next waitlisted entry (lowest position with is_primary=False, status=RANKING)
# 3. Promote: set is_primary=True, update application status appropriately
# 4. Notify newly promoted applicant
# 5. Write AuditLog "WAITLIST_PROMOTION"
# Returns: promoted entry, or None if waitlist exhausted
```

### Task 2 — API
```
POST /api/ygk/rankings/{ranking_id}/promote-waitlisted
  Auth: TRANSFER_COMMISSION
  Body: { withdrawn_application_id }
  Response: 200 { promoted: ApplicantSummary | null, message }
```

---

## Acceptance Criteria
- Promotion is atomic (transaction)
- Promoted applicant receives notification within 2 minutes
- If waitlist exhausted, returns null with informative message

---
---

# SPEC-013 — YDYO: English Proficiency Approval

## Goal
YDYO staff reviews English proficiency documents and approves or rejects each applicant. Approved applicants advance to department evaluation.

## Depends On
SPEC-004

---

## Tasks

### Task 1 — EnglishProficiencyService
File: `backend/app/services/english_service.py`

```python
class EnglishProficiencyService:
    async def approve(
        self, application_id: UUID, reviewer_id: UUID,
        exam_type: str, exam_score: float
    ) -> EnglishProficiencyReview
    # status → DEPT_EVAL, AuditLog, notify applicant

    async def reject(
        self, application_id: UUID, reviewer_id: UUID, notes: str
    ) -> EnglishProficiencyReview
    # status → REJECTED, AuditLog, notify applicant
```

### Task 2 — YDYO API
File: `backend/app/api/ydyo.py`

```
GET /api/ydyo/applications
  Auth: YDYO
  Query: status=ENGLISH_REVIEW
  Response: [ApplicationSummary]

POST /api/ydyo/applications/{id}/approve-english
  Auth: YDYO
  Body: { exam_type, exam_score }
  Response: 200

POST /api/ydyo/applications/{id}/reject-english
  Auth: YDYO
  Body: { notes }
  Response: 200
```

---

## Test Scenarios

| ID | Scenario | Expected |
|----|----------|----------|
| T1 | YDYO approves English | status=DEPT_EVAL, applicant notified |
| T2 | YDYO rejects English | status=REJECTED, applicant notified |
| T3 | Non-YDYO accesses endpoint | 403 |

---
---

# SPEC-014 — YDYO: Announce Proficiency Exam Results

## Goal
YDYO enters bulk exam results. Passing applicants advance; failing applicants are rejected and notified.

## Depends On
SPEC-013, SPEC-019

---

## Tasks

### Task 1 — Bulk Exam Results API
File: `backend/app/api/ydyo.py`

```
POST /api/ydyo/exam-results
  Auth: YDYO
  Body: { results: [{ application_id, score, passed }] }
  Response: 200 { processed: int, advanced: int, rejected: int }
```

Processing (atomic per result):
- If `passed=True`: approve English, advance to DEPT_EVAL
- If `passed=False`: reject, enqueue notification
- Write AuditLog per applicant

---

## Acceptance Criteria
- Publication is irreversible (once marked, cannot undo bulk operation without SYSTEM_ADMIN)
- Each result written to audit_logs
- Notifications dispatched for all affected applicants

---
---

# SPEC-015 — Dean's Office: Final Application Decision

## Goal
Dean's Office makes the final binding approval or rejection for applications that have passed all evaluation stages. Acceptance forwarded to UBYS.

## Depends On
SPEC-010, SPEC-013

---

## Tasks

### Task 1 — UBYS Registration Adapter
File: `backend/app/external/ubys_adapter.py` (extension)

```python
async def register_accepted_student(
    self, application: Application, academic_record: AcademicRecord
) -> bool
# Sends acceptance to UBYS for formal enrollment
# Timeout: 10 seconds
# On failure: log error, retry via Celery worker
```

### Task 2 — DeanOfficeService
File: `backend/app/services/dean_service.py`

```python
class DeanOfficeService:
    async def approve_final(
        self, application_id: UUID, approver_id: UUID
    ) -> Application
    # status → ANNOUNCED, AuditLog "FINAL_APPROVED"
    # Forward to UBYS (via adapter + Celery retry)
    # Notify applicant

    async def reject_final(
        self, application_id: UUID, approver_id: UUID, reason: str
    ) -> Application
    # status → REJECTED, AuditLog "FINAL_REJECTED"
    # Notify applicant
```

### Task 3 — Dean API
File: `backend/app/api/dean.py`

```
GET /api/dean/applications
  Auth: DEAN_OFFICE
  Query: status=RANKING
  Response: [ApplicationSummary + RankingEntry]

POST /api/dean/applications/{id}/approve
  Auth: DEAN_OFFICE
  Response: 200

POST /api/dean/applications/{id}/reject
  Auth: DEAN_OFFICE
  Body: { reason }
  Response: 200
```

---

## Acceptance Criteria
- Approval constitutes a legally binding record (written to audit_logs as immutable entry)
- UBYS registration failures retried via Celery (do not block UI response)
- Only DEAN_OFFICE role can access these endpoints

---
---

# SPEC-016 — IT/Admin: Staff Registration & Role Management

## Goal
System Administrator (BIDB) registers new staff accounts and assigns roles. Soft-delete for deactivation.

## Depends On
SPEC-001

---

## Tasks

### Task 1 — AdminService
File: `backend/app/services/admin_service.py`

```python
class AdminService:
    async def create_staff(
        self, payload: StaffCreateRequest, created_by: UUID
    ) -> Staff
    # Create users + staff rows, assign role, is_verified=True (staff don't need email verify)
    # Enqueue welcome email with temporary password
    # Write AuditLog "STAFF_CREATED"

    async def update_role(
        self, staff_id: UUID, new_role: UserRole, updated_by: UUID
    ) -> Staff
    # Write AuditLog "ROLE_UPDATED"

    async def deactivate_staff(
        self, staff_id: UUID, deactivated_by: UUID
    ) -> Staff
    # Set is_active=False (soft delete)
    # Revoke all active JTIs from Redis
    # Write AuditLog "STAFF_DEACTIVATED"
```

### Task 2 — Admin API
File: `backend/app/api/admin.py`

```
POST /api/admin/staff
  Auth: SYSTEM_ADMIN
  Body: { email, first_name, last_name, role, department, title }
  Response: 201 Staff

GET /api/admin/staff
  Auth: SYSTEM_ADMIN
  Response: [StaffSummary]

PATCH /api/admin/staff/{id}/role
  Auth: SYSTEM_ADMIN
  Body: { role }
  Response: 200

DELETE /api/admin/staff/{id}
  Auth: SYSTEM_ADMIN
  Response: 204 (soft delete, sets is_active=False)
```

---

## Test Scenarios

| ID | Scenario | Expected |
|----|----------|----------|
| T1 | Create staff with STUDENT_AFFAIRS role | 201, can log in and access officer endpoints |
| T2 | Deactivate staff | is_active=False, sessions revoked |
| T3 | Deactivated staff tries to login | 401 |
| T4 | Non-admin creates staff | 403 |

## Acceptance Criteria
- Soft delete only — audit history preserved
- Role changes take effect on next request (Redis session revoked immediately)

---
---

# SPEC-017 — IT/Admin: Configure Application Periods

## Goal
System Administrator sets opening and closing dates for the transfer application window. ApplicationPeriod status drives whether applicants can submit applications.

## Depends On
SPEC-016

---

## Tasks

### Task 1 — PeriodService
File: `backend/app/services/period_service.py`

```python
class PeriodService:
    async def create_period(
        self, label: str, opens_at: datetime, closes_at: datetime,
        created_by: UUID
    ) -> ApplicationPeriod
    # Validates: opens_at < closes_at
    # Validates: no overlapping active period
    # Write AuditLog "PERIOD_CREATED"

    async def is_open(self, period_id: UUID) -> bool
    # Uses server-side NOW() — NOT client time (SRS UC-07-02 SR1)

    async def activate_period(self, period_id: UUID, by: UUID) -> ApplicationPeriod
    async def deactivate_period(self, period_id: UUID, by: UUID) -> ApplicationPeriod
```

### Task 2 — Admin API Extension
File: `backend/app/api/admin.py`

```
POST /api/admin/periods
  Auth: SYSTEM_ADMIN
  Body: { label, opens_at, closes_at }
  Response: 201 ApplicationPeriod

GET /api/admin/periods
  Auth: SYSTEM_ADMIN
  Response: [ApplicationPeriod]

PATCH /api/admin/periods/{id}/activate
  Auth: SYSTEM_ADMIN
  Response: 200

PATCH /api/admin/periods/{id}/deactivate
  Auth: SYSTEM_ADMIN
  Response: 200
```

---

## Acceptance Criteria
- `is_open()` uses server-side time, never client-provided time (SRS SR1)
- Cannot create overlapping active periods

---
---

# SPEC-018 — Applicant Q&A: Questions & Replies

## Goal
Applicants can submit questions about their applications. Student Affairs can reply.

## Depends On
SPEC-002

---

## Tasks

### Task 1 — Q&A API
File: `backend/app/api/qa.py`

```
POST /api/questions
  Auth: APPLICANT
  Body: { subject, body, application_id (optional) }
  Response: 201 Question

GET /api/questions
  Auth: APPLICANT → own questions
        STUDENT_AFFAIRS → all unresolved
  Response: [Question + replies]

POST /api/questions/{id}/reply
  Auth: STUDENT_AFFAIRS
  Body: { body }
  Response: 201 Reply

PATCH /api/questions/{id}/resolve
  Auth: STUDENT_AFFAIRS
  Response: 200 { is_resolved: true }
```

---

## Acceptance Criteria
- Applicants can only view their own questions
- Staff can view all questions and reply
- Replies trigger in-app notification to applicant

---
---

# SPEC-019 — Notification Worker: Email Delivery & Retry

## Goal
All email notifications go through Celery workers. Failed deliveries retry with exponential backoff. Audit trail via notifications table.

## Depends On
SPEC-001

---

## Tasks

### Task 1 — NotificationService
File: `backend/app/services/notification_service.py`

```python
class NotificationService:
    async def enqueue(
        self, user_id: UUID, subject: str, body: str,
        application_id: UUID | None = None,
        channel: NotifChannel = NotifChannel.EMAIL
    ) -> Notification
    # Creates notifications row (status=PENDING)
    # Calls send_notification.delay(notification_id)

    async def get_delivery_log(
        self, application_id: UUID
    ) -> list[Notification]
    # For UI communication logs tab
```

### Task 2 — Celery Task with Retry
File: `backend/app/workers/notification_tasks.py`

```python
@celery.task(bind=True, max_retries=5, default_retry_delay=60)
def send_notification(self, notification_id: str):
    # 1. Load notification from DB
    # 2. Build SMTP message (from SMTP_* env vars)
    # 3. Send via smtplib or aiosmtplib
    # 4. On success: status=SENT, sent_at=NOW()
    # 5. On failure: retry with exponential backoff
    #    delay = 60 * (2 ** self.request.retries)
    # 6. After max_retries: status=FAILED, log via Python logger
```

### Task 3 — Email Templates
Directory: `backend/app/workers/templates/`

Templates (Jinja2 HTML):
- `application_submitted.html` — tracking number, program name
- `status_changed.html` — old status, new status, note
- `correction_requested.html` — correction note
- `results_announced.html` — result (Accepted/Waitlisted/Rejected)
- `password_reset.html` — reset link (expires in 1 hour)
- `email_verification.html` — verification link (expires in 24 hours)
- `welcome_staff.html` — temporary password for staff accounts

### Task 4 — Celery Worker Config
File: `backend/app/core/celery_app.py`

```python
celery = Celery(
    broker="redis://localhost:6379/1",
    backend="redis://localhost:6379/2"
)
celery.conf.task_serializer = "json"
celery.conf.task_acks_late = True           # only ack after successful processing
celery.conf.worker_prefetch_multiplier = 1  # one task at a time per worker
```

---

## Test Scenarios

| ID | Scenario | Expected |
|----|----------|----------|
| T1 | Enqueue notification | notifications row created, task queued |
| T2 | SMTP success | status=SENT, sent_at populated |
| T3 | SMTP failure, first attempt | status=PENDING, retry queued |
| T4 | SMTP failure 5 times | status=FAILED, error logged |
| T5 | Delivery log for application | Returns all notifications for that application |

## Acceptance Criteria
- `task_acks_late=True` prevents task loss on worker crash
- Exponential backoff: 60s, 120s, 240s, 480s, 960s
- All emails rendered from Jinja2 templates (no inline HTML strings)
- Bulk operation (1,000 notifications) dispatched within 5 minutes (SRS SR1)
- Notification status queryable via communication logs endpoint
