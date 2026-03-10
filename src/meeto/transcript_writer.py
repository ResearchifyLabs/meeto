"""JSONL transcript writer for STT segments."""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from meeto.storage import ArtifactStorageAdapter
from meeto.stt.base import TranscriptSegment

_logger = logging.getLogger(__name__)

DEFAULT_TRANSCRIPT_DIR = "./transcripts"


class TranscriptWriter:
    """Writes STT segments to a JSONL transcript file."""

    def __init__(
        self,
        meeting_id: str,
        *,
        sample_rate: int = 16000,
        stt_provider: str = "deepgram",
        transcript_dir: Optional[str] = None,
        storage_adapter: Optional[ArtifactStorageAdapter] = None,
    ) -> None:
        """Initialize the transcript writer.

        Args:
            meeting_id: Unique meeting identifier.
            sample_rate: Audio sample rate used.
            stt_provider: STT provider name (e.g., 'deepgram', 'openai').
            transcript_dir: Directory to write transcripts (default: ./.gmeet_transcripts).
            storage_adapter: Optional storage adapter for remote upload on close.
        """
        self.meeting_id = meeting_id
        self.sample_rate = sample_rate
        self.stt_provider = stt_provider
        self.transcript_dir = transcript_dir or DEFAULT_TRANSCRIPT_DIR
        self._file = None
        self._filepath: Optional[str] = None
        self._created_at: Optional[str] = None
        self._filename: Optional[str] = None
        self._storage_adapter = storage_adapter
        self._remote_path: Optional[str] = None

    def open(self) -> str:
        """Open the transcript file and write metadata header.

        Returns:
            The path to the created transcript file.
        """
        # Create directory if needed
        Path(self.transcript_dir).mkdir(parents=True, exist_ok=True)

        # Generate filename with UTC timestamp
        self._created_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_meeting_id = self.meeting_id.replace("/", "_").replace("\\", "_")
        self._filename = f"{safe_meeting_id}.jsonl"
        self._filepath = os.path.join(self.transcript_dir, self._filename)

        # Open file and write metadata line
        self._file = open(self._filepath, "w", encoding="utf-8")  # noqa: SIM115
        metadata = {
            "type": "metadata",
            "meeting_id": self.meeting_id,
            "sample_rate": self.sample_rate,
            "stt_provider": self.stt_provider,
            "created_at": self._created_at,
        }
        self._write_line(metadata)
        _logger.info("GMEET: transcript file opened: %s", self._filepath)
        return self._filepath

    def write_segment(
        self,
        segment: TranscriptSegment,
        speaker_name: Optional[str] = None,
    ) -> None:
        """Write a transcript segment to the file.

        Args:
            segment: The STT transcript segment.
            speaker_name: Speaker name from DOM tracking (if available).
        """
        if not self._file:
            return

        record = {
            "type": "segment",
            "seq": segment.seq,
            "ts_start": segment.ts_start,
            "ts_end": segment.ts_end,
            "speaker": speaker_name,
            "diarized_speaker": segment.speaker,
            "is_final": segment.is_final,
            "confidence": segment.confidence,
            "lang": segment.lang,
            "text": segment.text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._write_line(record)

    def _write_line(self, data: dict) -> None:
        """Write a JSON line to the file."""
        if self._file:
            self._file.write(json.dumps(data, ensure_ascii=False) + "\n")
            self._file.flush()

    def close(self) -> dict:
        """Close the transcript file and upload to remote storage if configured.

        Returns:
            Dict with 'local_path' and/or 'remote_path' keys.
        """
        result = {"local_path": self._filepath, "remote_path": None}

        if self._file:
            try:
                self._file.close()
                _logger.info("GMEET: transcript file closed: %s", self._filepath)
            except Exception:
                _logger.exception("GMEET: failed to close transcript file")
            self._file = None

        if self._storage_adapter and self._filepath:
            try:
                remote_path = self._storage_adapter.upload(self._filepath, content_type="application/jsonl")
                result["remote_path"] = remote_path
                self._remote_path = remote_path
                if remote_path and not os.path.exists(self._filepath):
                    result["local_path"] = None
            except Exception:
                _logger.exception("GMEET: failed to upload transcript")

        return result

    @property
    def filepath(self) -> Optional[str]:
        """Get the path to the transcript file."""
        return self._filepath

    @property
    def remote_path(self) -> Optional[str]:
        """Get the remote storage path to the transcript file (if uploaded)."""
        return self._remote_path
