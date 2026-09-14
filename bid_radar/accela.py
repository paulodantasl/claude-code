"""
Parse a City of Tampa Accela record page — PLAN.md Phase 4, and the answer to
most of what the ArcGIS permit layer cannot tell us.

Why this exists. The plan's route to a measured win rate was the Hillsborough
Clerk's Notices of Commencement. Both of the Clerk's public-records hosts
refuse traffic from a cloud runner outright (ConnectTimeout on
pubrec6.hillsclerk.com, ConnectionError on pubrec.hillsclerk.com, while
www.hillsclerk.com answers 200 — so it is those hosts, not the network).

But every permit the collector returns already carries a per-record Accela URL,
and that page holds far more than the Clerk would have:

    Applicant            name, work phone, email
    Licensed Professional the GC OF RECORD — name, company, licence number,
                         email. This is the win-rate dataset.
    Owner                name and mailing address
    Tenant contact       where the record has one
    Job Value            the valuation the ArcGIS layer omits entirely
    Sq Ft                the real floor area

Observed on BLD-26-0526061 (Wagamama, 1050 Water St) on 2026-09-14: applicant
Stephen Torres with a phone and an email, GC "TWT Restaurant Design
Construction & Development Company" licence CBC1262713, owner "Wst 1010 Water
Street Llc c/o Strategic Property Partners Llc", Job Value 300000, Sq Ft 4525.

The page is a 370 KB ASP.NET document. Parsing the DOM of it would be
brittle; the printed labels are not. So this flattens the page to text and
anchors on the labels.
"""
from __future__ import annotations

import html
import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")
PHONE = re.compile(r"(?:Work|Mobile|Home|Primary)\s*Phone:\s*([\d\-() .]{7,20})")
# Florida contractor licence formats seen on these pages.
LICENCE = re.compile(r"\b((?:CBC|CGC|CRC|CCC|CFC|CAC|CMC|CPC|EC|ER|BU|PX|RF|RG|RC|SCC)"
                     r"\s?\d{4,9})\b")

_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
_WS = re.compile(r"[ \t\xa0\r\n]+")


def to_text(page_html: str) -> str:
    """Flatten the page to single-spaced text, scripts and styles removed."""
    body = _SCRIPT.sub(" ", page_html)
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", body))).strip()


def _between(text: str, start: str, stops: tuple[str, ...]) -> str | None:
    i = text.find(start)
    if i < 0:
        return None
    i += len(start)
    end = len(text)
    for stop in stops:
        j = text.find(stop, i)
        if 0 <= j < end:
            end = j
    seg = text[i:end].strip(" :")
    return seg or None


def _party(block: str | None) -> dict | None:
    """Pull a person, a company, a licence and contacts out of one party block."""
    if not block:
        return None
    emails = EMAIL.findall(block)
    phones = [" ".join(p.split()) for p in PHONE.findall(block)]
    licence = LICENCE.search(block)

    # The name is whatever precedes the first email, company or address number.
    head = block
    for cut in emails[:1] + ([licence.group(1)] if licence else []):
        k = head.find(cut)
        if k > 0:
            head = head[:k]
    name = re.split(r"\s{2,}|\s(?=\d{2,5}\s[A-Z])", head.strip())[0].strip(" ,")

    # An ALL-CAPS or Title-Case run after the name, before the address, is the firm.
    company = None
    m = re.search(r"([A-Z][A-Za-z&'.\- ]{4,60}(?:LLC|INC|CORP|COMPANY|CO|LP|PA|LTD"
                  r"|CONSTRUCTION|CONTRACTORS?|DEVELOPMENT|GROUP|SERVICES|ELECTRIC"
                  r"|PLUMBING|MECHANICAL|BUILDERS?))\b", block)
    if m:
        company = " ".join(m.group(1).split())

    out = {"name": name[:80] or None, "company": company,
           "licence": (licence.group(1).replace(" ", "") if licence else None),
           "emails": sorted(set(e.lower() for e in emails))[:3],
           "phones": phones[:2]}
    return out if any(out.values()) else None


def parse(page_html: str) -> dict:
    """Everything worth having from one record page. Absent fields stay None."""
    text = to_text(page_html)

    applicant = _party(_between(text, "Applicant:",
                                ("Licensed Professional:", "Project Description:",
                                 "Owner:", "Record Details")))
    gc = _party(_between(text, "Licensed Professional:",
                         ("View Additional Licensed Professionals",
                          "Project Description:", "Owner:")))
    owner_raw = _between(text, "Owner:", ("More Details", "Related Contacts",
                                          "Parcel Information"))
    tenant_raw = _between(text, "Tenant information", ("Record Details", "Fees",
                                                       "More Details"))

    def _num(label: str) -> float | None:
        m = re.search(re.escape(label) + r":\s*\$?([\d,]+(?:\.\d+)?)", text)
        if not m:
            return None
        try:
            return float(m.group(1).replace(",", "")) or None
        except ValueError:
            return None

    # Every additional licensed professional on the record — the sub list.
    extra = _between(text, "View Additional Licensed Professionals",
                     ("Project Description:", "Owner:")) or ""
    subs = []
    for chunk in re.split(r"\s\d+\)\s", extra):
        p = _party(chunk)
        if p and p.get("company"):
            subs.append({"company": p["company"], "licence": p["licence"]})

    return {
        "applicant": applicant,
        "contractor": gc,
        "owner": " ".join(owner_raw.split())[:160] if owner_raw else None,
        "tenant_contact": " ".join(tenant_raw.split())[:160] if tenant_raw else None,
        "job_value": _num("Job Value"),
        "sqft": _num("Sq Ft"),
        "subs": subs[:8],
    }


def contacts_from(parsed: dict) -> list[dict]:
    """Signal `contacts[]` entries — only what the record actually printed."""
    out, seen = [], set()
    for role in ("applicant", "contractor"):
        party = parsed.get(role) or {}
        for email in party.get("emails") or []:
            if email not in seen:
                seen.add(email)
                out.append({"kind": "email", "value": email, "from": f"accela.{role}"})
        for phone in party.get("phones") or []:
            key = re.sub(r"\D", "", phone)
            if key and key not in seen:
                seen.add(key)
                out.append({"kind": "phone", "value": phone, "from": f"accela.{role}"})
    return out
