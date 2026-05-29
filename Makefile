.PHONY: help install test lint format check run run-deterministic run-agentic run-json run-local run-local-json clean

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
	@echo "  run-local Run CLI with local registry XLSX"
	@echo "  run-local-json Run CLI with local registry XLSX and JSON output"
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

run-local:
	poetry run fa-checker "$(URL)" --mode deterministic --registry-path "$(REGISTRY_PATH)"

run-local-json:
	poetry run fa-checker "$(URL)" --mode deterministic --registry-path "$(REGISTRY_PATH)" --output-format json

clean:
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
