# ElderCare Connect

An elderly care and medication management platform connecting elderly individuals, family members and caretakers.

**Features:** registration and login for three roles (Elderly, Caretaker, Family member) with Argon2id and JWT; elderly profiles with invitation-based linking; medications with generated dose schedules and adherence; appointments; a care dashboard for linked caretakers and family; email reminders and missed-dose alerts; demo accounts; accessibility for older users (18px base text, 48px+ targets, route announcements).


## Technology stack

| Layer      | Technology                                      |
| ---------- | ----------------------------------------------- |
| Frontend   | React 19 + Vite, Tailwind CSS v4, React Router, Axios |
| Backend    | Python 3.11+, FastAPI, Uvicorn, pydantic-settings, argon2-cffi, PyJWT |
| Database   | MongoDB Atlas via PyMongo                       |
| Deployment | Vercel (frontend), Render (backend)             |

## Project structure

```
frontend/
  src/
    api/          Axios client (token + 401 interceptors) and endpoint functions
    auth/         Token storage, role constants, form validation
    config/       Validated environment variables
    context/      AuthContext + AuthProvider (session state)
    hooks/        useHealthStatus, useAuth
    components/   layout/, ui/, dashboard/, auth/ (route guards, role selector)
    pages/        Home, Login, Register, MyDashboard, NotFound
    test/         Vitest + Testing Library tests
backend/
  app/
    core/         Settings (env vars), logging, security (Argon2id, JWT)
    db/           MongoDB connection manager + index definitions
    repositories/ Data access (users)
    api/          Router, deps (auth/RBAC dependencies), routes (health, auth, portal)
    schemas/      Pydantic request/response models
    main.py       FastAPI app, CORS, lifespan, error handler
  tests/          Pytest suite
```

## Setup

### Prerequisites
- Node.js 20.19+ (or 22.12+) and npm
- Python 3.11+
- A MongoDB Atlas cluster (optional for local UI work; the API reports `not_configured` without it)

### Backend

```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt          # add -r requirements-dev.txt for tests
cp .env.example .env                      # then edit .env
```

**Start the backend:**

```bash
uvicorn app.main:app --reload --port 8000
```

- Health check: http://localhost:8000/api/health
- API docs: http://localhost:8000/docs
- Tests: `pip install -r requirements-dev.txt`, then `python -m pytest`. The auth tests use a throwaway database on a local MongoDB (set `TEST_MONGODB_URI`, default `mongodb://127.0.0.1:27017`) and are skipped if none is reachable. They never use the database in `.env`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env                      # then edit .env if needed
```

**Start the frontend:**

```bash
npm run dev                               # http://localhost:5173
```

Other scripts: `npm test` (Vitest), `npm run build`, `npm run preview`, `npm run lint`.

## Environment configuration

Real `.env` files are git-ignored. Only commit the `.env.example` templates.

**backend/.env**

| Variable             | Description                                              | Default                     |
| -------------------- | -------------------------------------------------------- | --------------------------- |
| `APP_NAME`           | Name shown in the health response                        | `ElderCare Connect API`     |
| `APP_VERSION`        | Application version                                      | `0.1.0`                     |
| `ENVIRONMENT`        | `development` / `staging` / `production`                 | `development`               |
| `DEBUG`              | Verbose logging                                          | `false`                     |
| `CORS_ORIGINS`       | Comma-separated allowed frontend origins                 | `http://localhost:5173,...` |
| `MONGODB_URI`        | Atlas connection string (**secret**)                     | unset                       |
| `MONGODB_DB_NAME`    | Database name                                            | `eldercare_connect`         |
| `MONGODB_TIMEOUT_MS` | Server selection / connect timeout                       | `5000`                      |
| `JWT_SECRET_KEY`     | Token signing key, at least 32 random characters (**secret**). Auth endpoints return 503 if it is unset | unset |
| `JWT_ALGORITHM`      | `HS256` / `HS384` / `HS512`                              | `HS256`                     |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime (5–1440)                  | `30`                        |
| `DEMO_ACCOUNTS_ENABLED` | Allow demo-account provisioning, demo sign-in and the login-page listing | `false` |
| `DEMO_ACCOUNTS_ALLOW_PRODUCTION` | Second opt-in required when `ENVIRONMENT=production` | `false` |

Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

