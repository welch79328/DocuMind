# AI Document Intelligence - Backend

FastAPI backend for AI-powered document processing.

## 🚀 Quick Start

### 1. Install Dependencies

Python 3.11 is required (the Docker image uses `python:3.11-slim`).

```bash
cd backend

# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
# macOS/Linux
source venv/bin/activate
# Windows
venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 2. Setup Database

```bash
# Install PostgreSQL (if not already installed)
# macOS
brew install postgresql@14
brew services start postgresql@14

# Ubuntu
sudo apt-get install postgresql-14

# Create database
createdb ai_doc_demo
```

### 3. Configure Environment

Settings are read from `backend/.env` when the server runs from `backend/`
(`backend/app/config.py`, `env_file = ".env"`).

```bash
# Copy the example env file from the repo root
cp ../.env.example .env

# Edit .env with your API keys
nano .env
```

Environment variables:
- `DATABASE_URL` (default `postgresql://postgres:postgres@localhost:5432/ai_doc_demo`)
- `OPENAI_API_KEY` — all LLM calls go to OpenAI by default
- `BEDROCK_API_KEY` — only when `LLM_PROVIDER_BY_DOCUMENT_TYPE` routes a document type to `bedrock`
- `STORAGE_TYPE` defaults to `local`; S3 keys are only needed with `STORAGE_TYPE=s3`

All keys and their defaults are in `app/config.py`; the deployment-relevant ones are explained in `docs/DEPLOYMENT.md` §8.

### 4. Run Migrations

```bash
# Migration scripts are already in alembic/versions/
alembic upgrade head
```

### 5. Start Server

```bash
# Development mode (with auto-reload)
uvicorn app.main:app --reload --port 8000

# Or using Python directly
python -m app.main
```

Server will start at: http://localhost:8000

## 📚 API Documentation

Once the server is running, visit:

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

Endpoints, fields and error codes for integrators: `docs/api/INTEGRATION.md`.

## 🏗️ Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app entry point, router registration
│   ├── config.py            # Configuration (pydantic-settings)
│   ├── database.py          # Database setup
│   ├── api/v1/              # API routes (analyze, review, samples, evaluation, classify, ...)
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic (analyze_service.py, ...)
│   ├── lib/
│   │   ├── multi_type_ocr/  # Per-document-type processors (ProcessorFactory)
│   │   ├── ocr_enhanced/    # OCR pipeline (preprocess, engines, post-processing)
│   │   ├── llm_service/     # LLM providers and per-document-type routing
│   │   └── ...
│   └── prompts/             # AI prompts
├── alembic/                 # Database migrations
├── tests/                   # pytest
├── requirements.txt
└── README.md
```

## 🔧 Development

### Run Tests

```bash
pytest
```

### Create New Migration

```bash
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

### Code Formatting

```bash
# Install black (optional)
pip install black

# Format code
black app/
```

## 🚢 Deployment

Deployed with the repo-root `docker-compose.yml` (frontend, backend, postgres, nginx).
See `docs/DEPLOYMENT.md`.

## 📖 API Endpoints

Routers registered in `app/main.py`:

- `POST /api/v1/analyze`, `POST /api/v1/analyze/batch`, `GET /api/v1/usage` — document analysis (main integration endpoint)
- `POST /api/v1/classify` — document type suggestion
- `/api/v1/review/*` — human review queue
- `/api/v1/samples/*` — correction samples
- `/api/v1/evaluation/*` — evaluation and baseline
- `POST /api/v1/ocr/test` — OCR test page backend (hidden from API docs)
- `/api/v1/documents/*`, `/api/v1/chat/*` — legacy document and chat endpoints (hidden from API docs)

## 📝 License

Internal use only.
