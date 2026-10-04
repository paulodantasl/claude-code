---
description: Harvest Florida public bid tabulations into the private bid-pricing DB, then sync Notion.
argument-hint: <tab URL | agency_id | weekly>
allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob, WebSearch, WebFetch
---

Harvest bid tabs for: **$ARGUMENTS**

You are the bid-data coordinator for Ideal Construction's FL public bid pricing tracker (`bid_tracker/`).
The code is in this public repo. **The data is not**: it lives in the private `paulodantasl/ideal-bid-data`
repo, cloned to `$BID_TRACKER_DATA`. Never write tab data, numbers from tabs, or Ideal's pricing into this
repo, its commit messages, or a PR.

0. **Setup.** Read `bid_tracker/README.md`, `bid_tracker/docs/HARVEST_PROTOCOL.md` and
   `bid_tracker/docs/EXTRACTION_PROTOCOL.md`. Confirm `BID_TRACKER_DATA` points at a clone of the private
   data repo (clone it if missing), then `python3 -m bid_tracker rebuild` if `bids.db` is absent.
   Check that agency hosts are reachable (e.g. `curl -sI https://www.tampa.gov`). If they are blocked,
   say which hosts are blocked and stop. Don't build rows from search snippets unless Paulo asks for that.

1. **Find tabs.**
   - A URL: that tab.
   - An `agency_id`: that agency's tabs since its last row in the DB.
   - `weekly`: every `watch=1` agency in `bid_tracker/reference/agencies.csv`, posted since the last
     Bid Pricing Updates row.
   Phase-1 scope is Tampa Bay vertical building (V-*) and disaster/restoration (R-*) from 2023 on.

2. **Extract.** Run one subagent per agency (in parallel), each following EXTRACTION_PROTOCOL.md. Each one
   writes a package to `$BID_TRACKER_DATA/packages/<YYYY-MM-DD>-<agency>-<slug>/` and runs
   `python3 -m bid_tracker validate <package>` until there are 0 errors. Every number must be quoted from
   its source. A blank beats a guess.

3. **Verify.** A separate subagent re-reads about 10% of the new bid rows (at least 3, always including
   the low bids) against the source PDFs and reports any mismatch. Fix mismatches before importing.

4. **Import.** Run `python3 -m bid_tracker import-csv <package> --feed weekly|manual` for each package.
   Log any Ch. 119 requests still needed (winners' cost sheets on jobs Ideal bid) in the report.

5. **Persist.** In the data repo: `git add packages index private && git commit -m "Harvest <date>: <n> tabs"`
   and push.

6. **Notion.** Follow `bid_tracker/docs/NOTION_SYNC.md`:
   - Run `export-notion --feed weekly|manual`.
   - Apply the manifest with the Notion MCP into the FL Public Bid Pricing databases. The data-source ids
     are in `$BID_TRACKER_DATA/notion_ids.json`.
   - Run `notion-ack`.
   - Repeat until no relations are pending.
   - Add the Bid Pricing Updates row. If the run found nothing new, skip this row.

7. **Report.**
   - New and updated tabs, each with its source link.
   - Segments whose benchmark moved.
   - New competitors.
   - Validator warnings left open.
   - Blocked sources.
   Keep it short. Cite the source document for every number.
