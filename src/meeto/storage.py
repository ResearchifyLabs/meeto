"""Storage adapters for GMeet worker data (transcripts, audio dumps, screenshots)."""

import abc
import logging
import os
from typing import Optional

_logger = logging.getLogger(__name__)


class ArtifactStorageAdapter(abc.ABC):
    """Interface for uploading local files to remote storage."""

    @abc.abstractmethod
    def upload(self, local_path: str, content_type: str = "application/octet-stream") -> Optional[str]:
        """Upload a local file to remote storage.

        Args:
            local_path: Path to the local file.
            content_type: MIME type of the file.

        Returns:
            Remote URI (e.g. gs://...) on success, None otherwise.
        """


class LocalStorageAdapter(ArtifactStorageAdapter):
    """Local adapter that returns a deterministic absolute path."""

    def upload(self, local_path: str, content_type: str = "application/octet-stream") -> Optional[str]:
        if not os.path.exists(local_path):
            _logger.warning("GMEET: local file not found: %s", local_path)
            return None
        return os.path.abspath(local_path)
