# Contributing to meeto

## Prerequisites

- Python 3.10+
- `make`

## Setup

```bash
git clone https://github.com/ResearchifyLabs/meeto.git
cd meeto
make setup
source .venv/bin/activate
make pre-commit
```

This creates a virtual environment, installs all dependencies, installs the package in editable mode, downloads Playwright's Chromium browser, and sets up pre-commit hooks.

## Running Tests

```bash
make test
```

## Code Style

The project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting (120-character line length).

```bash
make format   # auto-fix lint issues and format
make lint     # check without modifying
```

Pre-commit hooks run these checks automatically on every commit.

## Adding a New STT Provider

1. Create `src/meeto/stt/your_provider.py`
2. Implement the `STTStreamingAdapter` interface from `meeto.stt.base`
3. Register it in `src/meeto/stt/__init__.py`:
   ```python
   from meeto.stt.your_provider import YourAdapter
   register_stt("your_provider", YourAdapter)
   ```

## Adding a Custom Storage Adapter

Implement `ArtifactStorageAdapter` from `meeto.storage`:

```python
from meeto.storage import ArtifactStorageAdapter

class MyStorageAdapter(ArtifactStorageAdapter):
    def upload(self, local_path, content_type="application/octet-stream"):
        # Upload and return the remote URI
        ...
```

## Pull Requests

1. Branch off `main` using `feature/<name>`, `fix/<name>`, or `docs/<name>`
2. Make your changes
3. Update `CHANGELOG.md` under `[Unreleased]`
4. Run `make format && make lint && make test`
5. Push and open a PR against `main`
