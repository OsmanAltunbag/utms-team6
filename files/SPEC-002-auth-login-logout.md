# SPEC-002 — Authentication: Login & Logout

## Goal
Implement the login and logout flows for all six user roles. Issue RS256 JWT via HttpOnly Secure cookie. Enforce account lockout after 5 failed attempts.

## Depends On
SPEC-001 (users, applicants, staff tables)

---

## Tasks

### Task 1 — AuthService
File: `backend/app/services/auth_service.py`

```python
class AuthService:
    async def login(self, email: str, password: str, ip: str) -> TokenPair
    async def logout(self, user_id: UUID, token_jti: str) -> None
    async def refresh_token(self, refresh_token: str) -> TokenPair
    async def _check_lockout(self, user: User) -> None  # raises HTTPException 423 if locked
    async def _record_failed_attempt(self, user: User) -> None  # increments + locks if >= 5
    async def _clear_failed_attempts(self, user: User) -> None
```

Rules:
- On success: clear `failed_attempts`, set `locked_until = NULL`
- On failure: increment `failed_attempts`; if `failed_attempts >= 5`, set `locked_until = NOW() + 15 minutes`
- Lockout response: HTTP 423 with `Retry-After` header showing seconds remaining
- Never disclose whether email or password was wrong — always return the same generic message

### Task 2 — JWT Utilities
File: `backend/app/core/security.py`

```python
def create_access_token(user_id: UUID, role: UserRole, jti: str) -> str
def create_refresh_token(user_id: UUID, jti: str) -> str
def decode_token(token: str) -> dict          # raises 401 on invalid/expired
def hash_password(plain: str) -> str
def verify_password(plain: str, hashed: str) -> bool
```

- Access token TTL: 15 minutes
- Refresh token TTL: 7 days
- Algorithm: RS256 (load private key from env `JWT_PRIVATE_KEY`)
- JTI stored in Redis with TTL matching token expiry (for revocation)

### Task 3 — Redis Session Store
File: `backend/app/core/redis.py`

```python
async def store_jti(jti: str, ttl_seconds: int) -> None
async def revoke_jti(jti: str) -> None
async def is_jti_valid(jti: str) -> bool   # returns False if key missing (revoked or expired)
```

On logout: call `revoke_jti()` to delete the JTI from Redis.

### Task 4 — Auth Router
File: `backend/app/api/auth.py`

```
POST /api/auth/login
  Body: { email: str, password: str }
  Response: 200 + Set-Cookie: access_token (HttpOnly, Secure, SameSite=Strict)
           + Set-Cookie: refresh_token (HttpOnly, Secure, SameSite=Strict)
  Error: 401 generic message | 423 locked

POST /api/auth/logout
  Auth: Bearer/cookie required
  Response: 204 + clears both cookies

POST /api/auth/refresh
  Cookie: refresh_token
  Response: 200 + new access_token cookie
```

### Task 5 — RBAC Middleware / Dependency
File: `backend/app/core/dependencies.py`

```python
async def get_current_user(token: str = cookie) -> User
async def require_role(*roles: UserRole) -> Callable
```

- Decode JWT from cookie
- Validate JTI in Redis
- Check role against allowed roles list
- Total time budget for RBAC check: < 100 ms (enforced by integration test)

### Task 6 — AuditLog Writes
On every login (success/failure) and logout, write to `audit_logs`:
- action: `"LOGIN_SUCCESS"`, `"LOGIN_FAILURE"`, `"LOGOUT"`
- entity_type: `"User"`, entity_id: user.id
- new_value: `{ "ip": "...", "role": "..." }`

---

## API Contract

| Method | Path | Auth | Body | Response |
|--------|------|------|------|----------|
| POST | /api/auth/login | None | `{email, password}` | 200 + cookies |
| POST | /api/auth/logout | Cookie | — | 204 |
| POST | /api/auth/refresh | Cookie | — | 200 + new cookie |

---

## Test Scenarios

| ID | Scenario | Expected |
|----|----------|----------|
| T1 | Login with valid credentials (applicant) | 200, cookies set, JTI in Redis |
| T2 | Login with wrong password | 401, same generic message |
| T3 | Login with unknown email | 401, same generic message |
| T4 | Login failure 5 times in a row | 6th attempt returns 423 with Retry-After |
| T5 | Login after lockout window expires | 200, lockout cleared |
| T6 | Logout | 204, JTI deleted from Redis |
| T7 | Access protected route after logout | 401 |
| T8 | Refresh with valid refresh token | 200, new access token |
| T9 | Staff login (each role) | 200, role embedded in JWT claims |
| T10 | RBAC: applicant accessing staff endpoint | 403 |

---

## Acceptance Criteria
- Login with valid credentials returns HTTP 200 within 2 seconds
- Cookies are `HttpOnly`, `Secure`, `SameSite=Strict`
- Failed login never reveals which field was wrong
- 5th failed attempt locks account for 15 minutes
- Locked account returns HTTP 423 + `Retry-After` header
- All login/logout events written to `audit_logs`
- RBAC check completes in < 100 ms (measured in integration test)
