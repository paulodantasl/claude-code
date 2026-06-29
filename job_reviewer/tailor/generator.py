"""
Generate a tailored application packet for a matched job.

For each job that clears the review threshold the tailor produces, using Claude:

  • cover_letter   — a focused, honest cover letter tied to the posting
  • resume_bullets — 4-8 reframed resume bullets that mirror the posting's
                     language (truthfully — only from what's in the profile)
  • answers        — drafted responses to the supplemental questions NEOGOV
                     applications commonly ask (why this role, relevant
                     experience, salary expectation)
  • summary        — a one-paragraph "why you fit" for the review queue

Everything is grounded ONLY in the candidate's real resume/LinkedIn. The system
never invents experience, and never submits — output is written to disk and
flagged for the human to review, edit, and submit.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..matching import FitResult
from ..profile_loader import CandidateProfile
from ..scrapers.base import RawJob

logger = logging.getLogger(__name__)


@dataclass
class ApplicationPacket:
    job_source_id: str
    job_title: str
    agency_name: str
    cover_letter: str = ""
    resume_bullets: list[str] = field(default_factory=list)
    answers: dict[str, str] = field(default_factory=dict)
    summary: str = ""
    apply_url: str | None = None

    def to_markdown(self, fit: FitResult | None = None) -> str:
        lines = [
            f"# Application packet — {self.job_title}",
            f"**Agency:** {self.agency_name}  ",
            f"**Apply at:** {self.apply_url or 'N/A'}  ",
        ]
        if fit:
            lines.append(
                f"**Fit score:** {fit.score:.0f}/100 "
                f"(recommendation: {fit.recommendation or 'n/a'})  "
            )
        lines += ["", "> ⚠️ DRAFT — review, edit, and submit yourself. Nothing is submitted automatically.", ""]
        if self.summary:
            lines += ["## Why you fit", self.summary, ""]
        if self.resume_bullets:
            lines += ["## Suggested resume bullets", ""]
            lines += [f"- {b}" for b in self.resume_bullets]
            lines.append("")
        if self.cover_letter:
            lines += ["## Cover letter", "", self.cover_letter, ""]
        if self.answers:
            lines += ["## Drafted supplemental answers", ""]
            for q, a in self.answers.items():
                lines += [f"**{q}**", "", a, ""]
        return "\n".join(lines)


class ApplicationTailor:
    MODEL = "claude-opus-4-8"

    DEFAULT_QUESTIONS = [
        "Why are you interested in this position with this agency?",
        "Describe your most relevant experience for this role.",
        "What are your salary expectations?",
    ]

    def __init__(self, profile: CandidateProfile, api_key: str | None = None):
        self.profile = profile
        self._client = None
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if key:
            try:
                import anthropic

                self._client = anthropic.Anthropic(api_key=key)
            except Exception as exc:
                logger.warning("Tailor AI unavailable (%s)", exc)

    @property
    def available(self) -> bool:
        return self._client is not None

    def tailor(
        self,
        job: RawJob,
        fit: FitResult | None = None,
        questions: list[str] | None = None,
    ) -> ApplicationPacket:
        packet = ApplicationPacket(
            job_source_id=job.source_id,
            job_title=job.title or "(untitled)",
            agency_name=job.agency_name,
            apply_url=job.apply_url,
        )
        if not self.available:
            packet.summary = (
                "Set ANTHROPIC_API_KEY to auto-draft a cover letter and answers. "
                "Listed here because it cleared the fit threshold."
            )
            return packet

        questions = questions or self.DEFAULT_QUESTIONS
        prompt = self._build_prompt(job, fit, questions)
        resp = self._client.messages.create(
            model=self.MODEL,
            max_tokens=2048,
            system=(
                "You are an expert applicant writing materials for a U.S. local-government "
                "job application. Ground everything ONLY in the candidate's real resume / "
                "LinkedIn — never invent employers, titles, degrees, certifications, or "
                "metrics. Match the posting's language where the candidate truthfully "
                "qualifies. Plain, professional, specific. Respond ONLY with the JSON."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        data = self._parse_json(resp.content[0].text) or {}
        packet.cover_letter = (data.get("cover_letter") or "").strip()
        packet.resume_bullets = data.get("resume_bullets") or []
        packet.summary = (data.get("summary") or "").strip()
        answers = data.get("answers") or {}
        # Normalise answer keys back to the question text where possible.
        if isinstance(answers, dict):
            packet.answers = {str(k): str(v) for k, v in answers.items()}
        return packet

    def write_packet(
        self, packet: ApplicationPacket, out_dir: Path, fit: FitResult | None = None
    ) -> Path:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", packet.job_title.lower()).strip("-")[:50]
        agency = re.sub(r"[^a-z0-9]+", "-", packet.agency_name.lower()).strip("-")[:30]
        path = out_dir / f"{agency}__{slug}.md"
        path.write_text(packet.to_markdown(fit), encoding="utf-8")
        logger.info("Wrote application packet → %s", path)
        return path

    # ── Internals ───────────────────────────────────────────────────────────

    def _build_prompt(
        self, job: RawJob, fit: FitResult | None, questions: list[str]
    ) -> str:
        gaps = ", ".join(fit.gaps) if fit and fit.gaps else "none noted"
        strengths = ", ".join(fit.matched_skills) if fit and fit.matched_skills else "n/a"
        q_block = "\n".join(f"- {q}" for q in questions)
        return (
            "CANDIDATE PROFILE (resume + LinkedIn):\n"
            f"{self.profile.combined_text[:8000]}\n\n"
            "JOB POSTING:\n"
            f"Title: {job.title}\nAgency: {job.agency_name}\n"
            f"Salary: {job.salary_raw or 'n/a'}\n\n"
            f"{(job.description or '')[:5000]}\n\n"
            f"Minimum qualifications:\n{(job.requirements or '')[:2500]}\n\n"
            f"Known matched strengths: {strengths}\n"
            f"Known gaps to address tactfully (do not fabricate): {gaps}\n\n"
            "Draft these supplemental answers:\n"
            f"{q_block}\n\n"
            "Return JSON exactly like:\n"
            "{\n"
            '  "summary": "1 paragraph: why this candidate fits",\n'
            '  "cover_letter": "3-4 short paragraphs, addressed to the hiring team",\n'
            '  "resume_bullets": ["reframed bullet 1", "..."],\n'
            '  "answers": {"<question text>": "<answer>", ...}\n'
            "}"
        )

    @staticmethod
    def _parse_json(text: str) -> dict | None:
        text = (text or "").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
