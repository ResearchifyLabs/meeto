"""Participant manifest writer for speaker identity resolution.

Produces a JSON file that maps per-participant stream files to their
real-world identity (name, email, avatar) as scraped from the Google
Meet DOM.  Post-processing pipelines use this manifest together with
voice embeddings to resolve Pyannote's anonymous speaker labels.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from meeto.storage import ArtifactStorageAdapter

_logger = logging.getLogger(__name__)

DEFAULT_MANIFESTS_DIR = "./manifests"


class ManifestWriter:
    """Writes a participant manifest JSON mapping streams to identities."""

    def __init__(
        self,
        meeting_id: str,
        *,
        manifests_dir: Optional[str] = None,
        storage_adapter: Optional[ArtifactStorageAdapter] = None,
    ) -> None:
        self.meeting_id = meeting_id
        self.manifests_dir = manifests_dir or DEFAULT_MANIFESTS_DIR
        self._storage_adapter = storage_adapter
        self._participants: dict[str, dict[str, Any]] = {}
        self._filepath: Optional[str] = None
        self._created_at: Optional[str] = None

    def open(self) -> str:
        Path(self.manifests_dir).mkdir(parents=True, exist_ok=True)
        safe_id = self.meeting_id.replace("/", "_").replace("\\", "_")
        self._filepath = os.path.join(self.manifests_dir, f"{safe_id}_manifest.json")
        self._created_at = datetime.now(timezone.utc).isoformat()
        _logger.info("GMEET: manifest writer opened: %s", self._filepath)
        return self._filepath

    def add_participant(
        self,
        participant_id: str,
        *,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
        avatar_url: Optional[str] = None,
        first_seen_at: Optional[float] = None,
    ) -> None:
        existing = self._participants.get(participant_id, {"participant_id": participant_id})
        if display_name is not None:
            existing["display_name"] = display_name
        if email is not None:
            existing["email"] = email
        if avatar_url is not None:
            existing["avatar_url"] = avatar_url
        if first_seen_at is not None:
            existing.setdefault("first_seen_at", first_seen_at)
            existing["last_seen_at"] = first_seen_at
        self._participants[participant_id] = existing

    def close(self) -> dict:
        result: dict = {"local_path": self._filepath, "remote_path": None}
        if not self._filepath:
            return result

        manifest = {
            "meeting_id": self.meeting_id,
            "created_at": self._created_at,
            "participants": list(self._participants.values()),
        }

        try:
            with open(self._filepath, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            _logger.info(
                "GMEET: manifest written: %s (%d participants)",
                self._filepath,
                len(self._participants),
            )
        except Exception:
            _logger.exception("GMEET: failed to write manifest")

        if self._storage_adapter and self._filepath:
            try:
                remote = self._storage_adapter.upload(self._filepath, content_type="application/json")
                result["remote_path"] = remote
            except Exception:
                _logger.exception("GMEET: failed to upload manifest")

        return result

    @property
    def filepath(self) -> Optional[str]:
        return self._filepath

    @property
    def participants(self) -> dict[str, dict[str, Any]]:
        return dict(self._participants)
