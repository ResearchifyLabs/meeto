PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: setup lint format test clean build pre-commit

help:
	@echo "Available commands:"
	@echo "  setup       Setup the development environment"
	@echo "  lint        Run linting checks"
	@echo "  format      Format the code"
	@echo "  test        Run tests"
	@echo "  clean       Clean up temporary files"
	@echo "  build       Build the package"
	@echo "  pre-commit  Install pre-commit hooks"
	@echo "  help        Show this help message"

setup:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements-dev.txt
	$(BIN)/pip install -e .
	$(BIN)/playwright install chromium
	@echo "\n  Setup complete. Activate with:  source $(VENV)/bin/activate\n"

lint:
	$(BIN)/ruff check src/ tests/
	$(BIN)/ruff format --check src/ tests/

format:
	$(BIN)/ruff check --fix src/ tests/
	$(BIN)/ruff format src/ tests/

test:
	PYTHONPATH=src $(BIN)/python -m unittest discover -s tests -p "test_*.py" -v

clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

pre-commit:
	$(BIN)/pip install pre-commit -q
	$(BIN)/pre-commit install

build: clean
	$(BIN)/python -m build
