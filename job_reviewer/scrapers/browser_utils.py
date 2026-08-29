"""Utility to locate the available Playwright Chromium binary.

Mirrors permit_scraper's resolver so the two packages behave identically across
environments (local laptop, CI, Claude Code on the web — which pre-installs a
Chromium at /opt/pw-browsers).
"""
from __future__ import annotations

import glob
import os


def find_chromium() -> str | None:
    """Return the path to the first usable Chromium binary, or None for default."""
    candidates: list[str] = []

    # Claude Code on the web / containers that pin PLAYWRIGHT_BROWSERS_PATH
    env_root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    roots = [env_root] if env_root else []
    roots.append(os.path.expanduser("~/.cache/ms-playwright"))

    for root in roots:
        if not root:
            continue
        candidates.extend(
            [
                f"{root}/chromium",  # explicit pin (e.g. /opt/pw-browsers/chromium)
                f"{root}/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
                f"{root}/chromium_headless_shell-*/chrome-headless-shell-linux/chrome-headless-shell",
                f"{root}/chromium-*/chrome-linux64/chrome",
                f"{root}/chromium-*/chrome-linux/chrome",
                f"{root}/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
            ]
        )

    for pattern in candidates:
        if os.path.isfile(pattern):
            return pattern
        matches = glob.glob(pattern)
        if matches:
            return sorted(matches)[-1]
    return None


CHROMIUM_PATH = find_chromium()

# A realistic desktop UA — NEOGOV portals serve a stripped page to obvious bots.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
