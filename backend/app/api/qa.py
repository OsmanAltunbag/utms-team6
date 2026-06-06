"""Two-way messaging between applicants and Student Affairs.

Applicants open a thread (Question); Student Affairs reply (Reply).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import require_role
from app.domain.enums import UserRole
from app.domain.qa import Question, Reply
from app.domain.user import Applicant, User
from app.schemas.qa import QuestionCreate, QuestionOut, ReplyCreate, ReplyOut

router = APIRouter()

_require_applicant = require_role(UserRole.APPLICANT)
_require_sa = require_role(UserRole.STUDENT_AFFAIRS)

# Eager-load replies (with their author) and the asking applicant (with user).
_Q_OPTS = (
    selectinload(Question.replies).selectinload(Reply.staff),
    selectinload(Question.applicant).selectinload(Applicant.user),
)


def _reply_out(r: Reply) -> ReplyOut:
    return ReplyOut(
        id=r.id,
        body=r.body,
        staff_name=r.staff.full_name if r.staff else "Student Affairs",
        created_at=r.created_at,
    )


def _question_out(q: Question, include_applicant: bool = False) -> QuestionOut:
    applicant_name = None
    if include_applicant and q.applicant and q.applicant.user:
        applicant_name = q.applicant.user.full_name
    return QuestionOut(
        id=q.id,
        subject=q.subject,
        body=q.body,
        application_id=q.application_id,
        applicant_name=applicant_name,
        is_resolved=q.is_resolved,
        created_at=q.created_at,
        replies=[_reply_out(r) for r in q.replies],
    )


async def _load(db: AsyncSession, question_id: uuid.UUID) -> Question:
    result = await db.execute(
        select(Question).options(*_Q_OPTS).where(Question.id == question_id)
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Applicant endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
async def create_question(
    body: QuestionCreate,
    current_user: User = Depends(_require_applicant),
    db: AsyncSession = Depends(get_db),
) -> QuestionOut:
    question = Question(
        applicant_id=current_user.id,  # Applicant.id == User.id
        application_id=body.application_id,
        subject=body.subject,
        body=body.body,
    )
    db.add(question)
    await db.flush()
    # No replies yet — build the response without touching lazy relationships.
    return QuestionOut(
        id=question.id,
        subject=question.subject,
        body=question.body,
        application_id=question.application_id,
        applicant_name=current_user.full_name,
        is_resolved=question.is_resolved,
        created_at=question.created_at,
        replies=[],
    )


@router.get("", response_model=list[QuestionOut])
async def list_my_questions(
    current_user: User = Depends(_require_applicant),
    db: AsyncSession = Depends(get_db),
) -> list[QuestionOut]:
    result = await db.execute(
        select(Question)
        .options(*_Q_OPTS)
        .where(Question.applicant_id == current_user.id)
        .order_by(Question.created_at.desc())
    )
    return [_question_out(q) for q in result.scalars().all()]


# ---------------------------------------------------------------------------
# Student Affairs endpoints
# ---------------------------------------------------------------------------

@router.get("/all", response_model=list[QuestionOut])
async def list_all_questions(
    current_user: User = Depends(_require_sa),
    db: AsyncSession = Depends(get_db),
) -> list[QuestionOut]:
    result = await db.execute(
        select(Question)
        .options(*_Q_OPTS)
        .order_by(Question.is_resolved.asc(), Question.created_at.desc())
    )
    return [_question_out(q, include_applicant=True) for q in result.scalars().all()]


@router.post(
    "/{question_id}/replies",
    response_model=QuestionOut,
    status_code=status.HTTP_201_CREATED,
)
async def reply_to_question(
    question_id: uuid.UUID,
    body: ReplyCreate,
    current_user: User = Depends(_require_sa),
    db: AsyncSession = Depends(get_db),
) -> QuestionOut:
    question = await db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    db.add(Reply(question_id=question_id, staff_id=current_user.id, body=body.body))
    question.is_resolved = True
    await db.flush()
    return _question_out(await _load(db, question_id), include_applicant=True)
