.PHONY: help install test lint format check run clean

help:
	@echo "Available targets:"
	@echo "  install   Install dependencies"
	@echo "  test      Run tests"
	@echo "  lint      Run ruff checks"
	@echo "  format    Format code with ruff"
	@echo "  check     Run lint and tests"
	@echo "  run       Run CLI"
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
	poetry run fa-checker

clean:
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
