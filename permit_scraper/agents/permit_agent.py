"""
AI-powered permit scraping agent using Claude + Playwright.

This agent is designed for complex or non-standard permit portals where
rule-based scrapers fail. It uses Claude to:

  1. Understand the portal's UI by reading its DOM/screenshot.
  2. Generate step-by-step Playwright actions to navigate the site.
  3. Extract and normalise the permit data.
  4. Handle pagination, CAPTCHAs hints, and dynamic content.

The agent uses the "agentic loop" pattern:
  - Observe (screenshot + DOM snapshot)
  - Think (Claude decides next action)
  - Act (execute Playwright command)
  - Repeat until done

Architecture
------------
PermitAgent.run(county_config) -> list[RawPermit]
  |
  +-- _observe(page)          -> observation dict
  +-- _decide(observation)    -> action dict  [Claude]
  +-- _execute(page, action)  -> result
  +-- _extract(page)          -> list[RawPermit]  [Claude]
"""
from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

import anthropic
from playwright.sync_api import Page, sync_playwright

from ..scrapers.base import RawPermit

logger = logging.getLogger(__name__)

# ── Tool definitions for the Claude tool-use loop ──────────────────────────

BROWSER_TOOLS = [
    {
        "name": "click",
        "description": "Click on an element matching a CSS selector or visible text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector or text to click"},
                "text": {"type": "string", "description": "Visible text of the element (used if selector not provided)"},
            },
        },
    },
    {
        "name": "type_text",
        "description": "Type text into a focused input field.",
        "input_schema": {
            "type": "object",
            "required": ["selector", "text"],
            "properties": {
                "selector": {"type": "string", "description": "CSS selector for the input"},
                "text": {"type": "string", "description": "Text to type"},
                "clear_first": {"type": "boolean", "default": True},
            },
        },
    },
    {
        "name": "select_option",
        "description": "Select a value from a <select> dropdown.",
        "input_schema": {
            "type": "object",
            "required": ["selector", "value"],
            "properties": {
                "selector": {"type": "string"},
                "value": {"type": "string", "description": "Option value or visible text"},
            },
        },
    },
    {
        "name": "navigate",
        "description": "Navigate the browser to a URL.",
        "input_schema": {
            "type": "object",
            "required": ["url"],
            "properties": {"url": {"type": "string"}},
        },
    },
    {
        "name": "scroll",
        "description": "Scroll the page down to reveal more content.",
        "input_schema": {
            "type": "object",
            "properties": {"pixels": {"type": "integer", "default": 800}},
        },
    },
    {
        "name": "wait_for_selector",
        "description": "Wait until a CSS selector is visible on the page.",
        "input_schema": {
            "type": "object",
            "required": ["selector"],
            "properties": {
                "selector": {"type": "string"},
                "timeout_ms": {"type": "integer", "default": 10000},
            },
        },
    },
    {
        "name": "extract_permits",
        "description": (
            "Extract permit records from the current page HTML. "
            "Returns a JSON array of permit objects."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "page_html": {
                    "type": "string",
                    "description": "The full inner HTML of the results section (pass '' to use current page)",
                }
            },
        },
    },
    {
        "name": "done",
        "description": "Signal that scraping is complete. Return all collected permits.",
        "input_schema": {
            "type": "object",
            "required": ["permits"],
            "properties": {
                "permits": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Array of permit records extracted from the portal",
                }
            },
        },
    },
]


# ── Main Agent Class ────────────────────────────────────────────────────────

