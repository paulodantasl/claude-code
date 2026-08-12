#!/usr/bin/env python3
"""Keep the construction-estimating toolkit's duplicated trees in sync.

The same knowledge base is deliberately present in several places, because each
surface loads files a different way:

    estimating/{reference,templates,scripts}    CANONICAL — edit here
      -> plugins/construction-estimating/{reference,templates,scripts}
           the portable plugin bundle (paths via ${CLAUDE_PLUGIN_ROOT})
      -> plugins/construction-estimating/skills/<skill>/{resources,scripts}
           self-contained Agent Skills — each must carry its own copy so the
           folder zips cleanly for Claude Cowork / claude.ai upload
      -> .claude/skills/<skill>
           repo-level mirror so the skills load in this repo and in Claude Code
           on the web sessions opened against it

Agents and the /bid* commands are NOT handled here: those are authored
separately per surface (the plugin copies carry ${CLAUDE_PLUGIN_ROOT} paths and
an extra plugin-paths section). The per-stage commands (/takeoff, /scope, ...)
ARE handled, because they are written to be byte-identical on every surface.

Usage:
    python3 estimating/sync.py --check    # drift gate, exit 1 on any difference
    python3 estimating/sync.py --write    # regenerate every derived copy
"""

import argparse
import filecmp
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CANON = REPO / "estimating"
PLUGIN = REPO / "plugins" / "construction-estimating"
DOT = REPO / ".claude"

# Canonical dir -> plugin dir. Every file in the canonical dir is mirrored.
BUNDLE_DIRS = ["reference", "templates", "scripts"]

# Files that legitimately differ per surface: they quote the path of a bundled
# script, and each surface loads scripts from a different place (repo-relative
# `estimating/scripts/`, plugin `${CLAUDE_PLUGIN_ROOT}/scripts/`, skill-local
# `resources/`). These are authored per surface. Sync still checks that a copy
# EXISTS everywhere it should, it just does not compare or overwrite bytes.
PER_SURFACE = {"templates/estimate-workbook.md"}

# Files each skill carries so it is self-contained when zipped for upload.
# Keys are skill names; values map the destination subdir to canonical files.
SKILL_FILES = {
    "construction-takeoff": {
        "resources": [
            "reference/takeoff-accuracy-protocol.md",
            "reference/csi-divisions.md",
            "reference/florida-code.md",
            "reference/jobtread-takeoff-protocol.md",
            "templates/takeoff-template.md",
        ],
        "scripts": ["scripts/jobtread_takeoff.py"],
    },
    "construction-estimating": {
        "resources": [
            "reference/estimating-accuracy-protocol.md",
            "reference/estimating-methodology.md",
            "reference/florida-code.md",
            "templates/estimate-workbook.md",
            "scripts/build_estimate_xlsx.py",
            "scripts/validate_estimate.py",
        ],
    },
    "estimate-audit": {
        "resources": [
            "reference/estimating-accuracy-protocol.md",
            "reference/takeoff-accuracy-protocol.md",
            "reference/csi-divisions.md",
            "templates/audit-checklist.md",
            "scripts/validate_estimate.py",
        ],
    },
    "material-procurement": {
        "resources": [
            "reference/florida-code.md",
            "templates/procurement-template.md",
        ],
    },
    "public-bid": {
        "resources": [
            "reference/sector-public-bidding.md",
            "reference/estimating-accuracy-protocol.md",
            "reference/takeoff-accuracy-protocol.md",
            "reference/csi-divisions.md",
            "reference/florida-code.md",
        ],
    },
    "residential-construction": {
        "resources": [
            "reference/sector-residential-new.md",
            "reference/estimating-accuracy-protocol.md",
            "reference/takeoff-accuracy-protocol.md",
            "reference/csi-divisions.md",
            "reference/florida-code.md",
        ],
    },
    "commercial-construction": {
        "resources": [
            "reference/sector-commercial-new.md",
            "reference/estimating-accuracy-protocol.md",
            "reference/takeoff-accuracy-protocol.md",
            "reference/csi-divisions.md",
            "reference/florida-code.md",
        ],
    },
    "tenant-improvement": {
        "resources": [
            "reference/sector-tenant-improvement.md",
            "reference/estimating-accuracy-protocol.md",
            "reference/takeoff-accuracy-protocol.md",
            "reference/csi-divisions.md",
            "reference/florida-code.md",
        ],
    },
}

