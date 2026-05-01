import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.domain.enums import UserRole

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def _private_key() -> str:
    # Env vars may store newlines as literal \n
    return settings.JWT_PRIVATE_KEY.replace("\\n", "\n")


def _public_key() -> str:
    return settings.JWT_PUBLIC_KEY.replace("\\n", "\n")


def create_access_token(user_id: uuid.UUID, role: UserRole, jti: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "jti": jti,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, _private_key(), algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: uuid.UUID, jti: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "iat": now,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, _private_key(), algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTP 401 on any error."""
    try:
        payload = jwt.decode(
            token,
            _public_key(),
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
