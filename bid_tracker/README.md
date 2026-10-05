# bid_tracker — Florida public bid pricing database

What comparable Florida public jobs actually went for, who bid them, and what markup wins. It is built
from public bid tabulations (Ch. 119 makes them public once the agency posts its intended decision).
It feeds `/bid-public` before OH&P is set.

**The code is public. The data is not.** Bid data lives in the private `paulodantasl/ideal-bid-data` repo.
Nothing under `bid_tracker/data/` is committed, and `tests/test_exports.py::test_repo_hygiene` fails CI if
anything but code or synthetic fixtures is tracked here.

## Setup

```bash
git clone https://github.com/paulodantasl/ideal-bid-data ../ideal-bid-data   # private
export BID_TRACKER_DATA=$(cd ../ideal-bid-data && pwd)
python3 -m bid_tracker rebuild          # replays index/, packages/, private/ into $BID_TRACKER_DATA/bids.db
pip install -r bid_tracker/requirements-dev.txt   # only for tests and export-xlsx
```

The core uses only the standard library. PDF text uses `pdftotext` (poppler) or pdfplumber if installed.

## Data layout (private repo)

```
ideal-bid-data/
  packages/<YYYY-MM-DD>-<slug>/   one import package per harvest (CSV, see below)
  index/<YYYY-MM-DD>-bls-ppi/     escalation index values (cost_index.csv)
  private/ideal_pursuits.csv      Ideal's own go/no-go, cost, bid, result, debrief
  private/bidder_aliases.csv      manual bidder merges, re-applied on rebuild
  area_misses.csv                 tabs with no area found yet: sol_ref, searched, last_tried
  ideal_profile.json              bond_limit_single, bond_limit_aggregate, largest_win, ohp_floor_pct
  exports/                        xlsx snapshots
```

`bids.db` is derived. `rebuild` recreates it from the packages, so the packages are the record.

## Import packages

A package is a folder of CSVs; column specs are in `canonical.py`. Only `solicitations.csv` is required:
`agencies.csv`, `solicitations.csv`, `bids.csv`, `bid_items.csv`, `rate_cards.csv`, `ideal_pursuits.csv`,
`cost_index.csv`, `areas.csv`. Each solicitation is keyed by `sol_ref = agency_id:SOLICITATION-NO`.

`areas.csv` holds square footage, one row per solicitation and kind:
- `scope_area`: the area the price covers.
- `roof_area`
- `building_gsf`: the whole building.

Each row carries its basis (`stated` > `measured` > `derived`), page and quoted line. Areas live in their
own table, so updating a solicitation never erases one. The project type's preferred kind becomes the
tab's `gsf` and its $/SF; see [EXTRACTION_PROTOCOL.md](docs/EXTRACTION_PROTOCOL.md#square-footage-areascsv).

The validator refuses a package with any ERROR. The rules that matter most:

| Code | Rule |
|---|---|
| E-NOSRC | The award amount (or the low bid when there is no award) and every rate-card price must appear as a number in a quoted source excerpt. This is how "never invent a number" is enforced. |
| E-URL | Every row has a public source URL; the excerpt quotes at least 20 characters of the source. |
| E-TOTAL | Base + alternates = total; unit-price lines sum to the base bid. |
| E-RANK / E-LOW | Published ranks match the numbers; a low-bid award to someone other than the low bidder needs a stated reason. |
| E-EE | Low/EE outside 0.3–3.0 is refused (usually a transcription slip). |
| E-SCHEMA | Derived columns (low_bid, gap, $/SF…) are refused in input; the tool computes them. |

Evidence ranks: `official_tab` > `board_award_item` > `portal_award_notice` > `news` > `search_snippet` > `internal`.
A weaker source never overwrites a stronger one; it is kept as an extra source. `search_snippet` marks a number
quoted from a search-result snippet when the page itself couldn't be fetched; the official document replaces
it on the next harvest. `date_basis` records what `bid_open_date` really is (`bid_open`, `award`, `board`,
`posted`) when a source gives no opening date. How to turn a tab PDF into a package:
[docs/EXTRACTION_PROTOCOL.md](docs/EXTRACTION_PROTOCOL.md). Where to find tabs: [docs/HARVEST_PROTOCOL.md](docs/HARVEST_PROTOCOL.md).

## Commands

