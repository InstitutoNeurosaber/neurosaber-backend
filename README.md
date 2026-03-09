# Neurosaber Backend

Backend API for **Neurosaber Certificaciones** — a certificate issuance and validation platform for Faculdade NeuroSaber. Built with FastAPI, SQLAlchemy 2.0, and PostgreSQL.

## What it does

1. Syncs courses from the [Guru](https://digitalmanager.guru) platform (Brazilian digital product marketplace)
2. Verifies student purchases by CPF (Brazilian tax ID) against Guru transactions
3. Generates two-page PDF certificates with QR codes for validation
4. Provides admin endpoints for course management and manual sync

## Tech Stack

| Category | Technology |
|---|---|
| Framework | FastAPI 0.115 |
| Language | Python 3.12+ |
| Database | PostgreSQL |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| DI | injector + fastapi-injector |
| PDF generation | ReportLab + pypdf + qrcode |
| External API | Guru (httpx) |
| Scheduling | APScheduler |
| Logging | structlog |
| Monitoring | Sentry |
| Testing | pytest + testcontainers + factory-boy |

## Project Structure

```
backend/
├── app/
│   ├── main.py                  # App factory
│   ├── routers.py               # Route assembly
│   ├── dependencies.py          # DI container setup
│   ├── core/                    # Auth, config, logging, scheduler, events
│   ├── database/sql/            # SQLAlchemy base, mixins, engine
│   ├── repositories/            # Generic repository pattern (CRUD + bulk)
│   ├── modules/
│   │   └── certificate/         # Domain module (models, schemas, service, routers)
│   ├── services/
│   │   ├── guru/                # Guru API client
│   │   └── pdf/                 # Certificate PDF generator + templates
│   └── migrations/              # Alembic migrations
├── tests/
│   ├── unit/                    # Mocked unit tests
│   └── integration/             # Full API tests with testcontainers (Postgres 16)
├── Dockerfile
├── alembic.ini
└── pyproject.toml
```

## API Endpoints

### Public

| Method | Path | Description |
|---|---|---|
| GET | `/api/courses` | List active courses (paginated, filterable) |
| POST | `/api/certificates/emit` | Emit a certificate PDF (requires CPF + course_id) |
| GET | `/api/certificates/validate/{token}` | Validate a certificate by token |
| GET | `/health` | Health check |

### Admin (requires `x-admin-api-key` header)

| Method | Path | Description |
|---|---|---|
| GET | `/api/admin/courses` | List all courses including inactive |
| PATCH | `/api/admin/courses/{id}` | Update course metadata |
| POST | `/api/admin/sync-courses` | Trigger Guru course sync |

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL
- [Poetry](https://python-poetry.org/)

### Setup

```bash
# Install dependencies
poetry install

# Copy env template and fill in values
cp .env.example .env

# Run migrations
poetry run alembic upgrade head

# Start development server
poetry run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

### Docker

```bash
docker build -t neurosaber-backend .
docker run --env-file .env -it -p 8000:8000 neurosaber-backend
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DB_URL` | Yes | — | PostgreSQL connection string |
| `GURU_API_KEY` | Yes | — | Guru API bearer token |
| `GURU_API_URL` | No | `https://digitalmanager.guru/api/v2` | Guru API base URL |
| `GURU_INGRESSO_GROUP_ID` | Yes | — | Guru product group filter |
| `GURU_SYNC_INTERVAL_MINUTES` | No | `60` | Auto-sync interval |
| `ADMIN_API_KEY` | Yes | — | Secret for admin endpoints |
| `FRONTEND_URL` | No | `http://localhost:3000` | Frontend URL (CORS + QR codes) |
| `ENVIRONMENT` | No | `local` | Environment, e.g: local, dev, prod |

## Testing

Tests use [testcontainers](https://testcontainers.com/) to spin up a real PostgreSQL 16 instance — Docker must be running.

```bash
# Run all tests
poetry run pytest

# With coverage
poetry run pytest --cov
```

## Migrations

```bash
# Apply migrations
poetry run alembic upgrade head

# Create a new migration
poetry run alembic revision --autogenerate -m "description"
```
