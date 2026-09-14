"""
Browser tests for tampa-bid-radar.html.

The page is the product; a broken tray is worse than a broken collector,
because nobody sees a stack trace. These load the real file in Chromium with
a stubbed `claude.use` and assert the behaviours that matter:

  * it renders with NO capabilities at all (a plain browser, no db, no mcp)
  * the tray shows only signals that are neither dismissed nor promoted
  * Promote writes ONE opportunity at a deterministic id and records the
    promotion on the signal — it never touches any other machine-owned field
  * Dismiss writes only `dismissed`
  * PT-BR renders

Skipped when Playwright or Chromium is unavailable.
"""
from __future__ import annotations

import json
import os
import pathlib

import pytest

pytest.importorskip("playwright", reason="playwright not installed")
from playwright.sync_api import sync_playwright  # noqa: E402

PAGE = pathlib.Path(__file__).resolve().parent.parent / "tampa-bid-radar.html"
# This sandbox ships Chromium at a fixed path; CI installs it where Playwright
# expects it. Prefer the sandbox copy, otherwise let Playwright resolve its own.
CHROME = next((p for p in (
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome",
) if os.path.exists(p)), None)

SIGNALS = [
    {"id": "abt-1", "source": "abt", "source_id": "AB1-26-0000021",
     "source_url": "https://arcgis.tampagov.net/x", "hood": "ybor",
     "address": "1616 E 7th Ave", "entity": "Tommy's Chophouse",
     "trade": "restaurant", "stage_hint": "abt", "score": 83,
     "filed_at": "2026-07-20", "sqft": 4445,
     "bid_window": {"open": "2026-10-14", "close": "2027-04-12"},
     "contacts": [{"kind": "phone", "value": "(727) 444-1414"},
                  {"kind": "email", "value": "owner@example.com"}],
     "warnings": [], "blockers": []},
    {"id": "permit-1", "source": "permit", "source_id": "BLD-26-0526061",
     "source_url": "https://aca-prod.accela.com/y", "hood": "waterst",
     "address": "1050 Water St", "entity": "Wagamama Pan Asian",
     "trade": "restaurant", "stage_hint": "early_start", "score": 73,
     "filed_at": "2026-06-22",
     "bid_window": {"open": "2026-09-14", "close": "2026-11-13"},
     "contacts": [], "warnings": ["needs_contact"], "blockers": []},
    {"id": "ent-1", "source": "entitlement", "source_id": "REZ-26-0000116",
     "source_url": "https://aca-prod.accela.com/z", "hood": "airport",
     "address": "253 N West Shore Blvd", "entity": None,
     "scope": "Rezoning case, hearing 2026-11-05", "trade": "other",
     "stage_hint": "pre_permit", "score": 58, "filed_at": "2026-08-10",
     "bid_window": {"open": "2026-11-05", "close": "2027-05-04"},
     "contacts": [], "warnings": ["trade_undeclared", "needs_contact"],
     "blockers": []},
    {"id": "dismissed-1", "source": "permit", "source_id": "OLD", "hood": "ybor",
     "address": "x", "entity": "Dismissed already", "trade": "retail",
     "stage_hint": "issued", "score": 60, "contacts": [], "dismissed": True},
    {"id": "promoted-1", "source": "permit", "source_id": "OLD2", "hood": "ybor",
     "address": "y", "entity": "Promoted already", "trade": "retail",
     "stage_hint": "revision", "score": 61, "contacts": [],
     "promotedTo": "sig-promoted-1"},
]

STUB = """(() => {
  const store = {signals: __SIGNALS__};
  const docs = __DOCS__;
  window.__writes = [];
  const col = (name) => ({
    onSnapshot(cb){ cb({docs:(store[name]||[]).map(d=>({id:d.id, data:()=>d}))}); return ()=>{}; },
    add(rec){ window.__writes.push(['add', name, rec]); return Promise.resolve({id:'new'}); }
  });
  const doc = (path) => ({ onSnapshot(cb){
    const d = docs[path];
    cb(d ? {exists:true, data:()=>d} : {exists:false, data:()=>({})});
    return ()=>{};
  } });
  const docAt = (path) => Object.assign(doc(path), {
    set(v){ window.__writes.push(['set', path, v]); return Promise.resolve(); },
    update(v){ window.__writes.push(['update', path, v]); return Promise.resolve(); },
    delete(){ window.__writes.push(['delete', path]); return Promise.resolve(); }
  });
  window.claude = { use: async (n) => n === 'db' ? {collection: col, doc: docAt} : null };
})();"""


