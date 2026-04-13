"""Scrapes participant metadata from Google Meet DOM.

Extracts display names, email addresses (when visible), and avatar URLs
from participant tiles and the People sidebar panel.  Runs as a periodic
JS poller inside the browser page and reports updates to Python via a
Playwright binding.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

_logger = logging.getLogger(__name__)


@dataclass
class ParticipantInfo:
    participant_id: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    first_seen_at: Optional[float] = None
    last_seen_at: Optional[float] = None


class ParticipantScraper:
    """Scrapes and maintains participant metadata from Google Meet DOM."""

    def __init__(self, page: object) -> None:
        self._page = page
        self._participants: dict[str, ParticipantInfo] = {}
        self._running = False

    async def start(self) -> None:
        self._running = True
        await self._page.expose_binding("onParticipantUpdate", self._handle_update)
        await self._page.evaluate(_participant_scraper_script())
        _logger.info("GMEET: participant scraper started")

    async def _handle_update(self, source, participants) -> None:
        if not participants or not isinstance(participants, list):
            return
        now = time.time()
        for p in participants:
            if not isinstance(p, dict):
                continue
            pid = p.get("participant_id")
            if not pid:
                continue
            existing = self._participants.get(pid)
            if existing:
                if p.get("display_name"):
                    existing.display_name = p["display_name"]
                if p.get("email"):
                    existing.email = p["email"]
                if p.get("avatar_url"):
                    existing.avatar_url = p["avatar_url"]
                existing.last_seen_at = now
            else:
                self._participants[pid] = ParticipantInfo(
                    participant_id=pid,
                    display_name=p.get("display_name"),
                    email=p.get("email"),
                    avatar_url=p.get("avatar_url"),
                    first_seen_at=now,
                    last_seen_at=now,
                )
        _logger.debug("GMEET: participant update: %d participants", len(self._participants))

    def get_participants(self) -> dict[str, ParticipantInfo]:
        return dict(self._participants)

    def stop(self) -> None:
        self._running = False


def _participant_scraper_script() -> str:
    """JS that scrapes participant metadata from tiles and People panel."""
    return """
(() => {
    if (window.__gmeetParticipantScraperRunning) return;
    window.__gmeetParticipantScraperRunning = true;

    const SCRAPE_INTERVAL_MS = 15000;
    const PIN_RE = /^Pin\\s+(.+?)\\s+to your main screen$/i;
    const MORE_RE = /^More options for\\s+(.+)$/i;
    const BOT_NAME = /^(automation|bot|recorder|notetaker|meeting\\s*bot|meeto)/i;
    const UI_TEXT = /^(you|pin|mute|unmute|remove|turn|more|present|share|raise|lower|add|host)/i;

    let peoplePanelOpened = false;

    function scrapeTiles() {
        const participants = [];
        for (const tile of document.querySelectorAll('[data-participant-id]')) {
            const pid = tile.getAttribute('data-participant-id');
            if (!pid) continue;

            let name = null;
            let avatarUrl = null;

            for (const child of tile.querySelectorAll('[aria-label]')) {
                const label = child.getAttribute('aria-label') || '';
                let m = label.match(PIN_RE);
                if (m) { name = m[1].trim(); break; }
                m = label.match(MORE_RE);
                if (m) { name = m[1].trim(); break; }
            }

            if (!name) {
                const walker = document.createTreeWalker(tile, NodeFilter.SHOW_TEXT);
                let node;
                while (node = walker.nextNode()) {
                    const t = (node.textContent || '').trim();
                    if (t.length < 2 || t.length > 60) continue;
                    if (UI_TEXT.test(t) || /^\\(You\\)$/i.test(t)) continue;
                    const parent = node.parentElement;
                    if (parent && parent.closest('button')) continue;
                    name = t;
                    break;
                }
            }

            const img = tile.querySelector('img[src*="googleusercontent.com"]');
            if (img) avatarUrl = img.getAttribute('src');

            if (name && !BOT_NAME.test(name)) {
                participants.push({
                    participant_id: pid,
                    display_name: name,
                    avatar_url: avatarUrl,
                    email: null,
                    source: 'tile',
                });
            }
        }
        return participants;
    }

    function tryOpenPeoplePanel() {
        if (peoplePanelOpened) return;
        for (const btn of document.querySelectorAll('button[aria-label]')) {
            const label = (btn.getAttribute('aria-label') || '').toLowerCase();
            if (label.includes('people') || label.includes('participant')
                || label.includes('show everyone')) {
                btn.click();
                peoplePanelOpened = true;
                return;
            }
        }
    }

    function scrapePeoplePanel() {
        const results = [];
        const panel = document.querySelector(
            '[aria-label*="People" i], [aria-label*="participant" i]'
        );
        if (!panel) return results;

        const entries = panel.querySelectorAll(
            '[data-participant-id], [role="listitem"]'
        );
        for (const entry of entries) {
            const texts = [];
            const walker = document.createTreeWalker(entry, NodeFilter.SHOW_TEXT);
            let node;
            while (node = walker.nextNode()) {
                const t = (node.textContent || '').trim();
                if (t.length > 0) texts.push(t);
            }

            let email = null;
            let name = null;
            for (const t of texts) {
                if (t.includes('@') && t.includes('.')) {
                    email = t;
                } else if (t.length >= 2 && t.length <= 60
                           && !BOT_NAME.test(t) && !UI_TEXT.test(t)) {
                    if (!name) name = t;
                }
            }

            const pid = entry.getAttribute('data-participant-id')
                || (entry.closest('[data-participant-id]')
                    || {}).getAttribute?.('data-participant-id');

            if (name || email) {
                results.push({
                    participant_id: pid,
                    display_name: name,
                    email: email,
                    source: 'people_panel',
                });
            }
        }
        return results;
    }

    function scrapeAll() {
        const tileData = scrapeTiles();
        tryOpenPeoplePanel();
        const panelData = scrapePeoplePanel();

        const merged = new Map();
        for (const p of tileData) {
            merged.set(p.participant_id, { ...p });
        }
        for (const p of panelData) {
            if (p.participant_id && merged.has(p.participant_id)) {
                const existing = merged.get(p.participant_id);
                if (p.email) existing.email = p.email;
                if (p.display_name && !existing.display_name) {
                    existing.display_name = p.display_name;
                }
            } else if (p.display_name) {
                for (const [pid, existing] of merged) {
                    if (existing.display_name === p.display_name) {
                        if (p.email) existing.email = p.email;
                        break;
                    }
                }
            }
        }

        try {
            window.onParticipantUpdate(Array.from(merged.values()));
        } catch (_) {}
    }

    setTimeout(scrapeAll, 3000);
    setInterval(scrapeAll, SCRAPE_INTERVAL_MS);
})();
"""
