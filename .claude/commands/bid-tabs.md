---
description: Harvest Florida public bid tabulations into the private bid-pricing DB, then sync Notion.
argument-hint: <tab URL | agency_id | weekly>
allowed-tools: Agent, Workflow, Read, Write, Edit, Bash, Grep, Glob, WebSearch, WebFetch
---

Harvest bid tabs for: **$ARGUMENTS**

You are the bid-data coordinator for Ideal Construction's FL public bid pricing tracker.

**Paths:**
- Code: this public repo at `/home/user/claude-code`.
- Data: the private `paulodantasl/ideal-bid-data` repo, cloned at `/home/user/ideal-bid-data` (called **D** below).

**Shell variables don't persist between Bash calls, and subagents start fresh.** So run every tool command in full, and give subagents absolute paths, never `$BID_TRACKER_DATA`:

`cd /home/user/claude-code && BID_TRACKER_DATA=/home/user/ideal-bid-data python3 -m bid_tracker <command>`

This is written **BT** below. A tool run without it silently uses an empty scratch DB.

## Rules (paste them verbatim into every subagent or workflow prompt you start)
- **Keep private data out of the public repo:**
  - Never put tab data, Ideal's pricing, anything from `D/private/` or the BLS key into `/home/user/claude-code`, a commit there, or a PR.
  - Treat `/home/user/claude-code` as read-only during a harvest: no edits, commits or branches. If a code bug blocks a step, report it and skip that step.
- **Fetch honestly:**
  - Use the User-Agent `ideal-bid-tracker/0.1 (public records research)`.
  - A 403/429, a challenge page, a CAPTCHA or a login means: stop fetching that host, log it as blocked, and use the agency's board-agenda system (HARVEST_PROTOCOL.md) or list a Ch. 119 request.
  - Never retry with a browser User-Agent, changed headers, a headless or signed-in browser, or another proxy.
- **Numbers:** every number is copied from a saved official document, to the cent. A blank beats a guess. Never build rows from search snippets unless Paulo asks.
- **No messages:** send no email or messages and file no records requests. Paulo does that.
- **Writes:** write only to git in D and to the FL Public Bid Pricing databases in Notion.

## 0. Setup
1. Read `bid_tracker/README.md` and `bid_tracker/docs/{HARVEST_PROTOCOL,EXTRACTION_PROTOCOL,NOTION_SYNC}.md`.
2. Update both repos with `git -C <repo> pull`.
3. If D's `git log -1 --format=%s` already says `Harvest <today>`, report that and stop: another run got here first.
4. Run `BT rebuild`. It replays every package, preloads agencies, applies `private/bidder_aliases.csv` and restores Notion page IDs from `notion_map.csv`.
5. Run `BT status`. It must show `data dir: /home/user/ideal-bid-data` and at least as many solicitations as the last Bid Pricing Updates row. If not, stop.
6. **Cost index, once a month:** if `D/index/` has no folder starting with the current `YYYY-MM`, run `BT refresh-index`.
   - It reads the key from `D/private/bls_api_key`.
   - If the new `cost_index.csv` matches the previous one apart from `retrieved_at`, delete the new folder.
   - If BLS refuses, note "BLS refresh failed" in the report and go on. Never print the error text.
7. **Reachability.** For each `watch=1` agency host, run:
   `curl -s -o /dev/null -A "ideal-bid-tracker/0.1 (public records research)" -w "%{http_connect} %{http_code}\n" <url>`
   - `http_connect` not 200 means the proxy refused. Name the hosts, and stop if none are reachable.
   - A 403 after `http_connect` 200 is the site's own wall. See the Rules.

## 1. Find tabs
- **A URL:** that tab.
- **An `agency_id`:** that agency.
- **`weekly`:** every `watch=1` agency in `bid_tracker/reference/agencies.csv`. Its notes and HARVEST_PROTOCOL.md say where the numbers are.

