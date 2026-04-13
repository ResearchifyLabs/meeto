import abc
from typing import Optional


class MeetingLifecycleStore(abc.ABC):
    @abc.abstractmethod
    def update_status(
        self,
        meeting_id: str,
        *,
        status: str,
        ended_at: Optional[float] = None,
        transcription_path: Optional[str] = None,
        speaker_events_path: Optional[str] = None,
        manifest_path: Optional[str] = None,
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def heartbeat(self, meeting_id: str) -> None:
        raise NotImplementedError
