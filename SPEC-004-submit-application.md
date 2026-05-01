# SPEC-004 — Submit Transfer Application

## Goal
Applicant creates and submits a transfer application. System auto-fetches academic data from UBYS, ÖSYM, YÖKSİS in parallel. Validates documents, checks eligibility (GPA, YKS), and issues a tracking number.

## Depends On
SPEC-002, SPEC-003

---

## Tasks

### Task 1 — External Adapters
File: `backend/app/external/`

**ubys_adapter.py**
```python
class UBYSAdapter:
    async def fetch_transcript(self, national_id: str) -> TranscriptData
    # TranscriptData: { gpa_4: float, credits: int, institution: str }
    # Timeout: 10 seconds; raise ExternalServiceTimeoutError on failure
```

**yoksis_adapter.py**
```python
class YOKSISAdapter:
    async def fetch_academic_record(self, national_id: str) -> YOKSISRecord
    # YOKSISRecord: { gpa_4: float, institution: str, credits: int }
    # Timeout: 10 seconds
```

**osym_adapter.py**
```python
class OSYMAdapter:
    async def fetch_yks_score(self, national_id: str) -> YKSScore
    # YKSScore: { score: float, exam_year: int, score_type: str }
    # Timeout: 10 seconds
```

All adapters: mocked in tests via `pytest-mock`. Inject via FastAPI dependency.

### Task 2 — ApplicationService (Core)
File: `backend/app/services/application_service.py`

```python
class ApplicationService:
    async def create_application(
        self, applicant_id: UUID, program_id: UUID, period_id: UUID
    ) -> Application
    # Checks: period is open, no duplicate application for same program+period

    async def fetch_academic_data(self, application_id: UUID) -> AcademicRecord
    # Runs UBYS + YOKSIS + OSYM calls in parallel (asyncio.gather)
    # Total timeout: 10 seconds
    # Stores result in academic_records table

    async def run_eligibility_checks(self, application_id: UUID) -> list[EligibilityCheck]
    # Checks GPA >= program.min_gpa
    # Stores each check result in eligibility_checks table
    # Returns list with passed/failed results

    async def submit_application(self, application_id: UUID) -> Application
    # Validates all required documents uploaded
    # All eligibility checks must pass
    # Changes status DRAFT → SUBMITTED
    # Generates tracking_number = f"APP-{year}-{seq:05d}"
    # Writes AuditLog action "APPLICATION_SUBMITTED"
    # Enqueues confirmation notification to applicant

    async def change_status(
        self, application_id: UUID, new_status: AppStatus,
        actor_id: UUID, note: str | None = None
    ) -> Application
    # ALL status transitions go through this method
    # Validates transition is legal (state machine)
    # Writes AuditLog: old_value={status}, new_value={status, note}
```

**Legal state transitions:**
```
DRAFT → SUBMITTED
SUBMITTED → UNDER_REVIEW
SUBMITTED → REJECTED           (by student affairs: ineligible)
UNDER_REVIEW → ENGLISH_REVIEW
UNDER_REVIEW → CORRECTION_REQUESTED
UNDER_REVIEW → REJECTED
CORRECTION_REQUESTED → UNDER_REVIEW   (after applicant re-uploads)
ENGLISH_REVIEW → DEPT_EVAL    (YDYO approves)
ENGLISH_REVIEW → REJECTED     (YDYO rejects)
DEPT_EVAL → RANKING
DEPT_EVAL → REJECTED
RANKING → ANNOUNCED
RANKING → REJECTED
```

### Task 3 — Document Upload Service
File: `backend/app/services/document_service.py`

```python
class DocumentService:
    async def generate_upload_url(
        self, application_id: UUID, doc_type: DocType
    ) -> PresignedUploadResult
    # Returns { upload_url: str (5 min TTL), object_key: str }

    async def confirm_upload(
        self, application_id: UUID, doc_type: DocType, object_key: str,
        file_name: str, file_size: int
    ) -> Document
    # Validates: PDF only (check MIME type server-side)
    # Validates: file_size <= 5 MB (5_242_880 bytes)
    # Creates documents row (status=PENDING)
    # object_key stored as file_path (NOT a URL)

    async def generate_preview_url(self, document_id: UUID) -> str
    # Returns pre-signed GET URL (5 min TTL)
    # Validates caller has permission to view this document
```

