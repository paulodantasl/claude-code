"""Utility to locate the available Playwright Chromium binary."""
from __future__ import annotations

import glob
import os


def find_chromium() -> str | None:
    """
    Return the path to the first usable Chromium binary in the Playwright cache.

    Playwright 1.58+ switched to 'chromium_headless_shell' but many environments
    only have the older 'chromium' build installed. This function checks both.
    """
    cache = os.path.expanduser("~/.cache/ms-playwright")
    patterns = [
        # Preferred: headless shell (faster, lighter)
        f"{cache}/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
        f"{cache}/chromium_headless_shell-*/chrome-headless-shell-linux/chrome-headless-shell",
        # Fallback: full Chromium
        f"{cache}/chromium-*/chrome-linux64/chrome",
        f"{cache}/chromium-*/chrome-linux/chrome",
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return sorted(matches)[-1]   # newest version
    return None   # let Playwright use its default (will fail if missing)


CHROMIUM_PATH = find_chromium()