class PermitAgent:
    """
    Agentic scraper that uses Claude to navigate any permit portal.

    Usage:
        agent = PermitAgent()
        permits = agent.run(county_config, days_back=14)
    """

    MAX_STEPS = 30          # safety limit on agent loop iterations
    MODEL = "claude-opus-4-6"

    def __init__(self, api_key: str | None = None):
        self.client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])

    def run(
        self,
        county_config: dict[str, Any],
        days_back: int = 7,
        permit_types: list[str] | None = None,
    ) -> list[RawPermit]:
        county_id = county_config["id"]
        county_name = county_config["name"]
        base_url = county_config.get("base_url", "")
        since = datetime.utcnow() - timedelta(days=days_back)
        since_str = since.strftime("%m/%d/%Y")

        logger.info("Starting AI agent for %s (%s)", county_name, base_url)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=county_config.get("headless", True))
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
            )
            page = context.new_page()

            raw_permits: list[dict] = []
            messages: list[dict] = []

            # ── System prompt ──────────────────────────────────────────────
            system_prompt = f"""You are a web scraping agent. Your job is to extract building permit records from a government permitting portal.

Target portal: {base_url}
County/City: {county_name}
Date range: permits filed on or after {since_str}
{f"Permit types of interest: {', '.join(permit_types)}" if permit_types else "All permit types"}

Instructions:
1. Navigate to the permit search/list page.
2. Set filters for the date range and permit types if possible.
3. Extract ALL matching permit records including: permit number, type, status, applicant/owner name, address, description, estimated value, filed date.
4. Paginate through ALL result pages.
5. Use the `extract_permits` tool to extract data from each result page.
6. When finished, call `done` with all collected permits.

Important:
- Focus on commercial/industrial permits — these are most likely to contain business names.
- Include the applicant name, owner name, and contractor name — they may reveal the company behind a project.
- If you see a CAPTCHA, note it in your response and stop.
- Be efficient: use selectors you can see in screenshots/HTML.
"""

            # ── First user message ─────────────────────────────────────────
            screenshot_b64 = self._screenshot(page, base_url)
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Please begin scraping the permit portal at {base_url}. "
                            f"I need permits filed since {since_str}. "
                            "Here is a screenshot of the initial page:"
                        ),
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                ],
            })

            # ── Agentic loop ───────────────────────────────────────────────
            for step in range(self.MAX_STEPS):
                logger.debug("Agent step %d/%d", step + 1, self.MAX_STEPS)

                response = self.client.messages.create(
                    model=self.MODEL,
                    max_tokens=4096,
                    system=system_prompt,
                    tools=BROWSER_TOOLS,
                    messages=messages,
                )

                messages.append({"role": "assistant", "content": response.content})

                # Check if done
                if response.stop_reason == "end_turn":
                    logger.info("Agent finished (end_turn) after %d steps", step + 1)
                    break

                # Process tool calls
                tool_results = []
                finished = False

                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_name = block.name
                    tool_input = block.input
                    result_content = ""

                    try:
                        if tool_name == "navigate":
                            page.goto(tool_input["url"], wait_until="networkidle")
                            ss = self._screenshot_b64(page)
                            result_content = json.dumps({
                                "status": "ok",
                                "url": page.url,
                                "screenshot": ss,
                            })

                        elif tool_name == "click":
                            selector = tool_input.get("selector")
                            text = tool_input.get("text")
                            if text and not selector:
                                page.get_by_text(text, exact=False).first.click()
                            else:
                                page.locator(selector).first.click()
                            page.wait_for_load_state("networkidle")
                            ss = self._screenshot_b64(page)
                            result_content = json.dumps({"status": "ok", "screenshot": ss})

                        elif tool_name == "type_text":
                            sel = tool_input["selector"]
                            text = tool_input["text"]
                            if tool_input.get("clear_first", True):
                                page.locator(sel).first.clear()
                            page.locator(sel).first.type(text)
                            result_content = json.dumps({"status": "ok"})

                        elif tool_name == "select_option":
                            page.locator(tool_input["selector"]).select_option(tool_input["value"])
                            result_content = json.dumps({"status": "ok"})

                        elif tool_name == "scroll":
                            page.mouse.wheel(0, tool_input.get("pixels", 800))
                            result_content = json.dumps({"status": "ok"})

                        elif tool_name == "wait_for_selector":
                            page.wait_for_selector(
                                tool_input["selector"],
                                timeout=tool_input.get("timeout_ms", 10000),
                            )
                            result_content = json.dumps({"status": "ok"})

                        elif tool_name == "extract_permits":
                            html = tool_input.get("page_html") or page.content()
                            extracted = self._ai_extract_permits(html, county_id, county_name)
                            raw_permits.extend(extracted)
                            result_content = json.dumps({
                                "status": "ok",
                                "extracted_count": len(extracted),
                                "total_so_far": len(raw_permits),
                            })

                        elif tool_name == "done":
                            # Final extraction passed directly
                            direct = tool_input.get("permits", [])
                            raw_permits.extend(direct)
                            finished = True
                            result_content = json.dumps({"status": "done", "total": len(raw_permits)})

                    except Exception as exc:
                        result_content = json.dumps({"status": "error", "error": str(exc)})
                        logger.warning("Tool %s failed: %s", tool_name, exc)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content,
                    })

                messages.append({"role": "user", "content": tool_results})

                if finished:
                    logger.info("Agent signalled done. Total raw: %d", len(raw_permits))
                    break

            browser.close()

        # Convert raw dicts to RawPermit objects
        return [self._normalise(r, county_id, county_name) for r in raw_permits]

    # ── Helper methods ──────────────────────────────────────────────────────

    def _screenshot(self, page: Page, url: str) -> str:
        """Navigate and take a screenshot, returning base64 PNG."""
        try:
            page.goto(url, wait_until="networkidle", timeout=20_000)
        except Exception:
            pass
        return self._screenshot_b64(page)

    def _screenshot_b64(self, page: Page) -> str:
        png_bytes = page.screenshot(full_page=False)
        return base64.b64encode(png_bytes).decode()

    def _ai_extract_permits(self, html: str, county_id: str, county_name: str) -> list[dict]:
        """Use Claude to extract structured permit data from HTML."""
        # Truncate to ~100k chars to stay within token budget
        html_snippet = html[:100_000]

        resp = self.client.messages.create(
            model="claude-haiku-4-5-20251001",   # cheaper model for extraction
            max_tokens=8192,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract all permit records from this HTML. "
                        "Return ONLY a valid JSON array. Each object should have: "
                        "permit_number, permit_type, status, description, applicant_name, "
                        "owner_name, contractor_name, address, city, zip_code, parcel_number, "
                        "estimated_value, filed_date. Use null for missing fields.\n\n"
                        f"HTML:\n{html_snippet}"
                    ),
                }
            ],
        )

        text = resp.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        try:
            data = json.loads(text)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            logger.warning("Could not parse JSON from AI extraction")
            return []

    def _normalise(self, raw: dict, county_id: str, county_name: str) -> RawPermit:
        def g(key: str) -> Any:
            return raw.get(key) or raw.get(key.replace("_", ""))

        return RawPermit(
            source_id=str(g("permit_number") or g("id") or hash(str(raw)))[:64],
            county_id=county_id,
            county_name=county_name,
            permit_number=str(g("permit_number") or ""),
            permit_type=g("permit_type"),
            status=g("status"),
            description=g("description"),
            applicant_name=g("applicant_name"),
            owner_name=g("owner_name"),
            contractor_name=g("contractor_name"),
            address=g("address"),
            city=g("city"),
            zip_code=g("zip_code"),
            parcel_number=g("parcel_number"),
            estimated_value=self._parse_float(g("estimated_value")),
            filed_date=self._parse_date(g("filed_date")),
            raw_data=raw,
        )

    @staticmethod
    def _parse_float(v: Any) -> float | None:
        if v is None:
            return None
        try:
            return float(str(v).replace(",", "").replace("$", "").strip())
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_date(v: Any) -> datetime | None:
        if not v:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(str(v).strip()[:19], fmt)
            except ValueError:
                continue
        return None
