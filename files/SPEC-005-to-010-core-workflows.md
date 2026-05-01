# SPEC-005 — Track Application Status

## Goal
Applicant views real-time application status with dynamic progress bar. Status updates reflected in UI within ≤ 2 minutes without page refresh.

## Depends On
SPEC-004

---

## Tasks

### Task 1 — Status Query Endpoints
File: `backend/app/api/applications.py` (extension)

```
GET /api/applications/{id}/status
  Auth: APPLICANT (own) | any STAFF
  Response: {
    tracking_number, status, progress: {...},
    history: [{ status, changed_at, changed_by_role, note }]
  }
  Performance: < 3 seconds (SRS UC-02-03 SR1)
```

Status history: query `audit_logs` where `entity_type='Application'` and `entity_id=application_id`, ordered by `created_at DESC`.

### Task 2 — Server-Sent Events (SSE) for Real-Time Updates
File: `backend/app/api/events.py`

```
GET /api/applications/{id}/events
  Auth: APPLICANT (own)
  Response: text/event-stream
  Events emitted: { type: "STATUS_CHANGED", data: { status, updated_at } }
```

Implementation:
- Redis pub/sub channel: `app_status:{application_id}`
- When `ApplicationService.change_status()` is called, publish to this channel
- SSE endpoint subscribes and streams to the client
- Client reconnects automatically on disconnect

### Task 3 — Frontend Status Page
File: `frontend/src/pages/ApplicationStatusPage.tsx`

Components:
- `<ProgressBar stages={...} currentStage={...} />` — shows all stages, highlights current
- `<StatusHistory entries={...} />` — timeline of status changes
- For REJECTED status: display rejection reason in red text, hide all action buttons
- For ANNOUNCED status: display final result (Accepted / Waitlisted / Rejected)

---

## Test Scenarios

| ID | Scenario | Expected |
|----|----------|----------|
| T1 | Get status of own application | 200, progress data |
| T2 | Get status of another applicant's application | 403 |
| T3 | DB unavailable | 503 "Unable to retrieve information. Please try again later." |
| T4 | SSE: status changes in backend | SSE event received within 2 minutes |
| T5 | Rejected application | Reason in red text, no action buttons |

## Acceptance Criteria
- Status page loads within 3 seconds (SRS UC-02-03)
- Status changes reflected within 2 minutes without manual refresh (SRS SR1)
- DB failure shows graceful error message (SRS UC-02-03 EX-01)

---
---

# SPEC-006 — Student Affairs: Oversee Application Documents

## Goal
Student Affairs Officer reviews submitted applications, previews documents in-browser, and takes one of three actions: Approve Verification, Request Correction, or Reject.

## Depends On
SPEC-004

---

## Tasks

### Task 1 — Student Affairs API
File: `backend/app/api/student_affairs.py`

```
GET /api/staff/applications
  Auth: STUDENT_AFFAIRS
  Query: status, program_id, period_id (filters)
  Response: 200 [ApplicationSummary + auto_validation_results]

GET /api/staff/applications/{id}
  Auth: STUDENT_AFFAIRS
  Response: 200 ApplicationDetail + Documents + EligibilityChecks

POST /api/staff/applications/{id}/approve-verification
  Auth: STUDENT_AFFAIRS
  Response: 200, status → UNDER_REVIEW
  Side effects: AuditLog, notify applicant

POST /api/staff/applications/{id}/request-correction
  Auth: STUDENT_AFFAIRS
  Body: { note: str (required) }
  Response: 200, status → CORRECTION_REQUESTED
  Side effects: AuditLog, notify applicant with note

POST /api/staff/applications/{id}/reject
  Auth: STUDENT_AFFAIRS
  Body: { rejection_reason_code: str, note: str }
  Response: 200, status → REJECTED
  Side effects: AuditLog, notify applicant
```

Rejection reason codes: `"INVALID_DOCUMENT"`, `"FRAUDULENT_DOCUMENT"`, `"DUPLICATE_APPLICATION"`, `"MISSED_DEADLINE"`, `"OTHER"`

