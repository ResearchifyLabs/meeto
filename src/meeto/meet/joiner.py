import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from meeto.storage import ArtifactStorageAdapter, LocalStorageAdapter

_logger = logging.getLogger(__name__)

_background_uploads: list[asyncio.Task] = []


async def flush_background_uploads() -> None:
    """Await all pending screenshot uploads so nothing is lost on exit."""
    if _background_uploads:
        await asyncio.gather(*list(_background_uploads), return_exceptions=True)
        _background_uploads.clear()


def _upload_screenshot_bg(local_path: str, storage: Optional[ArtifactStorageAdapter]) -> None:
    """Synchronous upload helper -- meant to run via asyncio.to_thread."""
    if not storage:
        return
    try:
        storage.upload(local_path, content_type="image/png")
    except Exception:
        _logger.exception("GMEET: background screenshot upload failed for %s", local_path)


async def _take_and_upload_screenshot(
    page,
    local_path: str,
    storage: Optional[ArtifactStorageAdapter],
) -> None:
    """Take a screenshot, save locally, and fire-and-forget upload to remote storage."""
    await page.screenshot(path=local_path)
    if storage:
        task = asyncio.create_task(asyncio.to_thread(_upload_screenshot_bg, local_path, storage))
        _background_uploads.append(task)
        task.add_done_callback(lambda t: _background_uploads.remove(t) if t in _background_uploads else None)


async def _dismiss_consent_popup(
    page,
    screenshot_dir: Optional[str],
    screenshot_storage: Optional[ArtifactStorageAdapter] = None,
) -> bool:
    consent_clicked = False
    consent_dialog = page.locator('div[role="dialog"]').first
    consent_selectors = [
        'button:has-text("Continue without")',
        'a:has-text("Continue without")',
        '[role="link"]:has-text("Continue without")',
        'button:has-text("Continue without microphone")',
        "text=/Continue without/i",
    ]

    for selector in consent_selectors:
        target = consent_dialog.locator(selector).first
        if await target.count() > 0 and await target.is_visible():
            await target.click()
            consent_clicked = True
            _logger.info("GMEET: consent popup dismissed")
            if screenshot_dir:
                await _take_and_upload_screenshot(
                    page,
                    f"{screenshot_dir}/02b_after_consent.png",
                    screenshot_storage,
                )
            break

    if not consent_clicked:
        dropdown_button = consent_dialog.locator(
            'button[aria-label*="More"], button[aria-label*="options"], button[aria-haspopup="menu"]'
        ).first
        if await dropdown_button.count() > 0:
            await dropdown_button.click()
            menu_option = page.locator('div[role="menu"]').locator("text=/Continue without/i").first
            if await menu_option.count() > 0 and await menu_option.is_visible():
                await menu_option.click()
                consent_clicked = True
                _logger.info("GMEET: consent popup dismissed via menu")
                if screenshot_dir:
                    await _take_and_upload_screenshot(
                        page,
                        f"{screenshot_dir}/02b_after_consent.png",
                        screenshot_storage,
                    )

    if not consent_clicked:
        direct_text = page.locator("text=/Continue without microphone and camera/i").first
        if await direct_text.count() > 0 and await direct_text.is_visible():
            await direct_text.click()
            consent_clicked = True
            _logger.info("GMEET: consent popup dismissed via direct text")
            if screenshot_dir:
                await _take_and_upload_screenshot(
                    page,
                    f"{screenshot_dir}/02b_after_consent.png",
                    screenshot_storage,
                )

    return consent_clicked


async def _dismiss_consent_with_retry(
    page,
    screenshot_dir: Optional[str],
    *,
    max_attempts: int = 5,
    interval_s: float = 1.0,
    wait_for_dialog: bool = False,
    screenshot_storage: Optional[ArtifactStorageAdapter] = None,
) -> bool:
    """Try to dismiss the consent popup, retrying up to *max_attempts* times.

    When *wait_for_dialog* is True, first waits up to 5 s for a dialog element
    to appear before entering the retry loop (useful after join click when the
    dialog can lag).
    """
    if wait_for_dialog:
        try:
            await page.wait_for_selector('div[role="dialog"]', timeout=5000)
        except PlaywrightTimeoutError:
            _logger.debug("GMEET: no consent dialog appeared within 5 s, skipping retry loop")
            return False

    for attempt in range(1, max_attempts + 1):
        try:
            if await _dismiss_consent_popup(
                page,
                screenshot_dir,
                screenshot_storage=screenshot_storage,
            ):
                return True
        except Exception:
            _logger.debug("GMEET: consent dismiss attempt %d raised, retrying", attempt)

        if attempt < max_attempts:
            await asyncio.sleep(interval_s)

    _logger.warning("GMEET: consent popup not dismissed after %d attempts", max_attempts)
    return False


