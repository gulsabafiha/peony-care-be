# Peony Care Backend

Django REST API for the Peony Care food-share app (PostgreSQL + JWT + Docker).

## Stack

- Django 5.2 + Django REST Framework
- PostgreSQL 16
- JWT auth (SimpleJWT) with phone OTP
- Swagger / OpenAPI (`drf-spectacular`)
- Docker Compose for local dev
- GitHub Actions CI/CD

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

| URL | Purpose |
|-----|---------|
| http://localhost:8000/health/ | Health check |
| http://localhost:8000/api/docs/ | Swagger UI |
| http://localhost:8000/api/schema/ | OpenAPI schema |
| http://localhost:8000/admin/ | Django Admin |

Create an admin user:

```bash
docker compose exec web python manage.py createsuperuser
```

Migrations run automatically on container start via `docker/entrypoint.sh`.

## Local development (without Docker)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env
# Start PostgreSQL and set DATABASE_URL
python manage.py migrate
python manage.py runserver
```

## Response format

All API responses use a standard envelope:

```json
{
  "status": "success",
  "data": { },
  "error": null,
  "timestamp": "2026-06-14T12:00:00+08:00"
}
```

Errors return `"status": "error"` with `error.code`, `error.message`, and optional `error.details`.

## Authentication

Phone OTP registration for three roles: **receiver**, **restaurant**, **donor**.

### 1. Send OTP

```http
POST /api/v1/auth/otp/send/
{ "phone": "+6591234567", "purpose": "register" }
```

With `OTP_PROVIDER=console` (default in dev), the code is printed to container logs:

```
[Peony OTP] +6591234567 (register): 123456
```

### 2. Verify OTP

```http
POST /api/v1/auth/otp/verify/
{ "phone": "+6591234567", "code": "123456", "purpose": "register" }
```

Returns a short-lived `registration_token`.

### 3. Register

```http
POST /api/v1/auth/register/receiver/
POST /api/v1/auth/register/restaurant/
POST /api/v1/auth/register/donor/
```

Include the token in the `Registration-Token` header. Response includes `access` and `refresh` JWT tokens.

### 4. Authenticated requests

```http
Authorization: Bearer <access_token>
```

Refresh: `POST /api/v1/auth/token/refresh/`  
Logout: `POST /api/v1/auth/logout/`

## API modules (P1)

### Auth — `/api/v1/auth/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `otp/send/` | Send OTP |
| POST | `otp/verify/` | Verify OTP, get registration token |
| POST | `register/receiver/` | Register receiver |
| POST | `register/restaurant/` | Register restaurant |
| POST | `register/donor/` | Register donor |
| POST | `token/refresh/` | Refresh JWT |
| POST | `logout/` | Revoke refresh token |

### Receiver — `/api/v1/receiver/`

Requires `Authorization: Bearer` and receiver role.

**Donations** (`receiver_donations` namespace)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `donations/browse/` | Browse nearby active listings |
| GET | `donations/search/` | Search by keyword / filters |
| GET | `donations/{food_id}/` | Food detail |

**Claims** (`receiver_claims` namespace)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `claims/today/` | Today's claim status (daily limit) |
| GET | `claims/` | Claim history |
| POST | `claims/` | Claim food (scan QR payload) |
| GET | `claims/{claim_id}/` | Claim detail |

**Profile** (`receiver_accounts` namespace)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/PATCH | `profile/` | Receiver profile |
| GET | `stats/` | Meals saved, claims count |

### Restaurant — `/api/v1/restaurant/`

Requires `Authorization: Bearer` and restaurant role.

**Donations** (`restaurant_donations` namespace)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `dashboard/` | Today's stats and active listings |
| GET | `donations/?status=active\|past\|inactive` | List donations |
| POST | `donations/` | Create donation |
| GET/PATCH/DELETE | `donations/{food_id}/` | Detail / update / soft-delete |
| POST | `donations/{food_id}/close/` | Close listing |
| POST | `donations/{food_id}/reactivate/` | Re-open closed listing |
| GET/PATCH | `profile/` | Restaurant profile |
| GET | `approval-status/` | Activation status |

**Claims** (`restaurant_claims` namespace)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `claims/today/` | Today's claims board |
| GET | `donations/{food_id}/claims/` | Claims for one donation |

Restaurants are active immediately after registration and can post donations without Django Admin approval.

