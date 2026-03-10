"""Speaker attribution adapters for the Meet worker."""

import abc
from typing import Optional

from meeto.meet.speaker_tracker import SpeakerTracker
from meeto.stt.base import TranscriptSegment


class SpeakerAttributionAdapter(abc.ABC):
    @abc.abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_speaker_for_segment(self, segment: TranscriptSegment) -> Optional[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def stop(self) -> None: ...


class DOMSpeakerAttribution(SpeakerAttributionAdapter):
    """Attributes speech to the active speaker detected from the Google Meet DOM."""

    def __init__(self, page: object) -> None:
        self._tracker = SpeakerTracker(page=page)

    async def start(self) -> None:
        await self._tracker.start()

    def get_speaker_for_segment(self, segment: TranscriptSegment) -> Optional[str]:
        return self._tracker.current_speaker

    def stop(self) -> None:
        self._tracker.stop()


class STTDiarizationAttribution(SpeakerAttributionAdapter):
    """Uses the STT provider's built-in diarization labels (e.g. Deepgram 'Speaker 0')."""

    async def start(self) -> None:
        pass

    def get_speaker_for_segment(self, segment: TranscriptSegment) -> Optional[str]:
        return segment.speaker

    def stop(self) -> None:
        pass


class HybridAttribution(SpeakerAttributionAdapter):
    """Audio-level speaker detection with DOM name resolution and STT
    diarization as fallback when only a stream ID is available."""

    def __init__(self, page: object) -> None:
        self._dom = DOMSpeakerAttribution(page=page)

    async def start(self) -> None:
        await self._dom.start()

    def get_speaker_for_segment(self, segment: TranscriptSegment) -> Optional[str]:
        tracked_speaker = self._dom.get_speaker_for_segment(segment)
        if tracked_speaker is not None and not tracked_speaker.startswith("stream_"):
            return tracked_speaker
        return segment.speaker or tracked_speaker

    def stop(self) -> None:
        self._dom.stop()


DIARIZATION_REGISTRY: dict[str, type[SpeakerAttributionAdapter]] = {
    "dom": DOMSpeakerAttribution,
    "stt_native": STTDiarizationAttribution,
    "hybrid": HybridAttribution,
}


def create_speaker_attribution(diarization: str, *, page: object = None) -> SpeakerAttributionAdapter:
    cls = DIARIZATION_REGISTRY.get(diarization)
    if not cls:
        raise ValueError(f"Unknown diarization strategy: {diarization}. Available: {list(DIARIZATION_REGISTRY)}")
    if cls in (DOMSpeakerAttribution, HybridAttribution):
        if page is None:
            raise ValueError(f"Diarization strategy '{diarization}' requires a Playwright page.")
        return cls(page=page)
    return cls()
