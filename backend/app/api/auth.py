from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import decode_token
from app.domain.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegistrationRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService
from app.services.password_reset_service import PasswordResetService
from app.services.registration_service import RegistrationService

router = APIRouter()

_COOKIE_SECURE = settings.APP_ENV == "production"


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="strict",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="strict",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth/refresh",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/auth/refresh")


# ---------------------------------------------------------------------------
# Existing auth endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate user and issue HttpOnly JWT cookies."""
    ip = request.client.host if request.client else None
    service = AuthService(db)
    pair = await service.login(body.email, body.password, ip)
    _set_auth_cookies(response, pair.access_token, pair.refresh_token)
    return TokenResponse(role=pair.role)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke JTI and clear cookies."""
    token = request.cookies.get("access_token", "")
    payload = decode_token(token)
    jti = payload.get("jti", "")
    ip = request.client.host if request.client else None

    service = AuthService(db)
    await service.logout(current_user.id, jti, ip)
    _clear_auth_cookies(response)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Rotate the refresh token and issue new cookies."""
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Refresh token missing")

    service = AuthService(db)
    pair = await service.refresh_token(raw_refresh)
    _set_auth_cookies(response, pair.access_token, pair.refresh_token)
    return TokenResponse(role=pair.role)


# ---------------------------------------------------------------------------
# Registration (SPEC-003 Task 3)
# ---------------------------------------------------------------------------

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegistrationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RegistrationService(db)
    await service.register(body, background_tasks)
    return {"message": "Account created. Verification email sent."}


@router.post("/verify-email/{token}", status_code=status.HTTP_200_OK)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RegistrationService(db)
    await service.verify_email(token)
    return {"message": "Email verified successfully"}


# ---------------------------------------------------------------------------
# Password Reset (SPEC-003 Task 3)
# ---------------------------------------------------------------------------

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = PasswordResetService(db)
    await service.request_reset(body.email, background_tasks)
    return {"message": "If this email is registered, a password reset link has been sent."}


@router.get("/reset-password/{token}", status_code=status.HTTP_200_OK)
async def validate_reset_token(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = PasswordResetService(db)
    await service.validate_token(token)
    return {"message": "Token is valid"}


@router.post("/reset-password/{token}", status_code=status.HTTP_200_OK)
async def reset_password(
    token: str,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = PasswordResetService(db)
    await service.reset_password(token, body.new_password)
    return {"message": "Password updated successfully"}
