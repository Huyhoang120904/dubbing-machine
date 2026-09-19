# JWT Authentication with DB-Backed Sessions — Design

**Date:** 2026-09-19
**Status:** Design approved; implementation plan pending
**Branch:** `feat/jwt-auth-and-sessions`
**Removes:** the `Item` reference slice (model, repository, service, schemas, routes, tests, `items` table)

## 1. Goal

Give the dubbing backend real authentication: bcrypt-hashed passwords, short-lived
JWT access tokens, and refresh tokens persisted as revocable rows in a `sessions`
table. The `Item` CRUD slice is deleted in the same change so the auth flow becomes
the codebase's reference example of the layering.

## 2. Non-goals

- No roles, permissions, `is_active`, or `is_superuser`.
- No email verification, password reset, OAuth/social login, or login rate limiting.
- No refresh-token **reuse detection**. Rotation plus explicit revocation only.
- No cookie transport, therefore no CSRF handling.
- No user-listing endpoint. `get_multi`/`count` stay on the base repository unused.

## 3. Architecture

One direction only, enforced by import discipline:

```
routes → services → repositories → AsyncSession (SQLAlchemy)
```

| Layer | May do | Must never do |
| --- | --- | --- |
| `app/api/v1/routes/` | Parse/validate HTTP, call a service, translate typed domain errors into `HTTPException` | Import a repository, build SQL, decide business rules |
| `app/services/` | Business rules, transaction boundaries (`commit`), raise typed domain errors | Import FastAPI/`HTTPException`, build SQL |
| `app/repositories/` | All query construction, `add`/`flush`/`delete` | Business decisions, `commit` |
| `app/core/security.py` | Pure crypto/inspection helpers | Touch the DB or FastAPI |

**Transaction rule (deliberate change).** Repositories `flush()`; **services** own
`commit()`. The old `CRUDBase` committed inside every write. `POST /auth/refresh`
must revoke the old session row and insert its replacement atomically — committing
inside each repository call would leave a window where the user has no valid
session. Since the only consumers of the old base class are the Item files being
deleted, the boundary is corrected rather than worked around. `get_db` already
rolls back on exception, so a failed service leaves no partial state.

## 4. Data model

### `users`

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | `Integer` | PK |
| `email` | `String(320)` | unique index, not null, stored `.strip().lower()` |
| `hashed_password` | `String(255)` | not null (bcrypt output is 60 chars) |
| `created_at` / `updated_at` | `DateTime(timezone=True)` | `TimestampMixin` |

### `sessions`

| Column | Type | Constraints |
| --- | --- | --- |
| `id` | `Integer` | PK |
| `user_id` | `Integer` | FK → `users.id`, `ondelete="CASCADE"`, indexed, not null |
| `token_hash` | `String(64)` | unique index, not null — SHA-256 hex, never the plaintext |
| `expires_at` | `DateTime(timezone=True)` | not null |
| `revoked_at` | `DateTime(timezone=True)` | nullable — set on rotation and logout |
| `created_at` / `updated_at` | `DateTime(timezone=True)` | `TimestampMixin` |

Module `app/db/models/user_session.py`, class `UserSession`, table `sessions` —
named `UserSession` because a class called `Session` collides conceptually with
SQLAlchemy's `AsyncSession` throughout `deps.py` and the repositories. No ORM
relationship on `User`; the FK plus `PRAGMA foreign_keys=ON` (already enabled in
`app/db/session.py`) does the cascading.

Datetimes are aware UTC. SQLite returns naive values for `timezone=True` columns,
so a small `ensure_utc()` helper normalises before every comparison; expiry checks
run in Python, not in SQL, to avoid dialect timezone surprises.

## 5. Components / files

**Create**

| File | Contents |
| --- | --- |
| `app/core/security.py` | `hash_password`, `verify_password`, `create_access_token`, `decode_access_token`, `new_refresh_token`, `hash_refresh_token`, `utcnow`, `ensure_utc`, `AccessTokenPayload` |
| `app/db/models/user.py` | `User` |
| `app/db/models/user_session.py` | `UserSession` |
| `app/schemas/user.py` | `UserCreate` (request), `UserRead` (response) |
| `app/schemas/auth.py` | `LoginRequest`, `RefreshRequest`, `LogoutRequest`, `TokenPair` |
| `app/repositories/user.py` | `UserRepository` — `get_by_email` |
| `app/repositories/session.py` | `UserSessionRepository` — `get_by_token_hash`, `revoke`, `create_for_user` |
| `app/services/auth.py` | `AuthService(db, users: UserRepository, sessions: UserSessionRepository)` + `EmailAlreadyRegisteredError`, `InvalidCredentialsError`, `InvalidSessionError` |
| `app/api/v1/routes/auth.py` | the five endpoints |
| `tests/test_auth.py` | see §9 |

