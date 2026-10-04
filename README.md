# ROC Litigation Verification

An internal decision-support tool for an IP law practice. It extracts company claims from litigation
documents, checks them against official ROC/MCA records, flags inconsistencies with a transparent,
explainable risk score, and keeps a human lawyer in the loop for every judgment.

> This system is an automated verification aid. It does not give legal advice or make a legal
> determination of fraud.

The full design is in [docs/architecture-analysis.md](docs/architecture-analysis.md).

## Status

| Phase | What | State |
|---|---|---|
| 1 | Project setup: FastAPI skeleton, React shell, PostgreSQL, tooling, CI | Done |
| 2 | Database models, migrations, app login | Next |

## What's in the stack (and why)

| Tool | What it does here |
|---|---|
| **FastAPI** | Python web framework for the backend API. Validates requests with type hints and serves interactive docs at `/api/docs`. |
| **Uvicorn** | The server process that runs the FastAPI app. |
| **PostgreSQL** | The database. Stores cases, extracted claims, ROC results, reviews, audit logs, and (later) the job queue. |
| **SQLAlchemy** | Lets Python code talk to PostgreSQL safely (parameterised queries, so no SQL injection). |
| **Docker Desktop** | Runs PostgreSQL in an isolated container, so you don't have to install it on Windows directly. |
| **React + TypeScript** | The browser UI. TypeScript adds types to JavaScript so mistakes show up before runtime. |
| **Vite** | Frontend dev server and bundler. Instant reloads while you edit; also forwards `/api` calls to the backend. |
| **Tailwind CSS** | Utility CSS classes for styling directly in components. |
| **pytest / Vitest** | Test runners for backend and frontend. |
| **Ruff / oxlint** | Linters/formatters that catch bugs and keep code style consistent. |
| **pre-commit** | Runs the linters and a secret-key check automatically before every `git commit`. |

## Repository layout

```
backend/            FastAPI application
  app/
    main.py         app factory, security headers
    api/            routers (all routes under /api/v1)
    config/         settings loaded from .env
    database/       SQLAlchemy engine and health check
    schemas/        request/response models
  tests/            pytest suite
  pyproject.toml    dependencies and tool config
frontend/           React + TypeScript + Tailwind (Vite)
  src/
    api/            typed API client
    components/     UI components
    types/          shared TypeScript types
docs/               architecture and design documents
docker-compose.yml  PostgreSQL for local development
.env.example        template for your local .env (never commit .env)
```

More folders (`services/`, `workers/`, `models/`, `security/`, frontend `features/`) are added in the
phases that need them.

## Prerequisites (Windows 11)

Install these once:

1. **Python 3.12** from [python.org](https://www.python.org/downloads/windows/). Tick "Add python.exe to PATH" in the installer.
2. **Node.js 22 LTS** from [nodejs.org](https://nodejs.org/).
3. **Git** from [git-scm.com](https://git-scm.com/download/win).
4. **Docker Desktop** from [docker.com](https://www.docker.com/products/docker-desktop/). Start it once so the whale icon shows in the tray.

Check them in PowerShell:

```powershell
python --version
node --version
git --version
docker --version
```

## First-time setup

All commands are PowerShell, run from the repository root unless stated otherwise.

```powershell
# 1. Get the code
git clone https://github.com/AbhishekLim17/roc-litigation-verifier.git
cd roc-litigation-verifier

# 2. Create your local settings file
Copy-Item .env.example .env

# 3. Start PostgreSQL (in the background)
docker compose up -d db

# 4. Backend: virtual environment + dependencies
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cd ..

# 5. Frontend dependencies
cd frontend
npm install
cd ..

# 6. Git hooks (optional but recommended)
backend\.venv\Scripts\pre-commit.exe install
```

If `Activate.ps1` is blocked with "running scripts is disabled on this system", run this once and retry:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Running the app

Use two terminals (VS Code: Terminal → Split Terminal).

**Terminal 1: backend**

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

**Terminal 2: frontend**

```powershell
cd frontend
npm run dev
```

Then open:

- App: <http://localhost:5173>. The System status card should show API Online, Database Connected, ROC data provider "Mock data".
- API docs: <http://localhost:8000/api/docs>
- Health check: <http://localhost:8000/api/v1/health>

If Database shows "Unavailable", check that Docker Desktop is running and run `docker compose ps`. The `db` service should show `healthy`.

## Running tests and checks

```powershell
# Backend
cd backend
.\.venv\Scripts\Activate.ps1
pytest              # tests (the database test is skipped if PostgreSQL isn't running)
ruff check .        # lint
ruff format .       # auto-format

# Frontend
cd frontend
npm test            # Vitest
npm run lint        # oxlint
npm run build       # type-check and production build
```

GitHub Actions runs the same checks on every push and pull request (`.github/workflows/ci.yml`).

## Stopping things

```powershell
docker compose down       # stop PostgreSQL (data is kept)
docker compose down -v    # stop and DELETE the database volume
```

## Security ground rules

These apply from Phase 1 onwards:

- `.env`, credentials, MCA session data, cookies, tokens, uploaded documents and generated reports are excluded by `.gitignore`. Never commit them.
- MCA credentials are never stored, logged, or sent to an LLM. A human logs in to MCA directly and completes any CAPTCHA. The app never bypasses CAPTCHA or other MCA access controls.
- PostgreSQL is bound to `127.0.0.1` only.
- Development uses the mock ROC provider. No live MCA access is needed until Phase 15, which follows a review of MCA's terms of use.
