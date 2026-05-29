import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.status_labels import srs_display_status
from app.domain.application import Application
from app.domain.audit import AuditLog
from app.domain.enums import AppStatus, RankStatus
from app.repositories.application_repository import ApplicationRepository
from app.repositories.ranking_repository import RankingRepository
from app.schemas.officer import (
    ApplicantResultEntry,
    ApplicationSummaryWithValidation,
    AutoValidationResult,
    PublishResultsResponse,
    ResultsListResponse,
)
from app.services.application_service import ApplicationService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

CORRUPTED_DOCUMENT_MESSAGE = (
    "Document Cannot Be Viewed – File May Be Corrupted."
)

REJECTION_REASON_CODES = frozenset({
    "INVALID_DOCUMENT",
    "FRAUDULENT_DOCUMENT",
    "DUPLICATE_APPLICATION",
    "MISSED_DEADLINE",
    "OTHER",
})


@dataclass
class ApplicationFilters:
    status: Optional[AppStatus] = None
    program_id: Optional[uuid.UUID] = None
    period_id: Optional[uuid.UUID] = None


@dataclass
class PublicationResult:
    announced_count: int
    notifications_enqueued: int
    published_at: datetime


def _result_outcome_for_entry(is_primary: bool) -> tuple[str, str]:
    """Return (email template result, SRS display label)."""
    if is_primary:
        return "Accepted", "Asil"
    return "Waitlisted", "Yedek"


def _result_outcome_for_unlisted() -> tuple[str, str]:
    return "Rejected", "Rejected"


def build_auto_validation_results(app: Application) -> List[AutoValidationResult]:
    results: List[AutoValidationResult] = []

    for check in app.eligibility_checks:
        results.append(
            AutoValidationResult(
                rule_key=check.rule_key,
                passed=check.passed,
                detail=check.detail,
            )
        )

    for doc in app.documents:
        passed = doc.extraction_confirmed
        detail: str | None = None
        if doc.extracted_data is None:
            detail = "Extraction not attempted"
            passed = False
        elif not doc.extracted_data:
            detail = "No data extracted from document"
            passed = False
        elif not doc.extraction_confirmed:
            detail = "Applicant has not confirmed extracted data"
        else:
            detail = "Document data confirmed by applicant"

        results.append(
            AutoValidationResult(
                rule_key=f"DOC_{doc.doc_type.value}",
                passed=passed,
                detail=detail,
            )
        )

    return results


class OfficerApplicationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._app_repo = ApplicationRepository(db)
        self._ranking_repo = RankingRepository(db)
        self._notif_service = NotificationService(db)
        self._app_service = ApplicationService(db)

    async def list_applications(
        self, filters: ApplicationFilters
    ) -> List[ApplicationSummaryWithValidation]:
        status_filter = filters.status or AppStatus.SUBMITTED
        apps = await self._app_repo.get_all_filtered(
            status=status_filter,
            program_id=filters.program_id,
            period_id=filters.period_id,
        )
        return [self._to_summary(app) for app in apps]

    async def get_application(self, application_id: uuid.UUID) -> Application:
        application = await self._app_repo.get_by_id(application_id)
        if application is None:
            raise HTTPException(status_code=404, detail="Application not found")
        return application

    async def approve_verification(
        self, application_id: uuid.UUID, officer_id: uuid.UUID
    ) -> Application:
        application = await self._require_submitted(application_id)
        application = await self._app_service.change_status(
            application_id=application_id,
            new_status=AppStatus.UNDER_REVIEW,
            actor_id=officer_id,
            note="Document verification approved",
        )
        await self._log_officer_action(
            officer_id=officer_id,
            action="DOCUMENT_VERIFIED",
            application_id=application_id,
            new_value={
                "status": AppStatus.UNDER_REVIEW.value,
                "display_status": srs_display_status(AppStatus.UNDER_REVIEW),
            },
        )
        await self._enqueue_notification(
            application=application,
            subject="UTMS — Document Verification Approved",
            body=(
                "Your application documents have been verified and your application "
                "has been routed to the relevant faculty/department for review."
            ),
            template_name="status_changed.html",
            template_context={
                "old_status": "Submitted",
                "new_status": srs_display_status(AppStatus.UNDER_REVIEW),
                "note": (
                    "Your application documents have been verified and routed "
                    "to the relevant faculty/department."
                ),
            },
        )
        return application

    async def request_correction(
        self, application_id: uuid.UUID, officer_id: uuid.UUID, note: str
    ) -> Application:
        if not note or not note.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Correction note is required",
            )

        application = await self._require_submitted(application_id)
        deadline = datetime.now(timezone.utc) + timedelta(
            days=settings.CORRECTION_DEADLINE_DAYS
        )
        deadline_str = deadline.strftime("%d.%m.%Y %H:%M UTC")

        application = await self._app_service.change_status(
            application_id=application_id,
            new_status=AppStatus.CORRECTION_REQUESTED,
            actor_id=officer_id,
            note=note.strip(),
        )
        application.correction_requested_at = datetime.now(timezone.utc)
        application.correction_deadline = deadline
        await self.db.flush()

        notification_body = (
            f"{note.strip()}\n\n"
            f"Please re-upload the corrected document(s) by {deadline_str}."
        )

        await self._log_officer_action(
            officer_id=officer_id,
            action="CORRECTION_REQUESTED",
            application_id=application_id,
            new_value={
                "status": AppStatus.CORRECTION_REQUESTED.value,
                "display_status": srs_display_status(AppStatus.CORRECTION_REQUESTED),
                "note": note.strip(),
                "correction_deadline": deadline.isoformat(),
            },
        )
        await self._enqueue_notification(
            application=application,
            subject="UTMS — Document Correction Requested",
            body=notification_body,
            template_name="correction_requested.html",
            template_context={
                "correction_note": note.strip(),
                "correction_deadline": deadline_str,
            },
        )
        return application

    async def reject_application(
        self,
        application_id: uuid.UUID,
        officer_id: uuid.UUID,
        reason_code: str,
        note: str,
    ) -> Application:
        if reason_code not in REJECTION_REASON_CODES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid rejection reason code: {reason_code}",
            )

        application = await self._require_rejectable(application_id)
        rejection_note = note.strip() if note else reason_code
        application = await self._app_service.change_status(
            application_id=application_id,
            new_status=AppStatus.REJECTED,
            actor_id=officer_id,
            note=rejection_note,
        )
        application.correction_deadline = None
        application.correction_requested_at = None
        await self.db.flush()

        await self._log_officer_action(
            officer_id=officer_id,
            action="APPLICATION_REJECTED",
            application_id=application_id,
            new_value={
                "status": AppStatus.REJECTED.value,
                "display_status": srs_display_status(AppStatus.REJECTED),
                "reason_code": reason_code,
                "note": rejection_note,
            },
        )
        await self._enqueue_notification(
            application=application,
            subject="UTMS — Application Rejected",
            body=rejection_note,
            template_name="status_changed.html",
            template_context={
                "old_status": srs_display_status(AppStatus.SUBMITTED),
                "new_status": srs_display_status(AppStatus.REJECTED),
                "note": rejection_note,
            },
        )
        return application

    async def get_results(
        self, period_id: uuid.UUID, program_id: uuid.UUID
    ) -> ResultsListResponse:
        ranking = await self._ranking_repo.get_by_program_and_period(
            program_id, period_id
        )
        if ranking is None:
            raise HTTPException(status_code=404, detail="Ranking not found")

        if ranking.status == RankStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Ranking has not been approved by the Dean's Office",
            )

        primary, waitlisted = self._split_ranking_entries(ranking)

        return ResultsListResponse(
            period_id=period_id,
            program_id=program_id,
            program_name=ranking.program.name if ranking.program else "",
            period_label=ranking.period.label if ranking.period else "",
            ranking_status=ranking.status.value,
            published_at=ranking.published_at,
            is_read_only=True,
            can_publish=ranking.status == RankStatus.APPROVED,
            primary=primary,
            waitlisted=waitlisted,
        )

    async def publish_results(
        self, period_id: uuid.UUID, program_id: uuid.UUID, officer_id: uuid.UUID
    ) -> PublicationResult:
        ranking = await self._ranking_repo.get_by_program_and_period(
            program_id, period_id
        )
        if ranking is None:
            raise HTTPException(status_code=404, detail="Ranking not found")

        if ranking.status == RankStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Results have already been published for this program and period",
            )

        if ranking.status != RankStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Ranking must be approved before results can be published",
            )

        entry_by_app = {entry.application_id: entry for entry in ranking.entries}
        ranking_apps = await self._app_repo.get_by_program_period_and_status(
            program_id, period_id, AppStatus.RANKING
        )

        now = datetime.now(timezone.utc)
        announced_count = await self._app_repo.bulk_update_status(
            program_id, period_id, AppStatus.RANKING, AppStatus.ANNOUNCED
        )

        ranking.status = RankStatus.PUBLISHED
        ranking.published_at = now
        await self.db.flush()

        notification_items: list[dict] = []
        for application in ranking_apps:
            entry = entry_by_app.get(application.id)
            if entry is not None:
                result, label = _result_outcome_for_entry(entry.is_primary)
                detail = (
                    f"You have been placed on the primary (Asil) list at position "
                    f"{entry.position}."
                    if entry.is_primary
                    else (
                        f"You have been placed on the waitlist (Yedek) at position "
                        f"{entry.position}."
                    )
                )
            else:
                result, label = _result_outcome_for_unlisted()
                detail = "Your application was not placed on the final transfer list."

            applicant_user = application.applicant.user
            notification_items.append(
                {
                    "user_id": application.applicant_id,
                    "application_id": application.id,
                    "subject": "UTMS — Transfer Results Announced",
                    "body": f"Your result: {result}. {detail}",
                    "template_name": "results_announced.html",
                    "template_context": {
                        "result": result,
                        "detail": detail,
                        "result_label": label,
                        "tracking_number": application.tracking_number or "",
                        "program_name": (
                            ranking.program.name if ranking.program else ""
                        ),
                    },
                }
            )

        notifications_enqueued = 0
        if notification_items:
            notifications_enqueued = await self._notif_service.enqueue_bulk(
                notification_items
            )

        await self._log_officer_action(
            officer_id=officer_id,
            action="RESULTS_PUBLISHED",
            entity_id=ranking.id,
            entity_type="Ranking",
            new_value={
                "period_id": str(period_id),
                "program_id": str(program_id),
                "announced_count": announced_count,
                "notifications_enqueued": notifications_enqueued,
                "published_at": now.isoformat(),
            },
        )

        return PublicationResult(
            announced_count=announced_count,
            notifications_enqueued=notifications_enqueued,
            published_at=now,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _split_ranking_entries(
        self, ranking
    ) -> tuple[list[ApplicantResultEntry], list[ApplicantResultEntry]]:
        primary: list[ApplicantResultEntry] = []
        waitlisted: list[ApplicantResultEntry] = []

        for entry in sorted(ranking.entries, key=lambda e: e.position):
            app = entry.application
            user = app.applicant.user if app.applicant else None
            row = ApplicantResultEntry(
                application_id=entry.application_id,
                tracking_number=app.tracking_number,
                first_name=user.first_name if user else "",
                last_name=user.last_name if user else "",
                email=user.email if user else "",
                position=entry.position,
                composite_score=float(entry.composite_score),
                result_label="Asil" if entry.is_primary else "Yedek",
            )
            if entry.is_primary:
                primary.append(row)
            else:
                waitlisted.append(row)

        return primary, waitlisted

    async def _require_submitted(self, application_id: uuid.UUID) -> Application:
        application = await self._app_repo.get_by_id(application_id)
        if application is None:
            raise HTTPException(status_code=404, detail="Application not found")
        if application.status != AppStatus.SUBMITTED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Application must be in SUBMITTED status, "
                    f"currently {application.status.value}"
                ),
            )
        return application

    async def _require_rejectable(self, application_id: uuid.UUID) -> Application:
        application = await self._app_repo.get_by_id(application_id)
        if application is None:
            raise HTTPException(status_code=404, detail="Application not found")

        if application.status == AppStatus.SUBMITTED:
            return application

        if application.status == AppStatus.CORRECTION_REQUESTED:
            now = datetime.now(timezone.utc)
            if (
                application.correction_deadline is not None
                and now > application.correction_deadline
            ):
                return application
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Application can only be rejected after the correction deadline "
                    "has passed while in CORRECTION_REQUESTED status. "
                    "Reject critical issues directly from SUBMITTED status."
                ),
            )

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Application cannot be rejected from status "
                f"{application.status.value}"
            ),
        )

    async def _log_officer_action(
        self,
        officer_id: uuid.UUID,
        action: str,
        new_value: dict,
        application_id: uuid.UUID | None = None,
        entity_id: uuid.UUID | None = None,
        entity_type: str = "Application",
    ) -> None:
        log = AuditLog(
            actor_id=officer_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id or application_id,
            new_value=new_value,
        )
        self.db.add(log)
        await self.db.flush()

    async def _enqueue_notification(
        self,
        application: Application,
        subject: str,
        body: str,
        template_name: str,
        template_context: dict | None = None,
    ) -> None:
        await self._notif_service.enqueue(
            user_id=application.applicant_id,
            subject=subject,
            body=body,
            application_id=application.id,
            template_name=template_name,
            template_context=template_context,
        )

    def _to_summary(self, app: Application) -> ApplicationSummaryWithValidation:
        return ApplicationSummaryWithValidation(
            id=app.id,
            program_id=app.program_id,
            period_id=app.period_id,
            status=app.status.value,
            display_status=srs_display_status(app.status),
            tracking_number=app.tracking_number,
            submitted_at=app.submitted_at,
            created_at=app.created_at,
            auto_validation_results=build_auto_validation_results(app),
        )
