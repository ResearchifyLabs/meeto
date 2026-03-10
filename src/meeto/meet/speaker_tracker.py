"""Speaker tracking from Google Meet via per-stream audio level analysis.

Uses the Web Audio API to create per-participant AnalyserNodes, detecting
who is actually producing audio rather than relying on DOM visual indicators
which break during screen sharing.  DOM is still used as a secondary signal
for resolving participant names.
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
    stream_id: Optional[str] = None
    detection: Optional[str] = None


@dataclass
class SpeakerTracker:
    """Tracks the active speaker in Google Meet using per-stream audio
    level analysis with DOM-based name resolution."""

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
        _logger.info("GMEET: speaker tracking initialized (audio-level mode)")

    async def _handle_speaker_change(self, source, payload) -> None:
        if not payload or not isinstance(payload, dict):
            return

        speaker_name = payload.get("speaker")
        is_speaking = payload.get("is_speaking", True)
        stream_id = payload.get("stream_id")
        detection = payload.get("detection")
        timestamp = time.time()

        event = SpeakerEvent(
            speaker_name=speaker_name,
            timestamp=timestamp,
            is_speaking=is_speaking,
            stream_id=stream_id,
            detection=detection,
        )
        self._speaker_history.append(event)

        if is_speaking:
            self._current_speaker = speaker_name
            _logger.info(
                "GMEET: active speaker: %s (detection=%s, stream=%s)",
                speaker_name,
                detection,
                stream_id,
            )
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

    const SILENCE_RMS = 0.005;
    const DEBOUNCE_MS = 300;
    const SPEAKER_TIMEOUT_MS = 3000;
    const SUSTAIN_MS = 2000;
    const ANALYSIS_INTERVAL_MS = 100;
    const SCAN_INTERVAL_MS = 2000;
    const NAME_SCRAPE_INTERVAL_MS = 5000;
    const SCREEN_SHARE_CHECK_TTL_MS = 2000;

    let lastReportedSpeaker = null;
    let lastReportedTime = 0;
    let lastAudioActivityTs = 0;
    let streamCounter = 0;

    const streamData = new Map();
    let participantNames = [];
    let nameMapBuilt = false;

    const analysisCtx = new (window.AudioContext || window.webkitAudioContext)();
    function ensureCtx() {
        if (analysisCtx.state !== 'running') analysisCtx.resume().catch(() => {});
    }
    ensureCtx();
    setInterval(ensureCtx, 3000);

    // --- Per-stream audio analysis ---

    function attachAnalyser(audioEl) {
        if (streamData.has(audioEl)) return;
        const stream = audioEl.srcObject;
        if (!stream) return;
        const tracks = stream.getAudioTracks();
        if (!tracks.length || tracks[0].readyState === 'ended') return;
        try {
            const source = analysisCtx.createMediaStreamSource(stream);
            const analyser = analysisCtx.createAnalyser();
            analyser.fftSize = 2048;
            analyser.smoothingTimeConstant = 0.5;
            source.connect(analyser);
            streamCounter++;
            streamData.set(audioEl, {
                analyser,
                source,
                mappedName: null,
                lastActiveTs: 0,
                streamId: 'stream_' + streamCounter,
            });
        } catch (_) {}
    }

    function scanAudioElements() {
        document.querySelectorAll('audio').forEach(attachAnalyser);
        for (const [el, data] of streamData) {
            if (!document.contains(el) || !el.srcObject) {
                try { data.source.disconnect(); } catch (_) {}
                streamData.delete(el);
            }
        }
    }

    function getRMS(analyser) {
        const buf = new Float32Array(analyser.fftSize);
        analyser.getFloatTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
        return Math.sqrt(sum / buf.length);
    }

    // --- Screen-share detection (cached) ---

    let _ssActive = false;
    let _ssCheckedAt = 0;

    function isScreenShareActive() {
        const now = Date.now();
        if (now - _ssCheckedAt < SCREEN_SHARE_CHECK_TTL_MS) return _ssActive;
        _ssCheckedAt = now;
        _ssActive = !!(
            document.querySelector('[data-is-presenting="true"]') ||
            document.querySelector('[aria-label*="presenting"]') ||
            document.querySelector('[aria-label*="presentation"]') ||
            document.querySelector('button[aria-label*="Stop presenting"]') ||
            document.querySelector('[data-call-type="presentation"]')
        );
        return _ssActive;
    }

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

            // Strategy A: aria-label patterns on child elements (hover buttons)
            for (const child of tile.querySelectorAll('[aria-label]')) {
                const label = child.getAttribute('aria-label') || '';
                let m;
                m = label.match(/^Pin\\s+(.+?)\\s+to your main screen$/i);
                if (m) { name = m[1].trim(); break; }
                m = label.match(/^More options for\\s+(.+)$/i);
                if (m) { name = m[1].trim(); break; }
            }

            // Strategy B: text content inside the tile (name label overlay)
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

    function scrapeParticipantNames() {
        const tileMap = buildTileNameMap();
        const names = [];
        for (const [pid, name] of tileMap) {
            if (!BOT_NAME.test(name)) names.push(name);
        }

        // Fallback: global aria-label patterns (visible when hovering)
        if (names.length === 0) {
            for (const el of document.querySelectorAll('[aria-label]')) {
                const label = el.getAttribute('aria-label') || '';
                let m;
                m = label.match(/^Pin\\s+(.+?)\\s+to your main screen$/i);
                if (m && m[1] && !BOT_NAME.test(m[1])) { names.push(m[1].trim()); continue; }
                m = label.match(/^More options for\\s+(.+)$/i);
                if (m && m[1] && !BOT_NAME.test(m[1])) { names.push(m[1].trim()); continue; }
            }
        }

        return [...new Set(names)];
    }

    function tryBuildNameMap() {
        const tileMap = buildTileNameMap();
        const humanNames = [];
        for (const [pid, name] of tileMap) {
            if (!BOT_NAME.test(name)) humanNames.push(name);
        }

        if (humanNames.length === 0) return;

        const unmapped = Array.from(streamData.values()).filter(d => !d.mappedName);
        if (unmapped.length === 0) return;

        // Identify the silent (bot) stream by checking which streams have never
        // had audio activity, so we only assign names to human streams.
        const active = unmapped.filter(d => d.lastActiveTs > 0)
            .sort((a, b) => b.lastActiveTs - a.lastActiveTs);
        const silent = unmapped.filter(d => d.lastActiveTs === 0);

        if (active.length === 1 && humanNames.length >= 1) {
            active[0].mappedName = humanNames[0];
            nameMapBuilt = true;
        } else if (active.length === humanNames.length) {
            for (let i = 0; i < active.length; i++) {
                active[i].mappedName = humanNames[i];
            }
            nameMapBuilt = true;
        } else if (active.length > 0 && humanNames.length > 0) {
            for (let i = 0; i < active.length && i < humanNames.length; i++) {
                active[i].mappedName = humanNames[i];
            }
            nameMapBuilt = true;
        }
    }

    // --- DOM debug dump (runs once after init) ---

    function dumpDOM() {
        const dump = {};
        dump.audio_count = document.querySelectorAll('audio').length;
        dump.stream_count = streamData.size;

        dump.tile_name_map = Object.fromEntries(buildTileNameMap());
        dump.scraped_names = scrapeParticipantNames();

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

        dump.audio_streams = [];
        for (const [audioEl, data] of streamData) {
            dump.audio_streams.push({
                streamId: data.streamId,
                mappedName: data.mappedName,
                lastActive: data.lastActiveTs > 0,
            });
        }

        window.onDOMDebug(dump);
    }

    // --- Main analysis loop ---

    function analyzeAndReport() {
        const now = Date.now();
        let loudestEl = null;
        let loudestRMS = SILENCE_RMS;

        for (const [el, data] of streamData) {
            const rms = getRMS(data.analyser);
            if (rms > SILENCE_RMS) data.lastActiveTs = now;
            if (rms > loudestRMS) {
                loudestRMS = rms;
                loudestEl = el;
            }
        }

        if (loudestEl) {
            lastAudioActivityTs = now;
        }

        if (!loudestEl) {
            const silenceDuration = now - lastAudioActivityTs;
            if (silenceDuration < SUSTAIN_MS) return;
            if (lastReportedSpeaker && (now - lastReportedTime) > SPEAKER_TIMEOUT_MS) {
                window.onSpeakerChange({ speaker: lastReportedSpeaker, is_speaking: false });
                lastReportedSpeaker = null;
                lastReportedTime = now;
            }
            return;
        }

        const active = streamData.get(loudestEl);
        const speakerName = active.mappedName || active.streamId;
        const detection = active.mappedName ? 'audio+name' : 'audio_only';

        if (speakerName !== lastReportedSpeaker && (now - lastReportedTime) > DEBOUNCE_MS) {
            if (lastReportedSpeaker) {
                window.onSpeakerChange({ speaker: lastReportedSpeaker, is_speaking: false });
            }
            window.onSpeakerChange({
                speaker: speakerName,
                is_speaking: true,
                stream_id: active.streamId,
                detection: detection,
            });
            lastReportedSpeaker = speakerName;
            lastReportedTime = now;
        }
    }

    scanAudioElements();
    setInterval(scanAudioElements, SCAN_INTERVAL_MS);
    setInterval(analyzeAndReport, ANALYSIS_INTERVAL_MS);

    setTimeout(() => { tryBuildNameMap(); dumpDOM(); }, 5000);
    setInterval(tryBuildNameMap, NAME_SCRAPE_INTERVAL_MS);

    setTimeout(analyzeAndReport, 1000);
})();
"""
