import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.domain.enums import UserRole
from app.domain.user import Staff, User
from app.schemas.admin import RoleUpdateRequest, StaffCreateRequest, StaffResponse
from app.services.admin_service import AdminService

router = APIRouter()

_require_admin = require_role(UserRole.SYSTEM_ADMIN)


def _staff_to_response(staff: Staff) -> StaffResponse:
    u: User = staff.user
    return StaffResponse(
        id=u.id,
        email=u.email,
        first_name=u.first_name,
        last_name=u.last_name,
        role=u.role,
        department=staff.department,
        title=staff.title,
        is_active=u.is_active,
        created_at=u.created_at,
    )


@router.get("/staff", response_model=list[StaffResponse])
async def list_staff(
    _: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[StaffResponse]:
    svc = AdminService(db)
    staff_list = await svc.list_staff()
    return [_staff_to_response(s) for s in staff_list]


@router.post("/staff", response_model=StaffResponse, status_code=status.HTTP_201_CREATED)
async def create_staff(
    payload: StaffCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> StaffResponse:
    svc = AdminService(db)
    staff, _ = await svc.create_staff(payload, current_user.id, background_tasks)
    return _staff_to_response(staff)


@router.patch("/staff/{staff_id}/role", response_model=StaffResponse)
async def update_staff_role(
    staff_id: uuid.UUID,
    payload: RoleUpdateRequest,
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> StaffResponse:
    svc = AdminService(db)
    staff = await svc.update_role(staff_id, payload.role, current_user.id)
    return _staff_to_response(staff)


@router.post("/staff/{staff_id}/activate", response_model=StaffResponse)
async def reactivate_staff(
    staff_id: uuid.UUID,
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> StaffResponse:
    svc = AdminService(db)
    staff = await svc.reactivate_staff(staff_id, current_user.id)
    return _staff_to_response(staff)


@router.delete("/staff/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_staff(
    staff_id: uuid.UUID,
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    svc = AdminService(db)
    await svc.deactivate_staff(staff_id, current_user.id)
