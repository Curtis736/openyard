.PHONY: help lint test run compose up down build manifests

help:
	@echo "lint       ruff"
	@echo "test       pytest"
	@echo "run        API locale (sans cluster)"
	@echo "compose    docker compose up --build"
	@echo "up         cluster kind + apply"
	@echo "down       détruit le cluster kind"
	@echo "build      image Docker locale"
	@echo "manifests  kustomize build overlays/kind"

lint:
	ruff check .

test:
	pytest -q

run:
	OPENYARD_CLUSTER=false uvicorn app.main:app --reload --port 8000

compose:
	docker compose up --build

build:
	docker build -t openyard:local .

up:
	./scripts/kind-up.sh

down:
	./scripts/kind-down.sh

manifests:
	kustomize build k8s/overlays/kind
