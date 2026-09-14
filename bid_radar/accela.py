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

# A party block runs "<person> [<email>] <COMPANY> <street address> <licence>".
# The address is where company detection goes wrong: without cutting it off,
# "1234 N Howard Ave Tampa" reads as a construction firm.
_STREET_START = re.compile(r"\b\d{2,6}\s+(?:[NSEW]\.?\s+)?[A-Za-z]")
_STREET_WORD = re.compile(
    r"\b(?:AVE|AVENUE|ST|STREET|BLVD|BOULEVARD|DR|DRIVE|RD|ROAD|HWY|HIGHWAY|"
    r"PKWY|PARKWAY|CIR|CIRCLE|LN|LANE|WAY|TRAIL|TRL|CT|COURT|PL|PLACE|TER|"
    r"SUITE|STE|APT|UNIT|FL|FLOOR)\b", re.I)
# Licence-type phrases that mark the end of the name/company/address run.
_LICENCE_TYPE = re.compile(
    r"\b(?:Building|General|Residential|Electrical|Plumbing|Mechanical|Roofing|"
    r"Specialty|Pollutant|Underground|Private\s+Provider)[\w\- ]{0,30}"
    r"(?:Contractor|Qualifier|Representative|Engineer)\b", re.I)

_FIRM = re.compile(r"([A-Z][A-Za-z&'.\- ]{3,70}(?:LLC|L\.L\.C|INC|CORP|COMPANY|CO|LP|"
                   r"PA|LTD|CONSTRUCTION|CONTRACTORS?|DEVELOPMENT|GROUP|SERVICES|"
                   r"ELECTRIC|PLUMBING|MECHANICAL|BUILDERS?|ENTERPRISES?))\b")

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


def _split_person_from_firm(text: str) -> tuple[str | None, str]:
    """"Matthew Gilbert BARR & BARR INC" -> ("Matthew Gilbert", "BARR & BARR INC").

    Accela prints the qualifier and their firm in one run. Where the qualifier
    is Title Case and the firm is not, the case change is the boundary; where
    both are the same case there is nothing to split on, and the whole string
    stays as the firm.
    """
    tokens = text.split()
    for i, tok in enumerate(tokens):
        if i == 0 or not re.fullmatch(r"[A-Z]{2,}[\w&'.\-]*", tok):
            continue
        head = tokens[:i]
        if head and all(re.fullmatch(r"[A-Z][a-z]+[\w'.\-]*", t) for t in head):
            return " ".join(head), " ".join(tokens[i:])
        break
    return None, text


def _party(block: str | None) -> dict | None:
    """Pull a person, a company, a licence and contacts out of one party block."""
    if not block:
        return None
    emails = EMAIL.findall(block)
    phones = [" ".join(p.split()) for p in PHONE.findall(block)]
    licence = LICENCE.search(block)

    # The name is whatever precedes the first email, company or address number.
    head = block
    cut0 = _STREET_START.search(head)
    if cut0:
        head = head[:cut0.start()]
    for cut in emails[:1] + ([licence.group(1)] if licence else []):
        k = head.find(cut)
        if k > 0:
            head = head[:k]
    name = re.split(r"\s{2,}|\s(?=\d{2,5}\s[A-Z])", head.strip())[0].strip(" ,")

    # The firm sits between the person (and their email) and the street address.
    # Cut the address off first — everything after the first street number is
    # location, not identity.
    ident = block
    cut = _STREET_START.search(ident)
    if cut:
        ident = ident[:cut.start()]
    company = None
    # Greedy, so "TWT Restaurant Design Construction & Development Company"
    # does not get cut short at the first "Construction".
    m = _FIRM.search(ident)
    if m:
        candidate = " ".join(m.group(1).split())
        # A street name that happens to end in a suffix word is not a firm.
        if not _STREET_WORD.search(candidate):
            company = _split_person_from_firm(candidate)[1]
            person_prefix = _split_person_from_firm(candidate)[0]
            if person_prefix and (not name or name.startswith(person_prefix)):
                name = person_prefix

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

    # A fitout permit valuation outside this band is a data-entry error on the
    # record, not a job. Observed: one at $280,000,000 and one at $500.
    VALUE_MIN, VALUE_MAX = 1_000.0, 50_000_000.0

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

    job_value = _num("Job Value")
    value_suspect = bool(job_value) and not (VALUE_MIN <= job_value <= VALUE_MAX)

    return {
        "applicant": applicant,
        "contractor": gc,
        "owner": " ".join(owner_raw.split())[:160] if owner_raw else None,
        "tenant_contact": " ".join(tenant_raw.split())[:160] if tenant_raw else None,
        "job_value": job_value,
        "value_suspect": value_suspect,
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
