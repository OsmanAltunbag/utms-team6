"""SRS-facing display labels for application statuses."""

from app.domain.enums import AppStatus

_SRS_LABELS: dict[AppStatus, str] = {
    AppStatus.DRAFT: "Draft",
    AppStatus.SUBMITTED: "Submitted",
    AppStatus.UNDER_REVIEW: "Verified",
    AppStatus.CORRECTION_REQUESTED: "Correction Requested",
    AppStatus.ENGLISH_REVIEW: "English Review",
    AppStatus.DEPT_EVAL: "Department Evaluation",
    AppStatus.RANKING: "Ranking",
    AppStatus.ANNOUNCED: "Announced",
    AppStatus.REJECTED: "Rejected",
}


def srs_display_status(status: AppStatus) -> str:
    return _SRS_LABELS.get(status, status.value)
