# Install — making the precon toolkit permanent

The construction takeoff / estimating toolkit is 6 subagents, 12 slash commands, 8 Agent
Skills, and a Florida knowledge base. There are four ways to have it, and they differ in
where the files live and how long they stick around. Pick by where you actually work.

| I want it… | Use | Persists |
|---|---|---|
| in every folder on my machine, offline | [Local install](#1-local-install-permanent-on-this-machine) | Until you uninstall |
| on my machine, auto-updating from GitHub | [Marketplace plugin](#2-marketplace-plugin-auto-updating) | Until you uninstall |
| in Claude Code on the web | [Nothing to do on this repo](#3-claude-code-on-the-web) | Every session on this repo |
| in claude.ai / Cowork chat, phone included | [Upload the skill zips](#4-claudeai--cowork-cloud) | On your account, permanently |

Local install and the marketplace plugin do the same job — **run one, not both**, or the
model sees two copies of every agent, command, and skill. The cloud options are
independent: uploading skills to your account is fine alongside either local option.

---

## 1. Local install (permanent, on this machine)

Copies everything into your personal `~/.claude/` directory, so it works in **every**
folder, in every future session, with no marketplace and no network.

```bash
git clone https://github.com/paulodantasl/claude-code.git
cd claude-code
python3 estimating/install.py
pip install openpyxl          # needed by the Excel builders
```

Then start a new Claude Code session — anywhere — and run `/bid`, `/takeoff`, `/estimate`.

What lands where:

```
~/.claude/construction-estimating/   knowledge base (reference, templates, scripts)
~/.claude/agents/                    6 specialist subagents
~/.claude/commands/                  /bid* + the 7 per-stage commands
~/.claude/skills/                    8 Agent Skills
```

The agents ship referring to their files as `${CLAUDE_PLUGIN_ROOT}/…`, which only expands
for an installed plugin. The installer rewrites every occurrence to the real absolute path
on the way in, so the references resolve from any working directory.

**It will not overwrite files it did not install.** If you already have your own
`~/.claude/commands/estimate.md`, it is skipped and reported, and yours is left alone.
Re-run with `--force` if you want ours to win.

```bash
python3 estimating/install.py --check       # what is installed, and is anything missing
python3 estimating/install.py --uninstall   # remove exactly what was installed
python3 estimating/install.py --prefix DIR  # install somewhere other than ~/.claude
```

To update: `git pull` in the clone, then re-run `python3 estimating/install.py`. Files
this version no longer ships are cleaned up. Your project folders are never touched.

## 2. Marketplace plugin (auto-updating)

```
/plugin marketplace add paulodantasl/claude-code
/plugin install construction-estimating@claude-code-plugins
```

```
/plugin marketplace update claude-code-plugins   # pick up changes
```

Needs read access to the GitHub repo. Prefer this if you want updates without a clone;
prefer the local install if you want it working offline or pinned to a version you control.

## 3. Claude Code on the web

Sessions opened against **this repo** load the toolkit automatically — the agents live in
`.claude/agents/`, the commands in `.claude/commands/`, and the skills in `.claude/skills/`,
all committed. Nothing to install, nothing to configure.

For web sessions on a **different** repo, either add the marketplace plugin (§2) in that
session, or copy `.claude/agents/`, `.claude/commands/`, and `.claude/skills/` into that
repo and commit them. Note that a web container is ephemeral: anything installed into it
rather than committed to the repo is gone when the session ends.

## 4. claude.ai / Cowork (cloud)

Claude Code reads skills off disk; the web and desktop apps take **one uploaded zip per
skill**. Build the zips:

```bash
python3 estimating/sync.py --write        # only if you edited anything under estimating/
python3 estimating/package_skills.py
```

That writes `dist/skills/*.zip` — 8 archives, each self-contained:

```
construction-takeoff.zip
  construction-takeoff/SKILL.md
  construction-takeoff/resources/…
  construction-takeoff/scripts/…
```

Upload them in **Settings → Capabilities → Skills → Upload skill**, one at a time. Once
uploaded they live on your account and trigger in any chat, on any device, including the
phone. Upload only the ones you want — `construction-takeoff`, `construction-estimating`,
`estimate-audit`, and `material-procurement` are the general-purpose four; `public-bid`,
`residential-construction`, `commercial-construction`, and `tenant-improvement` are the
sector-tuned pipelines.

Re-run the packager and re-upload to update a skill.

The packager validates before it writes and refuses to package a broken skill — it checks
that each `SKILL.md` has frontmatter, that its declared `name` matches its folder, that
every `resources/…` path it names is actually bundled, and that nothing depends on a
variable that will not expand once uploaded.

There is also a chat-only setup that mirrors the knowledge base into a claude.ai Project —
see `plugins/construction-estimating/claude-ai-project/SETUP.md`. Skills are the better
option now; the Project setup remains for anyone who prefers it.

---

## The commands

| Command | Does |
|---|---|
| `/bid <project>` | Full pipeline, sector auto-detected |
| `/bid-public` `/bid-residential` `/bid-commercial` `/bid-ti` | Full pipeline, sector-tuned |
| `/takeoff` | Quantities by CSI division |
| `/scope` | Executive scope of work |
| `/estimate` | Price a takeoff into `estimate.xlsx` |
| `/proposal` | Client/GC-facing bid proposal |
| `/audit` | Independent QA — ours or a third party's |
| `/procure` | Live material sourcing with cited prices |
| `/loan-package` | 13-tab bank construction-loan workbook |

You do not have to use commands at all — describing the task ("take off the structural
concrete from these plans") routes to the right agent on its own.

## Where your bid data goes

Deliverables are written to the folder **you run Claude in**, under
`estimating-projects/<slug>/` (or `estimating/projects/<slug>/` inside this repo) — never
into the install, which gets replaced on update.

Never commit `estimating-projects/` to a shared repo: it holds owner names, lender
details, real pricing, and sealed drawings. Both paths are already git-ignored here.

## Keeping the copies honest

The knowledge base is deliberately present on several surfaces, because each one loads
files differently. `estimating/{reference,templates,scripts}` is canonical; everything
else is derived:

```bash
python3 estimating/sync.py --check    # drift gate — exit 1 if any copy is stale
python3 estimating/sync.py --write    # regenerate every derived copy
```

Edit canonical, then run `--write`. Two files (`templates/estimate-workbook.md` and its
skill copy) are authored per surface because they quote a script path that differs per
surface; sync checks they exist but never overwrites them.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `/bid` not recognized | Start a new session — commands are indexed at startup |
| Both plugin and local install active | `python3 estimating/install.py --check` warns; keep one |
| Agent can't find its reference docs | `python3 estimating/install.py --check` for missing files; re-run the installer |
| `openpyxl` not found | `pip install openpyxl` (`pip3` on macOS) |
| Skill upload rejected | `python3 estimating/package_skills.py --validate` reports what is wrong |
| Numbers look soft | They are budgetary. Replace `unit_*` in `lineitems.csv` with real quotes and re-run `/estimate` |
| Job outside Florida | Say so up front — the methodology and CSI still apply, only the FL specifics change |
