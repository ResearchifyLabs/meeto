import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from meeto.meet.end_detector import check_meeting_ended


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_page(selector_counts=None, participant_count=5, url="https://meet.google.com/abc"):
    """Build a mock page.

    selector_counts: dict mapping selector string to count (default 0 for all).
    """
    selector_counts = selector_counts or {}
    page = MagicMock()
    page.url = url

    def make_locator(selector):
        loc = AsyncMock()
        loc.count = AsyncMock(return_value=selector_counts.get(selector, 0))
        return loc

    page.locator = make_locator
    page.evaluate = AsyncMock(return_value=participant_count)
    return page


class TestCheckMeetingEnded(unittest.TestCase):
    def test_returns_false_when_meeting_active(self):
        page = _mock_page(participant_count=4)
        self.assertFalse(_run(check_meeting_ended(page)))

    def test_detects_you_left_the_meeting(self):
        page = _mock_page(selector_counts={'text="You left the meeting"': 1})
        self.assertTrue(_run(check_meeting_ended(page)))

    def test_detects_call_ended(self):
        page = _mock_page(selector_counts={'text="The call has ended"': 1})
        self.assertTrue(_run(check_meeting_ended(page)))

    def test_detects_removed_from_meeting(self):
        page = _mock_page(selector_counts={'text="You\'ve been removed from the meeting"': 1})
        self.assertTrue(_run(check_meeting_ended(page)))

    def test_detects_rejoin_button(self):
        page = _mock_page(selector_counts={'button:has-text("Rejoin")': 1})
        self.assertTrue(_run(check_meeting_ended(page)))

    def test_detects_return_home_button(self):
        page = _mock_page(selector_counts={'button:has-text("Return to home screen")': 1})
        self.assertTrue(_run(check_meeting_ended(page)))

    def test_detects_low_participant_count(self):
        page = _mock_page(participant_count=1)
        self.assertTrue(_run(check_meeting_ended(page)))

    def test_zero_participants_ends(self):
        page = _mock_page(participant_count=0)
        self.assertTrue(_run(check_meeting_ended(page)))

    def test_navigated_away_from_meet(self):
        page = _mock_page(url="https://example.com/something")
        self.assertTrue(_run(check_meeting_ended(page)))

    def test_custom_min_participants(self):
        page = _mock_page(participant_count=2)
        self.assertFalse(_run(check_meeting_ended(page, min_participants=2)))
        self.assertTrue(_run(check_meeting_ended(page, min_participants=3)))

    def test_negative_participant_count_does_not_end(self):
        page = _mock_page(participant_count=-1)
        self.assertFalse(_run(check_meeting_ended(page)))
