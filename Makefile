# AI Document Intelligence Demo - Makefile
# Quick commands for Docker operations

.PHONY: help build up down restart logs clean migrate test shell

# Default target
help:
	@echo "🚀 AI Document Intelligence Demo - Docker Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build      - Build Docker images"
	@echo "  up         - Start all services"
	@echo "  down       - Stop all services"
	@echo "  restart    - Restart all services"
	@echo "  logs       - View logs (follow mode)"
	@echo "  logs-be    - View backend logs only"
	@echo "  logs-db    - View database logs only"
	@echo "  clean      - Stop and remove all containers, volumes"
	@echo "  migrate    - Run database migrations"
	@echo "  shell-be   - Open shell in backend container"
	@echo "  shell-db   - Open PostgreSQL shell"
	@echo "  test       - Run backend tests"
	@echo "  ps         - Show running containers"
	@echo ""

# Build Docker images
build:
	@echo "🔨 Building Docker images..."
	docker-compose build

# Start all services
up:
	@echo "🚀 Starting all services..."
	docker-compose up -d
	@echo "✅ Services started!"
	@echo ""
	@echo "📍 Access points:"
	@echo "   - Backend API: http://localhost:8000"
	@echo "   - API Docs: http://localhost:8000/api/docs"
	@echo "   - PostgreSQL: localhost:5432"
	@echo ""
	@echo "📋 Use 'make logs' to view logs"

# Start services in foreground (with logs)
up-logs:
	@echo "🚀 Starting all services (foreground)..."
	docker-compose up

# Stop all services
down:
	@echo "🛑 Stopping all services..."
	docker-compose down

# Restart all services
restart:
	@echo "🔄 Restarting all services..."
	docker-compose restart

# View logs (all services)
logs:
	docker-compose logs -f

# View backend logs only
logs-be:
	docker-compose logs -f backend

# View database logs only
logs-db:
	docker-compose logs -f postgres

# View frontend logs only
logs-fe:
	docker-compose logs -f frontend

# Clean up (remove containers and volumes)
clean:
	@echo "🧹 Cleaning up..."
	docker-compose down -v
	@echo "✅ Cleanup complete!"

# Run database migrations
migrate:
	@echo "🔄 Running database migrations..."
	docker-compose exec backend alembic upgrade head
	@echo "✅ Migrations complete!"

# Create new migration
migrate-create:
	@echo "📝 Creating new migration..."
	@read -p "Enter migration message: " msg; \
	docker-compose exec backend alembic revision --autogenerate -m "$$msg"

# Open shell in backend container
shell-be:
	@echo "🐚 Opening backend shell..."
	docker-compose exec backend /bin/sh

# Open PostgreSQL shell
shell-db:
	@echo "🐚 Opening PostgreSQL shell..."
	docker-compose exec postgres psql -U postgres -d ai_doc_demo

# Run backend tests
test:
	@echo "🧪 Running tests..."
	docker-compose exec backend pytest

# Show running containers
ps:
	docker-compose ps

# Initialize project (first time setup)
init:
	@echo "🎬 Initializing project..."
	@if [ ! -f .env ]; then \
		echo "📝 Creating .env file..."; \
		cp .env.docker.example .env; \
		echo "⚠️  Please edit .env and fill in your API keys!"; \
	else \
		echo "ℹ️  .env file already exists"; \
	fi
	@echo ""
	@echo "🔨 Building images..."
	@make build
	@echo ""
	@echo "🚀 Starting services..."
	@make up
	@echo ""
	@echo "⏳ Waiting for services to be ready..."
	@sleep 10
	@echo ""
	@echo "🔄 Running migrations..."
	@make migrate
	@echo ""
	@echo "✅ Initialization complete!"
	@echo ""
	@echo "📍 Access your app at:"
	@echo "   - API Docs: http://localhost:8000/api/docs"
	@echo ""
	@echo "📋 Next steps:"
	@echo "   1. Edit .env and add your API keys"
	@echo "   2. Run 'make restart' to apply changes"

# Quick development workflow
dev:
	@make build
	@make up-logs

# Full reset (clean + init)
reset:
	@echo "⚠️  This will delete all data. Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@make clean
	@make init