# Per-stage commands, byte-identical on every surface. The /bid* commands are
# intentionally absent — they are authored per surface.
STAGE_COMMANDS = [
    "takeoff.md",
    "scope.md",
    "estimate.md",
    "proposal.md",
    "audit.md",
    "procure.md",
    "loan-package.md",
]

SKIP_DIRS = {"__pycache__", ".pytest_cache"}


def canonical_files(subdir):
    """Every tracked file directly under a canonical bundle dir."""
    root = CANON / subdir
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.suffix != ".pyc"
    )


def pairs():
    """Build the (source, destination) list of files mirrored verbatim.

    Returns (mirrored, per_surface): per_surface holds destinations that must
    exist but are authored separately and so are never compared or overwritten.
    """
    out, authored = [], []

    # 1. canonical -> plugin bundle
    for subdir in BUNDLE_DIRS:
        for src in canonical_files(subdir):
            dst = PLUGIN / subdir / src.name
            if f"{subdir}/{src.name}" in PER_SURFACE:
                authored.append(dst)
            else:
                out.append((src, dst))

    # 2. canonical -> each skill's bundled copy
    for skill, groups in SKILL_FILES.items():
        for dest_subdir, rels in groups.items():
            for rel in rels:
                src = CANON / rel
                dst = PLUGIN / "skills" / skill / dest_subdir / Path(rel).name
                if rel in PER_SURFACE:
                    authored.append(dst)
                else:
                    out.append((src, dst))

    # 3. plugin skills -> repo-level .claude/skills mirror (verbatim)
    skills_root = PLUGIN / "skills"
    if skills_root.is_dir():
        for src in sorted(skills_root.rglob("*")):
            if not src.is_file() or src.suffix == ".pyc":
                continue
            if SKIP_DIRS & set(src.relative_to(skills_root).parts):
                continue
            out.append((src, DOT / "skills" / src.relative_to(skills_root)))

    # 4. plugin stage commands -> repo-level .claude/commands
    for name in STAGE_COMMANDS:
        out.append((PLUGIN / "commands" / name, DOT / "commands" / name))

    return out, authored


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true",
                      help="report drift and exit 1; changes nothing")
    mode.add_argument("--write", action="store_true",
                      help="regenerate every derived copy from canonical")
    args = ap.parse_args()

    mirrored, authored = pairs()
    missing_src, drifted, written = [], [], []

    for src, dst in mirrored:
        if not src.is_file():
            missing_src.append(src)
            continue
        if dst.is_file() and filecmp.cmp(src, dst, shallow=False):
            continue
        if args.check:
            drifted.append(dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            written.append(dst)

    # Per-surface files are authored by hand; only their absence is an error.
    absent_authored = [d for d in authored if not d.is_file()]

    for src in missing_src:
        print(f"MISSING SOURCE  {src.relative_to(REPO)}", file=sys.stderr)
    for dst in absent_authored:
        print(f"MISSING (per-surface, author by hand)  {dst.relative_to(REPO)}",
              file=sys.stderr)

    if args.check:
        for dst in drifted:
            state = "differs from canonical" if dst.exists() else "absent"
            print(f"DRIFT  {dst.relative_to(REPO)}  ({state})", file=sys.stderr)
        if drifted or missing_src or absent_authored:
            print(f"\n{len(drifted)} drifted, "
                  f"{len(missing_src) + len(absent_authored)} missing. "
                  f"Run: python3 estimating/sync.py --write", file=sys.stderr)
            return 1
        print(f"In sync — {len(mirrored)} mirrored file(s) match canonical, "
              f"{len(authored)} per-surface file(s) present.")
        return 0

    for dst in written:
        print(f"wrote  {dst.relative_to(REPO)}")
    problems = len(missing_src) + len(absent_authored)
    print(f"\n{len(written)} file(s) updated"
          + (f", {problems} missing" if problems else "")
          + ".")
    return 1 if problems else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # Output was piped into something that stopped reading (`| head`).
        os._exit(0)
