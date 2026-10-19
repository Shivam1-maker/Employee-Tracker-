# Employee Login Location Tracking & Shift Monitoring

A web application that records every employee sign-in, works out where in India it came from
(with the employee's consent), checks it against the employee's assigned shift, and gives
administrators a central dashboard with filters, compliance reports, CSV export and an audit trail.

Built with **FastAPI**, **SQLAlchemy 2**, **SQLite or PostgreSQL**, and a dependency-free
HTML/CSS/JS front end served by the same process.

---

## 1. Quick start (local, SQLite)

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                 # then set ELT_SECRET_KEY
python -m scripts.seed               # admin + 4 shifts + 8 offices + 24 employees + 14 days of demo sign-ins
uvicorn app.main:app --reload
```

Open http://localhost:8001

| Account | Employee ID | Password |
|---|---|---|
| Administrator | `ADM001` | `Admin@12345` |
| Demo employees | `EMP1001` … `EMP1024` | `Welcome@123` |

Change these immediately outside a test environment. For a clean production bootstrap:

```bash
python -m scripts.seed --reset --no-demo --admin-password 'a-long-unique-password'
```

Other seed options: `--employee-password 'Welcome@123'` (demo employees' password), `--days 14` (demo history length).

**Upgrading from an earlier version:** just restart the server. New tables and columns are added
automatically on start-up and existing records are kept. Run `python -m scripts.seed --reset` only
if you want fresh demo data (it deletes everything).

Interactive API docs: http://localhost:8001/docs (OpenAPI JSON is also saved in `docs/openapi.json`).

Run the test suite:

```bash
pytest -q        # 79 tests: shift rules, geolocation, auth, RBAC, reports, attendance, leave, alerts, import, notifications, security
```

---

## 2. What it does

**Sign-in page** (`/static/login.html`) shows the current IST time, explains what is recorded,
and offers an opt-in checkbox to share device location for that sign-in.

**Admin console** (`/static/admin.html`)
- Login records with filters for date range (IST), employee, state, shift result, location check,
  failed sign-ins and flagged events. Each row has an arrival bar showing the sign-in against the
  shift start and grace period; click a row for full details.
- Summary strip: successful sign-ins, on-time rate, late arrivals, outside-shift/off-day,
  verified-at-office count, flagged events, failed sign-ins.
- Shift compliance per employee: on-time %, late count, average minutes late, verified-location %.
- State-wise breakdown across India.
- Manage employees (add, edit, reset password, unlock, deactivate), shifts and offices
  (geofence radius and office IP ranges).
- CSV export and audit trail of every administrative action; retention purge.

- **Attendance:** a daily register for every employee (present and late, absent, on leave,
  holiday, weekly off, not due yet) with first sign-in, check-out, hours worked and location.
  Filter by department; download as CSV.
- **Alerts:** a review queue for sign-ins flagged for impossible travel, the wrong office, faked-
  looking GPS or a location outside India. Acknowledge or dismiss each with a note; the tab shows
  the open count.
- **Leave & holidays:** approve, reject or revoke leave requests; maintain national and
  state-specific holidays so those days aren't counted as absences.
- **Trends:** sign-ins per day split into on time, late and other.
- **Notifications:** every sign-in emails (and optionally texts) the employee and their manager
  with the time and location. See section 10.
- **Bulk import:** paste or upload a CSV of employees. The whole file is checked first and nothing
  is created if any row has a problem.

**Employee page** (`/static/employee.html`)
- Shows the current session with a **Check out** button that records hours worked, early leave or
  overtime.
- A month calendar of their own attendance.
- Request leave and track approval; cancel pending or future leave.
- Change password, see everything recorded about their sign-ins, and withdraw location consent.

---

## 3. How location is determined

Signals are checked in this order. Location is captured **only at the moment of sign-in**; there is
no background or continuous tracking.

| Status | Meaning | How |
|---|---|---|
| `verified_office` | At an office | Device GPS (with consent) inside an office geofence (radius + up to 200 m GPS tolerance) |
| `verified_network` | On an office network | Client IP is inside an office CIDR range |
| `offsite` | Located, not at an office | Precise GPS outside every geofence (e.g. remote work); city/state from the bundled city list |
| `approximate` | Low precision | GPS accuracy worse than 1.5 km, or optional IP lookup |
| `outside_india` | Abroad | Coordinates outside India's bounding box |
| `unverified` | Not located | No consent and not on an office network |

City/state lookup uses an offline list of ~80 Indian cities (`app/data/india_cities.py`), so no
location data is sent to a third party. Extend it (e.g. with GeoNames `IN.txt`) for finer coverage.

**Risk flags** raised on a sign-in: `impossible_travel` (implied speed > 900 km/h from the previous
located sign-in), `not_assigned_office`, `suspicious_accuracy` (GPS reports 0 m), `outside_india`,
`failed_login`.

---

## 4. How shift compliance is calculated

All times are evaluated in `Asia/Kolkata` and stored in UTC.

| Result | Rule |
|---|---|
| `on_time` | Sign-in between *start − early window* (default 60 min) and *start + grace* (default 10 min) |
| `late` | After *start + grace* and before shift end; minutes late are recorded |
| `off_day` | Sign-in on a day that isn't a working day for the shift |
| `outside_shift` | Any other time on a working day |
| `no_shift` | Employee has no shift assigned |

| `holiday` | Signed in on a holiday that applies to the employee's office state |
| `on_leave` | Signed in on a day of approved leave |

**Check-out** compares the sign-out time with the scheduled shift end: `early_leave` (before the
end), `completed` (up to 30 minutes after, configurable), `overtime` (later than that) or
`unscheduled` (the sign-in wasn't inside a shift). Hours worked are recorded either way. A sign-in
older than 20 hours can no longer be checked out.

**Attendance** for a day: anyone with a sign-in belonging to that day's shift is *present*;
otherwise the day is a *weekly off*, *holiday*, *on leave*, *not due yet* (shift start plus grace
hasn't passed) or *absent*, in that order.

Overnight shifts (e.g. 22:00–06:00) are supported: a sign-in at 00:30 on Tuesday is matched to
Monday's night shift and reported as 150 minutes late.

---

## 5. Project structure

```
app/
  main.py               App factory, security headers, static files
  config.py             Settings (env vars, ELT_ prefix)
  database.py           Engine/session, SQLite FK enforcement
  models.py             User, Shift, Office, LoginEvent, AuditLog
  schemas.py            Pydantic request/response models and validation
  security.py           bcrypt, JWT, client IP, rate limiter
  deps.py               Auth and admin-role dependencies
  routers/
    auth.py             Sign-in, /me, consent withdrawal
    admin_crud.py       Employees, shifts, offices
    logins.py           Records, reports, CSV export, audit, retention
    workforce.py        Attendance, leave, holidays, alert review, CSV import
    notifications.py    Notification outbox, retry, test message
  services/
    geo.py              Geofence, office networks, nearest city, India checks
    shift.py            Shift compliance engine
    login_events.py     Builds and serializes login events
    attendance.py       Daily attendance register
    calendar.py         Holiday and leave lookups
    notify.py           Sign-in emails/SMS to employee and manager
    audit.py            Audit logging
  data/india_cities.py  Offline city reference data
  static/               Sign-in, admin console, employee page (HTML/CSS/JS)
scripts/seed.py         Bootstrap and demo data
tests/                  pytest suite
docs/API.md             Endpoint reference
docs/openapi.json       Generated OpenAPI schema
```

---

## 6. Deployment

### Docker Compose (PostgreSQL)

```bash
export ELT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
docker compose up -d --build
docker compose exec app python -m scripts.seed --no-demo --admin-password 'a-long-unique-password'
```

Tables, and new columns from later versions, are created automatically on start-up. For more
complex schema changes in production, add Alembic
migrations (`alembic init`, point `target_metadata` at `app.database.Base.metadata`).

### Behind a reverse proxy (required for real use)

Browsers only allow the Geolocation API on **HTTPS** (localhost is exempt). Put nginx, Caddy or a
cloud load balancer in front with TLS, then set `ELT_TRUST_PROXY_HEADERS=true` so the real client
IP is used for office-network checks and rate limiting. Never enable that setting when the app is
directly exposed, or clients can spoof their IP.

```nginx
server {
    listen 443 ssl http2;
    server_name attendance.example.com;
    ssl_certificate     /etc/letsencrypt/live/attendance.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/attendance.example.com/privkey.pem;
    add_header Strict-Transport-Security "max-age=31536000" always;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
    }
}
```

### Scaling notes
- The login rate limiter is in-process. With multiple workers or instances, each keeps its own
  counter; move it to Redis for a strict global limit. Account lockout is stored in the database
  and is already global.
- Schedule `POST /api/admin/retention/purge` (or a cron job) to enforce your retention period.

---

## 7. Security measures

- bcrypt password hashing (cost 12); minimum 10-character passwords for new accounts.
- Signed JWT access tokens (HS256) with expiry; role-based access (admin vs employee).
- Account lockout after 5 failed attempts (15 min), per-IP rate limiting, identical error
  message for unknown user and wrong password, constant-time check for unknown users.
- Every sign-in attempt, successful or not, is recorded; every admin change, export and purge
  is written to the audit log.
- Strict Content-Security-Policy (no inline scripts or styles), `X-Frame-Options: DENY`,
  `nosniff`, `no-referrer`, `Permissions-Policy` limiting geolocation to this origin,
  `Cache-Control: no-store` on API responses.
- All UI rendering uses `textContent` (no `innerHTML`), preventing stored XSS from names or
  user agents.
- CSV export neutralises spreadsheet formula injection.
- Server-side validation of coordinates, CIDRs, shift days and foreign keys; ORM queries only.
- Soft delete for employees so history stays auditable; admins can't deactivate themselves.

**Known limits.** Browser GPS can be spoofed by a determined user with developer tools or a mock-
location app; treat `verified_office` as strong evidence, not proof. Pair it with office-network
verification, the impossible-travel flag, and (if needed) a managed-device MDM attestation.

---

## 8. Privacy and legal (India)

Location and attendance data are personal data under the **Digital Personal Data Protection Act,
2023**. The app is designed to support compliance, but your organisation is responsible for how
it is used. Before go-live:

- Give employees a clear written notice of what is collected, why, how long it's kept, and who
  can see it (the sign-in page text is a starting point, not a complete notice).
- Location is opt-in per employee, recorded with a timestamp, and can be withdrawn at any time
  from the employee page. Sign-ins still work without it.
- Collect only at sign-in, never continuously; coordinates are stored to 5 decimal places.
- Set `ELT_RETENTION_DAYS` to the shortest period you need and run the purge regularly.
- Restrict administrator accounts to people who need them; review the audit trail.
- Check your HR policy, employment contracts and any state-specific rules with your legal team.

---

## 9. Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `ELT_SECRET_KEY` | *(placeholder)* | JWT signing key. **Must** be set. |
| `ELT_DATABASE_URL` | `sqlite:///./elt.db` | SQLAlchemy URL; use `postgresql+psycopg://…` in production |
| `ELT_ACCESS_TOKEN_MINUTES` | `60` | Session length |
| `ELT_MAX_FAILED_LOGINS` / `ELT_LOCKOUT_MINUTES` | `5` / `15` | Lockout policy |
| `ELT_LOGIN_RATE_LIMIT_PER_MINUTE` | `20` | Per-IP sign-in attempts |
| `ELT_TIMEZONE` | `Asia/Kolkata` | Shift evaluation and display timezone |
| `ELT_NEAREST_CITY_MAX_KM` | `60` | Max distance to name a nearest city |
| `ELT_POOR_GPS_ACCURACY_M` | `1500` | Accuracy above this is "approximate" |
| `ELT_IMPOSSIBLE_TRAVEL_KMH` | `900` | Speed threshold for the travel flag |
| `ELT_RETENTION_DAYS` | `365` | Default purge age |
| `ELT_OVERTIME_THRESHOLD_MINUTES` | `30` | Minutes past shift end before a check-out counts as overtime |
| `ELT_MAX_SESSION_HOURS` | `20` | Oldest sign-in that can still be checked out |
| `ELT_TRUST_PROXY_HEADERS` | `false` | Use `X-Forwarded-For` (only behind your proxy) |
| `ELT_IP_GEO_PROVIDER` | `none` | `ipapi` enables coarse third-party IP lookup |
| `ELT_CORS_ORIGINS` | *(empty)* | Comma-separated origins if the UI is hosted elsewhere |

