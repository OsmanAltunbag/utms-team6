# UTMS — Implementation Plan

## Spec Overview

| Spec | Title | Size | Status | Depends On |
|------|-------|------|--------|------------|
| SPEC-001 | Database Schema & Migrations | L | TODO | — |
| SPEC-002 | Authentication — Login & Logout | M | TODO | SPEC-001 |
| SPEC-003 | Authentication — Register & Password Reset | M | TODO | SPEC-001 |
| SPEC-004 | Application — Submit Transfer Application | L | TODO | SPEC-002, SPEC-003 |
| SPEC-005 | Application — Track Status & Progress | S | TODO | SPEC-004 |
| SPEC-006 | Student Affairs — Oversee Documents | M | TODO | SPEC-004 |
| SPEC-007 | Student Affairs — Notify Transfer Results | M | TODO | SPEC-006 |
| SPEC-008 | Transfer Commission — Verify Scores & Convert GPA | M | TODO | SPEC-004 |
| SPEC-009 | Transfer Commission — Evaluate Department Conditions | M | TODO | SPEC-008 |
| SPEC-010 | Transfer Commission — Generate & Approve Ranking | L | TODO | SPEC-009 |
| SPEC-011 | Transfer Commission — Course Equivalency (Intibak) | M | TODO | SPEC-010 |
| SPEC-012 | Transfer Commission — Process Waitlisted Applicants | S | TODO | SPEC-010 |
| SPEC-013 | YDYO — English Proficiency Approval | M | TODO | SPEC-004 |
| SPEC-014 | YDYO — Announce Proficiency Exam Results | S | TODO | SPEC-013 |
| SPEC-015 | Dean's Office — Final Application Decision | M | TODO | SPEC-010, SPEC-013 |
| SPEC-016 | IT/Admin — Staff Registration & Role Management | M | TODO | SPEC-001 |
| SPEC-017 | IT/Admin — Configure Application Periods | S | TODO | SPEC-016 |
| SPEC-018 | Applicant Q&A — Questions & Replies | S | TODO | SPEC-002 |
| SPEC-019 | Notification Worker — Email Delivery & Retry | M | TODO | SPEC-001 |

## Dependency Order for Implementation

```
SPEC-001  (foundation)
    ↓
SPEC-002, SPEC-003, SPEC-016, SPEC-019  (parallel)
    ↓
SPEC-004
    ↓
SPEC-005, SPEC-006, SPEC-008, SPEC-013, SPEC-018  (parallel)
    ↓
SPEC-007, SPEC-009, SPEC-014  (parallel)
    ↓
SPEC-010, SPEC-015
    ↓
SPEC-011, SPEC-012, SPEC-017
```
