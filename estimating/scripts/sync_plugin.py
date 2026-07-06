#!/usr/bin/env python3
"""Fan canonical estimating/ files out to every copy in the plugin tree.

SOURCE OF TRUTH: estimating/reference/, estimating/templates/, estimating/scripts/.
Every same-named file under plugins/construction-estimating/ (reference/, templates/,
scripts/, skills/*/resources/, skills/*/scripts/, claude-ai-project/knowledge/) is a
GENERATED COPY — never hand-edit a copy; edit the canonical file and run this.

Intentionally divergent (never synced): plugins/.../agents/, plugins/.../commands/
(path-adapted for ${CLAUDE_PLUGIN_ROOT}), and claude-ai-project files with no
canonical counterpart (PROJECT_INSTRUCTIONS.md, deliverable-templates.md — those are
chat-specific transforms).

Usage:
    python3 estimating/scripts/sync_plugin.py --check   # list drift, exit 1 if any
    python3 estimating/scripts/sync_plugin.py --write   # copy canonical over copies

Run --check before committing any change under estimating/; run --write after
editing a canonical file, then bump the plugin version for the next release.
"""

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CANONICAL_DIRS = [
    REPO / "estimating" / "reference",
    REPO / "estimating" / "templates",
    REPO / "estimating" / "scripts",
]
PLUGIN = REPO / "plugins" / "construction-estimating"
COPY_GLOBS = [
    "reference/*",
    "templates/*",
    "scripts/*",
    "skills/*/resources/*",
    "skills/*/scripts/*",
    "claude-ai-project/knowledge/*",
]
# Copies allowed to diverge from a same-named canonical file (chat transforms etc.).
EXEMPT = set()
SELF = Path(__file__).resolve()


def canonical_files():
    for d in CANONICAL_DIRS:
        for f in sorted(d.iterdir()):
            if f.is_file() and not f.name.startswith(".") and f.resolve() != SELF:
                yield f


def copies_of(name):
    for pattern in COPY_GLOBS:
        for f in sorted(PLUGIN.glob(pattern)):
            if f.is_file() and f.name == name and f.relative_to(REPO).as_posix() not in EXEMPT:
                yield f


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report drift, exit 1 if any")
    mode.add_argument("--write", action="store_true", help="copy canonical over drifted copies")
    args = ap.parse_args()

    drifted, synced, total_copies = [], [], 0
    for src in canonical_files():
        for dst in copies_of(src.name):
            total_copies += 1
            if filecmp.cmp(src, dst, shallow=False):
                continue
            if args.write:
                shutil.copy2(src, dst)
                synced.append(dst)
            else:
                drifted.append((src, dst))

    if args.check:
        if drifted:
            print(f"DRIFT: {len(drifted)} copies differ from canonical:")
            for src, dst in drifted:
                print(f"  {dst.relative_to(REPO)}  !=  {src.relative_to(REPO)}")
            print("Fix: edit the CANONICAL file, then run sync_plugin.py --write "
                  "(never hand-edit a plugin copy).")
            sys.exit(1)
        print(f"OK: all {total_copies} plugin copies match canonical.")
    else:
        for dst in synced:
            print(f"synced {dst.relative_to(REPO)}")
        print(f"Done: {len(synced)} copies updated, "
              f"{total_copies - len(synced)} already in sync.")


if __name__ == "__main__":
    main()
