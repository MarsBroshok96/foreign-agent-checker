.PHONY: help install test lint format check run run-json run-local run-local-json clean

SAMPLE_URL ?= https://finance.rambler.ru/finansovaya-gramotnost/56512392-skolko-kopeek-v-odnom-ruble-chto-nuzhno-znat-o-perevode-kopeek-v-rubli-i-obratno/
REGISTRY_PATH ?= data/samples/registries/minjust_export_sample.xlsx

help:
	@echo "Available targets:"
	@echo "  install   Install dependencies"
	@echo "  test      Run tests"
	@echo "  lint      Run ruff checks"
	@echo "  format    Format code with ruff"
	@echo "  check     Run lint and tests"
	@echo "  run       Run CLI"
	@echo "  run-json  Run CLI with JSON output"
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

run:
	poetry run fa-checker "$(SAMPLE_URL)"

run-json:
	poetry run fa-checker "$(SAMPLE_URL)" --output-format json

run-local:
	poetry run fa-checker "$(SAMPLE_URL)" --registry-path "$(REGISTRY_PATH)"

run-local-json:
	poetry run fa-checker "$(SAMPLE_URL)" --registry-path "$(REGISTRY_PATH)" --output-format json

clean:
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
