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
```

This creates a virtual environment, installs all dependencies, installs the package in editable mode, and downloads Playwright's Chromium browser.

## Running Tests

```bash
make test
```

## Code Style

Format code before committing:

```bash
make format   # auto-fix with black + autoflake
make lint     # check without modifying
```

The project uses `black` with a 120-character line length.

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

1. Branch off `main`
2. Make your changes
3. Run `make format && make lint && make test`
4. Push and open a PR against `main`