### Public

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/restaurants/{restaurant_id}/` | Public restaurant page (no auth) |

### Donor — `/api/v1/donor/`

Requires `Authorization: Bearer` and donor role.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `dashboard/` | Impact stats + recent donations |
| GET | `history/` | Meal and money donation history |
| GET | `impact/` | Monthly chart data |
| GET/PATCH | `credit-preference/` | `SHOW_NAME` \| `INITIALS` \| `ANONYMOUS` |
| GET/PATCH | `profile/` | Name, photo, `contact_email` |
| GET | `restaurants/` | Browse restaurants to sponsor |
| GET | `restaurants/{id}/menu/` | Admin-managed menu |
| POST | `meal-orders/` | Meal order → auto-posts sponsored `FoodItem` |
| POST | `money-donations/` | Create donation + PayNow reference |
| POST | `money-donations/{id}/confirm-transfer/` | Donor marks PayNow transfer sent |

**Meal order flow:** donor picks menu items → `FoodItem` auto-created with sponsor credit → receivers can claim.

**Money donation flow:** create → PayNow details + `reference_code` → donor confirms transfer → admin confirms in Django Admin → `total_amount_donated_sgd` updated.

Menu items are managed in Django Admin only (not via restaurant API).

## End-to-end dev flow

1. **Register a restaurant** — OTP send → verify → `POST /auth/register/restaurant/` with `Registration-Token`
2. **Post a donation** — `POST /api/v1/restaurant/donations/` (QR payload generated automatically)
3. **Register a receiver** — same OTP flow with `register/receiver/`
4. **Browse food** — `GET /api/v1/receiver/donations/browse/`
5. **Claim food** — `POST /api/v1/receiver/claims/` with QR scan payload
6. **Restaurant views claims** — `GET /api/v1/restaurant/claims/today/`

### Donor flow

1. **Register a donor** — OTP send → verify → `POST /auth/register/donor/` with `Registration-Token`
2. **Add menu items** — Django Admin → `Menu items` for an approved restaurant
3. **Sponsor a meal** — `POST /api/v1/donor/meal-orders/` (auto-posts sponsored listing)
4. **Or donate money** — `POST /api/v1/donor/money-donations/` → confirm transfer → admin confirms in Django Admin
5. **View impact** — `GET /api/v1/donor/dashboard/` or `GET /api/v1/donor/impact/`

## Project structure

```
apps/
  accounts/      # users, OTP, JWT, receiver profile
  donations/     # receiver browse + restaurant donation CRUD
  claims/        # receiver claims + restaurant claims board
  donors/        # donor dashboard, meal/money donations
  notifications/
  common/        # response envelope, permissions, geo, geocoding
config/settings/
  base.py
  development.py
  production.py
docker/
  Dockerfile, Dockerfile.dev, entrypoint.sh
```

Key files:

| File | Purpose |
|------|---------|
| `apps/accounts/services.py` | OTP, registration, JWT |
| `apps/donations/receiver_*.py` | Receiver browse/search |
| `apps/donations/restaurant_*.py` | Restaurant donations |
| `apps/claims/services.py` | Transactional claim logic |
| `apps/common/permissions.py` | `IsReceiver`, `IsRestaurant`, `IsDonor` |
| `apps/donors/services.py` | Meal orders, money donations, donor profile |
| `config/urls.py` | All routing |

## Environment variables

See `.env.example`. Notable settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `OTP_PROVIDER` | `console` | `console` prints OTP to logs; `twilio` / `sns` for production |
| `MAX_CLAIM_DISTANCE_M` | `500` | Max distance (m) between receiver and restaurant to claim |
| `DAILY_CLAIM_LIMIT` | `1` | Max claims per receiver per day |
| `DEFAULT_BROWSE_RADIUS_KM` | `5` | Default browse radius |
| `PAYNOW_UEN` | — | PayNow UEN for money donations |
| `PAYNOW_ACCOUNT_NAME` | `Peony Care Ltd` | PayNow display name |

## Tests

```bash
pytest
```

42 tests cover auth, receiver, restaurant, and donor modules.

Lint and format:

```bash
ruff check .
ruff format .
```

## Production

```bash
docker compose -f docker-compose.prod.yml up --build
```

Set `DJANGO_SETTINGS_MODULE=config.settings.production` and a strong `DJANGO_SECRET_KEY`.

## CI/CD

- **CI** (`.github/workflows/ci.yml`): lint → test → Docker build on `main`
- **CD** (`.github/workflows/cd.yml`): push image to ECR when AWS secrets are configured

Required GitHub secrets for CD: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `ECR_REGISTRY`.

## Not yet implemented

- Restaurant approval API (admin only today)
- S3 QR image upload (`food_qr_image_url`)
- OneMap geocoding (stub returns Singapore default coords)
- Auto-expire food items past pickup window
- Notification settings (P2)
