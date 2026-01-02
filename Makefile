# =============================================================================
# DOPPELGANGER TRACKER - Makefile
# =============================================================================
# Simplified commands for Docker operations
# =============================================================================

.PHONY: help setup build up down restart logs status clean test init-db analyze collect

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

# Default target
.DEFAULT_GOAL := help

# =============================================================================
# Help
# =============================================================================

help: ## Show this help message
	@echo "$(BLUE)========================================$(NC)"
	@echo "$(BLUE)Doppelganger Tracker - Make Commands$(NC)"
	@echo "$(BLUE)========================================$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Examples:$(NC)"
	@echo "  make setup        # Initial setup"
	@echo "  make up           # Start all services"
	@echo "  make logs         # View logs"
	@echo "  make down         # Stop all services"
	@echo ""

# =============================================================================
# Setup & Configuration
# =============================================================================

setup: ## Run initial setup script
	@echo "$(BLUE)Running setup script...$(NC)"
	@chmod +x setup.sh docker-entrypoint.sh
	@./setup.sh

env: ## Create .env from .env.example
	@if [ ! -f .env ]; then \
		echo "$(GREEN)Creating .env file...$(NC)"; \
		cp .env.example .env; \
		echo "$(YELLOW)⚠ Please edit .env and configure your settings$(NC)"; \
	else \
		echo "$(YELLOW).env already exists$(NC)"; \
	fi

# =============================================================================
# Docker Operations
# =============================================================================

build: ## Build Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	docker compose build --no-cache

build-quick: ## Build Docker images (with cache)
	@echo "$(BLUE)Building Docker images (using cache)...$(NC)"
	docker compose build

up: ## Start all core services
	@echo "$(GREEN)Starting core services...$(NC)"
	docker compose up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(BLUE)Dashboard: http://localhost:8501$(NC)"

up-analysis: ## Start all services including analyzer
	@echo "$(GREEN)Starting all services (with analyzer)...$(NC)"
	docker compose --profile analysis up -d

down: ## Stop all services (keeps data)
	@echo "$(YELLOW)Stopping services...$(NC)"
	docker compose down

down-clean: ## Stop and remove all data (DESTRUCTIVE)
	@echo "$(YELLOW)WARNING: This will delete all data!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose down -v; \
		echo "$(GREEN)✓ All services and data removed$(NC)"; \
	else \
		echo "$(BLUE)Cancelled$(NC)"; \
	fi

restart: ## Restart all services
	@echo "$(BLUE)Restarting services...$(NC)"
	docker compose restart

restart-collector: ## Restart collector service only
	@echo "$(BLUE)Restarting collector...$(NC)"
	docker compose restart collector

restart-dashboard: ## Restart dashboard service only
	@echo "$(BLUE)Restarting dashboard...$(NC)"
	docker compose restart dashboard

# =============================================================================
# Logs & Monitoring
# =============================================================================

logs: ## View logs (all services)
	docker compose logs -f

logs-collector: ## View collector logs
	docker compose logs -f collector

logs-dashboard: ## View dashboard logs
	docker compose logs -f dashboard

logs-analyzer: ## View analyzer logs
	docker compose logs -f analyzer

logs-db: ## View database logs
	docker compose logs -f postgres

status: ## Show service status
	@echo "$(BLUE)Service Status:$(NC)"
	@docker compose ps

stats: ## Show resource usage
	@echo "$(BLUE)Resource Usage:$(NC)"
	@docker stats --no-stream

health: ## Check service health
	@echo "$(BLUE)Health Checks:$(NC)"
	@docker compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Health}}"

# =============================================================================
# Database Operations
# =============================================================================

init-db: ## Initialize database schema
	@echo "$(BLUE)Initializing database...$(NC)"
	docker compose run --rm db-init
	@echo "$(GREEN)✓ Database initialized$(NC)"

db-shell: ## Access PostgreSQL shell
	@echo "$(BLUE)Opening PostgreSQL shell...$(NC)"
	docker compose exec postgres psql -U doppelganger -d doppelganger

db-backup: ## Backup database
	@echo "$(BLUE)Backing up database...$(NC)"
	@mkdir -p backups
	@docker compose exec postgres pg_dump -U doppelganger doppelganger > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)✓ Backup created in backups/$(NC)"

db-restore: ## Restore database from latest backup
	@echo "$(YELLOW)Restoring database from latest backup...$(NC)"
	@LATEST=$$(ls -t backups/backup_*.sql | head -1); \
	if [ -n "$$LATEST" ]; then \
		docker compose exec -T postgres psql -U doppelganger -d doppelganger < $$LATEST; \
		echo "$(GREEN)✓ Database restored from $$LATEST$(NC)"; \
	else \
		echo "$(RED)✗ No backup found$(NC)"; \
	fi

# =============================================================================
# Application Operations
# =============================================================================

collect: ## Run collection once
	@echo "$(BLUE)Running collection...$(NC)"
	docker compose run --rm collector collect --limit 100

analyze: ## Run analysis once
	@echo "$(BLUE)Running analysis...$(NC)"
	docker compose run --rm analyzer analyze

