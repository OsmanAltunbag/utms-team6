from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import decode_token
from app.domain.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth_service import AuthService

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