**Look-back window.** Award items reach boards weeks after the opening, and some rows carry a board date. So check postings, board agendas and award notices dated on or after the earlier of (today − 120 days) and (the agency's newest date − 120 days). Get the newest dates from:

`cd /home/user/claude-code && BID_TRACKER_DATA=/home/user/ideal-bid-data python3 -c "from bid_tracker import db; c=db.connect(db.default_db_path()); [print(*r) for r in c.execute('SELECT a.agency_id, max(s.bid_open_date) FROM agencies a LEFT JOIN solicitations s ON s.agency_id=a.agency_id AND s.is_private=0 WHERE a.watch=1 GROUP BY 1')]"`

Agencies with no rows look back 120 days only. No backfill.

**Scope:** vertical building (V-*) and disaster/restoration (R-*), 2023 on. Skip roads, utilities, site-only work, design services and qualifications-only selections.

**Refs.** Build them with `bid_tracker.canonical.make_sol_ref(agency_id, solicitation_no)`. Skip a ref already in the DB unless:
- the new document is a stronger source (official_tab > board_award_item > portal_award_notice > news > search_snippet), or
- it moves award_status forward (opened/recommended/unknown → awarded).

Extract those as updates. Also re-try the refs in `D/private/holdback.csv`, the packages held back last run.

## 2. Extract (subagents; never write `D/bids.db`)
Run one subagent per agency, using the Workflow tool if it's available, else Agent. Each subagent:
- follows EXTRACTION_PROTOCOL.md;
- saves sources under `D/raw/<agency_id>/` (gitignored);
- writes one package to `D/staging/<run date>-<agency_id>/`, with the run date from `date -u +%F` (staging is gitignored);
- validates against **its own copy** of the live DB until there are 0 errors:
  `cp /home/user/ideal-bid-data/bids.db /tmp/<agency_id>.db && cd /home/user/claude-code && BID_TRACKER_DATA=/home/user/ideal-bid-data python3 -m bid_tracker --db /tmp/<agency_id>.db validate <package>`.

Subagents never run `import-csv`, `rebuild` or `notion-ack`.

## 3. Check every package (independent; replaces sampling)
For each staged package, a **separate** subagent:
- lists every bidder and total from the saved sources before opening `bids.csv`;
- then compares names (verbatim), totals (to the cent), responsive flags, dates, award, evidence class and scope;
- validates against its own DB copy, the same way as step 2.

On a blocking issue:
1. One repair agent fixes only what the source confirms.
2. One recheck follows.
3. A package that still fails stays in `staging/`. Add its refs and the reason to `D/private/holdback.csv` (columns: `sol_ref, reason, first_held`) and report it.

## 4. Import (coordinator only)
1. **Benchmarks before.** For each `(project_type, agency_type)` the checked packages touch, run `BT benchmark --project-type X --agency-type Y --json > /tmp/bm_before_X_Y.json`.
2. **Import.** For each package that passed, `mv` it from `D/staging/` to `D/packages/<run date>-<agency_id>` (add `-2`, `-3` and so on if that exists; never write into an existing package). Then run `BT import-csv <that path> --feed weekly`. Remove its refs from `holdback.csv`.
3. **Duplicates.**
   - Run `BT bidders review --threshold 0.85`, read the W-NAME warnings from validation, and list short forms with:
     `cd /home/user/claude-code && BID_TRACKER_DATA=/home/user/ideal-bid-data python3 -c "from bid_tracker import db; c=db.connect(db.default_db_path()); r=c.execute('SELECT canonical_name n, name_key k FROM bidders').fetchall(); [print(repr(a['n']),'<',repr(b['n'])) for a in r for b in r if a['k']!=b['k'] and b['k'].startswith(a['k']+' ')]"`
   - Merge only clear same-firm pairs: a typo, a cut-off name, a short form on the same agency's tab, or the same FL license. Use `BT bidders merge "<keep>" "<drop>"`.
   - Never merge because two names share a generic word ("Construction", "Roofing").
4. **Re-key.** If a source shows a record already in the DB carries the wrong solicitation number:
   1. Remove every row keyed by the old ref from every file that carries it. Find them with `grep -rl '<old ref>' D/packages D/private`; they can be in solicitations, bids, bid_items, rate_cards or ideal_pursuits.
   2. In `D/notion_map.csv`, change its `bid_tab` (and any `pursuit`) `local_ref` to the new ref.
   3. Run `BT rebuild` before any `notion-ack`.
5. **Benchmarks after.** Rerun the benchmarks and note changes in n, the p50 gap and p50 bidders.

## 5. Persist (data repo only)
1. Stage the data:
   `git -C /home/user/ideal-bid-data add packages index private exports notion_map.csv notion_ids.json && git -C /home/user/ideal-bid-data diff --cached --stat`.
2. Stop if any staged file is over 5 MB, or is a .pdf/.png/.jpg/.html/.db, or if a package is deleted that you didn't delete on purpose (re-key).
3. Commit and push:
   `git -C /home/user/ideal-bid-data commit -m "Harvest <today>: <n> tabs" && git -C /home/user/ideal-bid-data push`.

## 6. Notion
Follow NOTION_SYNC.md. The IDs are in `D/notion_ids.json`.

1. **Manifest.** Run `BT export-notion --feed weekly`. If it refuses because notion_map is empty, stop: the wrong data dir or a lost map. Never pass `--first-sync` here.
2. **Options.** For each property in the manifest's `options` block:
   1. Fetch the data source and copy every option it already has (name and color).
   2. Add the missing values.
   3. Send one `ALTER COLUMN "<prop>" SET SELECT(...)`, or `SET MULTI_SELECT(...)` for Agencies, Counties and Project Types, with that union. Never send a list shorter than the current one.
   4. Re-fetch afterwards. If an option disappeared, stop and report.
3. **Apply ops in chunks:**
   - creates: one `create-pages` call per ~30 pages;
   - updates: ~10 pages per agent; tab updates need `update_properties` and then `replace_content`.
   - **Before every create**, query the data source for a page whose `Ref` equals `op.ref`. If one exists, update that page and ack it with its id. This keeps a re-run from creating duplicates.
4. **Order:**
   1. Write bidders, then run `BT notion-ack <acks.json>`.
   2. Re-export, write the tabs, and ack.
   3. Repeat until `export-notion` reports `ops: {}`.
   - After every ack, run `git -C /home/user/ideal-bid-data add notion_map.csv && git -C /home/user/ideal-bid-data commit -m "Notion map" && git -C /home/user/ideal-bid-data push`.
5. **Merged-away firms.** `BT notion-orphans` lists bidder pages of merged-away firms. If it lists more than 5, stop and report. Otherwise:
   1. Move those page IDs with `move-pages` to `notion_ids.json` → `retired_bidders_page`.
   2. Run `BT notion-orphans --forget`.
   3. Commit `notion_map.csv` as above.
6. **Bid Pricing Updates row.** Write it **once**, from the `updates` op of the pass in which you write tabs, and only if step 4 imported at least one new or updated solicitation. Ignore `updates` ops in every other pass.

## 7. Report
Short, with a source link for each tab. Public tab numbers are fine. Never include Ideal's cost, markup, bids, rate cards, anything from `private/`, the BLS key, or raw command or error output; describe failures in your own words. Include:
- new and updated tabs;
- benchmark changes (n, p50 gap, p50 bidders) by segment;
- new competitors and merges made;
- packages held back and why;
- blocked hosts, and `watch=1` agencies with no reachable source;
- Ch. 119 requests Paulo should send (agency, solicitation, what to ask for);
- whether the cost index was refreshed or failed;
- the data-repo commit SHA and a link to the Bid Pricing Updates row.