**frontend/.env**

| Variable              | Description                         | Default                 |
| --------------------- | ----------------------------------- | ----------------------- |
| `VITE_API_BASE_URL`   | Backend base URL, no trailing slash | `http://localhost:8000` |
| `VITE_API_TIMEOUT_MS` | Axios request timeout               | `8000`                  |

> Every `VITE_` variable is bundled into the public JavaScript. Never put secrets in the frontend env. The MongoDB URI lives only on the backend.

### MongoDB Atlas
1. In Atlas, create a database user and add your IP (or Render's outbound IPs) to **Network Access**.
2. Copy the driver connection string (**Connect → Drivers**) into `MONGODB_URI` in `backend/.env`.
3. Restart the backend. `/api/health` should report `"database": {"status": "connected"}`.

## Health endpoint

`GET /api/health` always returns HTTP 200 while the API is running:

```json
{
  "status": "ok | degraded",
  "app_name": "ElderCare Connect API",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-01-01T00:00:00Z",
  "database": { "status": "connected | disconnected | not_configured", "name": "eldercare_connect", "message": "...", "latency_ms": 12.3 }
}
```

Database errors are logged on the server. Clients only receive a generic message; hosts and credentials are never returned.

## Authentication API

| Method | Path | Access | Description |
| ------ | ---- | ------ | ----------- |
| POST | `/api/auth/register` | Public | `{name, email, password, role}`. Returns 201 with `{access_token, token_type, expires_in, user}`, 409 if the email is taken, 422 for invalid input |
| POST | `/api/auth/login` | Public | `{email, password}`. Returns 200 with the same body as register, or 401 `Invalid email or password.` |
| GET | `/api/auth/me` | Any signed-in user | The current user (never includes the password hash). Includes `is_demo` |
| GET | `/api/auth/demo-accounts` | Public, demo mode only | Demo credentials that are provisioned; 404 when demo mode is off |
| GET | `/api/portal/elderly` | `elderly` | Role-restricted placeholder area |
| GET | `/api/portal/caretaker` | `caretaker` | Role-restricted placeholder area |
| GET | `/api/portal/family` | `family_member` | Role-restricted placeholder area |
| GET | `/api/portal/care-team` | `caretaker`, `family_member` | Area shared by multiple roles |

Send `Authorization: Bearer <access_token>` with each request. Responses: 401 means the token is missing, invalid or expired; 403 means the role is not permitted.

**Rules**
- **Email:** validated, trimmed and lower-cased, and unique across accounts (enforced by a unique index).
- **Password:** 12–128 characters, with uppercase and lowercase letters and a number.
- **Role:** one of `elderly`, `caretaker`, `family_member`.

To protect a new route, add `user = Depends(require_roles(Role.CARETAKER))` (from `app/api/deps.py`). For any signed-in user, use `Depends(get_current_user)` instead.

### Security design
- **Passwords:** hashed with Argon2id (argon2-cffi, RFC 9106 defaults) and salted per hash. Hashes are upgraded automatically on login if the parameters change. Plaintext is never stored or logged.
- **Tokens:** signed JWTs (HS256 by default) containing `sub`, `role`, `type`, `iss`, `aud`, `iat` and `exp`. Decoding pins the algorithm, so `alg: none` and algorithm-swap tokens are rejected, and it requires and verifies the signature, expiry, issuer and audience.
- **Identity and role:** the user ID comes only from a verified token. The role is re-read from the database on every request, so a role claim from the client or inside the token is never trusted. Tokens for deleted users stop working immediately.
- **No account enumeration:** a wrong password and an unknown email return the same 401 message. Login also runs a dummy Argon2 check for unknown emails, so response times match.
- **Sign-in throttling:** after `LOGIN_MAX_FAILURES` (default 10) failed sign-ins for one email within `LOGIN_FAILURE_WINDOW_MINUTES` (default 15), further attempts get 429. This applies to unknown emails too, so it reveals nothing about which accounts exist. A successful sign-in resets the count. Rows store only the case-folded email and a timestamp, and expire after 24 hours.
- **Validation errors (422)** do not echo submitted values back, so passwords never appear in error responses.
- **CORS** still comes from `CORS_ORIGINS`. The `Authorization` header is allowed.

### Token storage (frontend) and tradeoffs
The access token is kept **in memory** and mirrored to **`sessionStorage`**. It is attached as a Bearer header by the Axios interceptor and never put in URLs.

**Why this approach**
- It works across sites, which matters because the Vercel frontend and Render backend live on different domains.
- It needs no CSRF defenses, since the browser never attaches the token automatically.
- `sessionStorage` is limited to one tab and cleared when the tab closes. A page reload keeps the user signed in.

**Risk:** JavaScript running on the page can read the token, so an XSS bug could steal it. Mitigations:
- The token is short-lived (30 minutes by default).
- React escapes rendered output.
- There is no `dangerouslySetInnerHTML`.
- Every request is re-verified on the server.
- The client signs out automatically when the token expires or on any 401.

**Alternative for later:** when frontend and backend share a site, an `HttpOnly; Secure; SameSite` cookie plus CSRF protection removes XSS token theft. Refresh tokens and server-side revocation would come with that change.

Frontend route guards (`ProtectedRoute`) only control what the user sees. The backend enforces every permission.

## Elderly profiles & family/caretaker linking

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET / POST / PUT | `/api/profiles/me` | `elderly` | Read, create (201, 409 if one exists), or update your own profile |
| POST | `/api/invitations` | `elderly` | `{role: caretaker\|family_member}`. Returns the one-time `code` |
| GET | `/api/invitations` | `elderly` | Your invitations (status only, never the code) |
| DELETE | `/api/invitations/{id}` | `elderly` | Cancel an open invitation |
| POST | `/api/invitations/redeem` | `caretaker`, `family_member` | `{code}`. Links you to the inviter's profile |
| GET | `/api/relationships` | `elderly` | People connected to you |
| DELETE | `/api/relationships/{id}` | `elderly` | Revoke a connection (takes effect immediately) |
| GET | `/api/linked-profiles` | `caretaker`, `family_member` | Profiles shared with you |
| GET | `/api/linked-profiles/{profile_id}` | `caretaker`, `family_member` | One shared profile (404 if not actively linked) |

**Collections and indexes**
- `elderly_profiles`: unique `user_id`.
- `invitations`: unique `code_hash`; `(elderly_user_id, created_at)`; TTL on `expires_at` that removes invitations 30 days after they expire.
- `relationships`: partial unique `(profile_id, member_user_id)` where `status = "active"`; plus lookups by elderly user and by member.
- `redemption_failures`: `(user_id, created_at)`; TTL of 24 hours.

All timestamps are UTC.

**Security**
- **Ownership:** the owner always comes from the verified token. There is no endpoint that takes another user's ID for a profile.
- **Invitation codes:** 16 characters, Crockford Base32, 80 random bits (`secrets`), shown as `XXXX-XXXX-XXXX-XXXX`. Only their SHA-256 is stored, and the code is shown once.
- **Single use:** each code redeems once, through an atomic `pending → redeemed` update.
- **Limits:**
  - Codes expire after `INVITATION_EXPIRY_HOURS` (default 72).
  - Each elderly user can have at most `INVITATION_MAX_PENDING` (10) open invitations.
  - After `REDEEM_MAX_FAILURES` (5) failed redemptions within `REDEEM_FAILURE_WINDOW_MINUTES` (15), the user gets 429 with a `Retry-After` header.
  - Repeated wrong-role attempts lock the invitation.
- **Redemption checks:** the invited role must match the signed-in user's role. A user who is already connected gets 409 without using up the invitation. The partial unique index makes duplicate active links impossible, even when two requests race.
- **Access checks:** linked-profile access is checked against an *active* relationship on every request, so revocation takes effect at once even for tokens already issued. A profile you can't see and a profile that doesn't exist both return 404.
- **Demo isolation:** profiles, invitations and relationships copy the user's `is_demo` flag. Demo users can link only with demo data: a code from the other side is treated as invalid, and linked-profile queries filter by the flag.

## Medication management

The elderly user manages their own medicines. Linked family members get **read-only** access. Linked caretakers are read-only unless the elderly user allows them to record doses (Connections page). Every endpoint requires a profile, because the profile's IANA `timezone` (for example `Europe/London`) decides when doses happen. Profiles without a time zone default to `UTC`.

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET / POST | `/api/medications` | `elderly` | List (`?status=active\|discontinued`) or create. Returns 409 if you have no profile yet |
| GET / PUT | `/api/medications/{id}` | `elderly` | Read or edit an active medication |
| POST | `/api/medications/{id}/discontinue` | `elderly` | Stop the medication: upcoming doses are cancelled and history is kept |
| DELETE | `/api/medications/{id}` | `elderly` | Delete the medication and all of its doses |
| GET | `/api/doses/today` | `elderly` | Today's doses, in the profile's time zone |
| GET | `/api/doses/history` | `elderly` | Past doses. `days` is 1–90; optional `medication_id`; `limit` up to 500 |
| PATCH | `/api/doses/{id}/status` | `elderly` | Body `{status: taken\|missed, expected_status}` |
| GET | `/api/adherence` | `elderly` | Today, the last 7 days, and a daily breakdown (optional `medication_id`) |
| GET | `/api/linked-profiles/{profile_id}/medications[/{id}]`, `/doses/today`, `/doses/history`, `/adherence` | `caretaker`, `family_member` | The same data, read-only. Returns 404 unless there is an active link |

**Scheduling**
- **Frequencies:** once, twice, three or four times a day. Each dose has its own `HH:MM` wall-clock time in the profile's time zone.
- **Storage:** each dose is a document with a UTC `scheduled_at` plus `local_date`/`local_time`. For example, 08:00 in New York is stored as 13:00Z in winter and 12:00Z in summer.
- **Horizon:** doses are generated from the start date up to the end date, or today + `DOSE_SCHEDULE_HORIZON_DAYS` (default 7), whichever comes first. Generation runs on create and is topped up lazily on reads.
- **No duplicates:** a unique `(medication_id, scheduled_at)` index plus `$setOnInsert` upserts mean regeneration never creates duplicates and never overwrites a recorded status.
- **Edits:** changing the schedule rebuilds only upcoming, unrecorded doses. Changing the profile time zone does the same. Taken and missed doses are kept.
- **Back-fill:** days that were never generated are filled in when the user next visits, for at most the last 90 days.

**Dose tracking**
- **No automatic statuses:** a dose stays `pending` until the user records it. Past pending doses show as *Not recorded*.
- **Timing:** a dose can be marked `taken` from `DOSE_EARLY_TAKE_MINUTES` (default 120) before its time. It can be marked `missed` only after its time.
- **Corrections:** a dose can be switched between taken and missed. `cancelled` doses, created when a medication is stopped, cannot be changed.
- **Atomic updates:** each update is a compare-and-set on `expected_status`, so a double tap, a stale screen or a race returns 409 and changes nothing. Every change is appended to the dose's `history` with a timestamp.

**Adherence:** `taken / eligible × 100`, rounded to 0.1.
- Eligible doses are those that are not cancelled and are either due by now or already recorded. Upcoming unrecorded doses are excluded.
- When nothing is eligible, `adherence_percent` is `null` and the UI shows "No doses due". It never divides by zero.

**Collections and indexes**
- `medications`: `(user_id, status, name)`.
- `doses`: unique `(medication_id, scheduled_at)`; `(user_id, local_date)`; `(user_id, scheduled_at desc)`.

**Security:** every query is scoped by the owner's `user_id`, which comes from the token. Members are authorized through an active relationship on every request, so revocation takes effect immediately. Members have no write routes. Demo data is labelled `is_demo` and stays isolated: demo users only ever see demo profiles and demo medications.

## Appointment management

| Method | Path | Access | Purpose |
| ------ | ---- | ------ | ------- |
| GET | `/api/appointments?view=upcoming\|history` | `elderly` | Upcoming lists scheduled appointments still ahead, soonest first. History lists everything else, newest first |
| POST | `/api/appointments` | `elderly` | Create. Returns 409 if you have no profile yet, or if it duplicates a scheduled appointment |
| GET / PUT | `/api/appointments/{id}` | `elderly` | Read, or edit while it is scheduled and still in the future |
| POST | `/api/appointments/{id}/cancel` | `elderly` | `scheduled → cancelled` |
| POST | `/api/appointments/{id}/complete` | `elderly` | `scheduled → completed`, only once the appointment time has passed |
| GET | `/api/linked-profiles/{profile_id}/appointments[/{id}]` | `caretaker`, `family_member` | Read-only. Returns 404 unless there is an active link |

**Fields:** doctor name, clinic name, date and time are required. Specialization, clinic address, appointment type, reason and notes are optional.

**Time zones**
- The date and time are wall-clock values in the profile's IANA time zone. They are stored as entered, together with that zone and a UTC `scheduled_at`.
- Times that a daylight-saving jump skips are rejected (422), as are past times.

**Statuses**
- Nothing changes status automatically. An appointment whose time has passed stays `scheduled`, appears under history as *Needs update*, and offers *Mark as completed* or *Cancel*.
- Status changes are atomic compare-and-set updates on `status = "scheduled"`, so a repeated request gets 409. Each change is logged in `history`.

**Duplicate protection:** a partial unique index on `(user_id, doctor_key, scheduled_at)` where `status = "scheduled"`. `doctor_key` is the case-folded doctor name. A cancelled slot can be booked again.

**Indexes:**
- `(user_id, status, scheduled_at)`
- `(user_id, scheduled_at desc)`
- the duplicate guard above

**Access and demo data:** access works exactly as for medications. The owner comes from the token, and member access is re-checked against an active relationship on every request. Demo data is isolated by `is_demo`. The seed command adds three sample appointments: two upcoming and one completed.

## Care dashboard for caretakers and family

`GET /api/care-dashboard` (`caretaker`, `family_member`) returns a read-only summary of every profile the member is **actively** linked to. It powers the `/care` page. For each person it includes:
- Profile basics and emergency contact.
- Today's dose list and the next upcoming dose.
- Today's adherence. This uses the **same** eligibility rule (`eligible_filter`) and `period()` as `/api/adherence`, and a test asserts the numbers are identical.
- The next 3 appointments, plus the total count.
- Recent activity: doses recorded as taken or missed, and appointments completed or cancelled in the last 7 days. These are only real recorded status changes; nothing is inferred.

**Authorization:** this endpoint uses the same rules as `/linked-profiles/...`. Relationships are re-read on every request, only active links with a matching demo flag count, and it returns nothing those endpoints don't already expose. A revoked person disappears on the next refresh.

**Efficiency:** the endpoint uses a fixed number of batched queries regardless of how many people are linked, instead of the browser making 4 or more requests per person:
- relationships
- profiles
- medications
- today's dose counts
- today's doses
- upcoming appointments (one aggregation)
- recent dose changes
- recent appointment changes

Missing doses are generated only when needed. No new collections were added. Queries use the existing `doses (user_id, local_date)`, `appointments (user_id, status, scheduled_at)` and `user_id` indexes.

## Reminders and notifications

The `/notifications` page shows the delivery status, your settings, a "Send test message" button and your notification history.

**API** (all authenticated roles; everything is scoped to the caller):

| Endpoint | Purpose |
|---|---|
| `GET /api/notifications?limit=` | History. Owners see notifications about themselves; everyone sees notifications addressed to them. Bodies and email addresses are never returned. |
| `GET` / `PUT /api/notifications/preferences` | Your own settings only. Caretakers cannot change an elderly person's settings. |
| `GET /api/notifications/status` | Email or preview mode, whether SMTP is configured, whether the scheduler is running, and the last check time. |
| `POST /api/notifications/test` | Queues a test message to yourself (202). Returns 429 if you already sent one this minute. |

**What is sent:**
- **Medicine reminders:** sent N minutes before each dose (5–120, default 15).
- **Missed-dose alerts:** sent when a dose is still pending `MISSED_DOSE_GRACE_MINUTES` after its time. They go to the person and, if they allow it, to their actively linked caretakers and family.
- **Appointment reminders:** sent N minutes before the appointment (15 min to 1 week, default 1 day).

Times are shown in the elderly person's timezone. Dose statuses are never changed. Cancelled, completed or past items are skipped.

**Scheduling:**
- A daemon thread started in the FastAPI lifespan runs every `NOTIFICATION_INTERVAL_SECONDS`. Each cycle generates due notifications, then delivers them. Delivery runs outside request handling, so it never blocks API requests.
- Every notification has a unique `dedupe_key` (kind, item, event time, recipient), so repeated cycles and restarts never create duplicates.
- Delivery atomically claims a row with a 5-minute lease. A crash mid-send is retried after the lease expires.
- A failed send is retried up to 3 attempts, 5 minutes apart, and then marked `failed` with a safe reason.
- Before sending, the scheduler re-checks the relationship, dose status and appointment. Anything no longer relevant is marked `skipped`.

**Email:**
- Configure email only in the backend `.env`: set `EMAIL_MODE=smtp` and the `SMTP_*` values (see `.env.example`). Credentials never reach the frontend, API responses or logs.
- **Preview mode** (the default) is used whenever SMTP isn't configured, and always for demo data. Notifications are recorded with status `preview` and never emailed.
- Emails contain times, the timezone and the clinic name. They never include medicine names, doctor names, notes, passwords or links with tokens.

**Collections:**
- `notifications`: unique `uniq_notification` on `dedupe_key`; `(status, next_attempt_at)`; `(owner_user_id, created_at)`; `(recipient_user_id, created_at)`.
- `notification_preferences`: unique on `user_id`.

**Limits:** every process starts the scheduler thread, but only the holder of a MongoDB lease (`scheduler_locks`) runs cycles; see [Deployment](#deployment).

## Demo accounts

Three shared accounts let people try the app. They hold **sample data only**.

| Role | Email | Password |
| ---- | ----- | -------- |
| Elderly | `elderly.demo@eldercare.com` | `ElderDemo2026!` |
| Caretaker | `caretaker.demo@eldercare.com` | `CareDemo2026!` |
| Family member | `family.demo@eldercare.com` | `FamilyDemo2026!` |

**Enable and provision (one-off, not on startup):**

```bash
cd backend
# set DEMO_ACCOUNTS_ENABLED=true in backend/.env, then:
python -m app.scripts.seed_demo_accounts
```

The command is idempotent:
- It also creates **sample data** if it is missing: a demo elderly profile, three sample medicines named "… (sample)" with yesterday's doses recorded, three sample appointments, and links from the demo caretaker and family member to that profile.
- It creates only the accounts that are missing.
- It never changes an existing account or password.
- If an email belongs to a regular (non-demo) account, it skips that account and leaves it untouched.

Exit code 1 means demo mode is disabled; 2 means the database is unreachable. Restart the API after changing the setting.

**How demo mode behaves**
- **Login page:** shows a *Demo accounts* section only when the backend reports demo mode is on and the accounts exist. "Use Demo Account" fills in the form; the user still clicks **Sign in**.
- **Labelling:** demo users are stored with `is_demo: true`, and the header and dashboard show a *Demo* badge and a sample-data notice.
- **Isolation:** endpoints that touch real user data must use `Depends(get_non_demo_user)` or `require_roles(..., allow_demo=False)`. Both return 403 for demo accounts. The current portal endpoints serve placeholder content only, so demo users may use them.
- **Reserved emails:** the demo addresses can never be registered through the public sign-up.
- **Turning it off:** setting `DEMO_ACCOUNTS_ENABLED=false` blocks demo sign-ins at once and invalidates any demo tokens already issued. It also hides the listing.
- **Production:** demo mode stays off unless `DEMO_ACCOUNTS_ALLOW_PRODUCTION=true` is also set.

## Deployment

**Live setup:** backend on **Render**, frontend on **Vercel**, database on **MongoDB Atlas**, all on free tiers. No paid services are required. `backend/Dockerfile` also builds a slim, non-root image if a container host is preferred.

### Backend on Render

- Build: `pip install -r requirements.txt` (versions are pinned). Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Set `ENVIRONMENT=production`, `MONGODB_URI`, `JWT_SECRET_KEY`, `CORS_ORIGINS`, `APP_BASE_URL` and `EMAIL_MODE=preview` in the Render dashboard. Never commit them.
- Render sits behind Cloudflare. Set `CLIENT_IP_HEADER=CF-Connecting-IP` so per-IP login and registration limits apply. Without it, per-IP limits are off in production and only per-account limits apply.
- Indexes (including the notification retention TTL and the scheduler top-up index) are created at startup.
- Verify: `curl https://SERVICE_URL/api/health` returns `"status": "ok"` with the database `connected`.

**Reminder scheduler:** runs as a background thread. Only the holder of a MongoDB lease (`scheduler_locks`) runs cycles, so more than one instance is safe. Unique `dedupe_key`s and atomic delivery claims prevent duplicate emails. Set `NOTIFICATIONS_ENABLED=false` to turn it off.

**Email:** keep `EMAIL_MODE=preview` until real delivery has been tested. For SMTP, set `EMAIL_MODE=smtp`, `SMTP_HOST`, `SMTP_FROM`, `SMTP_USERNAME` and `SMTP_PASSWORD` (as a secret), then use **Send test message** on `/notifications`.

**Production safeguards** (`ENVIRONMENT=production`):
- Startup fails if `CORS_ORIGINS` contains `*` or `DEBUG=true`. API docs (`/docs`, `/openapi.json`) are disabled.
- Demo accounts stay off unless `DEMO_ACCOUNTS_ALLOW_PRODUCTION=true` is also set. Their credentials are public, so use them only for development or a judged demo.

### Quality checks and CI

`.github/workflows/ci.yml` runs on every push and pull request. It uses a throwaway `mongo:7` service container and never production credentials.
- Backend: `ruff check`, `ruff format --check`, `pytest --cov` (90% coverage gate).
- Frontend: `npm run lint` (oxlint), `npm run test:coverage` (Vitest with axe accessibility checks and coverage thresholds), `npm run build`.

To run locally: `cd backend && python -m ruff check app tests && python -m pytest --cov`, then `cd frontend && npm run lint && npm run test:coverage && npm run build`. `mypy app` is configured in `backend/pyproject.toml` but not yet enforced.

### Frontend on Vercel

1. Import the repo with root directory `frontend` and the **Vite** preset. The build command is `npm run build` and the output directory is `dist`.
2. Set the env var `VITE_API_BASE_URL=https://SERVICE_URL`, with no trailing slash. A production build without it shows a configuration error instead of calling localhost.
3. `vercel.json` adds the SPA rewrite and security headers (`nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`).
4. After Vercel assigns the URL, update `CORS_ORIGINS` and `APP_BASE_URL` on Render:

   ```bash
   gcloud run services update eldercare-api --region asia-south1 \
     --update-env-vars CORS_ORIGINS=https://YOUR-APP.vercel.app,APP_BASE_URL=https://YOUR-APP.vercel.app
   ```

Only `VITE_*` variables reach the browser. Never put secrets in them.

### Environment variables

| Where | Variable | Notes |
|---|---|---|
| Render (secret) | `MONGODB_URI`, `JWT_SECRET_KEY` (≥ 32 chars), `SMTP_PASSWORD` | Set in the Render dashboard; never commit. |
| Render | `ENVIRONMENT=production`, `CORS_ORIGINS`, `APP_BASE_URL`, `MONGODB_DB_NAME` | |
| Render | `EMAIL_MODE`, `SMTP_HOST`/`PORT`/`USERNAME`/`FROM`/`SECURITY` | Optional; defaults to preview. |
| Render | `NOTIFICATION_INTERVAL_SECONDS`, `MISSED_DOSE_GRACE_MINUTES`, `LOGIN_MAX_FAILURES`, … | Optional; see `backend/.env.example`. |
| Vercel | `VITE_API_BASE_URL`, `VITE_API_TIMEOUT_MS` | Public values only. |
