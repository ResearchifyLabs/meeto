"""Speaker tracking from Google Meet via DOM active-speaker indicator.

Polls the Google Meet DOM for the `.kssMZb` CSS class that marks the
currently speaking participant tile.  Resolves participant names from
tile aria-labels and text content.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Optional

_logger = logging.getLogger(__name__)


@dataclass
class SpeakerEvent:
    speaker_name: Optional[str]
    timestamp: float
    is_speaking: bool
    detection: Optional[str] = None


@dataclass
class SpeakerTracker:
    """Tracks the active speaker in Google Meet using the DOM
    active-speaker CSS indicator with tile-based name resolution."""

    page: object  # Playwright page
    _current_speaker: Optional[str] = None
    _speaker_history: list[SpeakerEvent] = field(default_factory=list)
    _on_speaker_change: Optional[Callable[[str, bool], None]] = None
    _running: bool = False

    @property
    def current_speaker(self) -> Optional[str]:
        return self._current_speaker

    def get_speaker_at(self, timestamp: float) -> Optional[str]:
        speaker = None
        for event in self._speaker_history:
            if event.timestamp <= timestamp:
                if event.is_speaking:
                    speaker = event.speaker_name
                else:
                    if speaker == event.speaker_name:
                        speaker = None
            else:
                break
        return speaker

    async def start(self, on_speaker_change: Optional[Callable[[str, bool], None]] = None) -> None:
        self._on_speaker_change = on_speaker_change
        self._running = True

        await self.page.expose_binding("onSpeakerChange", self._handle_speaker_change)
        await self.page.expose_binding("onDOMDebug", self._handle_dom_debug)
        await self.page.evaluate(_speaker_tracking_script())
        _logger.info("GMEET: speaker tracking initialized (DOM mode)")

    async def _handle_speaker_change(self, source, payload) -> None:
        if not payload or not isinstance(payload, dict):
            return

        speaker_name = payload.get("speaker")
        is_speaking = payload.get("is_speaking", True)
        detection = payload.get("detection")
        timestamp = time.time()

        event = SpeakerEvent(
            speaker_name=speaker_name,
            timestamp=timestamp,
            is_speaking=is_speaking,
            detection=detection,
        )
        self._speaker_history.append(event)

        if is_speaking:
            self._current_speaker = speaker_name
            _logger.info("GMEET: active speaker: %s (detection=%s)", speaker_name, detection)
        else:
            if self._current_speaker == speaker_name:
                self._current_speaker = None
            _logger.debug("GMEET: speaker stopped: %s", speaker_name)

        if self._on_speaker_change:
            try:
                self._on_speaker_change(speaker_name, is_speaking)
            except Exception:
                _logger.exception("GMEET: speaker change callback failed")

    async def _handle_dom_debug(self, source, payload) -> None:
        if not payload or not isinstance(payload, dict):
            return
        _logger.info("GMEET: DOM debug dump: %s", payload)

    def stop(self) -> None:
        self._running = False


def _speaker_tracking_script() -> str:
    return """
