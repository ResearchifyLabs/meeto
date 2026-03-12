"""Speaker attribution adapters for the Meet worker."""

import abc
import logging
from typing import Optional

from meeto.meet.speaker_tracker import SpeakerTracker
from meeto.stt.base import TranscriptSegment

_logger = logging.getLogger(__name__)


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


class SpeakerCorrelationMap:
    """Builds a mapping from diarization labels to participant names
    using majority-vote correlation between Deepgram labels and DOM
    active-speaker observations."""

    def __init__(self, confidence_threshold: int = 3) -> None:
        self._votes: dict[str, dict[str, int]] = {}
        self._resolved: dict[str, str] = {}
        self._threshold = confidence_threshold

    def record_vote(self, label: str, name: str) -> None:
        if not label or not name:
            return
        votes = self._votes.setdefault(label, {})
        votes[name] = votes.get(name, 0) + 1
        best_name = max(votes, key=votes.get)
        if votes[best_name] >= self._threshold:
            self._resolved[label] = best_name

    def resolve(self, label: str) -> Optional[str]:
        if not label:
            return None
        return self._resolved.get(label)

    @property
    def resolved_map(self) -> dict[str, str]:
        return dict(self._resolved)


def _active_speaker_poller_script() -> str:
    return """
(() => {
    if (window.__activeSpeakerPollerRunning) return;
    window.__activeSpeakerPollerRunning = true;

    const POLL_MS = 200;
    const NAME_REFRESH_MS = 10000;
    const PIN_RE = /^Pin (.+?) to your main screen$/;
    const MORE_RE = /^More options for (.+)$/;

    const nameMap = new Map();

    function refreshNames() {
        document.querySelectorAll('[data-participant-id].oZRSLe').forEach(tile => {
            const pid = tile.getAttribute('data-participant-id');
            if (!pid || nameMap.has(pid)) return;

            const pinBtn = tile.querySelector('button[aria-label^="Pin "]');
            if (pinBtn) {
                const m = (pinBtn.getAttribute('aria-label') || '').match(PIN_RE);
                if (m) { nameMap.set(pid, m[1]); return; }
            }

            const moreBtn = tile.querySelector('button[aria-label^="More options for "]');
            if (moreBtn) {
                const m = (moreBtn.getAttribute('aria-label') || '').match(MORE_RE);
                if (m) { nameMap.set(pid, m[1]); return; }
            }
        });
    }

    function poll() {
        let activeName = null;
        for (const tile of document.querySelectorAll('[data-participant-id].oZRSLe')) {
            if (!tile.querySelector('.kssMZb')) continue;
            const pid = tile.getAttribute('data-participant-id');
            activeName = nameMap.get(pid) || null;
            break;
        }
        try {
            window.onActiveSpeakerPoll({ name: activeName, ts: Date.now() });
        } catch (_) {}
    }

    refreshNames();
    setInterval(refreshNames, NAME_REFRESH_MS);
    setInterval(poll, POLL_MS);
})();
"""


class CorrelationSpeakerAttribution(SpeakerAttributionAdapter):
    """Correlates Deepgram diarization labels with the Google Meet
    active-speaker DOM indicator to resolve real participant names."""

    def __init__(self, page: object) -> None:
        self._page = page
        self._correlation = SpeakerCorrelationMap()
        self._active_speaker: Optional[str] = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        await self._page.expose_binding("onActiveSpeakerPoll", self._handle_poll)
        await self._page.evaluate(_active_speaker_poller_script())
        _logger.info("GMEET: correlation speaker attribution started")

    async def _handle_poll(self, source, payload) -> None:
        if not payload or not isinstance(payload, dict):
            return
        self._active_speaker = payload.get("name")

    def get_speaker_for_segment(self, segment: TranscriptSegment) -> Optional[str]:
        label = segment.speaker
        active = self._active_speaker

        if label and active and segment.is_final:
            self._correlation.record_vote(label, active)

        resolved = self._correlation.resolve(label)
        if resolved:
            return resolved

        return f"Speaker {label}" if label else active

    def stop(self) -> None:
        self._running = False

    @property
    def correlation_map(self) -> SpeakerCorrelationMap:
        return self._correlation


DIARIZATION_REGISTRY: dict[str, type[SpeakerAttributionAdapter]] = {
    "dom": DOMSpeakerAttribution,
    "stt_native": STTDiarizationAttribution,
    "hybrid": HybridAttribution,
    "correlation": CorrelationSpeakerAttribution,
}


def create_speaker_attribution(diarization: str, *, page: object = None) -> SpeakerAttributionAdapter:
    cls = DIARIZATION_REGISTRY.get(diarization)
    if not cls:
        raise ValueError(f"Unknown diarization strategy: {diarization}. Available: {list(DIARIZATION_REGISTRY)}")
    if cls in (DOMSpeakerAttribution, HybridAttribution, CorrelationSpeakerAttribution):
        if page is None:
            raise ValueError(f"Diarization strategy '{diarization}' requires a Playwright page.")
        return cls(page=page)
    return cls()
