"""Tiny stdlib HTTP helpers. `fetch` is injectable so tests never touch the network."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Callable

USER_AGENT = "ideal-bid-tracker/0.1 (public records research)"
Fetch = Callable[[str, bytes | None, dict], bytes]


def urllib_fetch(url: str, data: bytes | None = None, headers: dict | None = None, timeout: int = 60,
                 retries: int = 3) -> bytes:
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs, method="POST" if data is not None else "GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise ConnectionError(f"could not reach {url}: {last}")


def get_json(url: str, *, fetch: Fetch = urllib_fetch, headers: dict | None = None):
    return json.loads(fetch(url, None, headers or {}))


def post_json(url: str, payload: dict, *, fetch: Fetch = urllib_fetch, headers: dict | None = None):
    body = json.dumps(payload).encode()
    return json.loads(fetch(url, body, {"Content-Type": "application/json", **(headers or {})}))
