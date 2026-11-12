PYTHON ?= python3
IMAGE ?= osm-pbf-batch
TAG ?= local
REGION ?= monaco
YMD ?= 20261108
GEOFABRIK_AREA ?= europe
INCLUDE_WAY_GEOMETRY ?= true
COMMIT_SHA ?= $(shell git rev-parse HEAD 2>/dev/null || echo local)

.PHONY: help install deploy build run logs verify destroy test lint format typecheck terraform-fmt terraform-validate docker-build check clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

install: ## Install runtime and development dependencies
	$(PYTHON) -m pip install -r requirements-dev.txt

deploy: ## Initialise Terraform and apply the stack (visible plan + confirmation)
	terraform -chdir=infra init
	terraform -chdir=infra apply -var image_tag=$(COMMIT_SHA)

build: ## Build and push linux/amd64 image to ECR, tagged with the current commit
	bash scripts/docker_build_push.sh

run: ## Download the dated extract and upload it (REGION, YMD, GEOFABRIK_AREA)
	REGION="$(REGION)" YMD="$(YMD)" GEOFABRIK_AREA="$(GEOFABRIK_AREA)" \
	INCLUDE_WAY_GEOMETRY="$(INCLUDE_WAY_GEOMETRY)" \
	bash scripts/run_extract.sh

logs: ## Follow the Batch CloudWatch log group (SINCE=1h)
	bash scripts/logs.sh

verify: ## List the partition output and manifest (REGION, YMD)
	REGION_NAME="$(REGION)" YMD="$(YMD)" bash scripts/validate_output.sh

destroy: ## Destroy the stack (visible plan + confirmation)
	terraform -chdir=infra destroy

test: ## Run unit tests
	$(PYTHON) -m pytest

lint: ## Lint Python application, tests and scripts
	ruff check src tests scripts

format: ## Check Python formatting
	ruff format --check src tests scripts

typecheck: ## Run mypy
	mypy src

terraform-fmt: ## Check Terraform formatting
	terraform -chdir=infra fmt -check -recursive

terraform-validate: ## Initialise (no backend) and validate Terraform
	terraform -chdir=infra init -backend=false -input=false
	terraform -chdir=infra validate

docker-build: ## Build the container image for AWS Batch Fargate
	docker build --platform linux/amd64 -t $(IMAGE):$(TAG) .

check: lint format typecheck test terraform-fmt ## Run local code checks

clean: ## Remove local caches
	rm -rf .pytest_cache .ruff_cache .mypy_cache src/__pycache__ tests/__pycache__
