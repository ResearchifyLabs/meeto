"""JSONL writer for speaker change events detected from the meeting DOM."""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from meeto.storage import ArtifactStorageAdapter

_logger = logging.getLogger(__name__)

DEFAULT_SPEAKER_EVENTS_DIR = "./speaker_events"


class SpeakerEventWriter:
    """Writes speaker change events to a JSONL file."""

    def __init__(
        self,
        meeting_id: str,
        *,
        speaker_events_dir: Optional[str] = None,
        storage_adapter: Optional[ArtifactStorageAdapter] = None,
    ) -> None:
        self.meeting_id = meeting_id
        self.speaker_events_dir = speaker_events_dir or DEFAULT_SPEAKER_EVENTS_DIR
        self._file = None
        self._filepath: Optional[str] = None
        self._created_at: Optional[str] = None
        self._filename: Optional[str] = None
        self._storage_adapter = storage_adapter
        self._remote_path: Optional[str] = None

    def open(self) -> str:
        Path(self.speaker_events_dir).mkdir(parents=True, exist_ok=True)

        self._created_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_meeting_id = self.meeting_id.replace("/", "_").replace("\\", "_")
        self._filename = f"{safe_meeting_id}_speakers.jsonl"
        self._filepath = os.path.join(self.speaker_events_dir, self._filename)

        self._file = open(self._filepath, "w", encoding="utf-8")  # noqa: SIM115
        metadata = {
            "type": "metadata",
            "meeting_id": self.meeting_id,
            "created_at": self._created_at,
        }
        self._write_line(metadata)
        _logger.info("GMEET: speaker event file opened: %s", self._filepath)
        return self._filepath

    def write_event(
        self,
        speaker_name: Optional[str],
        timestamp: float,
        is_speaking: bool,
        *,
        stream_id: Optional[str] = None,
        detection: Optional[str] = None,
    ) -> None:
        if not self._file:
            return

        record = {
            "type": "speaker_event",
            "speaker": speaker_name,
            "timestamp": timestamp,
            "is_speaking": is_speaking,
            "stream_id": stream_id,
            "detection": detection,
            "wall_time": datetime.now(timezone.utc).isoformat(),
        }
        self._write_line(record)

    def _write_line(self, data: dict) -> None:
        if self._file:
            self._file.write(json.dumps(data, ensure_ascii=False) + "\n")
            self._file.flush()

    def close(self) -> dict:
        result = {"local_path": self._filepath, "remote_path": None}

        if self._file:
            try:
                self._file.close()
                _logger.info("GMEET: speaker event file closed: %s", self._filepath)
            except Exception:
                _logger.exception("GMEET: failed to close speaker event file")
            self._file = None

        if self._storage_adapter and self._filepath:
            try:
                remote_path = self._storage_adapter.upload(self._filepath, content_type="application/jsonl")
                result["remote_path"] = remote_path
                self._remote_path = remote_path
                if remote_path and not os.path.exists(self._filepath):
                    result["local_path"] = None
            except Exception:
                _logger.exception("GMEET: failed to upload speaker events")

        return result

    @property
    def filepath(self) -> Optional[str]:
        return self._filepath

    @property
    def remote_path(self) -> Optional[str]:
        return self._remote_path
