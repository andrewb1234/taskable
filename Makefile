# Convenience targets. Most commands assume you've already run `make bootstrap`
# once. See README for what each target does.

SHELL := /usr/bin/env bash
.SHELLFLAGS := -euo pipefail -c
.ONESHELL:

VENV_PY := .venv/bin/python
UVICORN := .venv/bin/uvicorn

.DEFAULT_GOAL := help

help:
	@echo "Taskable make targets:"
	@echo "  bootstrap  - interactive setup (venv, .env, Windsurf MCP config)"
	@echo "  dev        - start API + UI in parallel (Ctrl+C kills both)"
	@echo "  api        - uvicorn reload server only"
	@echo "  web        - vite dev server only"
	@echo "  seed       - populate demo project/subproject/tickets"
	@echo "  test       - pytest (api/tests)"
	@echo "  e2e        - playwright SSE realtime spec"
	@echo "  build-web  - production Vite build"
	@echo "  docker     - docker compose up --build"
	@echo "  clean-db   - remove ~/.taskable/taskable.db (DB reset)"

bootstrap:
	python3 bootstrap.py

api:
	$(UVICORN) api.main:app --reload --host 127.0.0.1 --port 8000

web:
	cd web && npm run dev

# Parallel dev. Kills both children when you Ctrl+C the make.
dev:
	@trap 'kill 0' SIGINT SIGTERM EXIT; \
		$(MAKE) -j2 api web

seed:
	$(VENV_PY) scripts/seed_demo.py

test:
	$(VENV_PY) -m pytest api/tests/ -v

e2e:
	cd web && npm run test:e2e

build-web:
	cd web && npm run build

docker:
	docker compose -f docker/docker-compose.yml up --build

clean-db:
	rm -f ~/.taskable/taskable.db
	@echo "Removed ~/.taskable/taskable.db; uvicorn will recreate on next start."

.PHONY: help bootstrap api web dev seed test e2e build-web docker clean-db
