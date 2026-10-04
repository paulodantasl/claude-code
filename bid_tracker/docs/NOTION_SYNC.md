# Notion sync

Notion is the team-facing mirror under **Ideal Ops Knowledge → FL Public Bid Pricing**. The private data repo
is the source of truth; Notion edits are overwritten on the next sync.

## Databases (schema in `notion.py` → `NOTION_SCHEMA`; print with `python3 -m bid_tracker notion-schema`)

- **Bid Tabs**: one row per solicitation; page body has the full bid table, unit prices, rate card.
- **Bidders**: every firm seen on a tab, with win rate, median % above low, median bid/EE.
- **Ideal Pursuits**: Ideal's own bids: decision, cost, bid, markup, result, debrief.
- **Bid Pricing Updates**: one row per sync run (same shape as Dental PSF Updates).

Relations: Bid Tabs ↔ Bidders ("Bidders on Tab"), Bid Tabs ↔ Ideal Pursuits ("Pursuit").

## Run

1. `python3 -m bid_tracker export-notion --feed weekly` writes `$BID_TRACKER_DATA/notion_out/<run>/manifest.json`.
   Each op: `{db, ref, op: create|update, page_id, hash, properties, content, relations, pending_relations}`.
   Properties are already in the Notion MCP's expanded format (`date:Bid Open:start`, `__YES__`).
2. Notion rejects a select / multi-select value that isn't already an option. For each property in the
   manifest's `options` block (`{db: {property: [values]}}`): fetch the data source, copy every option it
   already has (name and color), add the missing values, and send one `update-data-source` with
   `ALTER COLUMN "<prop>" SET SELECT(...)`, or `SET MULTI_SELECT(...)` for multi-selects (Agencies,
   Counties, Project Types). Either form replaces the whole list, so never send a list shorter than the
   current one; re-fetch afterwards and stop if an option disappeared.
3. Apply the ops with the Notion MCP: `create-pages` into the data source for `create`, `update-page` for
   `update` (`update_properties`, then `replace_content` for tab bodies). Set relation properties to the page
   URLs in `relations`. Before a create, look for an existing page with the same `Ref` and update that instead,
   so a re-run never duplicates pages. Write bidders first so tab relations resolve on the next pass. Only one
   `updates` op per run becomes a Bid Pricing Updates row.
4. Write `acks.json`: `[{"db": "...", "ref": "...", "page_id": "...", "hash": "..."}]` for every applied op.
5. `python3 -m bid_tracker notion-ack acks.json` records page ids and hashes in `notion_map` and writes them to
   `notion_map.csv` next to the DB. Commit and push that file after every ack: `rebuild` reloads it, so a
   fresh DB updates the existing pages instead of creating duplicates. `export-notion` refuses to run with an
   empty map on a non-empty DB (wrong data dir or a lost map); `--first-sync` is only for a new workspace.
6. Run export once more: ops whose relations were pending now resolve. Repeat until `ops: {}`.
7. Bidder pages of firms merged away (`bidders merge` / `private/bidder_aliases.csv`) no longer get updates.
   `notion-orphans` lists them; move those pages to the "Retired bidder pages" page
   (`notion_ids.json` → `retired_bidders_page`), then `notion-orphans --forget` and commit `notion_map.csv`.

The Notion data-source ids live in `$BID_TRACKER_DATA/notion_ids.json` (private).
