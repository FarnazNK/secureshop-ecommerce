.PHONY: install dev test lint format migrate revision serve clean help

help:
	@echo "Targets:"
	@echo "  install     Install the package"
	@echo "  dev         Install with dev extras"
	@echo "  test        Run pytest"
	@echo "  lint        Ruff check + format check"
	@echo "  format      Ruff format + autofix"
	@echo "  migrate     Apply DB migrations (alembic upgrade head)"
	@echo "  revision M=...  Create new migration (alembic revision --autogenerate)"
	@echo "  serve       Run uvicorn with --reload"
	@echo "  clean       Remove caches and build artifacts"

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest -v

lint:
	ruff check app tests
	ruff format --check app tests

format:
	ruff format app tests
	ruff check --fix app tests

migrate:
	alembic upgrade head

revision:
	@test -n "$(M)" || (echo "Usage: make revision M='message'"; exit 1)
	alembic revision --autogenerate -m "$(M)"

serve:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 3001

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info \
	       coverage.xml .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