analyze-nlp: ## Run NLP analysis only
	@echo "$(BLUE)Running NLP analysis...$(NC)"
	docker compose run --rm analyzer analyze --nlp-only --limit 500

analyze-network: ## Run network analysis only
	@echo "$(BLUE)Running network analysis...$(NC)"
	docker compose run --rm analyzer analyze --network-only --days 30

# =============================================================================
# Development & Testing
# =============================================================================

shell-collector: ## Open shell in collector container
	@echo "$(BLUE)Opening shell in collector...$(NC)"
	docker compose exec collector bash

shell-dashboard: ## Open shell in dashboard container
	@echo "$(BLUE)Opening shell in dashboard...$(NC)"
	docker compose exec dashboard bash

test: ## Run test suite
	@echo "$(BLUE)Running tests...$(NC)"
	docker compose run --rm collector python main.py test

test-coverage: ## Run tests with coverage
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	docker compose run --rm collector python main.py test --coverage

# =============================================================================
# Maintenance & Cleanup
# =============================================================================

clean: ## Clean Docker resources (images, containers, networks)
	@echo "$(YELLOW)Cleaning Docker resources...$(NC)"
	docker compose down
	docker system prune -f
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

clean-all: ## Deep clean (including volumes - DESTRUCTIVE)
	@echo "$(YELLOW)WARNING: This will delete all Docker data!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose down -v; \
		docker system prune -a -f --volumes; \
		echo "$(GREEN)✓ Deep cleanup complete$(NC)"; \
	else \
		echo "$(BLUE)Cancelled$(NC)"; \
	fi

clean-logs: ## Clean local log files
	@echo "$(BLUE)Cleaning log files...$(NC)"
	@rm -rf logs/*.log
	@echo "$(GREEN)✓ Log files cleaned$(NC)"

# =============================================================================
# Quick Actions
# =============================================================================

start: up ## Alias for 'up'

stop: down ## Alias for 'down'

rebuild: ## Rebuild and restart all services
	@echo "$(BLUE)Rebuilding and restarting...$(NC)"
	docker compose down
	docker compose build --no-cache
	docker compose up -d
	@echo "$(GREEN)✓ Services rebuilt and started$(NC)"

update: ## Pull latest changes and rebuild
	@echo "$(BLUE)Updating application...$(NC)"
	git pull
	docker compose build
	docker compose up -d
	@echo "$(GREEN)✓ Application updated$(NC)"

# =============================================================================
# Monitoring & Inspection
# =============================================================================

ps: ## Show running containers
	docker compose ps

top: ## Show processes in containers
	docker compose top

inspect-collector: ## Inspect collector container
	docker inspect doppelganger-collector | jq '.[0]'

inspect-db: ## Inspect database container
	docker inspect doppelganger-db | jq '.[0]'

volumes: ## List Docker volumes
	@echo "$(BLUE)Docker Volumes:$(NC)"
	@docker volume ls | grep doppelganger

networks: ## List Docker networks
	@echo "$(BLUE)Docker Networks:$(NC)"
	@docker network ls | grep doppelganger

# =============================================================================
# Dashboard
# =============================================================================

dashboard: ## Open dashboard in browser (Linux)
	@echo "$(GREEN)Opening dashboard...$(NC)"
	@xdg-open http://localhost:8501 2>/dev/null || open http://localhost:8501 2>/dev/null || echo "$(YELLOW)Please open http://localhost:8501 manually$(NC)"

# =============================================================================
# Production Deployment
# =============================================================================

prod-deploy: ## Production deployment (with health checks)
	@echo "$(BLUE)Deploying to production...$(NC)"
	@./setup.sh
	docker compose build
	docker compose up -d
	@echo "$(GREEN)Waiting for services to be healthy...$(NC)"
	@sleep 10
	@make health
	@echo "$(GREEN)✓ Production deployment complete$(NC)"

prod-backup: ## Production backup routine
	@echo "$(BLUE)Running production backup...$(NC)"
	@make db-backup
	@echo "$(GREEN)✓ Backup complete$(NC)"

# =============================================================================
# Info & Documentation
# =============================================================================

info: ## Show system information
	@echo "$(BLUE)System Information:$(NC)"
	@echo ""
	@echo "Docker Version:"
	@docker --version
	@echo ""
	@echo "Docker Compose Version:"
	@docker compose version
	@echo ""
	@echo "Running Containers:"
	@docker compose ps --format "table {{.Service}}\t{{.Status}}"
	@echo ""
	@echo "Disk Usage:"
	@docker system df

doc: ## Open Docker documentation
	@echo "$(BLUE)Opening documentation...$(NC)"
	@xdg-open README-DOCKER.md 2>/dev/null || open README-DOCKER.md 2>/dev/null || cat README-DOCKER.md

# =============================================================================
# CI/CD Helpers
# =============================================================================

ci-test: ## Run CI test suite
	docker compose -f docker-compose.yml run --rm collector python main.py test --coverage

ci-build: ## CI build (no cache)
	docker compose build --no-cache --pull

ci-deploy: ## CI deployment
	docker compose up -d --remove-orphans
