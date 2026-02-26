# meeto

Open-source Google Meet bot. Join meetings, capture audio, and transcribe in real time using Playwright and pluggable STT providers.

## Installation

```bash
pip install meeto
playwright install chromium
```

## Quick Start

### 1. Generate a Google login session

The bot needs a browser session to join meetings as a Google account.

```bash
meeto-auth --output storage_state.json
```

This opens a Chromium window. Log in to Google, then press Enter in the terminal.

### 2. Run the bot

```python
import asyncio
from meeto import run_meeting_worker
from meeto.config import WorkerConfig, JoinConfig, SttConfig

config = WorkerConfig(
    meeting_id="my-meeting-001",
    meet_url="https://meet.google.com/abc-defg-hij",
    duration_seconds=3600,
    join=JoinConfig(
        headless=True,
        storage_state_path="storage_state.json",
    ),
    stt=SttConfig(
        provider="deepgram",
        api_key="YOUR_DEEPGRAM_API_KEY",
    ),
)

asyncio.run(run_meeting_worker(config))
```

Audio dumps are saved to `./audio/` and transcripts to `./transcripts/` by default.

## Configuration

### WorkerConfig

| Field | Type | Default | Description |
|---|---|---|---|
| `meeting_id` | `str` | required | Unique identifier for the meeting |
| `meet_url` | `str` | required | Google Meet URL |
| `duration_seconds` | `int` | `3600` | Max recording duration |
| `audio` | `AudioConfig` | defaults | Audio capture settings |
| `stt` | `SttConfig` | defaults | Speech-to-text settings |
| `join` | `JoinConfig` | defaults | Browser join settings |

### Environment Variable Config

For container/job deployments, build config from env vars:

```python
from meeto.config import worker_config_from_env

config = worker_config_from_env()
```

Required env vars: `MEETING_ID`, `MEET_URL`. See `meeto/config/env_config.py` for the full list.

## Custom Storage Adapter

By default, artifacts stay local. To upload to cloud storage (S3, GCS, etc.), implement `ArtifactStorageAdapter`:

```python
from meeto.storage import ArtifactStorageAdapter

class S3StorageAdapter(ArtifactStorageAdapter):
    def upload(self, local_path, content_type="application/octet-stream"):
        # Upload to S3 and return the remote URI
        return f"s3://my-bucket/{local_path}"
```

Pass it to the runtime:

```python
asyncio.run(run_meeting_worker(config, storage_adapter=S3StorageAdapter()))
```

## Custom Meeting State Store

By default, meeting lifecycle state is kept in memory. To persist state (e.g. to a database), implement `MeetingLifecycleStore`:

```python
from meeto.state_store import MeetingLifecycleStore

class PostgresMeetingStore(MeetingLifecycleStore):
    def update_status(self, meeting_id, *, status, ended_at=None, transcription_path=None):
        # Persist to your database
        ...

    def heartbeat(self, meeting_id):
        # Update heartbeat timestamp
        ...
```

Pass it to the runtime:

```python
asyncio.run(run_meeting_worker(config, state_store=PostgresMeetingStore()))
```

## Custom STT Provider

Meeto ships with Deepgram support. To add your own STT provider, implement `STTStreamingAdapter`:

```python
from meeto.stt import STTStreamingAdapter, register_stt

class MySTTAdapter(STTStreamingAdapter):
    async def connect(self): ...
    async def send_audio(self, pcm_bytes): ...
    async def start(self, on_segment): ...
    async def close(self): ...

register_stt("my_provider", MySTTAdapter)
```

Then set `SttConfig(provider="my_provider")`.

## Architecture

```
meeto/
├── runtime.py              # Main entrypoint: run_meeting_worker()
├── pipeline.py             # Wires audio capture, STT, and transcript writing
├── storage.py              # ArtifactStorageAdapter ABC + LocalStorageAdapter
├── audio_writer.py         # PCM audio dump writer
├── transcript_writer.py    # JSONL transcript writer
├── auth/                   # Google login session generator
├── config/                 # Typed config models + env var parser
├── meet/                   # Playwright-based meeting join, end detection, speaker tracking
├── state_store/            # Meeting lifecycle state management
└── stt/                    # STT adapter interface + Deepgram implementation
```

## License

MIT
