"""
Headless-browser HTML rendering via Playwright.

Many procurement portals (OpenGov, Bonfire/Euna, DemandStar, ProcureWare) are
JavaScript single-page apps: a plain HTTP GET returns an near-empty shell with
no bid data. This module loads the page in headless Chromium, waits for the
content to render, and returns the fully-rendered HTML so the extractor can read
the actual solicitations.

No login is required — these are the public, browsable portal pages.

Setup:
    pip install playwright
    playwright install chromium
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def render_html(
    url: str,
    wait_selector: str | None = None,
    wait_until: str = "networkidle",
    timeout_ms: int = 45000,
    settle_ms: int = 2500,
    user_agent: str | None = None,
) -> str | None:
    """
    Load `url` in headless Chromium and return the rendered HTML.

    Returns None if Playwright is not installed or rendering fails, so callers
    can fall back to a plain HTTP fetch.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error(
            "playwright not installed — run `pip install playwright && "
            "playwright install chromium` to read JS portals"
        )
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()
            page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms)
                except Exception:
                    logger.debug("wait_selector %r not found on %s", wait_selector, url)
            else:
                # Give late XHR-driven content time to populate.
                page.wait_for_timeout(settle_ms)
            html = page.content()
            browser.close()
            return html
    except Exception as exc:
        logger.error("Browser render failed for %s: %s", url, exc)
        return None