**Locked interfaces.** `UserRepository` exposes `get(id)`, `get_by_email(email)`,
`add(email, hashed_password) -> User`. `UserSessionRepository` exposes
`add(user_id, token_hash, expires_at) -> UserSession`,
`get_by_token_hash(token_hash) -> UserSession | None` and `revoke(session)`.
Repositories are constructed with the request's session (`UserRepository(db)`) and
injected into the service; `app/api/deps.py` wires them in `get_auth_service`, so a
test can substitute either repository without touching the database. Email
normalisation (`strip().lower()`) happens once in `AuthService`, for register **and**
login, never in a repository or a route.

**Rename / move**

- `app/crud/base.py` → `app/repositories/base.py`: `CRUDBase` becomes
  `BaseRepository`, bound to its session in the constructor
  (`BaseRepository(db)`), methods lose the per-call `db` argument, and writes
  `flush()` instead of `commit()`.
- `app/crud/` → `app/repositories/`; `app/api/v1/endpoints/` → `app/api/v1/routes/`.

**Modify**

- `app/api/deps.py` — drop `ItemServiceDep`/`PaginationDep`; add `AuthServiceDep`,
  `CurrentUserDep` (`HTTPBearer(auto_error=False)` → `get_current_user`).
- `app/api/v1/router.py` — mount `auth.router` in place of the removed
  `items.router`. `app/main.py` needs no change.
- `app/db/models/__init__.py`, `app/repositories/__init__.py`, `app/schemas/__init__.py`
  — re-export lists.
- `app/core/config.py`, `backend/.env.example` — §6.
- `tests/test_health.py`, `tests/test_migrations.py` — §9.
- `README.md` (root, canonical) and `backend/README.md` — API table, layering
  paragraph, config table, troubleshooting row, curl examples.

**Delete**

`app/db/models/item.py`, `app/crud/item.py`, `app/services/item.py`,
`app/schemas/item.py`, `app/api/v1/endpoints/items.py`, `tests/test_items.py`, and
`app/schemas/common.py` (both `Page` and `ErrorDetail` become unreachable once the
Item routes go; `Page` existed only for paginated item listing and `ErrorDetail`
was never referenced).

## 6. API contract — `/api/v1/auth`, tag `auth`

| Method | Path | Request | Success | Failures |
| --- | --- | --- | --- | --- |
| POST | `/register` | `{email, password}` | `201 UserRead` (no tokens) | `409` email taken · `422` invalid email / password length |
| POST | `/login` | `{email, password}` | `200 TokenPair` | `401` invalid credentials |
| POST | `/refresh` | `{refresh_token}` | `200 TokenPair` (rotation) | `401` unknown / expired / revoked |
| POST | `/logout` | `{refresh_token}` + `Authorization: Bearer` | `204`, empty body | `401` bad access token · `401` token not this user's live session |
| GET | `/me` | `Authorization: Bearer` | `200 UserRead` | `401` |

`UserRead` = `{id, email, created_at, updated_at}` — the hash is never serialised.
`TokenPair` = `{access_token, refresh_token, token_type: "bearer", expires_in,
refresh_expires_in}` (both lifetimes in seconds).

`password`: `min_length=8, max_length=128`. bcrypt ignores input past 72 **bytes**,
so a password longer than that would be silently truncated to its first 72 bytes; the
schema rejects such a password with a `422` instead. Correctness guard, not a nicety.

`email`: pydantic `EmailStr`, which requires adding `email-validator` (plus its
`dnspython`/`idna` transitive deps) — the third runtime dependency, alongside
`pyjwt` and `bcrypt`. All three are added with `uv add` so `pyproject.toml` and
`uv.lock` stay in sync.

`register` stores `email.strip().lower()` and returns no tokens: tokens come from an
explicit `POST /auth/login`.

Transport: `Authorization: Bearer <jwt>` for the access token; the refresh token
travels in the JSON body as shown. No cookies.

## 7. Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `JWT_SECRET_KEY` | `change-me-in-production` | Startup fails when left at this default while `APP_ENV` is `staging` or `production` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | `sessions` row lifetime |

HS256 is a module constant in `app/core/security.py`, not a setting — a value that
never changes is not configuration. `jwt.decode` is always called with
`algorithms=["HS256"]` pinned, never with the algorithm taken from the token header.

`.env.example` gains the three variables with a `secrets.token_urlsafe(48)` hint for
generating the secret.

## 8. Security decisions

1. **bcrypt** for passwords via `bcrypt.hashpw`/`checkpw` with a fresh per-password
   salt. Plaintext never reaches the database or a log line.
2. **Refresh tokens are opaque** — `secrets.token_urlsafe(32)`, stored only as a
   SHA-256 hex digest. A database leak yields no usable token. SHA-256 rather than
   bcrypt is correct here: the input is high-entropy, so there is nothing to
   brute-force, and lookup must stay a single indexed query.
