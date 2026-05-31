import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.domain.enums import UserRole
from app.domain.user import User
from app.repositories.application_repository import ApplicationRepository
from app.repositories.eligibility_repository import DepartmentRequirementRepository
from app.schemas.evaluation import (
    ConditionResult,
    DeptConditionItem,
    DeptConditionsResponse,
    EvaluateConditionsRequest,
    EvaluateConditionsResponse,
    ManualCourseMappingRequest,
    ManualCourseMappingResponse,
)
from app.services.eligibility_engine import EligibilityEngine

router = APIRouter()

_COMMISSION = require_role(UserRole.TRANSFER_COMMISSION)


@router.get(
    "/{application_id}/dept-conditions",
    response_model=DeptConditionsResponse,
)
async def get_dept_conditions(
    application_id: uuid.UUID,
    current_user: User = Depends(_COMMISSION),
    db: AsyncSession = Depends(get_db),
) -> DeptConditionsResponse:
    application = await ApplicationRepository(db).get_by_id(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    requirements = await DepartmentRequirementRepository(db).get_by_program(application.program_id)

    return DeptConditionsResponse(
        application_id=application_id,
        program_id=application.program_id,
        conditions=[
            DeptConditionItem(
                id=r.id,
                rule_key=r.rule_key,
                rule_value=r.rule_value,
                description=r.description,
                is_active=r.is_active,
            )
            for r in requirements
        ],
    )


@router.post(
    "/{application_id}/evaluate-conditions",
    response_model=EvaluateConditionsResponse,
)
async def evaluate_conditions(
    application_id: uuid.UUID,
    body: EvaluateConditionsRequest,
    current_user: User = Depends(_COMMISSION),
    db: AsyncSession = Depends(get_db),
) -> EvaluateConditionsResponse:
    engine = EligibilityEngine(db)
    checks = await engine.evaluate_department_conditions(
        application_id=application_id,
        evaluator_id=current_user.id,
        notes=body.notes,
    )
    all_passed = all(c.passed for c in checks) if checks else True
    return EvaluateConditionsResponse(
        application_id=application_id,
        all_passed=all_passed,
        results=[
            ConditionResult(rule_key=c.rule_key, passed=c.passed, detail=c.detail)
            for c in checks
        ],
    )


@router.post(
    "/{application_id}/manual-course-mapping",
    response_model=ManualCourseMappingResponse,
    status_code=201,
)
async def manual_course_mapping(
    application_id: uuid.UUID,
    body: ManualCourseMappingRequest,
    current_user: User = Depends(_COMMISSION),
    db: AsyncSession = Depends(get_db),
) -> ManualCourseMappingResponse:
    engine = EligibilityEngine(db)
    result = await engine.manual_course_mapping(
        application_id=application_id,
        prepared_by=current_user.id,
        mappings=[m.model_dump() for m in body.mappings],
    )
    return ManualCourseMappingResponse(
        intibak_table_id=uuid.UUID(result["intibak_table_id"]),
        application_id=application_id,
        mappings_added=result["mappings_added"],
    )
