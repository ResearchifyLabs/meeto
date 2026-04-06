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

## Adding a New Meeting Platform

We'd love help adding support for Zoom, Microsoft Teams, or other platforms. Here's the general approach:

1. Create a new package under `src/meeto/` (e.g. `src/meeto/zoom/`)
2. Implement the core meeting lifecycle:
   - **Joiner** — connect to the meeting and handle lobby/admission
   - **Audio capture** — obtain the meeting's audio stream
   - **End detection** — detect when the meeting ends or the bot is removed
   - **Speaker tracking** — attribute audio segments to participants (if available)
3. Use whatever technology fits the platform best — native SDKs, REST/WebSocket APIs, or browser automation
4. Look at `src/meeto/meet/` as the reference implementation (it uses Playwright, but that's specific to Google Meet)
5. Add tests under `tests/unit/<platform>/`
6. Open a PR — we're happy to iterate together

If you're considering adding a new platform, open an issue first so we can coordinate and share context.

## Pull Requests

1. Branch off `main` using `feature/<name>`, `fix/<name>`, or `docs/<name>`
2. Make your changes
3. Update `CHANGELOG.md` under `[Unreleased]`
4. Run `make format && make lint && make test`
5. Push and open a PR against `main`
