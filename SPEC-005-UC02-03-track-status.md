# SPEC-005 — Track Application Status
## Maps to: UC-02-03

## Goal
Applicant views real-time status of their transfer application including a dynamic progress bar showing all pipeline stages, the current active stage, and the final result. Status updates reflected within ≤2 minutes without manual refresh (SRS SR1).

## Depends On
SPEC-004

---

## Tasks

### Task 1 — Status API
File: `backend/app/api/applications.py` (extension)

```
GET /api/applications/{id}/status
  Auth: APPLICANT (own) | any STAFF
  Response (200):
  {
    tracking_number: str,
    status: AppStatus,
    progress: {
      stages: [{ name, label_tr, label_en, completed, active }],
      current_stage: str
    },
    history: [
      { status, changed_at, changed_by_role, note }
    ],
    result: { outcome, reason } | null   # populated when ANNOUNCED or REJECTED
  }
  Performance: < 3 seconds (SRS UC-02-03 perf requirement)
  Error (DB down): 503 "Unable to retrieve application information. Please try again later." (SRS EX-01)
```

Stage history: query `audit_logs` where `entity_type='Application'` AND `entity_id=application_id`, ordered by `created_at DESC`.

**Progress bar stages (in order):**
```python
PIPELINE_STAGES = [
  { "name": "SUBMITTED",      "label_tr": "Başvuru Alındı",         "label_en": "Submitted" },
  { "name": "UNDER_REVIEW",   "label_tr": "Belge Doğrulama",        "label_en": "Document Verification" },
  { "name": "ENGLISH_REVIEW", "label_tr": "İngilizce Yeterliliği",  "label_en": "English Proficiency" },
  { "name": "DEPT_EVAL",      "label_tr": "Bölüm Değerlendirmesi",  "label_en": "Department Evaluation" },
  { "name": "RANKING",        "label_tr": "Sıralama",               "label_en": "Ranking" },
  { "name": "ANNOUNCED",      "label_tr": "Sonuç Açıklandı",        "label_en": "Result Announced" },
]
```

### Task 2 — Real-Time Updates via Server-Sent Events (SSE)
File: `backend/app/api/events.py`

```
GET /api/applications/{id}/events
  Auth: APPLICANT (own)
  Response: text/event-stream
  Event format: data: { "type": "STATUS_CHANGED", "status": "UNDER_REVIEW", "updated_at": "..." }
```

Implementation:
- Redis pub/sub channel: `app_status:{application_id}`
- `ApplicationService.change_status()` publishes to this channel after every transition
- SSE endpoint subscribes and streams to client
- Latency requirement: status visible to applicant within 2 minutes (SRS SR1)

### Task 3 — Application Progress Helper
In `Application` ORM model:

```python
def get_progress(self) -> dict:
    stages = ["SUBMITTED","UNDER_REVIEW","ENGLISH_REVIEW","DEPT_EVAL","RANKING","ANNOUNCED"]
    idx = stages.index(self.status) if self.status in stages else -1
    return {
        "current_stage": self.status,
        "stages": [
            {"name": s, "completed": i < idx, "active": i == idx}
            for i, s in enumerate(stages)
        ]
    }
```

### Task 4 — Frontend Status Page
File: `frontend/src/pages/ApplicationStatusPage.tsx`

Components:
- `<ProgressBar>` — shows all 6 stages, highlights completed (green) and current (blue)
- `<StatusHistory>` — timeline of status changes with timestamps
- REJECTED state: rejection reason in red text, no action buttons (SRS AC-02)
- ANNOUNCED state: display "Accepted / Waitlisted / Rejected" final outcome
- CORRECTION_REQUESTED: warning banner + "Upload Documents" button (SRS AC-03)
- SSE listener: auto-refresh UI when event received

---

## Test Scenarios (from SRS)

| ID | Scenario | Expected |
|----|----------|----------|
| T1 | Applicant views own application status | 200, progress + history returned within 3s |
| T2 | Applicant views another applicant's status | 403 |
| T3 | DB unavailable (EX-01) | 503 "Unable to retrieve application information. Please try again later." |
| T4 | Network lost during view (EX-02) | Client shows "Network error. Please check your internet connection." |
| T5 | Session expired (EX-03) | Redirect to login with "Session expired. Please log in again." |
| T6 | Application REJECTED (AC-02) | Rejection reason shown in red, no action buttons |
| T7 | Application CORRECTION_REQUESTED (AC-03) | Warning + Upload button shown |
| T8 | Status changes in backend | SSE event received; UI updates within 2 minutes |
| T9 | Archived/past application (AC-01) | Opened in read-only mode |

---

## Acceptance Criteria (from SRS)
- Status page loads within 3 seconds (SRS UC-02-03 performance)
- Real-time update latency ≤ 2 minutes (SRS SR1)
- DB failure returns graceful error message (SRS EX-01)
- Rejection reason shown in red for REJECTED status (SRS AC-02)
- Progress bar shows correct stage highlighting for all 6 pipeline stages
