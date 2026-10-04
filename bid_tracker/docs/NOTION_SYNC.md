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
2. Claude applies the ops with the Notion MCP: `create-pages` into the data source for `create`,
   `update-page` for `update`. Set relation properties to the page URLs in `relations`.
3. Write `acks.json`: `[{"db": "...", "ref": "...", "page_id": "...", "hash": "..."}]` for every applied op.
4. `python3 -m bid_tracker notion-ack acks.json` records page ids and hashes in `notion_map`.
5. Run export once more: ops whose relations were pending now resolve. Repeat until no pending relations.

The Notion data-source ids live in `$BID_TRACKER_DATA/notion_ids.json` (private).
