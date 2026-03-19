# AI Document Intelligence - Backend

FastAPI backend for AI-powered document processing.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd backend

# Create virtual environment
python -m venv venv

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

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your API keys
nano .env
```

Required environment variables:
- `DATABASE_URL`
- `OPENAI_API_KEY`
- `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (for Textract)

### 4. Run Migrations

```bash
# Initialize Alembic (only first time)
alembic revision --autogenerate -m "Initial migration"

# Run migrations
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

## 🏗️ Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Configuration
│   ├── database.py          # Database setup
│   ├── models/              # SQLAlchemy models
│   │   ├── document.py
│   │   ├── ocr_result.py
│   │   ├── ai_result.py
│   │   └── ...
│   ├── schemas/             # Pydantic schemas
│   │   ├── document.py
│   │   └── ...
│   ├── api/                 # API routes
│   │   └── v1/
│   │       ├── documents.py
│   │       └── chat.py
│   ├── services/            # Business logic
│   │   ├── document_service.py
│   │   └── chat_service.py
│   ├── lib/                 # External integrations
│   │   ├── s3_service.py
│   │   ├── ocr_service.py
│   │   └── ai_service.py
│   └── prompts/             # AI prompts
│       ├── classification.py
│       ├── extraction.py
│       └── ...
├── alembic/                 # Database migrations
├── requirements.txt
├── .env.example
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

### Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Deploy
railway up
```

### Docker

```bash
# Build image
docker build -t ai-doc-backend .

# Run container
docker run -p 8000:8000 --env-file .env ai-doc-backend
```

## 📖 API Endpoints

### Documents

- `POST /api/v1/documents/upload` - Upload document
- `POST /api/v1/documents/{id}/process` - Process document
- `GET /api/v1/documents/{id}` - Get document
- `GET /api/v1/documents/{id}/ai-result` - Get AI result
- `GET /api/v1/documents` - List documents
- `DELETE /api/v1/documents/{id}` - Delete document

### Chat

- `POST /api/v1/chat/{document_id}` - Ask question about document

## 🔑 Environment Variables

See `.env.example` for all available configuration options.

## 📝 License

Internal use only.
