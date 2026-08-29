"""
FL DBPR (MyFloridaLicense) enrichment for the general contractor of record.

Two implementations:

  DBPRDataFileEnricher (recommended, robust, offline)
      Reads a DBPR licensee **data extract** you download once from
      MyFloridaLicense (Public Records → data file downloads). Indexed by license
      number and by name, it adds the GC's business address, license type,
      license status, and expiration — no live requests, fully deterministic.
      DBPR's public extract does NOT include phone numbers, so this enricher
      never invents one.

  DBPRWebEnricher (optional, best-effort, live)
      Queries the public MyFloridaLicense search for the license number and
      parses the licensee detail. Useful when you don't keep a local extract, but
      the site is an ASP.NET form that changes and may rate-limit or block
      automated access — treat results as best-effort and verify against a real
      lookup before relying on it. Disabled unless explicitly selected.

Match priority: license number (exact, normalised) → contractor name (exact
normalised, else token-subset).
"""
from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Any

from .base import Enricher, EnrichmentResult

logger = logging.getLogger(__name__)


def _norm_license(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", str(value)).upper()


def _norm_name(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^A-Z0-9 ]", " ", str(value).upper())


def _norm_name_key(value: str | None) -> str:
    return re.sub(r"\s+", " ", _norm_name(value)).strip()


# Header-name candidates for auto-detecting columns in a DBPR extract. The extract
# format varies by download; match case-insensitively on substring.
_COLUMN_HINTS = {
    "license": ("license number", "licensenumber", "license no", "lic number", "license #"),
    "name": ("name (last first)", "licensee name", "full name", "name", "primary name"),
    "dba": ("dba name", "dba", "business name", "doing business as"),
    "type": ("license type", "licensetype", "board", "profession", "rank"),
    "status_primary": ("primary status", "status", "license status", "primarystatus"),
    "status_secondary": ("secondary status", "secondarystatus"),
    "addr1": ("address 1", "address1", "mailing address", "street address", "address"),
    "addr2": ("address 2", "address2"),
    "city": ("city", "mail city"),
    "state": ("state", "mail state"),
    "zip": ("zip", "zipcode", "zip code", "postal"),
    "expiry": ("expiration", "expiration date", "expiry", "license expiration date"),
}


class DBPRDataFileEnricher(Enricher):
    """Enrich the GC from a local DBPR licensee extract file."""

    name = "dbpr_datafile"

    def __init__(self, data_file: str | Path, column_overrides: dict | None = None):
        self.data_file = Path(data_file)
        self.column_overrides = column_overrides or {}
        self._by_license: dict[str, dict] = {}
        self._by_name: dict[str, dict] = {}
        self._loaded = False

    def load(self) -> None:
        self._by_license, self._by_name = {}, {}
        if not self.data_file.exists():
            logger.error("DBPR data file not found: %s", self.data_file)
            self._loaded = True
            return

        text = self.data_file.read_text(encoding="utf-8", errors="replace")
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",|\t;")
        except csv.Error:
            dialect = csv.excel  # default to comma
        reader = csv.DictReader(text.splitlines(), dialect=dialect)

        cols = self._resolve_columns(reader.fieldnames or [])
        rows = 0
        for row in reader:
            rows += 1
            lic = _norm_license(self._val(row, cols, "license"))
            if lic:
                self._by_license.setdefault(lic, row)
            for name_field in ("name", "dba"):
                nm = _norm_name_key(self._val(row, cols, name_field))
                if nm:
                    self._by_name.setdefault(nm, row)
        self._cols = cols
        self._loaded = True
        logger.info("DBPR extract loaded: %d rows, %d licenses, %d names",
                    rows, len(self._by_license), len(self._by_name))

    def _resolve_columns(self, fieldnames: list[str]) -> dict[str, str]:
        lowered = {fn.lower().strip(): fn for fn in fieldnames}
        cols: dict[str, str] = {}
        for logical, hints in _COLUMN_HINTS.items():
            if logical in self.column_overrides:
                cols[logical] = self.column_overrides[logical]
                continue
            for hint in hints:
                match = next((orig for low, orig in lowered.items() if hint in low), None)
                if match:
                    cols[logical] = match
                    break
        return cols

    @staticmethod
    def _val(row: dict, cols: dict, logical: str) -> str | None:
        col = cols.get(logical)
        if not col:
            return None
        v = row.get(col)
        return str(v).strip() if v not in (None, "") else None

    # ── Enricher interface ──────────────────────────────────────────────────

    def cache_key(self, lead) -> str | None:
        if lead.gc_license:
            return f"lic:{_norm_license(lead.gc_license)}"
        if lead.gc_name:
            return f"name:{_norm_name_key(lead.gc_name)}"
        return None

    def enrich(self, lead) -> EnrichmentResult:
        if not self._loaded:
            self.load()
        row = None
        if lead.gc_license:
            row = self._by_license.get(_norm_license(lead.gc_license))
        if row is None and lead.gc_name:
            row = self._by_name.get(_norm_name_key(lead.gc_name)) or self._fuzzy_name(lead.gc_name)
        if row is None:
            return EnrichmentResult(source=self.name)
        return self._row_to_result(row)

    def _fuzzy_name(self, name: str) -> dict | None:
        """Token-subset match: every token of the query appears in a stored name."""
        tokens = [t for t in _norm_name_key(name).split() if len(t) > 2]
        if not tokens:
            return None
        for stored_name, row in self._by_name.items():
            if all(t in stored_name for t in tokens):
                return row
        return None

    def _row_to_result(self, row: dict) -> EnrichmentResult:
        cols = self._cols
        addr_parts = [
            self._val(row, cols, "addr1"),
            self._val(row, cols, "addr2"),
        ]
        city = self._val(row, cols, "city")
        state = self._val(row, cols, "state")
        zipc = self._val(row, cols, "zip")
        tail = " ".join(p for p in (city, state, zipc) if p)
        addr = ", ".join(p for p in ([" ".join(a for a in addr_parts if a)] + ([tail] if tail else [])) if p)

        status = self._val(row, cols, "status_primary")
        sec = self._val(row, cols, "status_secondary")
        if status and sec and sec.lower() not in status.lower():
            status = f"{status}, {sec}"

        return EnrichmentResult(
            gc_address=addr or None,
            gc_license=_norm_license(self._val(row, cols, "license")) or None,
            gc_license_type=self._val(row, cols, "type"),
            gc_license_status=status,
            gc_license_expiry=self._val(row, cols, "expiry"),
            source=self.name,
        )


