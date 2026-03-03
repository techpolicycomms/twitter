.PHONY: help up down logs build seed migrate test lint clean

help: ## Show this help message
	@echo "AuditChain - Algorithm Auditing Platform"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Start all services with Docker Compose
	docker-compose up -d

down: ## Stop all services
	docker-compose down

logs: ## Follow logs from all services
	docker-compose logs -f

build: ## Rebuild all Docker images
	docker-compose build

migrate: ## Run database migrations
	cd packages/api && npx prisma migrate deploy

seed: ## Seed the database with demo data
	cd packages/api && npx ts-node src/seed.ts

test: ## Run all tests
	$(MAKE) test-api
	$(MAKE) test-engine
	$(MAKE) test-contracts

test-api: ## Run API tests
	cd packages/api && npm test

test-engine: ## Run Python audit engine tests
	cd packages/audit-engine && pytest tests/ -v

test-contracts: ## Run smart contract tests
	cd packages/contracts && npx hardhat test

lint: ## Run linters across all packages
	cd packages/api && npm run lint
	cd packages/web && npm run lint
	cd packages/audit-engine && black --check engine/ api.py

deploy-local: ## Deploy smart contracts to local Hardhat network
	cd packages/contracts && npx hardhat run scripts/deploy.ts --network localhost

deploy-sepolia: ## Deploy smart contracts to Sepolia testnet
	cd packages/contracts && npx hardhat run scripts/deploy.ts --network sepolia

clean: ## Remove all build artifacts and node_modules
	rm -rf packages/api/node_modules packages/api/dist
	rm -rf packages/web/node_modules packages/web/.next
	rm -rf packages/contracts/node_modules packages/contracts/artifacts packages/contracts/cache
	find packages/audit-engine -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find packages/audit-engine -name "*.pyc" -delete 2>/dev/null || true