@dataclass
class MeetSession:
    playwright: object
    browser: object
    context: object
    page: object

    async def close(self):
        await self.context.close()
        await self.browser.close()
        await self.playwright.stop()


_WAITING_ROOM_TEXTS = [
    "Please wait until a meeting host brings you into the call",
    "Asking to join",
    "Waiting for someone to let you in",
    "Ask to join",
]


async def wait_for_admission(
    page,
    *,
    timeout_s: float = 120.0,
    poll_interval_s: float = 2.0,
) -> bool:
    """Block until the bot is actually admitted into the meeting.

    The waiting room has a self-view tile and even a "Leave call" button,
    so neither of those is a reliable admission signal.  Instead we detect
    admission by confirming that **none** of the known waiting-room texts
    are visible AND at least 2 participant tiles exist (the bot + at least
    one real participant).

    Returns True if admitted, False if timed out.
    """
    import time as _time

    deadline = _time.monotonic() + timeout_s
    _logger.info("GMEET: waiting for host admission (timeout=%.0fs)", timeout_s)

    while _time.monotonic() < deadline:
        in_waiting_room = False
        for text in _WAITING_ROOM_TEXTS:
            try:
                if await page.locator(f'text="{text}"').count() > 0:
                    in_waiting_room = True
                    break
            except Exception as err:
                _logger.debug("GMEET: failed waiting-room text check text=%s err=%s", text, err)

        if in_waiting_room:
            await asyncio.sleep(poll_interval_s)
            continue

        try:
            tile_count = await page.evaluate("document.querySelectorAll('[data-participant-id]').length")
            if tile_count >= 2:
                _logger.info(
                    "GMEET: admitted to meeting (%d participant tiles)",
                    tile_count,
                )
                return True
        except Exception as err:
            _logger.debug("GMEET: failed participant tile count check err=%s", err)

        await asyncio.sleep(poll_interval_s)

    _logger.warning("GMEET: admission timeout after %.0fs", timeout_s)
    return False


_STEALTH_INIT_SCRIPT = """\
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
window.chrome = window.chrome || {};
window.chrome.runtime = window.chrome.runtime || {};
"""

_HEADLESS_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


async def _fill_guest_name(
    page,
    bot_name: str,
    screenshot_dir: Optional[str],
    screenshot_storage: Optional[ArtifactStorageAdapter] = None,
) -> None:
    name_selectors = [
        'input[aria-label="Your name"]',
        'input[type="text"][aria-label*="name" i]',
        'input[type="text"]',
    ]
    for selector in name_selectors:
        input_el = page.locator(selector).first
        try:
            await input_el.wait_for(state="visible", timeout=10000)
        except PlaywrightTimeoutError:
            continue
        await input_el.fill(bot_name)
        _logger.info("GMEET: guest name set to %r via %s", bot_name, selector)
        if screenshot_dir:
            await _take_and_upload_screenshot(
                page,
                f"{screenshot_dir}/01b_after_name.png",
                screenshot_storage,
            )
        return

    _logger.warning("GMEET: could not find guest name input")


