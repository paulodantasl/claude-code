"""
Bid package builder.

For each qualified opportunity, creates an organised folder with everything the
estimating / proposal team needs to start work:

    bid_packages/2026-07-01_W912EP-26-B-0001_runway-repair/
      00_OPPORTUNITY_SUMMARY.md
      01_REQUIREMENTS_CHECKLIST.md
      02_SUBMITTAL_CHECKLIST.md
      03_PROPOSAL_DRAFT.md
      04_COVER_LETTER.md
      opportunity.json
      documents/            ← downloaded solicitation attachments
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from .agents.proposal_agent import ProposalDrafter
from .agents.qualifier import QualificationResult
from .agents.requirements_agent import RequirementsExtractor
from .sources.base import BROWSER_USER_AGENT, RawOpportunity

logger = logging.getLogger(__name__)


def _slug(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:max_len].strip("-") or "opportunity"


class BidPackager:
    """Assembles a bid package folder for a qualified opportunity."""

    def __init__(
        self,
        output_dir: Path,
        company: dict[str, Any],
        download_documents: bool = True,
        model: str = "claude-sonnet-4-6",
    ):
        self.output_dir = Path(output_dir)
        self.company = company or {}
        self.download_documents = download_documents
        self.requirements_extractor = RequirementsExtractor(model=model)
        self.proposal_drafter = ProposalDrafter(model=model)

    def build(self, opp: RawOpportunity, qual: QualificationResult) -> Path:
        folder = self._folder_for(opp)
        folder.mkdir(parents=True, exist_ok=True)
        docs_dir = folder / "documents"

        # 1. Download attachments (best effort) and gather their text.
        document_text = ""
        if self.download_documents and opp.documents:
            docs_dir.mkdir(exist_ok=True)
            document_text = self._download_documents(opp, docs_dir)

        # 2. Extract structured submission requirements.
        requirements = self.requirements_extractor.extract(opp, document_text)

        # 3. Draft the proposal + cover letter.
        draft = self.proposal_drafter.draft(opp, self.company, requirements)

        # 4. Write all files.
        (folder / "00_OPPORTUNITY_SUMMARY.md").write_text(self._summary_md(opp, qual), encoding="utf-8")
        (folder / "01_REQUIREMENTS_CHECKLIST.md").write_text(
            self._requirements_md(opp, requirements), encoding="utf-8"
        )
        (folder / "02_SUBMITTAL_CHECKLIST.md").write_text(
            self._submittal_md(requirements), encoding="utf-8"
        )
        (folder / "03_PROPOSAL_DRAFT.md").write_text(draft["proposal"], encoding="utf-8")
        (folder / "04_COVER_LETTER.md").write_text(draft["cover_letter"], encoding="utf-8")
        (folder / "opportunity.json").write_text(self._opportunity_json(opp, qual), encoding="utf-8")

        logger.info("Built bid package: %s (proposal engine=%s)", folder, draft["engine"])
        return folder

    # ── folder + downloads ────────────────────────────────────────────────

    def _folder_for(self, opp: RawOpportunity) -> Path:
        due = opp.due_date.strftime("%Y-%m-%d") if opp.due_date else "no-deadline"
        sol = _slug(opp.solicitation_number or opp.source_id, 30)
        title = _slug(opp.title or "", 40)
        return self.output_dir / f"{due}_{sol}_{title}"

    def _download_documents(self, opp: RawOpportunity, docs_dir: Path) -> str:
        collected: list[str] = []
        for i, doc in enumerate(opp.documents, 1):
            try:
                resp = requests.get(doc.url, timeout=60, headers={"User-Agent": BROWSER_USER_AGENT})
                resp.raise_for_status()
                name = _slug(doc.name, 50) or f"document-{i}"
                ext = self._guess_ext(doc.url, resp.headers.get("Content-Type", ""))
                path = docs_dir / f"{i:02d}_{name}{ext}"
                path.write_bytes(resp.content)
                if ext in (".txt", ".csv", ".html", ".htm"):
                    collected.append(resp.text[:20000])
            except Exception as exc:
                logger.warning("Could not download %s: %s", doc.url, exc)
        return "\n\n".join(collected)

    @staticmethod
    def _guess_ext(url: str, content_type: str) -> str:
        for ext in (".pdf", ".docx", ".doc", ".xlsx", ".xls", ".zip", ".txt", ".csv", ".html"):
            if url.lower().split("?")[0].endswith(ext):
                return ext
        if "pdf" in content_type:
            return ".pdf"
        if "word" in content_type:
            return ".docx"
        if "html" in content_type:
            return ".html"
        return ".bin"

    # ── markdown renderers ────────────────────────────────────────────────

    def _summary_md(self, opp: RawOpportunity, qual: QualificationResult) -> str:
        loc = ", ".join(x for x in [opp.city, opp.state, opp.zip_code] if x) or "—"
        value = f"${opp.estimated_value:,.0f}" if opp.estimated_value else "Not stated"
        lines = [
            f"# {opp.title or 'Untitled Opportunity'}",
            "",
            f"_Qualified at **{qual.score:.0f}/100** — generated {datetime.utcnow():%Y-%m-%d %H:%M} UTC_",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| Agency | {opp.agency or '—'} |",
            f"| Source | {opp.source_name} |",
            f"| Solicitation # | {opp.solicitation_number or '—'} |",
            f"| Type | {opp.opportunity_type or '—'} |",
            f"| NAICS | {opp.naics_code or '—'} |",
            f"| Set-aside | {opp.set_aside or 'Full & Open'} |",
            f"| Location | {loc} |",
            f"| Est. value | {value} |",
            f"| Posted | {opp.posted_date:%Y-%m-%d}" + " |" if opp.posted_date else "| Posted | — |",
            f"| **Due** | **{opp.due_date:%Y-%m-%d %H:%M}**" + " |" if opp.due_date else "| Due | — |",
            f"| Contact | {opp.contact_name or '—'} {('<' + opp.contact_email + '>') if opp.contact_email else ''} {opp.contact_phone or ''} |",
            f"| Link | {opp.source_url or '—'} |",
            "",
            "## Why this qualified",
            "",
        ]
        lines += [f"- {r}" for r in (qual.reasons or ["Met overall score threshold"])]
        lines += ["", "## Description", "", (opp.description or "_No description provided._").strip()]
        if opp.documents:
            lines += ["", "## Attachments", ""]
            lines += [f"- [{d.name}]({d.url})" for d in opp.documents]
        return "\n".join(lines) + "\n"

    def _requirements_md(self, opp: RawOpportunity, req: dict[str, Any]) -> str:
        def bullets(items: list[Any]) -> str:
            return "\n".join(f"- [ ] {i}" for i in items) if items else "- _None identified — verify in solicitation_"

        eval_rows = "\n".join(
            f"| {c.get('criterion','')} | {c.get('weight') or '—'} |"
            for c in req.get("evaluation_criteria", [])
        ) or "| _See solicitation_ | — |"

        return (
            f"# Requirements Checklist — {opp.title or ''}\n\n"
            f"**Submission method:** {req.get('submission_method') or 'See solicitation'}\n\n"
            f"**Due:** {req.get('due_summary') or 'See solicitation'}\n\n"
            f"## Required forms\n{bullets(req.get('required_forms', []))}\n\n"
            f"## Bonds\n{bullets(req.get('bonds', []))}\n\n"
            f"## Insurance\n{bullets(req.get('insurance', []))}\n\n"
            f"## Licenses & certifications\n{bullets(req.get('licenses_certifications', []))}\n\n"
            f"## Format / page limits\n{bullets(req.get('page_or_format_limits', []))}\n\n"
            f"## Mandatory meetings\n{bullets(req.get('mandatory_meetings', []))}\n\n"
            f"## Evaluation criteria\n\n| Criterion | Weight |\n|---|---|\n{eval_rows}\n"
        )

    def _submittal_md(self, req: dict[str, Any]) -> str:
        items = req.get("submittal_checklist", [])
        body = "\n".join(f"- [ ] {i}" for i in items) if items else "- [ ] _Build from requirements_"
        return f"# Submittal Checklist\n\n_Tick each item before submission._\n\n{body}\n"

    def _opportunity_json(self, opp: RawOpportunity, qual: QualificationResult) -> str:
        data = asdict(opp)
        data["documents"] = [asdict(d) for d in opp.documents]
        for k in ("posted_date", "due_date", "question_due_date"):
            if isinstance(data.get(k), datetime):
                data[k] = data[k].isoformat()
        data["qualification"] = {
            "qualified": qual.qualified,
            "score": qual.score,
            "reasons": qual.reasons,
            "disqualifiers": qual.disqualifiers,
        }
        data.pop("raw_data", None)
        return json.dumps(data, indent=2, default=str)