### Task 2 — Document Preview
Reuse `DocumentService.generate_preview_url()` from SPEC-004.
- Document renders in built-in browser viewer (return URL with `Content-Disposition: inline`)
- No file download required

### Task 3 — OfficerApplicationService
File: `backend/app/services/officer_service.py`

```python
class OfficerApplicationService:
    async def approve_verification(self, application_id: UUID, officer_id: UUID) -> Application
    async def request_correction(self, application_id: UUID, officer_id: UUID, note: str) -> Application
    async def reject_application(self, application_id: UUID, officer_id: UUID,
                                  reason_code: str, note: str) -> Application
```

All methods:
1. Call `ApplicationService.change_status()`
2. Call `AuditService.log_status_change()`
3. Enqueue notification to applicant via Celery

---

## Test Scenarios

| ID | Scenario | Expected |
|----|----------|----------|
| T1 | Officer approves verification | status=UNDER_REVIEW, audit logged, applicant notified |
| T2 | Officer requests correction with note | status=CORRECTION_REQUESTED, note saved, applicant notified |
| T3 | Officer rejects | status=REJECTED, reason code saved, applicant notified |
| T4 | Preview document | Pre-signed URL returned, document viewable in browser |
| T5 | Preview corrupted document | 200 URL returned; frontend shows "File may be corrupted" error |
| T6 | Non-officer accesses endpoint | 403 |

## Acceptance Criteria
- Officer action (approve/reject/correct) recorded in audit_logs with timestamp and officer ID
- Applicant notification enqueued within 2 seconds of action
- Corrupted file does not crash the system — graceful error message shown

---
---

# SPEC-007 — Student Affairs: Notify Transfer Results

## Goal
Student Affairs Officer publishes final results. System bulk-notifies all applicants. Announcements are irreversible. 1,000 notifications delivered within 5 minutes.

## Depends On
SPEC-006, SPEC-019 (Notification Worker)

---

## Tasks

### Task 1 — Results Publication API
File: `backend/app/api/student_affairs.py`

```
GET /api/staff/results/{period_id}/{program_id}
  Auth: STUDENT_AFFAIRS
  Response: 200 { primary: [ApplicantResult], waitlisted: [ApplicantResult] }
  Note: Read-only — no edit buttons. Lists match ranking data.

POST /api/staff/results/{period_id}/{program_id}/publish
  Auth: STUDENT_AFFAIRS
  Response: 200 { announced_count: int }
  Errors: 409 already published | 422 ranking not approved
  Side effects:
    - Atomic SQL UPDATE: all RANKING apps → ANNOUNCED in one transaction
    - Enqueue bulk notifications (Celery)
    - Write AuditLog action "RESULTS_PUBLISHED"
  This action is IRREVERSIBLE (enforced by DB constraint + service check)
```

### Task 2 — Bulk Notification Task
File: `backend/app/workers/notification_tasks.py`

```python
@celery.task(bind=True, max_retries=5)
def send_result_notification(self, notification_id: UUID):
    # Fetch notification record
    # Send via SMTP
    # On success: update status=SENT, sent_at=NOW()
    # On failure: increment retry_count, re-raise for Celery retry with exponential backoff
    # If retry_count >= max_retries: update status=FAILED, log error
```

Bulk enqueue: iterate all ANNOUNCED applications for this period/program, create one `notifications` record each, then `send_result_notification.delay(notification_id)` for each.

---

## Test Scenarios

| ID | Scenario | Expected |
|----|----------|----------|
| T1 | Publish results | All apps status=ANNOUNCED, notifications enqueued |
| T2 | Publish already-published results | 409 |
| T3 | Publish with unapproved ranking | 422 |
| T4 | SMTP failure during send | Retry queued, status=PENDING |
| T5 | Max retries exceeded | status=FAILED, error logged |

## Acceptance Criteria
- Bulk notification for 1,000 applicants dispatched within 5 minutes (SRS UC-03-02 SR1)
- Results page is read-only — no manual edit possible (SRS UC-03-02 SR3)
- Publication action is irreversible (SRS UC-03-02)
- Publication event written to audit_logs with timestamp and officer ID

---
---

# SPEC-008 — Transfer Commission: Verify Scores & Convert GPA