```bash
B="python3 -m bid_tracker"
$B status
$B validate path/to/package                    # dry check
$B import-csv path/to/package --feed weekly    # validate + load (idempotent)
$B refresh-index                               # BLS PPI series; key from $BLS_API_KEY or private/bls_api_key
$B stats <agency>:<SOLICITATION-NO>              # one tab: gap, low/EE, CV, $/SF, bidders
$B stats --agency hcps                         # an agency's history
$B benchmark --project-type V-REN --agency-type school_district --gsf 6000   # gsf = the type's area kind
$B areas                                       # which vertical tabs still lack square footage
$B rates --service mold                        # disaster rate-card bands + price cliffs
$B competitors --top 25 | --name "Keystone" | --vs-ideal
$B gonogo --project-type V-REN --agency hcps --cost 500000
$B position --cost 500000 --ee 550000 --project-type V-REN --agency-type school_district --gsf 6000
$B position --method best_value --cost 100000 --competitor-price 110000 --price-weight 20 --nonprice-gap 5
$B pursuit update <sol_ref> --result lost --rank 3 --score 61.5 --lessons "..."
$B export-xlsx                                 # $BID_TRACKER_DATA/exports/FL-Bid-Pricing-<date>.xlsx
$B export-notion && $B notion-ack acks.json    # see docs/NOTION_SYNC.md
$B bidders review | merge "KEEP NAME" "DROP NAME"
```

## How the numbers are computed

Per tab, with responsive totals sorted b1 ≤ b2 ≤ … ≤ bN:

- **gap** = (b2 − b1)/b1, the money the low bidder left on the table
- **low/median** = b1 / median(b)
- **low/EE** = b1 / EE, only when the agency published a true engineer's estimate (`ee_source=ee`); budgets are kept separate
- **CV** = stdev(b)/mean(b), how tightly the field priced
- **low $/SF** = b1 / area, using the project type's preferred area kind: scope area only for renovation/TI/ADA,
  roof area for envelope, building GSF for new and MEP work

**Escalation:** amount × I(now)/I(bid month), using BLS PPI. The series is picked by `sources.toml`:

| Applies to | Series | Index |
|---|---|---|
| Schools | PCU236222236222 | new school building construction |
| Other vertical work | PCU236223236223 | new office building construction (BLS has no aggregate commercial series) |
| Restoration and fallback | WPUIP2300001 | inputs to construction industries, goods (BLS has no remediation series) |

**Benchmarks** group tabs by project type × agency type × region × size band. Size uses GSF bands when floor area is known, otherwise dollar bands. Only low-bid awards count, and term contracts are excluded. The output gives p25/p50/p75 of escalated low $/SF, low/EE, bidder count and gap.
Low $/SF only pools tabs whose area is the same kind (`--area-kind` to pick one).

- n < 5 is labelled **SMALL SAMPLE**.
- n < 3 shows the raw values instead of percentiles.
- A thin segment widens by dropping size, then agency type, then region, and says so.

**Position** (Friedman-style) works from the ratios r = competitor bid / EE (or / tab median) in the segment:

1. Fit ln r ~ N(μ, σ).
2. For cost C, reference R and markup m, the chance one competitor bids above you is P1(m) = 1 − Φ((ln(C(1+m)/R) − μ)/σ).
3. P(win) = Σ p(k)·P1(m)^k, where p(k) is the segment's empirical distribution of competitor counts.
4. E[profit] = P(win)·m·C − bid cost.

The model refuses to run with fewer than 10 competitor bids and flags fewer than 30. Once Ideal has 8 or more pursuits with tabs, it switches to Ideal's own cost as the reference (true Friedman). The table informs OH&P; it never lowers bond, insurance or general-conditions floors. In **best-value** mode it shows price points versus the competitor and the break-even bid. If closing the non-price gap would need a bid below cost, it says so: fix the proposal, not the number.

**Rate cards:**

- Market bands are p25/p50/p75 $/SF by service and size bucket.
- Lump-sum buckets are converted to $/SF at the bucket midpoint and marked derived.
- A cliff check flags any adjacent-bucket price jump over 1.25× (evaluators read a 2×+ jump for one extra square foot as a broken price curve).

**Go/no-go flags:**

- crowded field (median ≥ 8 bidders)
- tight gaps (median < 3%)
- protest history
- non-low awards at the agency
- agency EEs that run high
- bid above the single-job bond limit (STOP)
- bid over 3× Ideal's largest win

## Taxonomy

The project types are:

| Group | Code | Work |
|---|---|---|
| Vertical, core | V-TI | interior buildout |
| | V-REN | renovation |
| | V-ADA | ADA/restroom |
| | V-NEW-S | new building ≤ 20k GSF |
| Vertical, context | V-NEW-L | new building > 20k GSF |
| | V-ENV | envelope |
| | V-MEP | MEP-led renovation |
| Restoration, core | R-WATER | water |
| | R-MOLD | mold |
| | R-FIRE | fire |
| | R-MULTI | disaster term contract |
| Restoration, other | R-ABATE | abatement |
| Horizontal, schema only | H-ROAD, H-UTIL, H-SITE | road, utility and site work |

All 67 counties roll up to regions; `tampa_bay` covers Hillsborough, Pinellas, Pasco, Polk, Manatee, Sarasota, Hernando and Citrus.

## Tests

```bash
python -m pytest bid_tracker/tests -m "not integration" -q
```

Fixtures are synthetic only: `fake-` agencies, `https://example.invalid` URLs, and round made-up numbers. `--fixtures` mode refuses to load into the real DB.
