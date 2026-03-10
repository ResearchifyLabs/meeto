"""PCM audio dump writer for GMeet bot."""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from meeto.storage import ArtifactStorageAdapter

_logger = logging.getLogger(__name__)

DEFAULT_AUDIO_DIR = "./audio"


class AudioDumpWriter:
    """Writes PCM audio chunks to a local file, uploads via storage adapter on close."""

    def __init__(
        self,
        meeting_id: str,
        *,
        sample_rate: int = 16000,
        channels: int = 1,
        audio_dir: Optional[str] = None,
        storage_adapter: Optional[ArtifactStorageAdapter] = None,
    ) -> None:
        """Initialize the audio dump writer.

        Args:
            meeting_id: Unique meeting identifier.
            sample_rate: Audio sample rate.
            channels: Number of audio channels.
            audio_dir: Directory to write audio dumps (default: ./.gmeet_audio_dump).
            storage_adapter: Optional storage adapter for remote upload on close.
        """
        self.meeting_id = meeting_id
        self.sample_rate = sample_rate
        self.channels = channels
        self.audio_dir = audio_dir or DEFAULT_AUDIO_DIR
        self._file = None
        self._filepath: Optional[str] = None
        self._filename: Optional[str] = None
        self._created_at: Optional[str] = None
        self._storage_adapter = storage_adapter
        self._remote_path: Optional[str] = None
        self._bytes_written: int = 0

    def open(self) -> str:
        """Open the audio file for writing.

        Returns:
            The path to the created audio file.
        """
        # Create directory if needed
        Path(self.audio_dir).mkdir(parents=True, exist_ok=True)

        # Generate filename with UTC timestamp
        self._created_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_meeting_id = self.meeting_id.replace("/", "_").replace("\\", "_")
        self._filename = f"{safe_meeting_id}_{self._created_at}.pcm"
        self._filepath = os.path.join(self.audio_dir, self._filename)

        # Open file for binary writing
        self._file = open(self._filepath, "wb")  # noqa: SIM115
        self._bytes_written = 0
        _logger.info(
            "GMEET: audio dump file opened: %s (sample_rate=%s, channels=%s)",
            self._filepath,
            self.sample_rate,
            self.channels,
        )
        return self._filepath

    def write_chunk(self, pcm_bytes: bytes) -> None:
        """Write a PCM audio chunk to the file.

        Args:
            pcm_bytes: Raw PCM16 audio bytes.
        """
        if not self._file or not pcm_bytes:
            return
        self._file.write(pcm_bytes)
        self._bytes_written += len(pcm_bytes)

    def close(self) -> dict:
        """Close the audio file and upload to remote storage if configured.

        Returns:
            Dict with 'local_path', 'remote_path', 'bytes_written', and 'duration_seconds'.
        """
        duration_seconds = 0
        if self._bytes_written > 0:
            # PCM16 = 2 bytes per sample
            total_samples = self._bytes_written // 2
            duration_seconds = total_samples / self.sample_rate / self.channels

        result = {
            "local_path": self._filepath,
            "remote_path": None,
            "bytes_written": self._bytes_written,
            "duration_seconds": round(duration_seconds, 2),
        }

        if self._file:
            try:
                self._file.close()
                _logger.info(
                    "GMEET: audio dump file closed: %s (bytes=%s, duration=%.2fs)",
                    self._filepath,
                    self._bytes_written,
                    duration_seconds,
                )
            except Exception:
                _logger.exception("GMEET: failed to close audio dump file")
            self._file = None

        if self._storage_adapter and self._filepath:
            try:
                remote_path = self._storage_adapter.upload(self._filepath, content_type="audio/pcm")
                result["remote_path"] = remote_path
                self._remote_path = remote_path
                if remote_path and not os.path.exists(self._filepath):
                    result["local_path"] = None
            except Exception:
                _logger.exception("GMEET: failed to upload audio dump")

        return result

    @property
    def filepath(self) -> Optional[str]:
        """Get the path to the audio file."""
        return self._filepath

    @property
    def remote_path(self) -> Optional[str]:
        """Get the remote storage path to the audio file (if uploaded)."""
        return self._remote_path

    @property
    def bytes_written(self) -> int:
        """Get the number of bytes written."""
        return self._bytes_written
