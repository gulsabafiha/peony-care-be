# Peony Care Backend

Django REST API for the Peony Care food-share app (PostgreSQL + JWT + Docker).

## Stack

- Django 5.2 + Django REST Framework
- PostgreSQL 16
- JWT auth (SimpleJWT) with phone OTP
- Docker Compose for local dev
- GitHub Actions CI/CD

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

API health check: http://localhost:8000/health/

Swagger UI: http://localhost:8000/api/docs/

OpenAPI schema: http://localhost:8000/api/schema/

Create admin user:

```bash
docker compose exec web python manage.py createsuperuser
```

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

## Project structure

```
apps/
  accounts/      # users, OTP, profiles, JWT
  donations/     # food_items, browse (receiver/restaurant)
  claims/        # instant claim on QR scan
  donors/        # meal/money donations (P2)
  notifications/
  common/        # response envelope, geo utils
config/settings/
  base.py
  development.py
  production.py
```

## API modules (P1)

| Module | Base path |
|--------|-----------|
| Auth | `/api/v1/auth/` |
| Receiver | `/api/v1/receiver/` |
| Restaurant | `/api/v1/restaurant/` |
| Donor | `/api/v1/donor/` |
| Shared | `/api/v1/` |

Endpoint implementations are added incrementally per the API design doc.

## Tests

```bash
pytest
```

## Production

```bash
docker compose -f docker-compose.prod.yml up --build
```

Set `DJANGO_SETTINGS_MODULE=config.settings.production` and strong `DJANGO_SECRET_KEY`.

## CI/CD

- **CI** (`.github/workflows/ci.yml`): lint → test → Docker build on `main`
- **CD** (`.github/workflows/cd.yml`): push image to ECR when AWS secrets are configured

Required GitHub secrets for CD: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `ECR_REGISTRY`.