## Goal
Transfer Commission (YGK) member verifies YKS exam scores via ÖSYM and runs the YÖK GPA conversion formula.

## Depends On
SPEC-004

---

## Tasks

### Task 1 — GPA Conversion Logic
File: `backend/app/services/evaluation_service.py`

```python
def convert_gpa_yok(gpa_4: float) -> float:
    """Convert 4.0-scale GPA to 100-scale using YÖK official table."""
    # Table-based lookup, not formula (use official YÖK mapping)
    # Example: 4.00 → 100, 3.50 → 88.33, 3.00 → 76.67, 2.50 → 65.00, ...
```

### Task 2 — EvaluationService
File: `backend/app/services/evaluation_service.py`

```python
class EvaluationService:
    async def verify_scores(self, application_id: UUID, evaluator_id: UUID) -> AcademicRecord
    # 1. Fetch ÖSYM score (async, 10s timeout)
    # 2. Convert GPA using YÖK table
    # 3. Update academic_records with verified scores
    # 4. Lock scores (add is_locked=True field to academic_records)
    # 5. Change status → DEPT_EVAL (via ApplicationService.change_status)
    # 6. Write AuditLog action "SCORES_VERIFIED"
```

### Task 3 — YGK API
File: `backend/app/api/evaluation.py`

```
GET /api/ygk/applications
  Auth: TRANSFER_COMMISSION
  Query: status=UNDER_REVIEW
  Response: [ApplicationSummary]

GET /api/ygk/applications/{id}/evaluation
  Auth: TRANSFER_COMMISSION
  Response: { application, academic_record, gpa_100_converted, documents }

POST /api/ygk/applications/{id}/verify-scores
  Auth: TRANSFER_COMMISSION
  Response: 200 { academic_record with verified scores and gpa_100 }
  Errors: 422 if ÖSYM data unavailable
```

---

## Test Scenarios

| ID | Scenario | Expected |
|----|----------|----------|
| T1 | Verify scores — ÖSYM responds | Scores locked, gpa_100 computed, status→DEPT_EVAL |
| T2 | Verify scores — ÖSYM timeout | 503, partial error detail logged |
| T3 | Discrepancy: declared GPA ≠ ÖSYM value | Evaluator can see both values; uses verified value |
| T4 | Non-YGK member accesses endpoint | 403 |

## Acceptance Criteria
- GPA conversion uses official YÖK table (not linear formula)
- Scores locked after verification (cannot be edited again without SYSTEM_ADMIN override)
- Verification written to audit_logs with evaluator ID and timestamp (SRS UC-04-01 SR2)

---
---

# SPEC-009 — Transfer Commission: Evaluate Department Conditions

## Goal
YGK evaluates application against configurable department-specific requirements. Ineligible applications auto-rejected. Manual evaluation notes supported.

## Depends On
SPEC-008

---

## Tasks

### Task 1 — Eligibility Engine
File: `backend/app/services/eligibility_engine.py`

```python
class EligibilityEngine:
    async def evaluate_department_conditions(
        self, application_id: UUID, evaluator_id: UUID
    ) -> DepartmentEvaluation
    # 1. Load DepartmentRequirement records for the target program
    # 2. Evaluate each rule against application's academic_record
    # 3. Store results in eligibility_checks
    # 4. If any rule fails: change_status → REJECTED, notify applicant
    # 5. If all pass: create DepartmentEvaluation record (passed=True)
    # 6. Write AuditLog
```

Supported rule_keys:
- `MIN_GPA` — compare academic_record.gpa_4 >= rule_value
- `MIN_YKS_SCORE` — compare academic_record.yks_score >= rule_value
- `MIN_CREDITS` — compare academic_record.credits_completed >= rule_value
- `REQUIRED_DOC` — check document of that type exists and is ACCEPTED

### Task 2 — API Endpoint
File: `backend/app/api/evaluation.py`

```
POST /api/ygk/applications/{id}/evaluate-conditions
  Auth: TRANSFER_COMMISSION
  Body: { notes: str (optional) }
  Response: 200 { evaluation, checks: [{ rule_key, passed, detail }] }
```

