from datetime import datetime, timezone
from typing import Any, Optional

from meeto.state_store.base import MeetingLifecycleStore


class InMemoryMeetingLifecycleStore(MeetingLifecycleStore):
    def __init__(self):
        self._meetings: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _ts_now() -> float:
        return datetime.now(timezone.utc).timestamp()

    def create_meeting(
        self,
        meeting_id: str,
        **fields: Any,
    ) -> dict[str, Any]:
        ts_now = self._ts_now()
        current = dict(self._meetings.get(meeting_id, {}))
        update: dict[str, Any] = {
            "meeting_id": meeting_id,
            "updated_at": ts_now,
        }
        normalized_fields = {k: v for k, v in fields.items() if v is not None}
        update.update(normalized_fields)

        created_at = current.get("created_at", ts_now)
        current.update(update)
        current["created_at"] = created_at

        self._meetings[meeting_id] = current
        return dict(current)

    def update_status(
        self,
        meeting_id: str,
        *,
        status: str,
        ended_at: Optional[float] = None,
        transcription_path: Optional[str] = None,
    ) -> None:
        ts_now = self._ts_now()
        current = self._meetings.get(meeting_id, {"meeting_id": meeting_id, "created_at": ts_now})
        current["status"] = status
        current["updated_at"] = ts_now
        if ended_at is not None:
            current["ended_at"] = ended_at
        if transcription_path is not None:
            current["transcription_path"] = transcription_path
        self._meetings[meeting_id] = current

    def heartbeat(self, meeting_id: str, *, worker_id: Optional[str] = None) -> None:
        ts_now = self._ts_now()
        current = self._meetings.get(meeting_id, {"meeting_id": meeting_id, "created_at": ts_now})
        current["last_heartbeat_at"] = ts_now
        current["updated_at"] = ts_now
        if worker_id is not None:
            current["worker_id"] = worker_id
        self._meetings[meeting_id] = current

    def get_meeting(self, meeting_id: str) -> Optional[dict[str, Any]]:
        current = self._meetings.get(meeting_id)
        if current is None:
            return None
        return dict(current)
