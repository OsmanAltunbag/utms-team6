# SPEC-004 — Submit Transfer Application
## Maps to: UC-02-02

## Goal
Applicant creates and submits a transfer application. System auto-fetches academic data from UBYS, ÖSYM, YÖKSİS in parallel. Validates documents (PDF only, ≤5MB), runs automated eligibility checks (GPA, YKS), and issues a tracking reference number on successful submission.

## Depends On
SPEC-002 (Auth), SPEC-003 (Registration)

---

## Tasks

### Task 1 — External API Adapters (all mocked in tests)
File: `backend/app/external/`

**ubys_adapter.py**
```python
class UBYSAdapter:
    async def fetch_transcript(self, national_id: str) -> TranscriptData
    # TranscriptData: { gpa_4: float, credits: int, institution: str }
    # Timeout: 10 s; raise ExternalServiceTimeoutError on failure
```

**yoksis_adapter.py**
```python
class YOKSISAdapter:
    async def fetch_academic_record(self, national_id: str) -> YOKSISRecord
    # YOKSISRecord: { gpa_4: float, institution: str, credits: int }
    # Timeout: 10 s
```

**osym_adapter.py**
```python
class OSYMAdapter:
    async def fetch_yks_score(self, national_id: str) -> YKSScore
    # YKSScore: { score: float, exam_year: int, score_type: str }
    # Timeout: 10 s
```

### Task 2 — ApplicationService
File: `backend/app/services/application_service.py`

```python
class ApplicationService:
    async def create_application(
        self, applicant_id: UUID, program_id: UUID, period_id: UUID
    ) -> Application
    # Guards: period is open (use server-side time, NOT client time)
    #         no duplicate application for same program+period → 409

    async def fetch_academic_data(self, application_id: UUID) -> AcademicRecord
    # Run UBYS + YÖKSİS + ÖSYM in parallel via asyncio.gather
    # Total timeout budget: 10 seconds (SRS PER-02)
    # Persist result in academic_records table

    async def run_eligibility_checks(self, application_id: UUID) -> list[EligibilityCheck]
    # Check: gpa_4 >= program.min_gpa
    # Check: yks_score >= program.min_yks_score (if configured)
    # Store each check in eligibility_checks table
    # Completes within 3 seconds (SRS PER-05)

    async def submit_application(self, application_id: UUID) -> Application
    # Validate all required documents are uploaded
    # All eligibility checks must pass; if not → 422 with specific reason
    # Change status: DRAFT → SUBMITTED
    # Generate tracking_number = f"APP-{year}-{seq:05d}"
    # Tracking number stored within 2 seconds (SRS UC-02-02)
    # Enqueue confirmation notification via Celery
    # Write AuditLog action="APPLICATION_SUBMITTED"
```

**Legal status transitions (ALL must go through change_status()):**
```
DRAFT → SUBMITTED
SUBMITTED → UNDER_REVIEW
SUBMITTED → REJECTED
UNDER_REVIEW → ENGLISH_REVIEW
UNDER_REVIEW → CORRECTION_REQUESTED
UNDER_REVIEW → REJECTED
CORRECTION_REQUESTED → UNDER_REVIEW
ENGLISH_REVIEW → DEPT_EVAL
ENGLISH_REVIEW → REJECTED
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
    # Returns { upload_url (5-min TTL), object_key }

    async def confirm_upload(
        self, application_id: UUID, doc_type: DocType,
        object_key: str, file_name: str, file_size_bytes: int
    ) -> Document
    # Server-side validation: PDF MIME type only (SRS UC-02-02 EX.2)
    # Max size: 5 MB = 5_242_880 bytes (SRS PER-03)
    # Store: object_key as file_path — NEVER a public URL
    # Upload + validation within 5 seconds (SRS PER-03)

    async def generate_preview_url(self, document_id: UUID, caller_id: UUID) -> str
    # Pre-signed GET URL (5-min TTL)
    # Validates caller has permission to view this document (KVKK)
```

### Task 4 — Application Router
File: `backend/app/api/applications.py`

```
POST /api/applications
  Auth: APPLICANT
  Body: { program_id, period_id }
  Response: 201 { application_id, status: "DRAFT" }
  Errors: 409 duplicate | 403 period closed

GET /api/applications
  Auth: APPLICANT → own only | STAFF → filtered
  Response: 200 [ApplicationSummary]

GET /api/applications/{id}
  Auth: APPLICANT (own) | any STAFF
  Response: 200 ApplicationDetail

POST /api/applications/{id}/fetch-academic-data
  Auth: APPLICANT (own)
  Response: 200 AcademicRecord

POST /api/applications/{id}/submit
  Auth: APPLICANT (own)
  Response: 200 { tracking_number, status: "SUBMITTED" }
  Errors: 422 missing docs (lists them) | 422 eligibility failed (specific reason)

GET /api/applications/{id}/documents
  Auth: APPLICANT (own) | STAFF
  Response: 200 [DocumentSummary]

POST /api/applications/{id}/documents/upload-url
  Auth: APPLICANT (own)
  Body: { doc_type }
  Response: 200 { upload_url, object_key }

POST /api/applications/{id}/documents/confirm
  Auth: APPLICANT (own)
  Body: { doc_type, object_key, file_name, file_size_bytes }
  Response: 201 Document
  Error: 422 "Invalid file format. Please upload a PDF file." (SRS EX.2)
         422 "File exceeds 5 MB limit."

GET /api/documents/{doc_id}/preview-url
  Auth: APPLICANT (own) | STAFF
  Response: 200 { preview_url }
```