---

## Test Scenarios

| ID | Scenario | Expected |
|----|----------|----------|
| T1 | All conditions pass | DeptEvaluation created, status→RANKING |
| T2 | GPA condition fails | status→REJECTED, specific reason in detail |
| T3 | Missing required document | specific check failure returned |

## Acceptance Criteria
- Eligibility rules are stored in DB (not hardcoded) — IT admin can update without deployment
- Each failed rule produces a human-readable reason message
- All evaluation results written to eligibility_checks table

---
---

# SPEC-010 — Transfer Commission: Generate & Approve Ranking

## Goal
System generates deterministic ranking for all eligible applicants of a program+period. YGK approves or returns for correction. Approval uses SERIALIZABLE isolation + row-level lock.

## Depends On
SPEC-009

---

## Tasks

### Task 1 — Ranking Score Formula
File: `backend/app/services/ranking_service.py`

Composite score formula (per YÖK regulation):
```
composite_score = (gpa_100 * 0.50) + (yks_score_normalized * 0.50)
```
Where `yks_score_normalized` = raw YKS score scaled to 100.

This must be a **pure function** — same inputs always yield same output. No randomness.

### Task 2 — RankingService
File: `backend/app/services/ranking_service.py`

```python
class RankingService:
    async def generate_ranking(
        self, program_id: UUID, period_id: UUID, generated_by: UUID
    ) -> Ranking
    # 1. Fetch all DEPT_EVAL-passed applications for this program+period
    # 2. Calculate composite_score for each
    # 3. Sort descending by composite_score (deterministic: tie-break by submitted_at ASC)
    # 4. Assign position 1..N
    # 5. Mark positions 1..quota as is_primary=True, rest as is_primary=False (waitlisted)
    # 6. Create Ranking record (status=DRAFT)
    # 7. Create RankingEntry records
    # 8. Write AuditLog "RANKING_GENERATED"

    async def approve_ranking(
        self, ranking_id: UUID, approver_id: UUID
    ) -> Ranking
    # MUST use SERIALIZABLE isolation + SELECT FOR UPDATE
    # 1. Lock ranking row
    # 2. Validate ranking.status == DRAFT
    # 3. Update ranking: status=APPROVED, approved_by, approved_at
    # 4. Update all associated application statuses → RANKING (via change_status)
    # 5. Write AuditLog "RANKING_APPROVED"
    # Concurrency: if serialization conflict → raise 409 "Ranking was modified, please retry"

    async def return_for_correction(
        self, ranking_id: UUID, reviewer_id: UUID, note: str
    ) -> Ranking
    # Soft-mark ranking as needing regeneration; log reason
```

### Task 3 — Ranking API
File: `backend/app/api/ranking.py`

```
POST /api/ygk/rankings/generate
  Auth: TRANSFER_COMMISSION
  Body: { program_id, period_id }
  Response: 201 Ranking

GET /api/ygk/rankings/{ranking_id}
  Auth: TRANSFER_COMMISSION
  Response: Ranking + RankingEntries + composite scores

POST /api/ygk/rankings/{ranking_id}/approve
  Auth: TRANSFER_COMMISSION
  Response: 200 Ranking (status=APPROVED)
  Errors: 409 concurrent modification | 403 not authorized

POST /api/ygk/rankings/{ranking_id}/return
  Auth: TRANSFER_COMMISSION
  Body: { note }
  Response: 200
```

---

## Test Scenarios

| ID | Scenario | Expected |
|----|----------|----------|
| T1 | Generate ranking for 10 applicants | Sorted by composite_score, quota respected |
| T2 | Tie in composite score | Tie broken by submitted_at ASC |
| T3 | Approve ranking | status=APPROVED, locked (no further edits) |
| T4 | Two concurrent approval requests | One succeeds, one gets 409 |
| T5 | Approve ranking with missing score data | 422 |

## Acceptance Criteria
- Composite score formula is deterministic (pure function, unit-testable)
- Ranking approval is atomic (transaction commits all or nothing)
- Post-approval: ranking entries cannot be modified (DB constraint + service check)
- All ranking events written to audit_logs