class DBPRWebEnricher(Enricher):
    """Best-effort live lookup against the public MyFloridaLicense search.

    NOTE: MyFloridaLicense is an ASP.NET form whose markup changes and which may
    rate-limit or block automated access. This enricher is intentionally
    conservative and fails soft (returns an empty result) rather than raising.
    Prefer :class:`DBPRDataFileEnricher` for reliable, bulk enrichment.
    """

    name = "dbpr_web"
    SEARCH_URL = "https://www.myfloridalicense.com/wl11.asp"

    def __init__(self, timeout: int = 20, session: Any | None = None):
        self.timeout = timeout
        self._session = session

    def cache_key(self, lead) -> str | None:
        if lead.gc_license:
            return f"web:lic:{_norm_license(lead.gc_license)}"
        if lead.gc_name:
            return f"web:name:{_norm_name_key(lead.gc_name)}"
        return None

    def enrich(self, lead) -> EnrichmentResult:
        if not (lead.gc_license or lead.gc_name):
            return EnrichmentResult(source=self.name)
        try:
            import requests
            from bs4 import BeautifulSoup  # optional dep; parsing helper
        except Exception as exc:  # pragma: no cover - env dependent
            logger.warning("DBPRWebEnricher unavailable (%s)", exc)
            return EnrichmentResult(source=self.name)

        session = self._session or requests.Session()
        try:
            params = (
                {"mode": "0", "SID": "", "brd": "", "typ": "N", "licnbr": lead.gc_license}
                if lead.gc_license
                else {"mode": "0", "SID": "", "brd": "", "typ": "N", "SearchName": lead.gc_name}
            )
            resp = session.get(
                self.SEARCH_URL, params=params, timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0 (compatible; permit-leads/1.0)"},
            )
            resp.raise_for_status()
            return self._parse(resp.text)
        except Exception as exc:  # fail soft
            logger.info("DBPR web lookup failed for %s: %s",
                        lead.gc_license or lead.gc_name, exc)
            return EnrichmentResult(source=self.name)

    def _parse(self, html: str) -> EnrichmentResult:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        text = " ".join(soup.get_text(" ").split())
        result = EnrichmentResult(source=self.name)

        # Best-effort label scraping — kept defensive because the layout shifts.
        m = re.search(r"(Certified|Registered)\s+[A-Za-z ]*Contractor", text)
        if m:
            result.gc_license_type = m.group(0)
        m = re.search(r"Status[:\s]+([A-Za-z, ]+?)(?:Expires|License|$)", text)
        if m:
            result.gc_license_status = m.group(1).strip(" ,")
        m = re.search(r"Expires?[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})", text)
        if m:
            result.gc_license_expiry = m.group(1)
        return result
