# PRIME Search task runner (docs/09 names these eight targets).
#
# Recipes are single-line and portable between /bin/sh and cmd.exe, because GNU
# Make on Windows runs recipes through cmd.exe when sh is not on PATH: no single
# quotes, no shell conditionals, no multi-line recipes.
#
#   make setup
#   make smoke
#   make test
#   make ask Q="Is a therapeutic CGM covered under Medicare for a type 2 diabetic not on insulin?"
#   make ask Q="..." ARGS="--mode baseline"
#   make bench ARGS="--mode prime --split dev --prompt-set base"
#   make gepa ARGS="--split train"
#   make dev-api
#   make dev-ui

.PHONY: setup smoke test ask bench gepa dev-api dev-ui

setup:
	uv sync --all-groups

smoke:
	uv run prime-search smoke

test:
	uv run pytest tests/ -x -q

ask:
	$(if $(strip $(Q)),,$(error Q is required. Example: make ask Q=Is a therapeutic CGM covered))
	uv run prime-search ask "$(Q)" $(ARGS)

bench:
	uv run python -m eval.run_eval $(ARGS)

gepa:
	uv run python -m eval.gepa.run_gepa $(ARGS)

dev-api:
	uv run uvicorn prime_search.api.main:app --reload --port 8000

dev-ui:
	cd ui && pnpm dev
