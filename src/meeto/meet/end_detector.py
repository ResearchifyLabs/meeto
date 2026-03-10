"""Detect when a Google Meet session has ended by checking DOM signals."""

import logging

_logger = logging.getLogger(__name__)

_END_SELECTORS = [
    'text="You left the meeting"',
    'text="The call has ended"',
    'text="You\'ve been removed from the meeting"',
    'text="The meeting has ended for everyone"',
    'button:has-text("Rejoin")',
    'button:has-text("Return to home screen")',
    'a:has-text("Rejoin")',
    'a:has-text("Return to home screen")',
]

_LEAVE_BUTTON_SELECTOR = 'button[aria-label*="Leave call"], button[aria-label*="Leave meeting"]'

_PARTICIPANT_COUNT_JS = """
(() => {
    // Primary: participant tiles (current Meet DOM 2026)
    const tiles = document.querySelectorAll('[data-participant-id]');
    if (tiles.length > 0) return tiles.length;

    // Fallback: participant count shown in the toolbar button
    const btn = document.querySelector(
        'button[aria-label*="participant"], button[aria-label*="people"]'
    );
    if (btn) {
        const match = (btn.textContent || '').match(/(\\d+)/);
        if (match) return parseInt(match[1], 10);
    }

    return -1;
})()
"""


async def _get_participant_count(page) -> int:
    try:
        return await page.evaluate(_PARTICIPANT_COUNT_JS)
    except Exception as err:
        _logger.debug("GMEET: participant count evaluate failed err=%s", err)
        return -1


async def check_meeting_ended(page, *, min_participants: int = 2) -> bool:
    for selector in _END_SELECTORS:
        try:
            count = await page.locator(selector).count()
            if count > 0:
                _logger.info("GMEET: meeting-end signal detected: %s", selector)
                return True
        except Exception as err:
            _logger.debug("GMEET: end selector check failed selector=%s err=%s", selector, err)

    try:
        leave_count = await page.locator(_LEAVE_BUTTON_SELECTOR).count()
        if leave_count == 0:
            url = page.url or ""
            if "meet.google.com" not in url:
                _logger.info("GMEET: navigated away from Meet, treating as ended")
                return True
    except Exception as err:
        _logger.debug("GMEET: leave button check failed err=%s", err)

    participant_count = await _get_participant_count(page)
    if 0 <= participant_count < min_participants:
        _logger.info(
            "GMEET: participant count dropped to %d (threshold %d), treating as ended",
            participant_count,
            min_participants,
        )
        return True

    return False
