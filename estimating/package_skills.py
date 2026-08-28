#!/usr/bin/env python3
"""Package the toolkit's Agent Skills as zips for Claude Cowork / claude.ai upload.

This is the "cloud" path. Claude Code loads skills from disk, but the web and
desktop apps take one uploaded zip per skill (Settings -> Capabilities -> Skills),
so each skill has to travel as a self-contained bundle — SKILL.md plus every
resource it reads, with no reference to anything outside its own folder.

    python3 estimating/package_skills.py            # validate + write dist/skills/*.zip
    python3 estimating/package_skills.py --validate # validate only, write nothing

Each archive contains a single top-level folder named for the skill:

    construction-takeoff.zip
      construction-takeoff/SKILL.md
      construction-takeoff/resources/...
      construction-takeoff/scripts/...

Zips are written with fixed timestamps so re-running produces byte-identical
output when nothing changed.

Run `python3 estimating/sync.py --write` first if you edited anything under
`estimating/` — that is what refreshes each skill's bundled copies.
"""

import argparse
import os
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "plugins" / "construction-estimating" / "skills"
DEFAULT_OUT = REPO / "dist" / "skills"

SKIP_NAMES = {"__pycache__", ".pytest_cache", ".DS_Store"}
# Fixed DOS timestamp (1980-01-01) keeps archives reproducible.
FIXED_DATE = (1980, 1, 1, 0, 0, 0)


def skill_files(skill_dir: Path):
    for p in sorted(skill_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(skill_dir)
        if p.suffix == ".pyc" or SKIP_NAMES & set(rel.parts):
            continue
        yield p, rel


def frontmatter(text: str):
    """Return the YAML frontmatter block of a SKILL.md, or None."""
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    return m.group(1) if m else None


def validate(skill_dir: Path):
    """Return a list of problems that would make this skill fail to load."""
    name = skill_dir.name
    problems = []

    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return [f"no SKILL.md in {name}/"]

    text = md.read_text(encoding="utf-8")
    fm = frontmatter(text)
    if fm is None:
        problems.append(f"{name}: SKILL.md has no YAML frontmatter block")
        return problems

    declared = re.search(r"^name:\s*(\S+)", fm, re.MULTILINE)
    if not declared:
        problems.append(f"{name}: frontmatter has no `name:`")
    elif declared.group(1).strip() != name:
        problems.append(
            f"{name}: frontmatter name is '{declared.group(1).strip()}' "
            f"but the folder is '{name}' — they must match")

    if not re.search(r"^description:", fm, re.MULTILINE):
        problems.append(f"{name}: frontmatter has no `description:` "
                        f"(without it the skill never triggers)")

    # A skill must be self-contained once uploaded: nothing outside its folder
    # travels with it, so an unexpandable variable or a repo path is a dead link.
    if "${CLAUDE_PLUGIN_ROOT}" in text:
        problems.append(f"{name}: SKILL.md references ${{CLAUDE_PLUGIN_ROOT}}, "
                        f"which does not expand for an uploaded skill")

    # Every relative resources//scripts/ path named in SKILL.md must exist.
    for ref in sorted(set(re.findall(r"`((?:resources|scripts)/[\w./-]+)`", text))):
        if not (skill_dir / ref).exists():
            problems.append(f"{name}: SKILL.md references `{ref}` which is not bundled")

    return problems


def write_zip(skill_dir: Path, out_dir: Path) -> tuple[Path, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{skill_dir.name}.zip"
    count = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for path, rel in skill_files(skill_dir):
            info = zipfile.ZipInfo(str(Path(skill_dir.name) / rel), date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, path.read_bytes())
            count += 1
    return dest, count


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help=f"output directory (default: {DEFAULT_OUT.relative_to(REPO)})")
    ap.add_argument("--validate", action="store_true",
                    help="check the skills are self-contained; write nothing")
    ap.add_argument("--skill", action="append", metavar="NAME",
                    help="package only this skill (repeatable)")
    args = ap.parse_args()

    if not SKILLS_DIR.is_dir():
        print(f"error: no skills directory at {SKILLS_DIR}", file=sys.stderr)
        return 1

    skills = sorted(d for d in SKILLS_DIR.iterdir()
                    if d.is_dir() and not d.name.startswith("."))
    if args.skill:
        wanted = set(args.skill)
        unknown = wanted - {d.name for d in skills}
        if unknown:
            print(f"error: no such skill(s): {', '.join(sorted(unknown))}\n"
                  f"available: {', '.join(d.name for d in skills)}", file=sys.stderr)
            return 1
        skills = [d for d in skills if d.name in wanted]

    problems = []
    for d in skills:
        problems += validate(d)

    if problems:
        print(f"{len(problems)} problem(s) found — nothing packaged:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    if args.validate:
        print(f"All {len(skills)} skill(s) valid and self-contained.")
        return 0

    total = 0
    for d in skills:
        dest, n = write_zip(d, args.out)
        total += n
        print(f"  {dest.relative_to(REPO)}  ({n} files, {dest.stat().st_size:,} bytes)")

    print(f"\nPackaged {len(skills)} skill(s), {total} files, into "
          f"{args.out.relative_to(REPO) if args.out.is_relative_to(REPO) else args.out}")
    print("\nUpload: claude.ai or the desktop app -> Settings -> Capabilities -> "
          "Skills -> Upload skill, one zip each.")
    print("Once uploaded they persist on your account and work in any chat.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # Output was piped into something that stopped reading (`| head`).
        os._exit(0)
