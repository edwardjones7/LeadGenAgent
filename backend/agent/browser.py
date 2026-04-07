"""Playwright browser service — persistent thread with its own event loop.

Playwright on Windows requires a ProactorEventLoop for subprocess spawning.
We run all Playwright operations in a single dedicated thread that has its
own event loop, and communicate via a queue.
"""

import asyncio
import base64
import logging
import platform
import queue
import threading
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

# Single persistent thread for all Playwright operations
_task_queue: queue.Queue = queue.Queue()
_thread: threading.Thread | None = None
_started = False

# Playwright state (only accessed from the worker thread)
_pw = None
_browser = None
_context = None
_page = None


def _worker():
    """Long-running worker thread that processes Playwright tasks."""
    global _pw, _browser, _context, _page

    # Windows needs its own event loop for subprocess support
    if platform.system() == "Windows":
        asyncio.set_event_loop(asyncio.new_event_loop())

    while True:
        fn, args, result_holder, event = _task_queue.get()
        if fn is None:  # shutdown sentinel
            break
        try:
            result_holder["result"] = fn(*args)
        except Exception as e:
            result_holder["result"] = {"error": str(e) or type(e).__name__}
        event.set()


def _ensure_thread():
    global _thread, _started
    if _started:
        return
    _thread = threading.Thread(target=_worker, daemon=True)
    _thread.start()
    _started = True


def _call_sync(fn, *args) -> dict:
    """Submit a function to the Playwright thread and wait for the result."""
    _ensure_thread()
    result_holder = {}
    event = threading.Event()
    _task_queue.put((fn, args, result_holder, event))
    event.wait(timeout=30)
    return result_holder.get("result", {"error": "Timed out"})


async def _call(fn, *args) -> dict:
    """Async wrapper — runs the sync call in a thread executor to not block the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _call_sync, fn, *args)


# --- Sync functions (run inside the Playwright worker thread) ---

def _ensure_browser():
    global _pw, _browser, _context, _page
    if _page and not _page.is_closed():
        return _page
    if not _pw:
        _pw = sync_playwright().start()
    if not _browser or not _browser.is_connected():
        _browser = _pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
    if not _context:
        _context = _browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
    _page = _context.new_page()
    return _page


def _navigate_sync(url):
    page = _ensure_browser()
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    return {"success": True, "url": page.url, "title": page.title()}


def _screenshot_sync():
    page = _ensure_browser()
    buf = page.screenshot(type="png", full_page=False)
    b64 = base64.b64encode(buf).decode("ascii")
    return {
        "success": True, "url": page.url, "title": page.title(),
        "screenshot_base64": b64, "message": "Screenshot captured.",
    }


def _click_sync(selector):
    page = _ensure_browser()
    page.click(selector, timeout=5000)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=3000)
    except Exception:
        pass
    return {"success": True, "url": page.url, "title": page.title(), "message": f"Clicked '{selector}'."}


def _type_sync(selector, text):
    page = _ensure_browser()
    page.fill(selector, text, timeout=5000)
    return {"success": True, "message": f"Typed into '{selector}'"}


def _get_text_sync(selector=None):
    page = _ensure_browser()
    if selector:
        text = page.locator(selector).first.inner_text(timeout=5000)
    else:
        text = page.inner_text("body", timeout=5000)
    if len(text) > 8000:
        text = text[:8000] + "\n... (truncated)"
    return {"success": True, "url": page.url, "text": text}


def _get_links_sync():
    page = _ensure_browser()
    links = page.evaluate("""
        () => {
            const anchors = document.querySelectorAll('a[href]');
            return Array.from(anchors).slice(0, 50).map(a => ({
                text: a.innerText.trim().substring(0, 100),
                href: a.href,
            })).filter(l => l.text && l.href);
        }
    """)
    return {"success": True, "url": page.url, "links": links, "count": len(links)}


def _close_sync():
    global _pw, _browser, _context, _page
    try:
        if _page and not _page.is_closed():
            _page.close()
        if _context:
            _context.close()
        if _browser:
            _browser.close()
        if _pw:
            _pw.stop()
    except Exception:
        pass
    _pw = None
    _browser = None
    _context = None
    _page = None
    return {"success": True, "message": "Browser closed."}


# --- Async public API ---

async def navigate(url: str) -> dict:
    return await _call(_navigate_sync, url)

async def screenshot() -> dict:
    return await _call(_screenshot_sync)

async def click(selector: str) -> dict:
    return await _call(_click_sync, selector)

async def type_text(selector: str, text: str) -> dict:
    return await _call(_type_sync, selector, text)

async def get_text(selector: str | None = None) -> dict:
    return await _call(_get_text_sync, selector)

async def get_links() -> dict:
    return await _call(_get_links_sync)

async def close_browser() -> dict:
    return await _call(_close_sync)