def _errors_filter(text: str) -> bool:
    """Google Fonts is blocked in CI; that is the sandbox, not the page."""
    return "ERR_CONNECTION" not in text and "ERR_NAME_NOT_RESOLVED" not in text


class _Page:
    def __init__(self, pw, stub):
        self.errors: list[str] = []
        launch = {"args": ["--no-sandbox"]}
        if CHROME:
            launch["executable_path"] = CHROME
        try:
            self.browser = pw.chromium.launch(**launch)
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"chromium unavailable: {exc}")
        self.page = self.browser.new_page()
        self.page.on("pageerror", lambda e: self.errors.append(f"PAGEERROR {e}"))
        self.page.on("console", lambda m: self.errors.append(m.text)
                     if m.type == "error" and _errors_filter(m.text) else None)
        if stub:
            self.page.add_init_script(stub)
        self.page.goto(PAGE.as_uri())
        self.page.wait_for_timeout(900)


@pytest.fixture(scope="module")
def pw():
    """One Playwright context for the module — the sync API does not allow two
    to be open in the same thread."""
    with sync_playwright() as instance:
        yield instance


def _stub(signals, docs=None):
    return (STUB.replace("__SIGNALS__", json.dumps(signals))
                .replace("__DOCS__", json.dumps(docs or {})))


@pytest.fixture(scope="module")
def bare(pw):
    p = _Page(pw, None)
    yield p
    p.browser.close()


@pytest.fixture(scope="module")
def wired(pw):
    p = _Page(pw, _stub(SIGNALS))
    yield p
    p.browser.close()


# --------------------------------------------------------------- no capabilities

def test_page_renders_with_no_capabilities_at_all(bare):
    assert bare.page.title() == "Tampa Bid Radar"
    assert bare.page.locator("#projects .proj").count() == 15
    assert bare.page.locator("#subtable tbody tr").count() == 8
    assert bare.page.locator("#bars .barcol").count() == 6
    assert bare.page.locator("#board .opp").count() == 4        # the placeholders


def test_the_tray_stays_hidden_without_a_shared_database(bare):
    """Signals only arrive through db; an empty tray heading would be noise."""
    assert bare.page.locator("#traysec").is_hidden()


def test_the_rays_row_names_the_construction_manager(bare):
    row = bare.page.locator("#projects .proj", has_text="Rays").first.inner_text()
    assert "AECOM Hunt" in row and "Turner" in row
    assert "28 Aug 2026" in row                                  # Hillsborough approval


def test_portuguese_renders(bare):
    bare.page.click("#pt")
    bare.page.wait_for_timeout(250)
    try:
        assert "Radar de Licitações" in bare.page.locator("h1").inner_text()
        row = bare.page.locator("#projects .proj", has_text="Rays").first.inner_text()
        assert "28/08/2026" in row
    finally:
        bare.page.click("#en")
        bare.page.wait_for_timeout(200)


def test_no_console_errors_on_a_bare_load(bare):
    assert bare.errors == []


# ------------------------------------------------------------------- the tray

def test_tray_shows_only_undecided_signals(wired):
    assert wired.page.locator("#traysec").is_visible()
    assert wired.page.locator("#tray .sig").count() == 3       # 5 minus 1 dismissed, 1 promoted


def test_tray_is_ordered_by_score(wired):
    texts = wired.page.locator("#tray .sig").all_inner_texts()
    assert "Tommy's Chophouse" in texts[0]
    assert "Wagamama" in texts[1]


def test_contacts_are_click_to_call_and_click_to_mail(wired):
    assert wired.page.locator('#tray .sig a[href^="tel:"]').count() == 1
    assert wired.page.locator('#tray .sig a[href^="mailto:"]').count() == 1


def test_an_undeclared_trade_says_so_rather_than_guessing(wired):
    card = wired.page.locator('#tray .sig[data-sig="ent-1"]').inner_text()
    assert "trade not declared yet" in card
    assert "Rezoning case" in card


@pytest.mark.parametrize("key,expected", [("all", 3), ("contact", 1), ("hot", 2)])
def test_tray_filters(wired, key, expected):
    wired.page.click(f'#trayfilters button[data-tray="{key}"]')
    wired.page.wait_for_timeout(150)
    assert wired.page.locator("#tray .sig").count() == expected
    wired.page.click('#trayfilters button[data-tray="all"]')
    wired.page.wait_for_timeout(150)