(() => {
    if (window.__gmeetSpeakerTrackerRunning) return;
    window.__gmeetSpeakerTrackerRunning = true;

    const POLL_MS = 200;
    const NAME_REFRESH_MS = 5000;
    const SPEAKER_TIMEOUT_MS = 3000;

    let lastReportedSpeaker = null;
    let lastSpeakerTs = 0;

    // --- Participant name scraping ---

    const BOT_NAME = /^(automation|bot|recorder|notetaker|meeting\\s*bot)/i;
    const UI_TEXT = /^(you|pin|mute|unmute|remove|turn|more|present|share|raise|lower|add|host)/i;
    const UI_TEXT_2 = /^(admit|deny|record|caption|setting|help|feedback|report)/i;
    const UI_TEXT_3 = /^(camera|microphone|background|reframe|reaction)/i;
    function isUIText(s) { return UI_TEXT.test(s) || UI_TEXT_2.test(s) || UI_TEXT_3.test(s); }

    function buildTileNameMap() {
        const map = new Map();
        for (const tile of document.querySelectorAll('[data-participant-id]')) {
            const pid = tile.getAttribute('data-participant-id');
            let name = null;

            // Strategy A: aria-label patterns on child elements
            for (const child of tile.querySelectorAll('[aria-label]')) {
                const label = child.getAttribute('aria-label') || '';
                let m;
                m = label.match(/^Pin\\s+(.+?)\\s+to your main screen$/i);
                if (m) { name = m[1].trim(); break; }
                m = label.match(/^More options for\\s+(.+)$/i);
                if (m) { name = m[1].trim(); break; }
            }

            // Strategy B: text content inside the tile
            if (!name) {
                const walker = document.createTreeWalker(tile, NodeFilter.SHOW_TEXT);
                let node;
                while (node = walker.nextNode()) {
                    const t = (node.textContent || '').trim();
                    if (t.length < 2 || t.length > 60) continue;
                    if (isUIText(t)) continue;
                    if (/^\\(You\\)$/i.test(t)) continue;
                    const parent = node.parentElement;
                    if (parent && parent.closest('button')) continue;
                    name = t;
                    break;
                }
            }

            // Strategy C: aria-label directly on the tile element
            if (!name) {
                const tileLabel = (tile.getAttribute('aria-label') || '').trim();
                if (tileLabel.length > 1 && tileLabel.length < 80 && !isUIText(tileLabel)) {
                    name = tileLabel.split(',')[0].trim();
                }
            }

            if (name) map.set(pid, name);
        }
        return map;
    }

    function getDOMActiveSpeakerName() {
        const tileMap = buildTileNameMap();
        for (const tile of document.querySelectorAll('[data-participant-id]')) {
            if (!tile.querySelector('.kssMZb')) continue;
            const pid = tile.getAttribute('data-participant-id');
            const name = tileMap.get(pid);
            if (name && !BOT_NAME.test(name)) return name;
        }
        return null;
    }

    // --- DOM debug dump ---

    function dumpDOM() {
        const dump = {};
        dump.tile_name_map = Object.fromEntries(buildTileNameMap());

        const names = [];
        for (const [pid, name] of buildTileNameMap()) {
            if (!BOT_NAME.test(name)) names.push(name);
        }
        dump.scraped_names = names;

        dump.tiles = [];
        for (const tile of document.querySelectorAll('[data-participant-id]')) {
            const pid = tile.getAttribute('data-participant-id');
            const texts = [];
            const walker = document.createTreeWalker(tile, NodeFilter.SHOW_TEXT);
            let node;
            while (node = walker.nextNode()) {
                const t = (node.textContent || '').trim();
                if (t.length > 0) texts.push(t);
            }
            const childAria = [];
            for (const c of tile.querySelectorAll('[aria-label]')) {
                childAria.push(c.getAttribute('aria-label'));
            }
            dump.tiles.push({ pid: pid.split('/').pop(), texts, childAria: childAria.slice(0, 10) });
        }

        window.onDOMDebug(dump);
    }

    // --- Main poll loop ---

    function poll() {
        const now = Date.now();
        const name = getDOMActiveSpeakerName();

        if (name) {
            lastSpeakerTs = now;
            if (name !== lastReportedSpeaker) {
                if (lastReportedSpeaker) {
                    window.onSpeakerChange({ speaker: lastReportedSpeaker, is_speaking: false, detection: 'dom' });
                }
                window.onSpeakerChange({ speaker: name, is_speaking: true, detection: 'dom' });
                lastReportedSpeaker = name;
            }
        } else if (lastReportedSpeaker && (now - lastSpeakerTs) > SPEAKER_TIMEOUT_MS) {
            window.onSpeakerChange({ speaker: lastReportedSpeaker, is_speaking: false, detection: 'dom' });
            lastReportedSpeaker = null;
        }
    }

    setInterval(poll, POLL_MS);
    setTimeout(dumpDOM, 5000);
})();
"""
