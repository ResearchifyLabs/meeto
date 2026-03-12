#!/usr/bin/env python3
"""Run a full meeto meeting worker session from the command line.

Uses the same code path as runtime.run_meeting_worker().

Usage:
  PYTHONPATH=src python scripts/example.py <MEET_URL> [options]

Examples:
  # Minimal (no STT, just audio dump):
  PYTHONPATH=src python scripts/example.py https://meet.google.com/abc-defg-hij

  # With Deepgram STT + correlation speaker attribution:
  PYTHONPATH=src python scripts/example.py https://meet.google.com/abc-defg-hij \
      --stt-provider deepgram \
      --stt-api-key dg-xxxxx

  # Non-headless with storage state:
  PYTHONPATH=src python scripts/example.py https://meet.google.com/abc-defg-hij \
      --no-headless \
      --storage-state storage_state.json
"""

import argparse
import asyncio
import logging
import os
import uuid

from meeto.config.models import AudioConfig, JoinConfig, SttConfig, WorkerConfig
from meeto.runtime import run_meeting_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def parse_args() -> argparse.Namespace:
    stt_api_key = os.getenv("STT_API_KEY")
    p = argparse.ArgumentParser(description="Run a meeto meeting worker session.")
    p.add_argument("meet_url", help="Google Meet URL to join")
    p.add_argument("--meeting-id", default=None, help="Custom meeting ID (default: auto-generated UUID)")
    p.add_argument("--duration", type=int, default=3600, help="Max recording duration in seconds (default: 3600)")
    p.add_argument("--no-headless", action="store_true", help="Show the browser window")
    p.add_argument("--storage-state", default="storage_state.json", help="Path to Playwright storage state JSON")
    p.add_argument("--stt-provider", default=None, help="STT provider (e.g. 'deepgram')")
    p.add_argument("--stt-api-key", default=stt_api_key, help="STT API key")
    p.add_argument("--diarization", default="correlation", help="Diarization strategy (default: correlation)")
    p.add_argument("--no-audio-dump", action="store_true", help="Disable audio file dump")
    p.add_argument("--audio-debug", action="store_true", help="Enable audio debug logging")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    meeting_id = args.meeting_id or uuid.uuid4().hex[:12]

    config = WorkerConfig(
        meeting_id=meeting_id,
        meet_url=args.meet_url,
        duration_seconds=args.duration,
        audio=AudioConfig(
            debug=args.audio_debug,
            dump_enabled=not args.no_audio_dump,
        ),
        stt=SttConfig(
            provider=args.stt_provider,
            api_key=args.stt_api_key,
            diarization=args.diarization,
        ),
        join=JoinConfig(
            headless=not args.no_headless,
            storage_state_path=args.storage_state,
        ),
    )

    logging.getLogger().info("Starting worker meeting_id=%s url=%s", meeting_id, args.meet_url)
    asyncio.run(run_meeting_worker(config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
