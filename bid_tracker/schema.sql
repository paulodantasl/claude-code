-- FL public bid pricing tracker — SQLite schema.
-- Rows arrive only through validated import packages (importer.py). Derived numbers
-- (ranks, gaps, $/SF, escalation) are computed in views or Python, never stored from input.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS project_types (
    code        TEXT PRIMARY KEY,
    work_class  TEXT NOT NULL CHECK (work_class IN ('vertical','restoration','horizontal')),
    label       TEXT NOT NULL,
    phase1_core INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS agencies (
    agency_id       TEXT PRIMARY KEY,           -- short slug, e.g. tampa, hillsborough-bocc, hcps
    name            TEXT NOT NULL,
    agency_type     TEXT NOT NULL CHECK (agency_type IN
                        ('city','county','school_district','airport','port','university',
                         'state','special_district','federal','other')),
    county          TEXT,
    region          TEXT,
    state           TEXT NOT NULL DEFAULT 'FL',
    portal_platform TEXT,
    portal_url      TEXT,
    watch           INTEGER NOT NULL DEFAULT 0, -- 1 = checked on every /bid-tabs weekly run
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id           INTEGER PRIMARY KEY,
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    kind             TEXT CHECK (kind IN ('csv','adapter','index')),
    adapter          TEXT,
    input_path       TEXT,
    input_sha256     TEXT,
    feed             TEXT CHECK (feed IN ('weekday','weekly','manual')),
    rows_in          INTEGER DEFAULT 0,
    rows_new         INTEGER DEFAULT 0,
    rows_updated     INTEGER DEFAULT 0,
    rows_rejected    INTEGER DEFAULT 0,
    status           TEXT CHECK (status IN ('ok','partial','failed')),
    summary          TEXT,
    notion_synced_at TEXT
);

CREATE TABLE IF NOT EXISTS bidders (
    bidder_id          INTEGER PRIMARY KEY,
    canonical_name     TEXT NOT NULL,
    name_key           TEXT NOT NULL UNIQUE,
    fl_license_no      TEXT,
    license_source_url TEXT,
    hq_city            TEXT,
    hq_county          TEXT,
    is_ideal           INTEGER NOT NULL DEFAULT 0,
    notes              TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_bidder_license ON bidders(fl_license_no) WHERE fl_license_no IS NOT NULL;

CREATE TABLE IF NOT EXISTS bidder_aliases (
    alias_key  TEXT PRIMARY KEY,
    bidder_id  INTEGER NOT NULL REFERENCES bidders(bidder_id) ON DELETE CASCADE,
    alias_raw  TEXT NOT NULL,
    source_url TEXT
);

CREATE TABLE IF NOT EXISTS solicitations (
    solicitation_id    INTEGER PRIMARY KEY,
    sol_ref            TEXT NOT NULL UNIQUE,     -- agency_id:SOLICITATION-NO (dedupe key)
    agency_id          TEXT NOT NULL REFERENCES agencies(agency_id),
    solicitation_no    TEXT NOT NULL,
    title              TEXT NOT NULL,
    procurement_method TEXT NOT NULL CHECK (procurement_method IN
                           ('ITB','RFP','RFQ','JOC','CMAR','DB','term_contract','emergency','other')),
    award_basis        TEXT NOT NULL CHECK (award_basis IN ('low_bid','best_value','qualifications','rate_card')),
    work_class         TEXT NOT NULL CHECK (work_class IN ('vertical','restoration','horizontal')),
    project_type       TEXT NOT NULL REFERENCES project_types(code),
    facility_type      TEXT,
    county             TEXT,
    region             TEXT,
    gsf                REAL,
    gsf_basis          TEXT CHECK (gsf_basis IN ('stated','measured','derived')),
    advertise_date     TEXT,
    bid_open_date      TEXT NOT NULL,
    date_basis         TEXT NOT NULL DEFAULT 'bid_open' CHECK (date_basis IN ('bid_open','award','board','posted')),
    engineers_estimate REAL,
    ee_source          TEXT CHECK (ee_source IN ('ee','budget','not_published')),
    award_amount       REAL,
    award_is_nte       INTEGER NOT NULL DEFAULT 0,
    awardee_bidder_id  INTEGER REFERENCES bidders(bidder_id),
    award_date         TEXT,
    award_status       TEXT CHECK (award_status IN
                           ('open','opened','recommended','awarded','rejected_all','cancelled','unknown')),
    bid_bond_pct       REAL,
    pp_bond_required   INTEGER,
    sbe_goal_pct       REAL,
    contract_days      INTEGER,
    ld_per_day         REAL,
    federal_funds      INTEGER,
    prequal_required   INTEGER,
    protest_filed      INTEGER NOT NULL DEFAULT 0,
    source_url         TEXT NOT NULL,
    source_excerpt     TEXT NOT NULL CHECK (length(source_excerpt) >= 20),
    evidence_class     TEXT NOT NULL CHECK (evidence_class IN
                           ('official_tab','board_award_item','portal_award_notice','news','search_snippet','internal')),
    retrieved_at       TEXT NOT NULL,
    extracted_by       TEXT NOT NULL,
    is_private         INTEGER NOT NULL DEFAULT 0,
    record_hash        TEXT NOT NULL,
    run_id             INTEGER REFERENCES ingest_runs(run_id),
    notes              TEXT
);
CREATE INDEX IF NOT EXISTS ix_sol_segment ON solicitations(project_type, region, bid_open_date);
CREATE INDEX IF NOT EXISTS ix_sol_agency ON solicitations(agency_id, bid_open_date);

CREATE TABLE IF NOT EXISTS solicitation_sources (
    solicitation_id INTEGER NOT NULL REFERENCES solicitations(solicitation_id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    excerpt         TEXT,
    evidence_class  TEXT,
    retrieved_at    TEXT,
    PRIMARY KEY (solicitation_id, url)
);

CREATE TABLE IF NOT EXISTS bids (
    bid_id          INTEGER PRIMARY KEY,
    solicitation_id INTEGER NOT NULL REFERENCES solicitations(solicitation_id) ON DELETE CASCADE,
    bidder_id       INTEGER NOT NULL REFERENCES bidders(bidder_id),
    bidder_name_raw TEXT NOT NULL,
    base_bid        REAL,
    alternates_json TEXT,
    total_bid       REAL,
    total_basis     TEXT CHECK (total_basis IN ('base','base+all_alts','base+accepted_alts','as_tabulated','rate_card')),
    rank_published  INTEGER,
    score_total     REAL,
    score_price     REAL,
    responsive      INTEGER,                     -- 1 yes, 0 no, NULL not stated
    withdrawn       INTEGER NOT NULL DEFAULT 0,
    is_awardee      INTEGER NOT NULL DEFAULT 0,
    page_ref        TEXT,
    source_url      TEXT NOT NULL,
    source_excerpt  TEXT,
    UNIQUE (solicitation_id, bidder_id)
);
CREATE INDEX IF NOT EXISTS ix_bids_bidder ON bids(bidder_id);

CREATE TABLE IF NOT EXISTS bid_items (
    item_id      INTEGER PRIMARY KEY,
    bid_id       INTEGER NOT NULL REFERENCES bids(bid_id) ON DELETE CASCADE,
    line_no      TEXT NOT NULL,
    item_desc    TEXT NOT NULL,
    unit         TEXT,
    qty          REAL,
    unit_price   REAL,
    extended     REAL,
    item_code    TEXT,
    csi_division TEXT,
    is_allowance INTEGER NOT NULL DEFAULT 0,
    UNIQUE (bid_id, line_no)
);

CREATE TABLE IF NOT EXISTS rate_cards (
    rate_id                 INTEGER PRIMARY KEY,
    solicitation_id         INTEGER NOT NULL REFERENCES solicitations(solicitation_id) ON DELETE CASCADE,
    bidder_id               INTEGER NOT NULL REFERENCES bidders(bidder_id),
    service                 TEXT NOT NULL CHECK (service IN
                                ('water','mold','fire','smoke','sewage','dryout','demo','contents',
                                 'board_up','labor_hourly','equipment_daily','other')),
    service_desc            TEXT,
    size_min_sf             REAL,
    size_max_sf             REAL,
    unit                    TEXT NOT NULL,       -- sf | lump | hr | day | each | ...
    price                   REAL NOT NULL,
    after_hours_premium_pct REAL,
    response_hrs            REAL,
    source_url              TEXT NOT NULL,
    source_excerpt          TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_rate ON rate_cards(
    solicitation_id, bidder_id, service, unit,
    ifnull(size_min_sf, -1), ifnull(size_max_sf, -1), ifnull(service_desc, ''));

CREATE TABLE IF NOT EXISTS cost_index_series (
    series_id  TEXT PRIMARY KEY,
    title      TEXT,
    applies_to TEXT                              -- comma list of project_type codes / work classes
);

CREATE TABLE IF NOT EXISTS cost_index (
    series_id    TEXT NOT NULL REFERENCES cost_index_series(series_id),
    period       TEXT NOT NULL,                  -- YYYY-MM
    value        REAL NOT NULL,
    preliminary  INTEGER NOT NULL DEFAULT 0,
    retrieved_at TEXT NOT NULL,
    PRIMARY KEY (series_id, period)
);

CREATE TABLE IF NOT EXISTS ideal_pursuits (
    pursuit_id           INTEGER PRIMARY KEY,
    solicitation_id      INTEGER NOT NULL UNIQUE REFERENCES solicitations(solicitation_id) ON DELETE CASCADE,
    decision             TEXT CHECK (decision IN ('go','no_go','pending')),
    decision_date        TEXT,
    decision_reason      TEXT,
    est_direct_cost      REAL,
    est_cost_pre_ohp     REAL,                   -- direct + GCs + bonds + insurance, before OH&P
    bid_amount           REAL,
    markup_pct           REAL,
    position_json        TEXT,
    result               TEXT CHECK (result IN ('won','lost','no_bid','rejected','pending','cancelled')),
    rank                 INTEGER,
    score_total          REAL,
    score_breakdown_json TEXT,
    debrief              TEXT,
    lessons              TEXT,
    estimate_dir         TEXT,
    updated_at           TEXT
);

CREATE TABLE IF NOT EXISTS records_requests (
    req_id          INTEGER PRIMARY KEY,
    agency_id       TEXT REFERENCES agencies(agency_id),
    solicitation_id INTEGER REFERENCES solicitations(solicitation_id),
    requested_on    TEXT,
    items           TEXT,
    status          TEXT,
    received_on     TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS notion_map (
    entity         TEXT NOT NULL,                -- bid_tab | bidder | pursuit | update
    local_ref      TEXT NOT NULL,
    notion_page_id TEXT,
    synced_hash    TEXT,
    synced_at      TEXT,
    PRIMARY KEY (entity, local_ref)
);

-- Bids that count for pricing: responsive (or not stated), not withdrawn, with a total.
CREATE VIEW IF NOT EXISTS v_bids_clean AS
SELECT b.*, s.sol_ref, s.award_basis, s.engineers_estimate, s.ee_source, s.gsf,
       s.project_type, s.work_class, s.region, s.county, s.bid_open_date, a.agency_type,
       br.canonical_name, br.is_ideal
FROM bids b
JOIN solicitations s ON s.solicitation_id = b.solicitation_id
JOIN agencies a ON a.agency_id = s.agency_id
JOIN bidders br ON br.bidder_id = b.bidder_id
WHERE ifnull(b.responsive, 1) = 1 AND b.withdrawn = 0 AND b.total_bid > 0;

CREATE VIEW IF NOT EXISTS v_bid_order AS
SELECT c.*,
       ROW_NUMBER() OVER (PARTITION BY c.solicitation_id ORDER BY c.total_bid, c.bid_id) AS price_rank,
       COUNT(*)     OVER (PARTITION BY c.solicitation_id) AS n_bidders,
       MIN(c.total_bid) OVER (PARTITION BY c.solicitation_id) AS low_bid
FROM v_bids_clean c;

CREATE VIEW IF NOT EXISTS v_solicitation_base AS
SELECT s.*, a.name AS agency_name, a.agency_type,
       (SELECT COUNT(*) FROM v_bids_clean c WHERE c.solicitation_id = s.solicitation_id) AS n_bidders,
       (SELECT MIN(c.total_bid) FROM v_bids_clean c WHERE c.solicitation_id = s.solicitation_id) AS low_bid,
       (SELECT o.total_bid FROM v_bid_order o WHERE o.solicitation_id = s.solicitation_id AND o.price_rank = 2) AS second_bid,
       (SELECT br.canonical_name FROM bidders br WHERE br.bidder_id = s.awardee_bidder_id) AS awardee_name
FROM solicitations s
JOIN agencies a ON a.agency_id = s.agency_id;

CREATE VIEW IF NOT EXISTS v_competitor_bids AS
SELECT o.bidder_id, o.canonical_name, o.is_ideal, o.solicitation_id, o.sol_ref, o.total_bid,
       o.low_bid, o.n_bidders, o.price_rank, o.engineers_estimate, o.ee_source,
       o.project_type, o.agency_type, o.region, o.county, o.bid_open_date, o.is_awardee,
       o.total_bid / o.low_bid - 1.0 AS pct_above_low
FROM v_bid_order o;
