"""Boundary parser: reads environment variables into typed config objects."""

import json
import os

from meeto.config.models import AudioConfig, JoinConfig, SttConfig, WorkerConfig


def worker_config_from_env() -> WorkerConfig:
    stt_config_raw = json.loads(os.environ.get("STT_CONFIG", "{}"))

    return WorkerConfig(
        meeting_id=os.environ["MEETING_ID"],
        meet_url=os.environ["MEET_URL"],
        duration_seconds=int(os.environ.get("DURATION_SECONDS", "3600")),
        audio=AudioConfig(
            sample_rate=int(os.environ.get("AUDIO_SAMPLE_RATE", "16000")),
            chunk_ms=int(os.environ.get("AUDIO_CHUNK_MS", "20")),
            debug=os.environ.get("AUDIO_DEBUG", "false").lower() == "true",
            dump_enabled=os.environ.get("AUDIO_DUMP_ENABLED", "true").lower() == "true",
        ),
        stt=SttConfig(
            provider=os.environ.get("STT_PROVIDER") or None,
            api_key=os.environ.get("DEEPGRAM_API_KEY") or None,
            diarization=os.environ.get("DIARIZATION", "dom"),
            extra=stt_config_raw,
            connect_retries=int(os.environ.get("GMEET_STT_CONNECT_RETRIES", "4")),
            connect_initial_delay_s=float(os.environ.get("GMEET_STT_CONNECT_INITIAL_DELAY_S", "2")),
            connect_max_delay_s=float(os.environ.get("GMEET_STT_CONNECT_MAX_DELAY_S", "15")),
        ),
        join=JoinConfig(
            headless=os.environ.get("HEADLESS", "true").lower() == "true",
            storage_state_path=os.environ.get("MEET_STORAGE_STATE_PATH") or None,
        ),
    )
