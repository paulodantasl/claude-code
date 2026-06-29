"""
Score how well a job posting fits the candidate.

Two tiers, cheapest first:

  1. Lexical pre-score (always runs, no API cost)
     TF-style keyword overlap between the candidate profile and the posting,
     plus a title-similarity bonus. Fast gate so we only spend tokens on the
     postings that are plausibly relevant.

  2. Semantic fit (optional, needs ANTHROPIC_API_KEY)
     Claude reads the posting + profile and returns a calibrated 0–100 fit
     score with reasons, matched strengths, gaps, and a recommendation. This
     is what drives the human review queue.

If no API key is set, the lexical score alone is used (degraded but functional).
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field

from ..profile_loader import CandidateProfile
from ..scrapers.base import RawJob

logger = logging.getLogger(__name__)

_STOPWORDS = set(
    "the a an and or of to in for with on at by from as is are be this that your "
    "you we our will must may can shall not other related including etc job role "
    "position work experience ability knowledge skill skills required preferred".split()
)


@dataclass
class FitResult:
    score: float                       # 0–100 final fit score
    lexical_score: float               # 0–100 cheap overlap score
    semantic_score: float | None = None
    matched_skills: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    reasons: str = ""
    recommendation: str = ""           # apply | maybe | skip
    used_ai: bool = False


class JobMatcher:
    SEMANTIC_MODEL = "claude-opus-4-8"

    def __init__(
        self,
        profile: CandidateProfile,
        use_ai: bool = True,
        api_key: str | None = None,
    ):
        self.profile = profile
        self.profile_tokens = self._tokenize(profile.combined_text)
        self.profile_token_set = set(self.profile_tokens)
        self.use_ai = use_ai and bool(api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self._client = None
        if self.use_ai:
            try:
                import anthropic

                self._client = anthropic.Anthropic(
                    api_key=api_key or os.environ["ANTHROPIC_API_KEY"]
                )
            except Exception as exc:
                logger.warning("AI matching disabled (%s); using lexical only", exc)
                self.use_ai = False

    # ── Public API ──────────────────────────────────────────────────────────

    def score(self, job: RawJob, ai_threshold: float = 20.0) -> FitResult:
        """Return a FitResult. AI is only invoked if the lexical gate is cleared."""
        lexical = self._lexical_score(job)
        result = FitResult(score=lexical, lexical_score=lexical)

        if self.use_ai and lexical >= ai_threshold:
            try:
                self._semantic_score(job, result)
            except Exception as exc:
                logger.warning("Semantic scoring failed for '%s': %s", job.title, exc)

        if result.semantic_score is None and not result.recommendation:
            result.recommendation = (
                "apply" if lexical >= 60 else "maybe" if lexical >= 35 else "skip"
            )
        return result

    # ── Tier 1: lexical ─────────────────────────────────────────────────────

    def _lexical_score(self, job: RawJob) -> float:
        job_tokens = self._tokenize(job.full_text)
        if not job_tokens or not self.profile_token_set:
            return 0.0
        job_set = set(job_tokens)
        overlap = job_set & self.profile_token_set
        # Coverage = share of the posting's vocabulary the candidate also uses.
        coverage = len(overlap) / max(len(job_set), 1)
        # Title similarity bonus.
        title_bonus = self._title_similarity(job.title or "")
        score = 100.0 * (0.7 * coverage + 0.3 * title_bonus)
        return round(min(score, 100.0), 1)

    def _title_similarity(self, title: str) -> float:
        title_tokens = set(self._tokenize(title))
        if not title_tokens:
            return 0.0
        best = 0.0
        for cand in self.profile.titles or []:
            cand_tokens = set(self._tokenize(cand))
            if not cand_tokens:
                continue
            jac = len(title_tokens & cand_tokens) / len(title_tokens | cand_tokens)
            best = max(best, jac)
        if not self.profile.titles:
            # Fall back to overlap with the whole profile vocabulary.
            return len(title_tokens & self.profile_token_set) / len(title_tokens)
        return best

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        words = re.findall(r"[a-zA-Z][a-zA-Z+#.-]{1,}", (text or "").lower())
        return [w for w in words if w not in _STOPWORDS and len(w) > 2]

    # ── Tier 2: semantic (Claude) ───────────────────────────────────────────

    def _semantic_score(self, job: RawJob, result: FitResult) -> None:
        prompt = self._build_prompt(job)
        resp = self._client.messages.create(
            model=self.SEMANTIC_MODEL,
            max_tokens=1024,
            system=(
                "You are a candid career advisor evaluating fit between a candidate "
                "and a government job posting. Be calibrated and honest: a 90+ means "
                "an obviously strong, hireable match; 40 means a stretch; below 25 "
                "means do not apply. Reward transferable public-sector experience. "
                "Respond ONLY with the requested JSON."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        data = self._parse_json(resp.content[0].text)
        if not data:
            return
        sem = float(data.get("fit_score", result.lexical_score))
        result.semantic_score = round(sem, 1)
        # Final score: weight the AI judgment but keep the lexical signal.
        result.score = round(0.8 * sem + 0.2 * result.lexical_score, 1)
        result.matched_skills = data.get("matched_strengths", []) or []
        result.gaps = data.get("gaps", []) or []
        result.reasons = (data.get("reasoning") or "").strip()
        result.recommendation = (data.get("recommendation") or "").lower().strip()
        result.used_ai = True
        if result.recommendation not in {"apply", "maybe", "skip"}:
            result.recommendation = (
                "apply" if sem >= 65 else "maybe" if sem >= 40 else "skip"
            )

    def _build_prompt(self, job: RawJob) -> str:
        profile_snippet = self.profile.combined_text[:8000]
        posting = "\n".join(
            filter(
                None,
                [
                    f"Title: {job.title}",
                    f"Agency: {job.agency_name}",
                    f"Department: {job.department}" if job.department else "",
                    f"Salary: {job.salary_raw}" if job.salary_raw else "",
                    f"Location: {job.location}" if job.location else "",
                    "",
                    (job.description or "")[:6000],
                    "",
                    "Minimum qualifications:",
                    (job.requirements or "")[:3000],
                ],
            )
        )
        return (
            "CANDIDATE PROFILE (resume + LinkedIn):\n"
            f"{profile_snippet}\n\n"
            "JOB POSTING:\n"
            f"{posting}\n\n"
            "Return JSON exactly like:\n"
            "{\n"
            '  "fit_score": 0-100,\n'
            '  "recommendation": "apply" | "maybe" | "skip",\n'
            '  "matched_strengths": ["..."],\n'
            '  "gaps": ["..."],\n'
            '  "reasoning": "2-3 sentence honest assessment"\n'
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