---

## 10. Sign-in notifications (email and SMS)

Each successful sign-in sends:
- **the employee** a receipt with time (IST), city/state, office, how the location was checked,
  shift status, device and IP, plus "if this wasn't you, change your password";
- **their manager** the same details, with "Attention:" in the subject when the sign-in is late,
  outside shift hours, on an off day, or flagged (impossible travel, wrong office, faked GPS,
  outside India).

The employee also gets a warning when their account is locked after failed sign-ins.

Set each employee's **manager** and optional **mobile number** in Admin → Employees (or the
`manager` and `phone` columns of a CSV import). Phone numbers like `98765 43210` are stored as
`+919876543210`.

Messages are queued with the sign-in and sent in the background, so sign-in never waits on the
mail server. Failures are retried 3 times. Admin → Notifications shows every message with its
status, lets you read it, retry failed ones and send a test. Employees and managers see the
messages sent to them on their own page.

### Turning on real email

Out of the box `ELT_EMAIL_BACKEND=console`: messages are written to the server log and marked
sent, so you can try everything without a mail server. To deliver for real, set in `.env`:

```ini
ELT_EMAIL_BACKEND=smtp
ELT_COMPANY_NAME=Acme India
ELT_PUBLIC_URL=https://attendance.acme.in
ELT_SMTP_FROM=Acme Attendance <attendance@acme.in>
ELT_SMTP_USERNAME=attendance@acme.in
ELT_SMTP_PASSWORD=app-password-here
```

