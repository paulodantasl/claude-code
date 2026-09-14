"""
Turn relationships.yaml into `opportunities/` documents for the tracker.

These are the one exception to the machine/human split: `opportunities/` is
human-owned and no collector writes it, but PLAN.md §4 and Phase 5 call for
these eight rows to be seeded once so the developer and GC track sits on the
board next to real jobs instead of in a document nobody opens.

Dry run by default — prints what it would write. `--out DIR` writes one JSON
file per row for the Artifact tool's `write_db` to pick up by `file_path`.
"""
from __future__ import annotations

import argparse
import json
import os

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
YAML_PATH = os.path.join(HERE, "relationships.yaml")


def _one_line(text: str | None) -> str:
    return " ".join((text or "").split())


def build() -> list[dict]:
    with open(YAML_PATH) as fh:
        data = yaml.safe_load(fh)
    seeded_at = str(data.get("seeded_at"))
    owner = data.get("default_owner") or ""

    rows = []
    for target in sorted(data["targets"], key=lambda t: t["priority"]):
        rows.append({
            "_doc_id": target["id"],
            "name": target["name"],
            "hood": target["hood"],
            # `relationship` is its own trade on the board: these are not
            # fitouts and must never be counted as biddable value.
            "trade": "relationship",
            "stage": "signal",
            "valueEst": 0,
            "valueActual": 0,
            "source": "referral",
            "bidDate": str(target["due"]),
            "owner": owner,
            "nextAction": _one_line(target["action"]),
            "why": _one_line(target.get("why")),
            "sourceUrl": (target.get("url") or "").split(" | ")[0],
            "priority": target["priority"],
            "contacts": [],
            "seededAt": seeded_at,
            "createdAt": f"{seeded_at}T00:00:00Z",
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", help="write one JSON file per row into this directory")
    args = ap.parse_args(argv)

    rows = build()
    for r in rows:
        print(f"  [{r['priority']}] {r['_doc_id']:<22} {r['hood']:<20} due {r['bidDate']}")
        print(f"      {r['name']}")
        print(f"      → {r['nextAction'][:100]}")

    if not args.out:
        print(f"\n{len(rows)} relationship rows. DRY RUN — nothing written. "
              f"Re-run with --out DIR to emit documents.")
        return 0

    os.makedirs(args.out, exist_ok=True)
    for r in rows:
        doc = {k: v for k, v in r.items() if k != "_doc_id"}
        with open(os.path.join(args.out, f"{r['_doc_id']}.json"), "w") as fh:
            json.dump(doc, fh, indent=1)
    print(f"\nwrote {len(rows)} documents to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
