"""
First-pass classification of a City of Tampa permit record.

The big discovery of PLAN.md §3 source #1: the layer carries the Florida
Building Code OCCUPANCY CATEGORY the applicant filed under. That beats any
keyword guess at the trade, so it is the primary signal and free text is only
the fallback.
"""
from __future__ import annotations

import re

# OCCUPANCYCATEGORY code prefix -> trade. Codes observed in the live layer
# (bid_radar/data/vocab_tampa.json, retrieved 2026-09-14).
OCCUPANCY_TRADE = {
    "A-1": "hospitality",   # Fixed seating. Theater. Concert hall
    "A-2": "restaurant",    # Food & Drink. Restaurant. Night Club. Bar
    "A-3": "other",         # Worship. Amusement. Arcade. Church. Community Hall
    "A-4": "hospitality",   # Indoor sport viewing. Arena. Skating rink
    "A-5": "hospitality",   # Outdoor activities. Amusement park. Stadium
    "B-1": "medical",       # Animal hospital
    "B-2": "office",        # Bank
    "B-3": "retail",        # Barber shop / beauty shop
    "B-4": "retail",        # Car wash
    "B-5": "medical",       # Clinic. Outpatient
    "B-7": "medical",       # Laboratory
    "B-8": "retail",        # Motor vehicle showroom
    "B-9": "office",        # Professional office
    "B-10": "office",       # High rise office
    "E-1": "other", "E-2": "other",
    "F-1": "other", "F-2": "other",
    "I-1": "medical",       # Institutional, 17+ ambulatory
    "I-2": "medical",       # Institutional, 6+ non-ambulatory
    "I-4": "medical",       # Institutional day care
    "M-1": "retail", "M-2": "retail", "M-3": "retail", "M-4": "retail",
    "R-1": "hospitality",   # Transient boarding. Hotels. Motels
    "R-2": "other", "R-3": "other", "R-3A": "other", "R-3B": "other",
    "R-3C": "other", "R-3D": "other",
    "R-4": "medical",       # Assisted living 6-16 persons
    "S-1A": "other", "S-1B": "other", "S-2A": "other", "S-2B": "other", "S-2C": "other",
    "U-2": "other", "U-3": "other",
}

# Fallback only, when OCCUPANCYCATEGORY is blank (14% of commercial rows).
KEYWORD_TRADE = [
    ("restaurant", r"\b(restaurant|pizzer|kitchen|bar\b|caf[eé]|coffee|brewery|taproom|"
                   r"dining|food service|bakery|deli\b|grill\b|sushi|cantina|taqueria)"),
    ("medical",    r"\b(dental|dentist|\bdds\b|\bdmd\b|orthodon|medical|clinic|surgery|"
                   r"surgical|imaging|radiolog|urgent care|physician|pediatric|\bmd\b|"
                   r"veterinar|dialysis|pharmacy|therapy|wellness center)"),
    ("retail",     r"\b(retail|store|shop\b|boutique|salon|barber|spa\b|showroom|"
                   r"mercantile|tenant improvement within the mall|"
                   r"fitness|gym\b|yoga|pilates|cycling studio|nail|lash|med spa)"),
    ("hospitality", r"\b(hotel|motel|resort|lodging|guest room|ballroom|banquet)"),
    ("office",     r"\b(office|suite \d|workplace|coworking|law firm|headquarters)"),
]

# Record types that can carry a commercial fitout.
FITOUT_RECORD_TYPES = {
    "Commercial Building Alterations (Renovations)",
    "Commercial New Construction and Additions",
}
COMMERCIAL_RECORD_TYPES = FITOUT_RECORD_TYPES | {"Commercial Demolition Permit"}
DEMOLITION_RECORD_TYPES = {"Commercial Demolition Permit", "Residential Demolition Permit"}

# Occupancy categories broad enough that the free text is the better guide.
# A-3 is "Worship. Amusement. Arcade. Church. Community Hall" — a fitness
# studio, an arcade and a church all file under it, and a Hotworx buildout is
# a retail fitout while a sanctuary is not.
AMBIGUOUS_OCCUPANCY = {"A-3", "A-5", "B-9"}

# Occupancy codes that mean "someone's home". These show up under commercial
# record types because the building is a threshold high-rise, but the work is
# a condo kitchen or bathroom — not a job any GC bids. R-1 (hotel) and R-4
# (assisted living) are deliberately NOT here.
DWELLING_OCCUPANCY = {"R-2", "R-3", "R-3A", "R-3B", "R-3C", "R-3D"}

_EARLY_START = re.compile(r"\bEARLY\s*START\b", re.I)

