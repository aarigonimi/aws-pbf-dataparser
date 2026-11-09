PYTHON ?= python3
IMAGE ?= osm-pbf-batch
TAG ?= local

.PHONY: help install test lint format typecheck terraform-fmt terraform-validate docker-build check clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

install: ## Install runtime and development dependencies
	$(PYTHON) -m pip install -r requirements-dev.txt

test: ## Run unit tests
	$(PYTHON) -m pytest

lint: ## Lint Python application, tests and scripts
	ruff check src tests scripts

format: ## Check Python formatting
	ruff format --check src tests scripts

typecheck: ## Run mypy
	mypy src

terraform-fmt: ## Check Terraform formatting
	terraform -chdir=infrastructure fmt -check -recursive

terraform-validate: ## Initialise (no backend) and validate Terraform
	terraform -chdir=infrastructure init -backend=false -input=false
	terraform -chdir=infrastructure validate

docker-build: ## Build the container image for AWS Batch Fargate
	docker build --platform linux/amd64 -t $(IMAGE):$(TAG) .

check: lint format typecheck test terraform-fmt ## Run local code checks

clean: ## Remove local caches
	rm -rf .pytest_cache .ruff_cache .mypy_cache src/__pycache__ tests/__pycache__