plus the server for your provider:

| Provider | `ELT_SMTP_HOST` | Port / mode | Notes |
|---|---|---|---|
| Google Workspace / Gmail | `smtp.gmail.com` | `587`, STARTTLS | Use an **App Password** (needs 2-step verification), not the normal password |
| Microsoft 365 / Outlook | `smtp.office365.com` | `587`, STARTTLS | SMTP AUTH must be enabled for the mailbox |
| Zoho Mail (India) | `smtp.zoho.in` | `587`, STARTTLS, or `465` with `ELT_SMTP_SSL=true` | |
| Amazon SES (Mumbai) | `email-smtp.ap-south-1.amazonaws.com` | `587`, STARTTLS | Username/password are SES SMTP credentials; verify the sender domain |

For port 465 set `ELT_SMTP_PORT=465` and `ELT_SMTP_SSL=true`. Restart the server, then use
Admin → Notifications → **Send a test**. If it fails, the exact SMTP error is shown.

### SMS or WhatsApp

Set `ELT_SMS_WEBHOOK_URL` (and optionally `ELT_SMS_WEBHOOK_TOKEN`, sent as a Bearer token). For
each message the app POSTs JSON:

```json
{ "to": "+919876543210", "message": "Acme: Priya Iyer signed in 09:12 AM, Mumbai, Maharashtra (On time).", "kind": "login_manager" }
```

