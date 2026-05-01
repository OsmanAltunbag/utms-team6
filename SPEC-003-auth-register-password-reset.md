# SPEC-003 — Authentication: Register & Password Reset

## Goal
Applicant self-registration with e-Devlet identity verification (mocked in non-prod). Email verification flow. Password reset via time-limited token.

## Depends On
SPEC-001

---

## Tasks

### Task 1 — e-Devlet Adapter (External Integration)
File: `backend/app/external/edevlet_adapter.py`

```python
class EDevletAdapter:
    async def verify_identity(
        self,
        national_id: str,
        date_of_birth: date
    ) -> IdentityVerificationResult
```

- `IdentityVerificationResult`: `{ verified: bool, full_name: str | None }`
- In production: calls e-Devlet API (endpoint configured via env `EDEVLET_API_URL`)
- Must respond within 7 seconds; raise `ExternalServiceTimeoutError` on timeout
- Mock implementation for tests: returns `verified=True` for any well-formed national_id

### Task 2 — RegistrationService
File: `backend/app/services/registration_service.py`

```python
class RegistrationService:
    async def register(self, payload: RegistrationRequest) -> Applicant
    async def verify_email(self, token: str) -> None
    async def resend_verification(self, email: str) -> None
```

Registration steps (in order):
1. Check email uniqueness — raise 409 if duplicate
2. Check national_id uniqueness — raise 409 if duplicate
3. Call `EDevletAdapter.verify_identity()` — raise 422 if unverified
4. Hash password with bcrypt
5. Create `users` row (role=APPLICANT, is_verified=False)
6. Create `applicants` row
7. Generate email verification token (UUID, stored in Redis with TTL 24h, key: `email_verify:{token}`)
8. Enqueue notification (Celery) with verification link
9. Write `AuditLog` action `"REGISTER"`

Email verification:
- Token lookup in Redis; if missing, raise 410 Gone
- Set `users.is_verified = TRUE`
- Delete token from Redis
- Write `AuditLog` action `"EMAIL_VERIFIED"`

### Task 3 — PasswordResetService
File: `backend/app/services/password_reset_service.py`

```python
class PasswordResetService:
    async def request_reset(self, email: str) -> None
    async def validate_token(self, token: str) -> str  # returns email
    async def reset_password(self, token: str, new_password: str) -> None
```

Rules:
- `request_reset`: if email not found, return 200 anyway (prevent enumeration)
- Token: UUID stored in Redis key `pwd_reset:{token}` with TTL 1 hour, value = user_id
- `reset_password`: hash new password, save, delete token, purge all Redis JTIs for user
- Write `AuditLog` action `"PASSWORD_RESET"`

### Task 4 — Auth Router Extension
File: `backend/app/api/auth.py` (extend from SPEC-002)

```
POST /api/auth/register
  Body: { national_id, date_of_birth, email, password, password_confirm }
  Response: 201 { message: "Verification email sent" }
  Errors: 409 duplicate | 422 identity unverified | 503 e-Devlet unavailable

POST /api/auth/verify-email/{token}
  Response: 200 { message: "Email verified" }
  Error: 410 token expired/invalid

POST /api/auth/resend-verification
  Body: { email }
  Response: 200 (always, no enumeration)

POST /api/auth/forgot-password
  Body: { email }
  Response: 200 (always, no enumeration)

POST /api/auth/reset-password/{token}
  Body: { new_password, new_password_confirm }
  Response: 200
  Error: 410 token expired | 422 password too weak
```

### Task 5 — Password Complexity Validator
File: `backend/app/schemas/auth.py`

Password must satisfy all:
- Minimum 8 characters
- At least one uppercase letter
- At least one digit
- At least one special character (`!@#$%^&*`)

Enforce via Pydantic v2 `@field_validator`.

---

## API Contract

| Method | Path | Auth | Response |
|--------|------|------|----------|
| POST | /api/auth/register | None | 201 |
| POST | /api/auth/verify-email/{token} | None | 200 |
| POST | /api/auth/resend-verification | None | 200 |
| POST | /api/auth/forgot-password | None | 200 |
| POST | /api/auth/reset-password/{token} | None | 200 |

---

## Test Scenarios

| ID | Scenario | Expected |
|----|----------|----------|
| T1 | Register with valid data | 201, unverified account created, email enqueued |
| T2 | Register with duplicate email | 409 |
| T3 | Register with duplicate national_id | 409 |
| T4 | Register with e-Devlet returning unverified | 422 |
| T5 | Click valid email verification link | 200, is_verified=true |
| T6 | Click expired/invalid link | 410 |
| T7 | Request password reset for existing email | 200, token in Redis |
| T8 | Request password reset for unknown email | 200 (no leak) |
| T9 | Reset password with valid token | 200, old sessions invalidated |
| T10 | Reset password with expired token | 410 |
| T11 | Register with weak password | 422 with field errors |

---

## Acceptance Criteria
- Account created within 5 seconds of registration request
- Verification email enqueued within 10 seconds
- Token lookup and password reset completes within 2 seconds
- Unknown email addresses never yield different responses (no enumeration)
- All registration and reset events written to `audit_logs`
- e-Devlet adapter is mockable without changing service code
