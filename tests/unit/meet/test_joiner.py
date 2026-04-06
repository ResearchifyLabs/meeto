import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from meeto.meet.joiner import (
    MeetSession,
    _dismiss_consent_popup,
    _dismiss_consent_with_retry,
    _fill_guest_name,
    _flush_pending_uploads,
    _take_and_upload_screenshot,
    _upload_screenshot_bg,
    join_meet,
    wait_for_admission,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_locator(*, visible=False, count=0):
    loc = AsyncMock()
    loc.count = AsyncMock(return_value=count)
    loc.is_visible = AsyncMock(return_value=visible)
    loc.click = AsyncMock()
    loc.fill = AsyncMock()
    loc.wait_for = AsyncMock()
    loc.bounding_box = AsyncMock(return_value=None)
    return loc


def _page_with_consent(*, primary_visible=False, dropdown_visible=False, direct_text_visible=False):
    """Build a mock page that controls which consent-dismiss path fires."""
    page = AsyncMock()

    primary_btn = _make_locator(visible=primary_visible, count=1 if primary_visible else 0)
    dropdown_btn = _make_locator(count=1 if dropdown_visible else 0)
    menu_option = _make_locator(visible=dropdown_visible, count=1 if dropdown_visible else 0)
    direct_btn = _make_locator(visible=direct_text_visible, count=1 if direct_text_visible else 0)

    dialog_inner = MagicMock()

    def dialog_locator(selector):
        if "More" in selector or "options" in selector or "haspopup" in selector:
            m = MagicMock()
            m.first = dropdown_btn
            return m
        m = MagicMock()
        m.first = primary_btn
        return m

    dialog_inner.locator = dialog_locator

    def page_locator(selector):
        if 'div[role="dialog"]' in selector:
            m = MagicMock()
            m.first = dialog_inner
            m.count = AsyncMock(return_value=0)
            return m
        if 'div[role="menu"]' in selector:
            chain = MagicMock()
            chain.locator.return_value.first = menu_option
            return chain
        if "Continue without microphone and camera" in selector:
            m = MagicMock()
            m.first = direct_btn
            return m
        m = MagicMock()
        m.first = _make_locator()
        m.count = AsyncMock(return_value=0)
        return m

    page.locator = page_locator
    page.screenshot = AsyncMock()
    page.wait_for_selector = AsyncMock()
    return page


# ---------------------------------------------------------------------------
# _upload_screenshot_bg
# ---------------------------------------------------------------------------


class TestUploadScreenshotBg(unittest.TestCase):
    def test_noop_when_no_storage(self):
        _upload_screenshot_bg("/tmp/shot.png", None)

    def test_calls_upload(self):
        storage = MagicMock()
        _upload_screenshot_bg("/tmp/shot.png", storage)
        storage.upload.assert_called_once_with("/tmp/shot.png", content_type="image/png")

    def test_swallows_upload_exception(self):
        storage = MagicMock()
        storage.upload.side_effect = RuntimeError("boom")
        _upload_screenshot_bg("/tmp/shot.png", storage)


# ---------------------------------------------------------------------------
# _take_and_upload_screenshot
# ---------------------------------------------------------------------------


class TestTakeAndUploadScreenshot(unittest.TestCase):
    def test_takes_screenshot_without_storage(self):
        page = AsyncMock()
        _run(_take_and_upload_screenshot(page, "/tmp/shot.png", None))
        page.screenshot.assert_awaited_once_with(path="/tmp/shot.png")

    def test_takes_screenshot_with_storage(self):
        page = AsyncMock()
        storage = MagicMock()

        async def _screenshot_and_flush():
            await _take_and_upload_screenshot(page, "/tmp/shot.png", storage)
            await _flush_pending_uploads()

        _run(_screenshot_and_flush())
        page.screenshot.assert_awaited_once_with(path="/tmp/shot.png")


# ---------------------------------------------------------------------------
# _flush_pending_uploads
# ---------------------------------------------------------------------------


class TestFlushPendingUploads(unittest.TestCase):
    def test_noop_when_empty(self):
        _run(_flush_pending_uploads())


# ---------------------------------------------------------------------------
# _dismiss_consent_popup
# ---------------------------------------------------------------------------


class TestDismissConsentPopup(unittest.TestCase):
    def test_returns_true_via_primary_selector(self):
        page = _page_with_consent(primary_visible=True)
        self.assertTrue(_run(_dismiss_consent_popup(page, screenshot_dir=None)))

    def test_returns_true_via_dropdown_menu(self):
        page = _page_with_consent(dropdown_visible=True)
        self.assertTrue(_run(_dismiss_consent_popup(page, screenshot_dir=None)))

    def test_returns_true_via_direct_text(self):
        page = _page_with_consent(direct_text_visible=True)
        self.assertTrue(_run(_dismiss_consent_popup(page, screenshot_dir=None)))

    def test_returns_false_when_nothing_visible(self):
        page = _page_with_consent()
        self.assertFalse(_run(_dismiss_consent_popup(page, screenshot_dir=None)))

    @patch("meeto.meet.joiner._take_and_upload_screenshot", new_callable=AsyncMock)
    def test_takes_screenshot_on_success(self, mock_screenshot):
        page = _page_with_consent(primary_visible=True)
        self.assertTrue(_run(_dismiss_consent_popup(page, screenshot_dir="/tmp/ss")))
        mock_screenshot.assert_awaited_once()
        args = mock_screenshot.call_args
        self.assertIn("02b_after_consent.png", args[0][1])


# ---------------------------------------------------------------------------
# _dismiss_consent_with_retry
# ---------------------------------------------------------------------------


class TestDismissConsentWithRetry(unittest.TestCase):
    @patch("meeto.meet.joiner._dismiss_consent_popup", new_callable=AsyncMock)
    def test_returns_true_on_first_attempt(self, mock_dismiss):
        mock_dismiss.return_value = True
        page = AsyncMock()
        self.assertTrue(_run(_dismiss_consent_with_retry(page, None, max_attempts=3, interval_s=0)))
        self.assertEqual(mock_dismiss.await_count, 1)

    @patch("meeto.meet.joiner._dismiss_consent_popup", new_callable=AsyncMock)
    def test_retries_then_succeeds(self, mock_dismiss):
        mock_dismiss.side_effect = [False, False, True]
        page = AsyncMock()
        self.assertTrue(_run(_dismiss_consent_with_retry(page, None, max_attempts=3, interval_s=0)))
        self.assertEqual(mock_dismiss.await_count, 3)

    @patch("meeto.meet.joiner._dismiss_consent_popup", new_callable=AsyncMock)
    def test_returns_false_after_exhausting_attempts(self, mock_dismiss):
        mock_dismiss.return_value = False
        page = AsyncMock()
        self.assertFalse(_run(_dismiss_consent_with_retry(page, None, max_attempts=2, interval_s=0)))
        self.assertEqual(mock_dismiss.await_count, 2)

    @patch("meeto.meet.joiner._dismiss_consent_popup", new_callable=AsyncMock)
    def test_retries_on_exception(self, mock_dismiss):
        mock_dismiss.side_effect = [RuntimeError("flake"), True]
        page = AsyncMock()
        self.assertTrue(_run(_dismiss_consent_with_retry(page, None, max_attempts=2, interval_s=0)))

    def test_wait_for_dialog_returns_false_on_timeout(self):
        page = AsyncMock()
        page.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
        self.assertFalse(
            _run(_dismiss_consent_with_retry(page, None, max_attempts=1, interval_s=0, wait_for_dialog=True))
        )

    @patch("meeto.meet.joiner._dismiss_consent_popup", new_callable=AsyncMock)
    def test_wait_for_dialog_proceeds_when_found(self, mock_dismiss):
        mock_dismiss.return_value = True
        page = AsyncMock()
        page.wait_for_selector = AsyncMock()
        self.assertTrue(
            _run(_dismiss_consent_with_retry(page, None, max_attempts=1, interval_s=0, wait_for_dialog=True))
        )
        page.wait_for_selector.assert_awaited_once()


# ---------------------------------------------------------------------------
# MeetSession
# ---------------------------------------------------------------------------


class TestMeetSession(unittest.TestCase):
    def test_close_tears_down_all(self):
        ctx = AsyncMock()
        browser = AsyncMock()
        pw = AsyncMock()
        session = MeetSession(playwright=pw, browser=browser, context=ctx, page=AsyncMock())
        _run(session.close())
        ctx.close.assert_awaited_once()
        browser.close.assert_awaited_once()
        pw.stop.assert_awaited_once()


# ---------------------------------------------------------------------------
# wait_for_admission
# ---------------------------------------------------------------------------


class TestWaitForAdmission(unittest.TestCase):
    def _page_for_admission(self, *, waiting_room=False, tile_count=3):
        page = MagicMock()

        def locator(selector):
            loc = AsyncMock()
            if "text=" in selector:
                loc.count = AsyncMock(return_value=1 if waiting_room else 0)
            else:
                loc.count = AsyncMock(return_value=0)
            return loc

        page.locator = locator
        page.evaluate = AsyncMock(return_value=tile_count)
        return page

    def test_returns_true_when_admitted(self):
        page = self._page_for_admission(tile_count=3)
        self.assertTrue(_run(wait_for_admission(page, timeout_s=1, poll_interval_s=0)))

    def test_returns_false_on_timeout(self):
        page = self._page_for_admission(waiting_room=True)
        self.assertFalse(_run(wait_for_admission(page, timeout_s=0.05, poll_interval_s=0.01)))

    def test_returns_false_when_not_enough_tiles(self):
        page = self._page_for_admission(tile_count=1)
        self.assertFalse(_run(wait_for_admission(page, timeout_s=0.05, poll_interval_s=0.01)))

    def test_handles_evaluate_exception(self):
        page = MagicMock()

        def locator(selector):
            loc = AsyncMock()
            loc.count = AsyncMock(return_value=0)
            return loc

        page.locator = locator
        page.evaluate = AsyncMock(side_effect=RuntimeError("detached"))
        self.assertFalse(_run(wait_for_admission(page, timeout_s=0.05, poll_interval_s=0.01)))

    def test_handles_locator_exception(self):
        page = MagicMock()

        def locator(selector):
            loc = AsyncMock()
            loc.count = AsyncMock(side_effect=RuntimeError("detached"))
            return loc

        page.locator = locator
        page.evaluate = AsyncMock(return_value=5)
        self.assertTrue(_run(wait_for_admission(page, timeout_s=1, poll_interval_s=0)))


# ---------------------------------------------------------------------------
# _fill_guest_name
# ---------------------------------------------------------------------------


class TestFillGuestName(unittest.TestCase):
    def test_fills_name_on_first_selector(self):
        input_el = _make_locator()
        page = MagicMock()
        page.locator.return_value.first = input_el
        _run(_fill_guest_name(page, "TestBot", screenshot_dir=None))
        input_el.fill.assert_awaited_once_with("TestBot")

    def test_skips_timeout_and_tries_next_selector(self):
        timeout_el = _make_locator()
        timeout_el.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
        success_el = _make_locator()

        call_count = 0

        def locator_factory(selector):
            nonlocal call_count
            call_count += 1
            m = MagicMock()
            m.first = timeout_el if call_count <= 1 else success_el
            return m

        page = MagicMock()
        page.locator = locator_factory
        _run(_fill_guest_name(page, "TestBot", screenshot_dir=None))
        timeout_el.fill.assert_not_awaited()
        success_el.fill.assert_awaited_once_with("TestBot")

    def test_warns_when_no_input_found(self):
        el = _make_locator()
        el.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
        page = MagicMock()
        page.locator.return_value.first = el
        _run(_fill_guest_name(page, "TestBot", screenshot_dir=None))
        el.fill.assert_not_awaited()

    @patch("meeto.meet.joiner._take_and_upload_screenshot", new_callable=AsyncMock)
    def test_takes_screenshot_after_filling(self, mock_screenshot):
        input_el = _make_locator()
        page = MagicMock()
        page.locator.return_value.first = input_el
        _run(_fill_guest_name(page, "TestBot", screenshot_dir="/tmp/ss"))
        mock_screenshot.assert_awaited_once()


# ---------------------------------------------------------------------------
# join_meet  (patch async_playwright entirely)
# ---------------------------------------------------------------------------


def _mock_playwright_stack(*, join_button_visible=True):
    """Build a mock Playwright -> browser -> context -> page chain."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.screenshot = AsyncMock()

    join_btn = _make_locator(visible=join_button_visible, count=1 if join_button_visible else 0)
    mic_btn = _make_locator()
    cam_btn = _make_locator()

    def page_locator(selector):
        if "Ask to join" in selector or "Join now" in selector:
            m = MagicMock()
            m.first = join_btn
            return m
        if "microphone" in selector or "mic" in selector:
            m = MagicMock()
            m.first = mic_btn
            return m
        if "camera" in selector or "video" in selector:
            m = MagicMock()
            m.first = cam_btn
            return m
        m = MagicMock()
        loc = _make_locator()
        m.first = loc
        m.count = AsyncMock(return_value=0)
        return m

    page.locator = page_locator

    context = AsyncMock()
    context.new_page = AsyncMock(return_value=page)
    context.add_init_script = AsyncMock()

    browser = AsyncMock()
    browser.new_context = AsyncMock(return_value=context)

    pw = AsyncMock()
    pw.chromium.launch = AsyncMock(return_value=browser)

    pw_cm = AsyncMock()
    pw_cm.start = AsyncMock(return_value=pw)

    return pw_cm, pw, browser, context, page


class TestJoinMeet(unittest.TestCase):
    @patch("meeto.meet.joiner._flush_pending_uploads", new_callable=AsyncMock)
    @patch("meeto.meet.joiner._dismiss_consent_with_retry", new_callable=AsyncMock, return_value=False)
    @patch("meeto.meet.joiner._take_and_upload_screenshot", new_callable=AsyncMock)
    @patch("meeto.meet.joiner.async_playwright")
    def test_join_meet_happy_path(self, mock_ap, mock_ss, mock_consent, mock_flush):
        pw_cm, pw, browser, context, page = _mock_playwright_stack()
        mock_ap.return_value = pw_cm

        session = _run(
            join_meet(
                "https://meet.google.com/abc-defg-hij",
                headless=True,
                screenshot_dir=None,
            )
        )
        self.assertIsInstance(session, MeetSession)
        self.assertIs(session.page, page)
        page.goto.assert_awaited_once()

    @patch("meeto.meet.joiner._flush_pending_uploads", new_callable=AsyncMock)
    @patch("meeto.meet.joiner._dismiss_consent_with_retry", new_callable=AsyncMock, return_value=False)
    @patch("meeto.meet.joiner._take_and_upload_screenshot", new_callable=AsyncMock)
    @patch("meeto.meet.joiner.async_playwright")
    def test_join_meet_guest_mode(self, mock_ap, mock_ss, mock_consent, mock_flush):
        pw_cm, pw, browser, context, page = _mock_playwright_stack()
        mock_ap.return_value = pw_cm

        session = _run(
            join_meet(
                "https://meet.google.com/abc-defg-hij",
                bot_name="MeetoBot",
                headless=True,
                screenshot_dir=None,
            )
        )
        self.assertIsInstance(session, MeetSession)
        context.add_init_script.assert_awaited_once()

    @patch("meeto.meet.joiner._flush_pending_uploads", new_callable=AsyncMock)
    @patch("meeto.meet.joiner._dismiss_consent_with_retry", new_callable=AsyncMock, return_value=False)
    @patch("meeto.meet.joiner._take_and_upload_screenshot", new_callable=AsyncMock)
    @patch("meeto.meet.joiner.async_playwright")
    def test_join_meet_with_storage_state(self, mock_ap, mock_ss, mock_consent, mock_flush):
        pw_cm, pw, browser, context, page = _mock_playwright_stack()
        mock_ap.return_value = pw_cm

        session = _run(
            join_meet(
                "https://meet.google.com/abc-defg-hij",
                storage_state_path="/tmp/state.json",
                headless=True,
                screenshot_dir=None,
            )
        )
        self.assertIsInstance(session, MeetSession)
        ctx_kwargs = browser.new_context.call_args
        self.assertEqual(ctx_kwargs[1]["storage_state"], "/tmp/state.json")

    @patch("meeto.meet.joiner._flush_pending_uploads", new_callable=AsyncMock)
    @patch("meeto.meet.joiner._dismiss_consent_with_retry", new_callable=AsyncMock, return_value=False)
    @patch("meeto.meet.joiner._take_and_upload_screenshot", new_callable=AsyncMock)
    @patch("meeto.meet.joiner.async_playwright")
    def test_join_meet_mic_timeout_is_non_fatal(self, mock_ap, mock_ss, mock_consent, mock_flush):
        pw_cm, pw, browser, context, page = _mock_playwright_stack()
        mock_ap.return_value = pw_cm

        mic_btn = _make_locator()
        mic_btn.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
        original_locator = page.locator

        def locator_with_mic_timeout(selector):
            if "microphone" in selector or "mic" in selector:
                m = MagicMock()
                m.first = mic_btn
                return m
            return original_locator(selector)

        page.locator = locator_with_mic_timeout

        session = _run(
            join_meet(
                "https://meet.google.com/abc-defg-hij",
                headless=True,
                screenshot_dir=None,
            )
        )
        self.assertIsInstance(session, MeetSession)

    @patch("meeto.meet.joiner._flush_pending_uploads", new_callable=AsyncMock)
    @patch("meeto.meet.joiner._dismiss_consent_with_retry", new_callable=AsyncMock, return_value=False)
    @patch("meeto.meet.joiner._take_and_upload_screenshot", new_callable=AsyncMock)
    @patch("meeto.meet.joiner.async_playwright")
    def test_join_meet_cleans_up_on_failure(self, mock_ap, mock_ss, mock_consent, mock_flush):
        pw_cm, pw, browser, context, page = _mock_playwright_stack(join_button_visible=False)
        mock_ap.return_value = pw_cm

        join_btn = _make_locator()
        join_btn.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("no join button"))
        join_btn.bounding_box = AsyncMock(return_value=None)
        original_locator = page.locator

        def locator_with_broken_join(selector):
            if "Ask to join" in selector or "Join now" in selector:
                m = MagicMock()
                m.first = join_btn
                return m
            return original_locator(selector)

        page.locator = locator_with_broken_join

        with self.assertRaises(PlaywrightTimeoutError):
            _run(
                join_meet(
                    "https://meet.google.com/abc-defg-hij",
                    headless=True,
                    screenshot_dir=None,
                )
            )
        context.close.assert_awaited()
        browser.close.assert_awaited()
        pw.stop.assert_awaited()

    @patch("meeto.meet.joiner._flush_pending_uploads", new_callable=AsyncMock)
    @patch("meeto.meet.joiner._dismiss_consent_with_retry", new_callable=AsyncMock, return_value=False)
    @patch("meeto.meet.joiner._take_and_upload_screenshot", new_callable=AsyncMock)
    @patch("meeto.meet.joiner.async_playwright")
    def test_join_meet_force_click_on_overlay(self, mock_ap, mock_ss, mock_consent, mock_flush):
        pw_cm, pw, browser, context, page = _mock_playwright_stack()
        mock_ap.return_value = pw_cm

        join_btn = _make_locator()
        call_count = 0

        async def wait_for_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("overlay blocking")

        join_btn.wait_for = AsyncMock(side_effect=wait_for_side_effect)
        join_btn.bounding_box = AsyncMock(return_value={"x": 10, "y": 10, "width": 100, "height": 40})
        join_btn.click = AsyncMock()

        overlay_loc = AsyncMock()
        overlay_loc.count = AsyncMock(return_value=1)

        page.evaluate = AsyncMock(return_value={"className": "uW2Fw-IE5DDf", "tag": "DIV"})

        original_locator = page.locator

        def locator_with_overlay(selector):
            if "Ask to join" in selector or "Join now" in selector:
                m = MagicMock()
                m.first = join_btn
                return m
            if 'div[role="dialog"]' in selector:
                m = MagicMock()
                m.first = _make_locator()
                m.count = AsyncMock(return_value=1)
                return m
            return original_locator(selector)

        page.locator = locator_with_overlay

        session = _run(
            join_meet(
                "https://meet.google.com/abc-defg-hij",
                headless=True,
                screenshot_dir=None,
            )
        )
        self.assertIsInstance(session, MeetSession)
        join_btn.click.assert_awaited()

    @patch("meeto.meet.joiner._flush_pending_uploads", new_callable=AsyncMock)
    @patch("meeto.meet.joiner._dismiss_consent_with_retry", new_callable=AsyncMock, return_value=False)
    @patch("meeto.meet.joiner._take_and_upload_screenshot", new_callable=AsyncMock)
    @patch("meeto.meet.joiner.async_playwright")
    @patch.dict("os.environ", {"DISPLAY": ":99"})
    def test_guest_mode_switches_to_headed_with_display(self, mock_ap, mock_ss, mock_consent, mock_flush):
        pw_cm, pw, browser, context, page = _mock_playwright_stack()
        mock_ap.return_value = pw_cm

        _run(
            join_meet(
                "https://meet.google.com/abc-defg-hij",
                bot_name="MeetoBot",
                headless=True,
                screenshot_dir=None,
            )
        )
        launch_kwargs = pw.chromium.launch.call_args[1]
        self.assertFalse(launch_kwargs["headless"])