async def join_meet(
    meet_url: str,
    *,
    storage_state_path: Optional[str] = None,
    bot_name: Optional[str] = None,
    disable_mic: bool = True,
    disable_camera: bool = True,
    join_timeout_ms: int = 90000,
    headless: bool = True,
    slow_mo_ms: Optional[int] = None,
    screenshot_dir: Optional[str] = "./screenshots",
    storage_adapter: Optional[ArtifactStorageAdapter] = None,
) -> MeetSession:
    screenshot_storage = storage_adapter or LocalStorageAdapter()
    guest_mode = bool(bot_name) and not storage_state_path

    p = await async_playwright().start()
    if guest_mode:
        chrome_args = ["--disable-blink-features=AutomationControlled"]
        if headless:
            chrome_args.append("--window-size=1920,1080")
        browser = await p.chromium.launch(
            channel="chrome",
            headless=headless,
            slow_mo=slow_mo_ms,
            args=chrome_args,
        )
    else:
        browser = await p.chromium.launch(headless=headless, slow_mo=slow_mo_ms)

    if storage_state_path:
        context = await browser.new_context(storage_state=storage_state_path)
    elif guest_mode and headless:
        context = await browser.new_context(
            user_agent=_HEADLESS_USER_AGENT,
            viewport={"width": 1920, "height": 1080},
        )
    else:
        context = await browser.new_context()

    if guest_mode:
        await context.add_init_script(_STEALTH_INIT_SCRIPT)
    page = await context.new_page()
    _logger.info("GMEET: goto %s (guest_mode=%s)", meet_url, guest_mode)
    await page.goto(meet_url, wait_until="domcontentloaded")
    if screenshot_dir:
        Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
        await _take_and_upload_screenshot(
            page,
            f"{screenshot_dir}/01_after_goto.png",
            screenshot_storage,
        )

    if guest_mode:
        await _fill_guest_name(page, bot_name, screenshot_dir, screenshot_storage)

    if disable_mic:
        mic_button = page.locator('button[aria-label*="microphone"]').first
        if await mic_button.count() > 0:
            await mic_button.click()
            _logger.info("GMEET: mic toggled")

    if disable_camera:
        cam_button = page.locator('button[aria-label*="camera"]').first
        if await cam_button.count() > 0:
            await cam_button.click()
            _logger.info("GMEET: camera toggled")

    await _dismiss_consent_with_retry(
        page,
        screenshot_dir,
        screenshot_storage=screenshot_storage,
    )

    join_button = page.locator('button:has-text("Ask to join"), button:has-text("Join now")').first
    joined = False
    try:
        await join_button.wait_for(state="visible", timeout=join_timeout_ms)
        if screenshot_dir:
            await _take_and_upload_screenshot(
                page,
                f"{screenshot_dir}/02_before_join.png",
                screenshot_storage,
            )
        _logger.info("GMEET: clicking join")
        await join_button.click()
        _logger.info("GMEET: join clicked")
        if screenshot_dir:
            await asyncio.sleep(2)
            await _take_and_upload_screenshot(
                page,
                f"{screenshot_dir}/03_after_join.png",
                screenshot_storage,
            )
        await _dismiss_consent_with_retry(
            page,
            screenshot_dir,
            wait_for_dialog=True,
            screenshot_storage=screenshot_storage,
        )
        joined = True
    except Exception:
        bbox = await join_button.bounding_box()
        top_el = None
        overlay_count = await page.locator('div[role="dialog"]').count()
        material_overlay_count = await page.locator("div.uW2Fw-Sx9Kwc").count()
        if bbox:
            top_el = await page.evaluate(
                """(p) => {
                    const el = document.elementFromPoint(p.x, p.y);
                    if (!el) return null;
                    return {
                        tag: el.tagName,
                        id: el.id || null,
                        className: (typeof el.className === 'string' ? el.className : String(el.className)) || null,
                        role: el.getAttribute('role'),
                        ariaLabel: el.getAttribute('aria-label')
                    };
                }""",
                {
                    "x": bbox["x"] + bbox["width"] / 2,
                    "y": bbox["y"] + bbox["height"] / 2,
                },
            )
        try:
            top_class = (top_el or {}).get("className") if isinstance(top_el, dict) else None
            if overlay_count > 0 or material_overlay_count > 0 or top_class == "uW2Fw-IE5DDf":
                await join_button.click(force=True)
                await _dismiss_consent_with_retry(
                    page,
                    screenshot_dir,
                    wait_for_dialog=True,
                    screenshot_storage=screenshot_storage,
                )
                joined = True
        except Exception as err:
            _logger.warning("GMEET: join force-click fallback failed err=%s", err)
        if not joined:
            raise

    return MeetSession(
        playwright=p,
        browser=browser,
        context=context,
        page=page,
    )
