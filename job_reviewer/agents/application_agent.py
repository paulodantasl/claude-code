"""
Optional browser pre-fill assist (Claude + Playwright).

This is the "browser later" layer. For a job you've reviewed in the queue, it:

  1. Opens a REAL (non-headless by default) Chromium window.
  2. Logs into your governmentjobs.com account using credentials YOU supply via
     env vars (GOVJOBS_USERNAME / GOVJOBS_PASSWORD) — they are never stored,
     logged, or transmitted anywhere except to governmentjobs.com itself.
  3. Navigates to the posting and starts the application.
  4. Pre-fills free-text fields from your tailored packet / profile.
  5. STOPS at the final review screen, takes a screenshot, and hands control
     to you. It NEVER clicks the final submit button.

═══════════════════════════════════════════════════════════════════════════════
 SAFETY CONTRACT
   • No automatic submission. The submit step is yours, every time.
   • Defaults to headed mode so you watch every action.
   • Honors a hard allowlist of fields it will type into.
   • If it hits a CAPTCHA, MFA, or anything ambiguous, it pauses for you.
   • Respect governmentjobs.com's Terms of Service. This is a personal
     assistant for your own single application, not a bulk auto-applier.
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..profile_loader import CandidateProfile
from ..scrapers.browser_utils import CHROMIUM_PATH, DEFAULT_USER_AGENT
from ..tailor import ApplicationPacket

logger = logging.getLogger(__name__)

SIGN_IN_URL = "https://www.governmentjobs.com/employees/sign_in"


@dataclass
class PrefillResult:
    ok: bool
    stopped_at: str                 # "review_screen" | "captcha" | "login_failed" | "error"
    fields_filled: int = 0
    screenshot_path: str | None = None
    message: str = ""


class ApplicationAgent:
    """Drive a real browser to pre-fill (never submit) a NEOGOV application."""

    def __init__(
        self,
        profile: CandidateProfile,
        headless: bool = False,
        screenshot_dir: Path | None = None,
    ):
        self.profile = profile
        self.headless = headless
        self.screenshot_dir = Path(screenshot_dir or "review_screenshots")
        self.username = os.environ.get("GOVJOBS_USERNAME")
        self.password = os.environ.get("GOVJOBS_PASSWORD")

    def prefill(self, apply_url: str, packet: ApplicationPacket | None = None) -> PrefillResult:
        if not self.username or not self.password:
            return PrefillResult(
                ok=False,
                stopped_at="login_failed",
                message=(
                    "Set GOVJOBS_USERNAME and GOVJOBS_PASSWORD in your environment "
                    "to use the browser pre-fill assist. They are used only to log "
                    "into governmentjobs.com and are never stored."
                ),
            )
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return PrefillResult(
                ok=False, stopped_at="error",
                message="pip install playwright && playwright install chromium",
            )

        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        launch_kwargs: dict[str, Any] = {"headless": self.headless}
        if CHROMIUM_PATH:
            launch_kwargs["executable_path"] = CHROMIUM_PATH

        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                user_agent=DEFAULT_USER_AGENT,
                viewport={"width": 1366, "height": 900},
            )
            page = context.new_page()
            try:
                if not self._login(page):
                    shot = self._shot(page, "login_failed")
                    return PrefillResult(
                        ok=False, stopped_at="login_failed",
                        screenshot_path=shot,
                        message="Login did not reach a signed-in state. Check credentials/MFA.",
                    )

                page.goto(apply_url, wait_until="domcontentloaded", timeout=30_000)
                self._start_application(page)

                if self._has_captcha(page):
                    shot = self._shot(page, "captcha")
                    return PrefillResult(
                        ok=False, stopped_at="captcha", screenshot_path=shot,
                        message="A CAPTCHA/MFA appeared. Finish it manually in the open window.",
                    )

                filled = self._fill_known_fields(page, packet)
                shot = self._shot(page, "review_screen")
                return PrefillResult(
                    ok=True, stopped_at="review_screen", fields_filled=filled,
                    screenshot_path=shot,
                    message=(
                        f"Pre-filled {filled} field(s). STOPPED before submit. "
                        "Review the open browser window, then submit yourself."
                    ),
                )
            except Exception as exc:
                logger.exception("Pre-fill agent error")
                shot = self._shot(page, "error")
                return PrefillResult(
                    ok=False, stopped_at="error", screenshot_path=shot, message=str(exc)
                )
            finally:
                if not self.headless:
                    logger.info("Leaving browser open for your review — close it when done.")
                else:
                    browser.close()

    # ── Steps ───────────────────────────────────────────────────────────────

    def _login(self, page) -> bool:
        page.goto(SIGN_IN_URL, wait_until="domcontentloaded", timeout=30_000)
        for sel, value in (
            ("input[name='username'], input[type='email'], #user_email", self.username),
            ("input[name='password'], input[type='password'], #user_password", self.password),
        ):
            el = page.locator(sel).first
            if el.count():
                el.fill(value)
        for sel in ("button[type='submit']", "input[type='submit']", "button:has-text('Sign In')"):
            btn = page.locator(sel).first
            if btn.count():
                btn.click()
                break
        page.wait_for_load_state("networkidle", timeout=30_000)
        # Heuristic: signed in if the sign-in form is gone or a sign-out link exists.
        signed_out_form = page.locator("input[type='password']").count()
        sign_out = page.get_by_text("Sign Out", exact=False).count()
        return sign_out > 0 or signed_out_form == 0

    def _start_application(self, page) -> None:
        for text in ("Apply", "Apply Now", "Start Application", "Continue"):
            btn = page.get_by_role("button", name=text)
            if btn.count():
                btn.first.click()
                page.wait_for_load_state("networkidle", timeout=20_000)
                return
            link = page.get_by_role("link", name=text)
            if link.count():
                link.first.click()
                page.wait_for_load_state("networkidle", timeout=20_000)
                return

    def _fill_known_fields(self, page, packet: ApplicationPacket | None) -> int:
        """Fill only a conservative allowlist of obvious free-text fields."""
        filled = 0
        mapping = {
            "input[name*='email' i]": self.profile.email,
            "input[name*='phone' i]": self.profile.phone,
        }
        for selector, value in mapping.items():
            if not value:
                continue
            el = page.locator(selector).first
            try:
                if el.count() and not el.input_value():
                    el.fill(value)
                    filled += 1
            except Exception:
                continue

        # Cover letter / "additional information" textareas → packet cover letter.
        if packet and packet.cover_letter:
            for selector in (
                "textarea[name*='cover' i]",
                "textarea[name*='additional' i]",
                "textarea[name*='comment' i]",
            ):
                el = page.locator(selector).first
                try:
                    if el.count() and not el.input_value():
                        el.fill(packet.cover_letter)
                        filled += 1
                        break
                except Exception:
                    continue
        return filled

    @staticmethod
    def _has_captcha(page) -> bool:
        markers = ["iframe[src*='recaptcha']", "iframe[title*='captcha' i]", "div.g-recaptcha"]
        return any(page.locator(m).count() for m in markers)

    def _shot(self, page, label: str) -> str | None:
        try:
            path = self.screenshot_dir / f"{label}.png"
            page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Exception:
            return None