def test_promote_and_dismiss_touch_only_human_owned_fields(wired):
    wired.page.evaluate("window.__writes = []")
    wired.page.click('#tray .sig[data-sig="permit-1"] button[data-promote]')
    wired.page.wait_for_timeout(250)
    wired.page.click('#tray .sig[data-sig="ent-1"] button[data-dismiss]')
    wired.page.wait_for_timeout(250)
    writes = wired.page.evaluate("window.__writes")

    paths = [w[1] for w in writes]
    # exactly one opportunity, at an id derived from the signal so a second
    # promote updates the same row instead of duplicating it
    assert paths.count("opportunities/sig-permit-1") == 1
    assert sum(1 for p in paths if p.startswith("opportunities/")) == 1

    promo = next(w for w in writes if w[1] == "signals/permit-1")
    assert promo[0] == "update"
    assert set(promo[2]) == {"promotedTo", "promotedAt"}
    assert promo[2]["promotedTo"] == "sig-permit-1"

    dismiss = next(w for w in writes if w[1] == "signals/ent-1")
    assert dismiss[0] == "update"
    assert set(dismiss[2]) == {"dismissed", "dismissedAt"}

    opp = next(w for w in writes if w[1] == "opportunities/sig-permit-1")[2]
    assert opp["name"] == "Wagamama Pan Asian"
    assert opp["hood"] == "Water Street"        # submarket id mapped to the board label
    assert opp["address"] == "1050 Water St"
    assert opp["sourceUrl"].startswith("https://aca-prod.accela.com/")
    assert opp["signalId"] == "permit-1"
    assert opp["stage"] == "signal"


def test_no_console_errors_with_the_tray_wired(wired):
    assert wired.errors == []


# ------------------------------------------------------- relationship rows

REL = {
    "id": "rel-compass", "name": "COMPASS prequalification (opens Moss + 60 FL GCs)",
    "hood": "Water Street", "trade": "relationship", "stage": "signal",
    "valueEst": 0, "source": "referral", "bidDate": "2026-09-26", "owner": "",
    "priority": 1, "nextAction": "Register Ideal Construction on COMPASS",
    "why": "Moss is the GC for Water Street and Gasworx and prequalifies through COMPASS.",
    "sourceUrl": "https://compass.bespokemetrics.com", "contacts": [],
}

REL_STUB = """(() => {
  const store = {opportunities: [__REL__], signals: []};
  window.__writes = [];
  const col = (name) => ({
    onSnapshot(cb){ cb({docs:(store[name]||[]).map(d=>({id:d.id, data:()=>d}))}); return ()=>{}; },
    add(){ return Promise.resolve({id:'new'}); }
  });
  const docAt = (path) => ({
    onSnapshot(cb){ cb({exists:false, data:()=>({})}); return ()=>{}; },
    set(v){ window.__writes.push(['set', path, v]); return Promise.resolve(); },
    update(v){ window.__writes.push(['update', path, v]); return Promise.resolve(); },
    delete(){ return Promise.resolve(); }
  });
  window.claude = { use: async (n) => n === 'db' ? {collection: col, doc: docAt} : null };
})();"""


@pytest.fixture(scope="module")
def rel(pw):
    p = _Page(pw, REL_STUB.replace("__REL__", json.dumps(REL)))
    yield p
    p.browser.close()


def test_a_relationship_row_renders_on_the_board(rel):
    card = rel.page.locator("#board .opp").first
    text = card.inner_text()
    assert "COMPASS" in text
    assert "Relationship / prequal" in text
    assert "2026-09-26" in text
    assert "Moss is the GC" in text          # the `why` is the point of the row


def test_a_relationship_row_shows_no_dollar_value(rel):
    """These carry no value and must never read as biddable work."""
    assert "$0" not in rel.page.locator("#board .opp").first.inner_text()


def test_a_relationship_row_offers_no_jobtread_push(rel):
    """A prequalification is not a customer account."""
    assert rel.page.locator('#board .opp button[data-jt]').count() == 0


def test_a_relationship_row_does_not_inflate_live_pipeline(rel):
    """`Live` is what is actually in the pipeline; a vendor form is not."""
    row = rel.page.locator("#subtable tbody tr", has_text="Water Street").first
    assert row.locator("td").last.inner_text().strip() == "—"


def test_no_console_errors_with_a_relationship_row(rel):
    assert rel.errors == []


# ----------------------------------------------- JobTread status mapping

# The eleven values Ideal's own `Status` custom field offers on a job, read
# from custom field 22P6bRnsNu2Y (type option, targetType job) on 2026-09-14.
# Not a guess at a generic JobTread vocabulary — this organization's list.
JOB_STATUS_OPTIONS = [
    "New Lead", "Estimate with Cost $", "Estimating HOMEE", "Approved",
    "Permitting", "Construction", "Closed Waiting for payments",
    "Paid Waiting to split", "Closed Won", "Closed Lost",
    "Subcontractor Agreement",
]