3. **Rotation**: `POST /auth/refresh` sets `revoked_at` on the presented session and
   inserts its replacement in one transaction, so a replayed old token returns `401`.
4. **Uniform login failures**: unknown email and wrong password return the identical
   `401 "Invalid email or password"`, and an unknown email still runs a dummy bcrypt
   verification against a fixed hash so response time does not disclose whether an
   account exists.
5. **Access tokens are verified statelessly** — signature, `exp`, and a `typ:
   "access"` claim so a refresh token can never be replayed as an access token —
   then `get_current_user` loads the user row by PK. One indexed read per request,
   which is what stops a deleted user from continuing to act.
6. **Logout is explicit**: the session row is revoked; a refresh token that is not
   that user's live session returns `401`.
7. **`JWT_SECRET_KEY` fails fast** outside `local`/`test`, so the placeholder secret
   can never reach staging or production.

## 9. Testing (TDD — tests are written before the implementation)

`tests/test_auth.py`, using the existing in-memory ASGI `client` fixture; register
and login go over HTTP, so `conftest.py` needs no changes:

- register `201`; response contains no hash; the stored row starts with `$2b$`, and
  `verify_password` accepts the original while the plaintext appears nowhere
- register lowercases/strips the email
- duplicate email → `409`; invalid email → `422`; 7-character password → `422`;
  73-byte password → `422`
- login → `200` with both tokens and the right `expires_in`; two logins yield
  different refresh tokens
- wrong password → `401`; unknown email → `401` with an identical `detail`
- `/me` with a valid token → `200` and the right email; without a header → `401`;
  with garbage → `401`; with a tampered payload → `401`; with a refresh token sent
  as a bearer token → `401`; with an **expired** token → `401`, built by passing an
  explicit negative `expires_delta` to `create_access_token` so no clock mocking is
  needed
- refresh → `200` with a fresh pair, after which the old refresh token → `401`
  (rotation)
- refresh with an unknown token → `401`; with an expired session row → `401`;
  with a session already revoked by logout → `401`
- logout → `204` and the refresh token stops working; logout with a foreign or
  unknown refresh token → `401`; logout without a bearer token → `401`

Updated tests:

- `tests/test_health.py` — the OpenAPI assertion becomes `/api/v1/auth/login`.
- `tests/test_migrations.py` — the `items` index/column assertions become
  `users`/`sessions` equivalents; a new test asserts `items` is gone after
  `upgrade head`; `downgrade base` is asserted to remove all three tables.
  `test_migrations_are_in_sync_with_models` (`alembic check`) must stay green, which
  is the proof that the new migration matches the models.

## 10. Migration and removal

One new revision on top of `3f8c9e9e8567`, doing both halves atomically:
`op.drop_table("items")` plus `op.create_table` for `users` and `sessions` with the
unique indexes (`ix_users_email`, `ix_sessions_token_hash`), the `user_id` index and
the cascade FK — written by hand in the existing migration's style (`op.f()` for
convention-derived names) and then reviewed, per the repo rule that migrations are
read before committing. `downgrade()` recreates `items` with its unique index, then
drops `sessions` and `users`.

`make db-reset` is not required: an already-migrated `dubbing.db` upgrades with
`make migrate`.

Documentation updated in the same change (root `README.md` is canonical):
the API table, the `endpoint → service → crud → session` request-flow paragraph
becomes `routes → services → repositories → session`, the configuration table gains
the three new variables, the `no such table: items` troubleshooting row is replaced
with the auth equivalents, and the Item curl examples become register/login examples.
`backend/README.md` only needs the new dependency/secret line if it mentions them.

## 11. Acceptance criteria

- `make check` passes: `ruff check`, `ruff format --check`, full pytest suite.
- `alembic check` reports no pending model/migration drift.
- Every endpoint in §6 behaves as tabled, including every `401`/`409`/`422` case.
- No `Item`, `items`, or `crud` reference survives in `app/`, `tests/`, or the
  READMEs, apart from the migration that drops the `items` table.
- The migration is reversible: `downgrade base` runs clean on a fresh database.

## 12. Deliberately not doing

- **Refresh reuse detection** — a replayed revoked token revoking the whole token
  family. Worth adding when sessions become multi-device and token theft matters
  more; the schema already permits it, because revoked rows are retained rather than
  deleted.
- **Trimming `get_multi`/`count`/`update`/`remove` from `BaseRepository`.** Renaming
  the base is in scope; deleting its now-unused methods is separate cleanup.
- **Cookie transport and CSRF protection, roles/permissions, email verification,
  password reset, and `python-multipart`-style OAuth2 form login.** Not requested;
  each adds surface without serving the goal.