### Task 4 — MinIO Client
File: `backend/app/core/storage.py`

```python
class MinIOClient:
    def generate_presigned_put(self, object_key: str, ttl: int = 300) -> str
    def generate_presigned_get(self, object_key: str, ttl: int = 300) -> str
    def get_object_metadata(self, object_key: str) -> dict  # for MIME validation
```

Object key format: `applications/{application_id}/{doc_type}/{uuid}.pdf`

### Task 5 — Application Router
File: `backend/app/api/applications.py`

```
POST /api/applications
  Auth: APPLICANT
  Body: { program_id, period_id }
  Response: 201 { application_id, status: "DRAFT" }
  Errors: 409 duplicate | 403 period closed

GET /api/applications/{id}
  Auth: APPLICANT (own) | any STAFF
  Response: 200 ApplicationDetail

GET /api/applications
  Auth: APPLICANT → own applications only
        STAFF → filtered by status/program
  Response: 200 [ApplicationSummary]

POST /api/applications/{id}/fetch-academic-data
  Auth: APPLICANT (own)
  Response: 200 AcademicRecord

POST /api/applications/{id}/submit
  Auth: APPLICANT (own)
  Response: 200 { tracking_number, status }
  Errors: 422 missing docs | 422 eligibility failed

GET /api/applications/{id}/documents
  Auth: APPLICANT (own) | STAFF
  Response: 200 [DocumentSummary]

POST /api/applications/{id}/documents/upload-url
  Auth: APPLICANT (own)
  Body: { doc_type }
  Response: 200 { upload_url, object_key }

POST /api/applications/{id}/documents/confirm
  Auth: APPLICANT (own)
  Body: { doc_type, object_key, file_name, file_size }
  Response: 201 Document

GET /api/documents/{doc_id}/preview-url
  Auth: APPLICANT (own) | STAFF
  Response: 200 { preview_url }
```

### Task 6 — Application Progress Method
In the `Application` ORM model:

```python
def get_progress(self) -> dict:
    stages = [
        "SUBMITTED", "UNDER_REVIEW", "ENGLISH_REVIEW",
        "DEPT_EVAL", "RANKING", "ANNOUNCED"
    ]
    current_index = stages.index(self.status) if self.status in stages else -1
    return {
        "current_stage": self.status,
        "stages": [
            {"name": s, "completed": i < current_index, "active": i == current_index}
            for i, s in enumerate(stages)
        ]
    }
```

---

## Test Scenarios

| ID | Scenario | Expected |
|----|----------|----------|
| T1 | Applicant creates application during open period | 201, status=DRAFT |
| T2 | Applicant creates duplicate application same program | 409 |
| T3 | Create application when period is closed | 403 |
| T4 | Fetch academic data — all APIs respond | AcademicRecord saved |
| T5 | Fetch academic data — one API times out | Partial record, error detail logged |
| T6 | Upload non-PDF file | 422 "Invalid file format" |
| T7 | Upload file >5 MB | 422 "File too large" |
| T8 | Submit with all docs, GPA passes | 200, status=SUBMITTED, tracking number issued |
| T9 | Submit with GPA below threshold | 422, specific reason shown |
| T10 | Submit with missing required doc | 422, lists missing doc types |
| T11 | Get preview URL | 200, pre-signed URL with 5-min TTL |
| T12 | Status transition invalid path | 422 "Invalid status transition" |

---

## Acceptance Criteria
- Academic data fetched in parallel within 10 seconds (SRS PER-02)
- Tracking number generated within 2 seconds of submission (SRS UC-02-02)
- File format validated server-side (not only client-side)
- No public URL ever stored in `documents.file_path`
- Preview URLs expire after 5 minutes
- All status changes written to `audit_logs` with old and new status
- Eligibility failure message includes specific reason (e.g. "GPA 2.30 < minimum 3.00")
