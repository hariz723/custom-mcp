.PHONY: help setup build up down restart logs status shell run-stdio test-mcp clean

# Colors for terminal output
YELLOW := \033[1;33m
GREEN  := \033[1;32m
CYAN   := \033[1;36m
RESET  := \033[0m

help: ## Show this help message with available commands
	@echo ""
	@echo "$(CYAN)Custom Playwright MCP Server - Automation & Management$(RESET)"
	@echo ""
	@echo "$(YELLOW)Usage:$(RESET) make [target]"
	@echo ""
	@echo "$(YELLOW)Targets:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(RESET) %s\n", $$1, $$2}'
	@echo ""

setup: ## Setup local environment (.env file and output directories)
	@echo "$(CYAN)Setting up environment...$(RESET)"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(GREEN)Created .env from .env.example$(RESET)"; \
	else \
		echo ".env already exists, skipping copy."; \
	fi
	@mkdir -p output/screenshots output/pdfs
	@echo "$(GREEN)Environment ready! Make sure to set your GEMINI_API_KEY or OPENAI_API_KEY in .env$(RESET)"

build: ## Build the Docker image using pyproject.toml
	@echo "$(CYAN)Building Docker image...$(RESET)"
	docker compose build

up: setup ## Start the MCP server container in background (Streamable HTTP on :8000)
	@echo "$(CYAN)Starting Playwright MCP server...$(RESET)"
	docker compose up -d
	@echo "$(GREEN)Server started! Endpoint: http://localhost:8000/mcp$(RESET)"

down: ## Stop the running MCP server
	@echo "$(CYAN)Stopping Playwright MCP server...$(RESET)"
	docker compose down

restart: ## Restart the MCP server
	@echo "$(CYAN)Restarting Playwright MCP server...$(RESET)"
	docker compose restart

logs: ## Tail container logs in real time
	docker compose logs -f

status: ## View running status and container health
	docker compose ps

shell: ## Open interactive bash shell inside the container
	docker compose exec -it playwright-mcp /bin/bash

run-stdio: ## Run in Stdio transport mode (for CLI or Claude Desktop)
	@echo "$(CYAN)Running Playwright MCP server in stdio mode...$(RESET)"
	docker compose run --rm -i -e MCP_TRANSPORT=stdio playwright-mcp

test-mcp: ## Test if the Streamable HTTP endpoint is reachable
	@echo "$(CYAN)Checking MCP endpoint health at http://localhost:8000/mcp...$(RESET)"
	@curl -s -o /dev/null -w "HTTP Response Code: %{http_code}\n" http://localhost:8000/mcp || echo "Could not connect. Is the server running? Run 'make up' first."

clean: ## Clean up local cache and build artifacts
	@echo "$(CYAN)Cleaning cache and temporary files...$(RESET)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	rm -rf *.egg-info build dist .pytest_cache
	@echo "$(GREEN)Clean complete.$(RESET)"
