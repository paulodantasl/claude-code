#!/usr/bin/env python3
"""Install the construction-estimating toolkit into your personal Claude directory.

This is the "permanent local" path: it copies the agents, slash commands, skills,
and knowledge base into `~/.claude/`, so they are available in EVERY folder on
this machine, in every future session, with no marketplace and no network.

    python3 estimating/install.py              # install / update
    python3 estimating/install.py --check      # report what is installed
    python3 estimating/install.py --uninstall  # remove exactly what we installed

What lands where:

    ~/.claude/construction-estimating/   knowledge base (reference, templates, scripts)
    ~/.claude/agents/                    6 specialist subagents
    ~/.claude/commands/                  /bid* pipeline + per-stage commands
    ~/.claude/skills/                    8 Agent Skills

Agents and commands are copied from the portable plugin bundle, which refers to
its files as `${CLAUDE_PLUGIN_ROOT}/…`. That variable only expands for an
installed plugin, so on the way in every occurrence is rewritten to the real
absolute install path. Skills need no rewriting — they reference their own
bundled `resources/` relatively and are self-contained by design.

Already using the marketplace plugin (`/plugin install construction-estimating`)?
Pick one or the other. Running both puts two copies of every agent, command, and
skill in front of the model. `--check` warns when it detects the plugin too.

Nothing here touches your project data: deliverables always go to the working
directory you run Claude in, never into the install.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "construction-estimating"

PLACEHOLDER = "${CLAUDE_PLUGIN_ROOT}"
MANIFEST_NAME = ".install-manifest.json"
MANIFEST_VERSION = 1

# Bundle subdirs copied verbatim into the knowledge-base root.
BUNDLE_DIRS = ["reference", "templates", "scripts"]
SKIP_NAMES = {"__pycache__", ".pytest_cache", ".DS_Store"}


def is_junk(path: Path) -> bool:
    return path.suffix == ".pyc" or bool(SKIP_NAMES & set(path.parts))


def walk(root: Path):
    if not root.is_dir():
        return
    for p in sorted(root.rglob("*")):
        if p.is_file() and not is_junk(p.relative_to(root)):
            yield p


def plan(prefix: Path):
    """Return (kb_root, [(src, dst)]) for everything we install."""
    kb = prefix / "construction-estimating"
    items = []

    for sub in BUNDLE_DIRS:
        for src in walk(PLUGIN / sub):
            items.append((src, kb / sub / src.relative_to(PLUGIN / sub)))

    for src in walk(PLUGIN / "agents"):
        items.append((src, prefix / "agents" / src.name))

    for src in walk(PLUGIN / "commands"):
        items.append((src, prefix / "commands" / src.name))

    for src in walk(PLUGIN / "skills"):
        items.append((src, prefix / "skills" / src.relative_to(PLUGIN / "skills")))

    return kb, items


def copy_rewritten(src: Path, dst: Path, kb_str: str) -> None:
    """Copy src to dst, resolving ${CLAUDE_PLUGIN_ROOT} to the install path.

    Rewriting is decided by content, not by directory: any bundled file may
    quote a plugin-root path (the estimate-workbook template does), and a stale
    placeholder in an installed file points the model at a path that cannot
    exist. Files that are not UTF-8 text are copied byte-for-byte.
    """
    try:
        text = src.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        shutil.copy2(src, dst)
        return
    if PLACEHOLDER in text:
        dst.write_text(text.replace(PLACEHOLDER, kb_str), encoding="utf-8")
    else:
        shutil.copy2(src, dst)


def read_manifest(kb: Path):
    f = kb / MANIFEST_NAME
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def do_install(prefix: Path, force: bool) -> int:
    if not PLUGIN.is_dir():
        print(f"error: cannot find the plugin bundle at {PLUGIN}\n"
              f"Run this from a clone of the toolkit repo.", file=sys.stderr)
        return 1

    kb, items = plan(prefix)
    kb_str = str(kb)
    previous = read_manifest(kb)
    owned = set((previous or {}).get("files", []))

    written, skipped = [], []
    for src, dst in items:
        rel = str(dst.relative_to(prefix))
        # Never silently clobber a file we did not put there (e.g. your own
        # /estimate command). Ours are listed in the previous manifest.
        if dst.exists() and rel not in owned and not force:
            skipped.append(rel)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        copy_rewritten(src, dst, kb_str)
        written.append(rel)

    # Remove files from a previous install that this version no longer ships.
    removed = []
    for rel in sorted(owned - set(written)):
        stale = prefix / rel
        if stale.is_file():
            stale.unlink()
            removed.append(rel)
            for parent in stale.parents:
                if parent == prefix or not parent.is_dir():
                    break
                if any(parent.iterdir()):
                    break
                parent.rmdir()

    kb.mkdir(parents=True, exist_ok=True)
    (kb / MANIFEST_NAME).write_text(json.dumps(
        {"manifest_version": MANIFEST_VERSION,
         "installed_from": str(REPO),
         "knowledge_base": kb_str,
         "files": sorted(written)},
        indent=2) + "\n")

    print(f"Installed {len(written)} file(s) into {prefix}")
    print(f"  knowledge base : {kb}")
    print(f"  agents         : {sum(1 for r in written if r.startswith('agents/'))}")
    print(f"  commands       : {sum(1 for r in written if r.startswith('commands/'))}")
    print(f"  skills         : {len({r.split('/')[1] for r in written if r.startswith('skills/')})}")
    if removed:
        print(f"  removed {len(removed)} file(s) left over from a previous install")

    if skipped:
        print(f"\nSKIPPED {len(skipped)} pre-existing file(s) not installed by this "
              f"tool — your versions were left alone:", file=sys.stderr)
        for rel in skipped:
            print(f"  {rel}", file=sys.stderr)
        print("Re-run with --force to overwrite them.", file=sys.stderr)

    print("\nStart a new Claude Code session to pick these up. Then, in any folder:")
    print("  /bid <project>   full pipeline      /takeoff  /scope  /estimate")
    print("                                      /proposal /audit  /procure")
    print("                                      /loan-package")
    print("\nExcel builders need openpyxl:  pip install openpyxl")
    return 1 if skipped else 0


def do_uninstall(prefix: Path) -> int:
    kb = prefix / "construction-estimating"
    manifest = read_manifest(kb)
    if manifest is None:
        print(f"Nothing to uninstall — no install manifest under {kb}",
              file=sys.stderr)
        return 1

    removed = 0
    for rel in manifest.get("files", []):
        f = prefix / rel
        if f.is_file():
            f.unlink()
            removed += 1
    (kb / MANIFEST_NAME).unlink(missing_ok=True)

    # Drop directories that our removal emptied; leave anything still in use.
    for d in sorted((p for p in prefix.rglob("*") if p.is_dir()),
                    key=lambda p: len(p.parts), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()

    print(f"Removed {removed} file(s) from {prefix}. "
          f"Your project folders were not touched.")
    return 0


def do_check(prefix: Path) -> int:
    kb = prefix / "construction-estimating"
    manifest = read_manifest(kb)
    if manifest is None:
        print(f"Not installed under {prefix}.")
        print("Install with:  python3 estimating/install.py")
        return 1

    files = manifest.get("files", [])
    missing = [r for r in files if not (prefix / r).is_file()]
    print(f"Installed from : {manifest.get('installed_from', '?')}")
    print(f"Knowledge base : {manifest.get('knowledge_base', '?')}")
    print(f"Files          : {len(files) - len(missing)}/{len(files)} present")
    for rel in missing:
        print(f"  MISSING  {rel}", file=sys.stderr)

    # Both surfaces at once means duplicate agents/commands/skills.
    dupes = list((Path.home() / ".claude" / "plugins").rglob(
        "construction-estimating/.claude-plugin/plugin.json"))
    if dupes:
        print("\nWARNING: the marketplace plugin also looks installed:",
              file=sys.stderr)
        for d in dupes:
            print(f"  {d.parent.parent}", file=sys.stderr)
        print("Running both surfaces gives the model two copies of every agent, "
              "command, and skill. Keep one:\n"
              "  /plugin uninstall construction-estimating@claude-code-plugins\n"
              "or  python3 estimating/install.py --uninstall", file=sys.stderr)

    return 1 if missing else 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prefix", type=Path, default=Path.home() / ".claude",
                    help="Claude config dir to install into (default: ~/.claude)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite pre-existing files this tool did not install")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="report install state")
    mode.add_argument("--uninstall", action="store_true",
                      help="remove exactly the files listed in the manifest")
    args = ap.parse_args()

    prefix = args.prefix.expanduser().resolve()
    if args.check:
        return do_check(prefix)
    if args.uninstall:
        return do_uninstall(prefix)
    return do_install(prefix, args.force)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # Output was piped into something that stopped reading (`| head`).
        os._exit(0)