### Task 5 — Document Data Extraction & User Verification

After a document is uploaded, the system automatically extracts relevant data from it and presents the extracted information to the applicant for confirmation before submission.

**Extractor:** `backend/app/external/document_extractor.py`

```python
class DocumentExtractor:
    async def extract(self, doc_type: DocType, file_bytes: bytes) -> dict
    # Returns structured data depending on doc_type:
    # TRANSCRIPT:    { gpa: float, completed_credits: int, total_credits: int, institution: str }
    # YKS_RESULT:   { score: float, score_type: str, exam_year: int }
    # LANGUAGE_CERT: { certificate_type: str, score: int, validity_date: str }
    # ID_COPY:       { national_id_verified: bool }
    # Others:        {} (empty — no extraction for MILITARY_STATUS, DISCIPLINE_RECORD, OTHER)
    # Mocked in tests; real integration uses UBYS/ÖSYM OCR pipeline
```

**Schema changes (documents table):**
```sql
ALTER TABLE documents ADD COLUMN extracted_data  JSONB    DEFAULT NULL;
ALTER TABLE documents ADD COLUMN extraction_confirmed BOOLEAN NOT NULL DEFAULT FALSE;
```

**Verify endpoint:**
```
POST /api/applications/{id}/documents/{doc_id}/verify
  Auth: APPLICANT (own application)
  Response: 200 { id, extraction_confirmed: true }
  Effect: sets extraction_confirmed = TRUE
```

**Upload flow (updated):**
1. Receive multipart file → validate PDF, ≤5 MB
2. Store in MinIO
3. Run extractor on file bytes → persist `extracted_data` in DB
4. Return `DocumentSummary` including `extracted_data` and `extraction_confirmed: false`

**Frontend verification card:**
- After upload, each `DocumentUploadRow` shows an "Extracted Information" card
  with the key-value pairs from `extracted_data`
- Card has a "Confirm" button; clicking calls the verify endpoint and updates `extraction_confirmed: true`
- If `extraction_confirmed` is `false` and `extracted_data` is non-empty, the card appears with a yellow border
- Once confirmed, the card turns green and the "Confirm" button disappears
- For doc types with no extraction (empty `extracted_data`), no card is shown

**Test scenarios:**
| ID  | Scenario | Expected |
|-----|----------|----------|
| T13 | Upload TRANSCRIPT → extraction result contains GPA, credits, institution | Extractor returns structured TRANSCRIPT data |
| T14 | Upload YKS_RESULT → extraction result contains score, type, year | Extractor returns structured YKS data |
| T15 | Confirm extracted data → extraction_confirmed becomes true | 200, extraction_confirmed=true in response |
| T16 | Upload MILITARY_STATUS → no extraction card shown | extracted_data is null/empty |

---

## Test Scenarios (from SRS test cases + EX flows)

| ID | Scenario | Expected |
|----|----------|----------|
| T1 | Create application during open period | 201, status=DRAFT |
| T2 | Create duplicate application same program+period | 409 |
| T3 | Create application when period is closed | 403 |
| T4 | Fetch academic data — all APIs respond within 10s | AcademicRecord saved |
| T5 | Fetch academic data — one API times out | Partial record, error logged |
| T6 | Upload .jpg file (non-PDF) | 422 "Invalid file format. Please upload a PDF file." |
| T7 | Upload file > 5 MB | 422 "File exceeds 5 MB limit." |
| T8 | Submit with all docs, GPA passes eligibility | 200, status=SUBMITTED, tracking number issued within 2s |
| T9 | Submit with GPA below threshold (EX.1) | 422, specific reason: "GPA 2.30 < minimum 3.00" |
| T10 | Submit with missing required document | 422, lists missing doc types |
| T11 | Eligibility check completes within 3 seconds | Performance assertion in integration test |
| T12 | Preview URL returned | 200, URL expires after 5 minutes |

---

## Acceptance Criteria (from SRS)
- External API data retrieval parallel, within 10 seconds (SRS PER-02, UC-02-02)
- Document upload + validation within 5 seconds per file (SRS PER-03)
- Eligibility checks within 3 seconds (SRS PER-05)
- Tracking number generated within 2 seconds of submission
- PDF-only enforcement is server-side (not client-only)
- `documents.file_path` NEVER contains `http` (CHECK constraint)
- Preview URLs expire after 5 minutes
- All status changes written to `audit_logs` with old + new status
- Eligibility failure shows specific reason (SRS UC-02-02 EX.1)
