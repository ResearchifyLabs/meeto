PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: setup lint format test clean build

setup:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements-dev.txt
	$(BIN)/pip install -e .
	$(BIN)/playwright install chromium
	@echo "\n  Setup complete. Activate with:  source $(VENV)/bin/activate\n"

lint:
	$(BIN)/flake8 src/meeto --max-line-length=120 --select=E9,F63,F7,F82
	$(BIN)/black --check --diff src/ tests/

format:
	$(BIN)/autoflake --in-place --remove-all-unused-imports --recursive src/ tests/
	$(BIN)/black src/ tests/

test:
	PYTHONPATH=src $(BIN)/python -m unittest discover -s tests -p "test_*.py" -v

clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

build: clean
	$(BIN)/python -m build