def test_every_jobtread_status_maps_to_a_board_stage(bare):
    """A status the page cannot map silently leaves the row where it was."""
    mapping = bare.page.evaluate("JT_STAGE")
    missing = [s for s in JOB_STATUS_OPTIONS if s not in mapping]
    assert not missing, f"unmapped JobTread statuses: {missing}"
    assert set(mapping.values()) <= {"signal", "qualified", "bidding", "won", "lost"}


@pytest.mark.parametrize("status,stage", [
    ("New Lead", "signal"),
    ("Estimate with Cost $", "bidding"),
    ("Estimating HOMEE", "bidding"),
    ("Approved", "won"),            # the bid was accepted
    ("Subcontractor Agreement", "won"),
    ("Permitting", "won"),
    ("Construction", "won"),
    ("Closed Won", "won"),
    ("Closed Lost", "lost"),
])
def test_jobtread_status_lands_on_the_right_stage(bare, status, stage):
    assert bare.page.evaluate("s => JT_STAGE[s]", status) == stage


def test_the_refresh_never_writes_a_contract_value(bare):
    """documents.priceSum totals estimates, change orders and invoices
    together. Calibration is only worth having if the value on a Won row is
    the real contract somebody typed."""
    src = bare.page.evaluate("refreshFromJobTread.toString()")
    assert "valueActual" not in src
    assert "jobtreadStatus" in src


# --------------------------------------------------------- calibration seed

# Shaped like the real 2026-09-14 measurement: 29 valued permits whose median
# is $1.7M, well above the avgTI dial's $900k ceiling.
SEED_REAL = {"measures": "fitout permit value", "n": 29, "window_days": 365,
             "p25": 400000.0, "median": 1700000.0, "p75": 2775433.0,
             "mean": 2653242.91, "min": 5000.0, "max": 18800000.0,
             "basis": "declared job value on qualified fitout permits, City of Tampa Accela",
             "by_hood": {"waterst": {"hood_label": "Water Street", "n": 5,
                                     "median": 2658013.0}},
             "retrieved_at": "2026-09-14T03:05:20+00:00"}

# The same shape but inside the dial's range, which is what a narrower filter
# or a quieter year would produce.
SEED_IN_RANGE = {**SEED_REAL, "p25": 180000.0, "median": 410000.0,
                 "p75": 620000.0, "mean": 455000.0}


@pytest.fixture(scope="module")
def seeded(pw):
    p = _Page(pw, _stub(SIGNALS, {"meta/calibration_seed": SEED_REAL}))
    yield p
    p.browser.close()


@pytest.fixture(scope="module")
def seeded_in_range(pw):
    p = _Page(pw, _stub(SIGNALS, {"meta/calibration_seed": SEED_IN_RANGE}))
    yield p
    p.browser.close()


def test_without_a_seed_the_market_lines_stay_hidden(wired):
    assert wired.page.locator("#applymarket").is_hidden()
    assert "Quartile spread" not in wired.page.locator("#calbody").inner_text()


def test_the_spread_is_shown_not_a_single_flattering_number(seeded):
    body = seeded.page.locator("#calbody").inner_text()
    assert "29 with a value" in body
    # p25 -> median -> p75, because one number hides that the qualified set
    # spans a $5,000 job and an $18.8M hotel.
    assert "$400k → $1.7M → $2.8M" in body, body
    assert "not a contract value" in body
    assert "not our win rate" in body


def test_a_median_above_the_dial_is_reported_not_silently_clamped(seeded):
    """Pinning a $1.7M median onto a $900k slider would read as calibration and
    be a worse number than the default it replaced."""
    body = seeded.page.locator("#calbody").inner_text()
    assert "above this dial" in body
    assert seeded.page.locator("#applymarket").is_hidden()
    assert seeded.page.evaluate("dials.avgTI") == 325000      # untouched
    assert seeded.errors == []


def test_a_median_inside_the_dial_is_offered_and_moves_only_avgti(seeded_in_range):
    before = seeded_in_range.page.evaluate("({...dials})")
    assert seeded_in_range.page.locator("#applymarket").is_visible()
    assert "above this dial" not in seeded_in_range.page.locator("#calbody").inner_text()
    seeded_in_range.page.locator("#applymarket").click()
    seeded_in_range.page.wait_for_timeout(200)
    after = seeded_in_range.page.evaluate("({...dials})")
    assert after["avgTI"] == 410000               # the median, to the nearest $1k
    assert after["winRate"] == before["winRate"]  # never, from any market figure
    assert after["perFitout"] == before["perFitout"]
    assert seeded_in_range.errors == []
