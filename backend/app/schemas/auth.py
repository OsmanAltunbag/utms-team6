from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """Returned in the response body alongside the HttpOnly cookies."""

    token_type: str = "bearer"
    role: str