# A strip-out: the lease space is being demolished and the build-back will come
# under a separate permit. The trade is not declared yet, but the tenant is
# committed and the fitout has not been bid — which makes this one of the more
# actionable rows the layer produces, not noise.
_DEMO_SCOPE = re.compile(
    r"\b(interior\s+demolition|demolition\s+of\s+(?:existing\s+)?"
    r"(?:lease\s+space|partitions|interior)|strip[-\s]?out|gut\b)", re.I)
_BUILD_BACK_PENDING = re.compile(
    r"\b(?:build[-\s]?back|remodel\s+permit|fit[-\s]?out|build[-\s]?out|"
    r"tenant\s+improvement)\b[^.]{0,100}?\b(?:separate\s+permit|under\s+separate|"
    r"future\s+permit|to\s+be\s+(?:pulled|applied|submitted|permitted))"
    r"|\b(?:separate|future)\s+permit\b[^.]{0,60}?\b(?:build[-\s]?back|remodel)"
    , re.I)
# Build-back described in this same permit — an ordinary fitout, not a strip-out.
_BUILD_BACK_HERE = re.compile(
    r"\b(construction\s+of\s+new|new\s+partitions|installation\s+of\s+new|"
    r"new\s+finishes|build[-\s]?out\s+of|new\s+millwork|new\s+ceilings?)\b", re.I)


def is_strip_out(*text: str | None) -> bool:
    blob = " ".join(t for t in text if t)
    if not _DEMO_SCOPE.search(blob):
        return False
    if _BUILD_BACK_HERE.search(blob):
        return False
    # Only when the record itself says the build-back comes later. Being
    # conservative here is deliberate: mistaking a real fitout for a strip-out
    # demotes its trade to `other` and loses the lead, which costs more than
    # missing a strip-out and treating it as an ordinary record.
    return bool(_BUILD_BACK_PENDING.search(blob))

# --- Tenant-name extraction -------------------------------------------------
# There is no applicant or contractor field in this layer (PLAN.md §3 #1). The
# tenant, when it is recorded at all, is in PROJECTNAME2 or PROJECTDESCRIPTION.
# Every rule below was written against real strings from the live layer.

# Administrative prefixes Tampa staples onto PROJECTNAME2.
_ADMIN_PREFIX = re.compile(
    r"^(?:\s*(?:EARLY\s*START|SEC|FEMA|PP|TIA\s+PROJECT|THRESHOLD(?:\s+BUILDING)?|"
    r"THRESH|Facilitated\s+Project|Expedited\s+Project|CMP-[\d-]+)\s*[:\-]?\s*)+", re.I)

# "for new tenant: X", "for a tenant (X)", "NEW TENANT: X"
_TENANT_CUE = [
    re.compile(r"\(([A-Z][\w&.'\- ]{2,40})\)\s*$"),
    re.compile(r"\btenants?\s*[:(]\s*([^)\n;]{3,60})", re.I),
    re.compile(r"\bfor\s+(?:a\s+|new\s+|the\s+)?tenants?\s+([A-Z][\w&.'\- ]{2,45}?)"
               r"(?=[.,;)]|\s+relocat|\s*$)", re.I),
]

# Segment leaders that mean "this is scope, not a name".
_NOT_A_NAME = re.compile(
    r"^(?:suite|ste|unit|floor|fl|bldg|building|block|room|lot|phase|"
    r"interior|exterior|int\.?|ext\.?|common|remodel|renovation|reno|alteration|alt\.?|"
    r"build[-\s]?out|demo(?:lition)?|addition|repair|replace|install|upgrade|"
    r"bathroom|bath|restroom|kitchen|elevator|lobby|corridor|roof|pool|parking|"
    r"sign|canopy|facade|fa\u00e7ade|shell|core|site|deck|balcony|stair|window|door|"
    r"mep|hvac|electrical|plumbing|fire|sprinkler|structural|"
    r"tenant|space|project|work|scope|new|existing|the\s+proposed|"
    r"\d|[ivx]+)\b", re.I)

# Location noise that trails a real name: "Coca-Cola Suite 300",
# "Wagamama Pan Asian Block F2 Ground Floor", "Fly USA Hangar 4300".
_TRAILING_NOISE = re.compile(
    r"(?:\s*(?:"
    r"(?:suite|ste|unit|bldg|building|block|hangar|room|floor|fl|lvl|level)\s*[#:]?\s*[\w#]{0,6}"
    r"|(?:ground|basement|mezzanine|\d+(?:st|nd|rd|th))\s+floor"
    r"|#\s*\w+|[\d]{1,5}"
    r"))+\s*$", re.I)


def _cut_sentence(seg: str) -> str:
    """Stop at the next sentence when the record shouts the scope in caps."""
    m = re.search(r"\.\s+(?=[A-Z]{2,})", seg)
    return seg[:m.start()] if m else seg