Gateways such as MSG91, Gupshup, Twilio or the WhatsApp Business API each expect their own
request format, so point this URL at a small adapter (a few lines in a serverless function) that
forwards to your provider. In India, commercial SMS must use a **DLT-registered sender ID and
template** (TRAI rules): register the message text with your operator before going live, and keep
the wording in `app/services/notify.py` identical to the approved template.

### Options

| Variable | Default | Effect |
|---|---|---|
| `ELT_NOTIFY_EMPLOYEE_ON_LOGIN` | `true` | Send the employee a receipt |
| `ELT_NOTIFY_MANAGER_ON_LOGIN` | `true` | Tell the manager |
| `ELT_MANAGER_NOTIFY_MODE` | `all` | `all` = every sign-in; `exceptions` = only late, out-of-shift or flagged ones |
| `ELT_NOTIFY_COOLDOWN_MINUTES` | `30` | Skip repeat routine messages (e.g. signing in again after a browser restart). Exceptions are always sent |
| `ELT_NOTIFY_ON_LOCKOUT` | `true` | Warn the employee when their account locks |
| `ELT_INCLUDE_COORDINATES` | `false` | Add GPS coordinates to messages (city/state is always included) |
| `ELT_NOTIFY_MAX_ATTEMPTS` | `3` | Delivery attempts before a message is marked failed |

**Privacy:** sending location to a manager is processing of personal data. The sign-in page tells
employees who will be notified (it reads these settings), but include it in your written notice
too, and consider `exceptions` mode if a message on every sign-in is more than you need.
