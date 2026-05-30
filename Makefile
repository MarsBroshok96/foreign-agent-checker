.PHONY: help install test lint format check run run-deterministic run-agentic run-json run-agentic-json run-deterministic-fuzzy run-agentic-fuzzy run-local run-local-json eval-deterministic eval-agentic eval-agentic-trace eval-all eval-no-llm validate-profiles profile-coverage clean

URL ?= https://www.rambler.ru/example
REGISTRY_PATH ?= data/samples/registries/minjust_export_sample.xlsx

help:
	@echo "Available targets:"
	@echo "  install   Install dependencies"
	@echo "  test      Run tests"
	@echo "  lint      Run ruff checks"
	@echo "  format    Format code with ruff"
	@echo "  check     Run lint and tests"
	@echo "  run       Run CLI"
	@echo "  run-deterministic Run deterministic mode. Usage: make run-deterministic URL=\"https://...\""
	@echo "  run-agentic Run bounded LLM action loop. Usage: make run-agentic URL=\"https://...\""
	@echo "  run-json  Run deterministic mode with JSON output"
	@echo "  run-agentic-json Run agentic mode with JSON output"
	@echo "  run-deterministic-fuzzy Run deterministic mode with person-only fuzzy recall"
	@echo "  run-agentic-fuzzy Run agentic mode with person-only fuzzy recall"
	@echo "  run-local Run CLI with local registry XLSX"
	@echo "  run-local-json Run CLI with local registry XLSX and JSON output"
	@echo "  eval-deterministic Run deterministic eval cases"
	@echo "  eval-agentic Run agentic eval cases; requires local Ollama"
	@echo "  eval-agentic-trace Run agentic eval with compact action trace"
	@echo "  eval-all Run all eval cases; agentic cases may require local Ollama"
	@echo "  eval-no-llm Run eval cases while skipping agentic cases"
	@echo "  validate-profiles Validate example context profiles"
	@echo "  profile-coverage Show registry/profile coverage for local snapshot"
	@echo "  clean     Remove caches"

install:
	poetry install

test:
	poetry run pytest

lint:
	poetry run ruff check .

format:
	poetry run ruff format .
	poetry run ruff check . --fix

check: lint test

run: run-deterministic

run-deterministic:
	poetry run fa-checker "$(URL)" --mode deterministic

run-agentic:
	poetry run fa-checker "$(URL)" --mode agentic

run-json:
	poetry run fa-checker "$(URL)" --mode deterministic --output-format json

run-agentic-json:
	poetry run fa-checker "$(URL)" --mode agentic --output-format json

run-deterministic-fuzzy:
	poetry run fa-checker "$(URL)" --mode deterministic --enable-fuzzy

run-agentic-fuzzy:
	poetry run fa-checker "$(URL)" --mode agentic --enable-fuzzy

run-local:
	poetry run fa-checker "$(URL)" --mode deterministic --registry-path "$(REGISTRY_PATH)"

run-local-json:
	poetry run fa-checker "$(URL)" --mode deterministic --registry-path "$(REGISTRY_PATH)" --output-format json

eval-deterministic:
	poetry run python scripts/run_eval.py tests/eval_cases/basic_eval.json --mode deterministic

eval-agentic:
	poetry run python scripts/run_eval.py tests/eval_cases/basic_eval.json --mode agentic

eval-agentic-trace:
	poetry run python scripts/run_eval.py tests/eval_cases/basic_eval.json --mode agentic --trace

eval-all:
	poetry run python scripts/run_eval.py tests/eval_cases/basic_eval.json --mode all

eval-no-llm:
	poetry run python scripts/run_eval.py tests/eval_cases/basic_eval.json --mode all --skip-agentic

validate-profiles:
	poetry run python scripts/validate_context_profiles.py data/context/context_profiles.json --registry-xlsx data/registry/minjust_registry_latest.xlsx

profile-coverage:
	poetry run python scripts/profile_coverage.py data/registry/minjust_registry_latest.xlsx data/context/context_profiles.json --limit 50

clean:
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