def _clean_segment(seg: str) -> str | None:
    seg = re.sub(r"\s+", " ", seg).strip(" .,;:-–()[]\"'")
    for _ in range(4):
        stripped = _TRAILING_NOISE.sub("", seg).strip(" .,;:-–")
        if stripped == seg:
            break
        seg = stripped
    if len(seg) < 3 or seg[0].isdigit() or _NOT_A_NAME.match(seg):
        return None
    if not re.search(r"[A-Za-z]{3}", seg):
        return None
    return seg


def _from_cues(blob: str) -> str | None:
    for cue in _TENANT_CUE:
        m = cue.search(blob)
        if m:
            name = _clean_segment(_cut_sentence(m.group(1)))
            if name:
                return name
    return None


def _from_segments(blob: str) -> str | None:
    """PROJECTNAME2 reads '<admin prefixes>: <scope>: <name>' often enough."""
    body = _ADMIN_PREFIX.sub("", blob)
    for seg in reversed([x for x in re.split(r"\s*:\s*|\s+[-\u2013]\s+", body) if x.strip()]):
        name = _clean_segment(seg)
        if name:
            return name
    return None


def entity_of(*text: str | None) -> str | None:
    """Best-effort tenant name, or None. Never a guess dressed up as a fact.

    Order matters: PROJECTNAME2 is curated and mixed-case, the description is
    often shouted in caps, so the short field is tried first — both for an
    explicit tenant cue and for its 'prefix: scope: name' shape — before
    falling back to a cue anywhere in the long text.
    """
    blobs = [t for t in text if t]
    if not blobs:
        return None
    head, rest = blobs[0], blobs[1:]
    return (_from_cues(head)
            or _from_segments(head)
            or next((n for n in (_from_cues(b) for b in rest) if n), None))


def occupancy_code(occupancy_category: str | None) -> str | None:
    """'B-5 Business-Clinic. Outpatient' -> 'B-5'."""
    if not occupancy_category:
        return None
    m = re.match(r"\s*([A-Z]-\d+[A-Z]?)\b", occupancy_category)
    return m.group(1) if m else None


def _keyword_trade(blob: str) -> str | None:
    for trade, pattern in KEYWORD_TRADE:
        if re.search(pattern, blob, re.I):
            return trade
    return None


def trade_of(occupancy_category: str | None, *text: str | None,
             record_type: str | None = None) -> tuple[str, float]:
    """(trade, confidence).

    The filed FBC occupancy code is authoritative, with two exceptions:

      * A demolition permit has no fitout trade at all. Without this guard the
        keyword fallback reads "demolition of two story wood framed office
        buildings" and returns `office`, which would put a teardown on the
        outreach list.
      * A handful of occupancy codes are grab-bags (AMBIGUOUS_OCCUPANCY); for
        those the description is the better guide and keywords are tried first.
    """
    if (record_type or "") in DEMOLITION_RECORD_TYPES:
        return "other", 0.3

    blob = " ".join(t for t in text if t)
    if is_strip_out(*text):
        # The space is being emptied; the trade is declared on the build-back
        # permit, which has not been filed. Saying `office` here because the
        # word appears in the scope would be a guess.
        return "other", 0.3
    code = occupancy_code(occupancy_category)

    if code in AMBIGUOUS_OCCUPANCY:
        kw = _keyword_trade(blob)
        if kw and kw != OCCUPANCY_TRADE.get(code):
            return kw, 0.7
    if code and code in OCCUPANCY_TRADE:
        return OCCUPANCY_TRADE[code], 0.9
    kw = _keyword_trade(blob)
    if kw:
        return kw, 0.5
    return "other", 0.2


def stage_of(project_status: str | None, *text: str | None) -> str:
    """Where the job is, in the only three states this layer can express.

    `early_start` is the one with a live bid window: the city has released
    interior non-structural work but the main permit is NOT yet issued, so
    buyout for the rest of the scope is still open.
    """
    blob = " ".join(t for t in text if t)
    if _EARLY_START.search(blob):
        return "early_start"
    if is_strip_out(*text):
        return "strip_out"
    if (project_status or "").strip().lower() == "revision":
        return "revision"
    return "issued"



def is_dwelling(occupancy_category: str | None) -> bool:
    return occupancy_code(occupancy_category) in DWELLING_OCCUPANCY


def is_fitout(record_type: str | None, occupancy_category: str | None = None) -> bool:
    """A record a GC could actually bid a fitout on."""
    return ((record_type or "") in FITOUT_RECORD_TYPES
            and not is_dwelling(occupancy_category))


def scope_label(*text: str | None) -> str | None:
    """Readable scope for a record with no parsable tenant name."""
    for blob in text:
        if not blob:
            continue
        body = re.sub(r"\s+", " ", _ADMIN_PREFIX.sub("", blob)).strip(" .,;:-\u2013")
        if len(body) >= 4:
            return body
    return None


def is_commercial(record_type: str | None) -> bool:
    return (record_type or "") in COMMERCIAL_RECORD_TYPES
