"""
Load the candidate's profile from the ``profile/`` folder.

Drop any of the following into ``job_reviewer/profile/`` (filenames are matched
case-insensitively by keyword, so exact names don't matter):

    resume.pdf | resume.docx | resume.txt | resume.md   → the resume
    linkedin.pdf | linkedin.txt | ...                    → LinkedIn "Save to PDF" export
    profile.yaml                                         → optional structured overrides

Supported formats: .pdf, .docx, .txt, .md  (PDF needs `pypdf`, docx needs
`python-docx`; both are in requirements.txt). A profile.yaml can hand-curate
skills/titles/locations if the auto-parse misses something.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class CandidateProfile:
    """Everything the matcher and tailor need about the candidate."""

    resume_text: str = ""
    linkedin_text: str = ""
    # Optional structured fields (from profile.yaml or AI extraction)
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    headline: str | None = None
    skills: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)        # past/target job titles
    years_experience: float | None = None
    preferred_locations: list[str] = field(default_factory=list)
    desired_salary_min: float | None = None
    keywords: list[str] = field(default_factory=list)        # search keywords

    @property
    def combined_text(self) -> str:
        return f"{self.resume_text}\n\n{self.linkedin_text}".strip()

    def is_empty(self) -> bool:
        return not self.combined_text and not self.skills


class ProfileLoader:
    """Parse resume + LinkedIn files in a folder into a CandidateProfile."""

    def __init__(self, profile_dir: Path):
        self.profile_dir = Path(profile_dir)

    def load(self) -> CandidateProfile:
        if not self.profile_dir.exists():
            raise FileNotFoundError(
                f"Profile folder not found: {self.profile_dir}\n"
                "Create it and drop in your resume + LinkedIn export. "
                "See profile/README.md."
            )

        files = [
            p
            for p in self.profile_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".pdf", ".docx", ".txt", ".md", ".yaml", ".yml"}
        ]

        resume_text, linkedin_text = "", ""
        overrides: dict = {}

        for path in files:
            name = path.name.lower()
            if path.suffix.lower() in {".yaml", ".yml"}:
                overrides = self._load_yaml(path)
                continue
            text = self._extract_text(path)
            if not text:
                continue
            if "linkedin" in name:
                linkedin_text += "\n" + text
            elif "resume" in name or "cv" in name:
                resume_text += "\n" + text
            else:
                # Unlabelled doc — fold into resume so it still informs matching.
                resume_text += "\n" + text

        profile = CandidateProfile(
            resume_text=resume_text.strip(),
            linkedin_text=linkedin_text.strip(),
        )
        self._auto_extract(profile)
        self._apply_overrides(profile, overrides)

        if profile.is_empty():
            raise ValueError(
                f"No usable profile content found in {self.profile_dir}. "
                "Add a resume.pdf/.txt (and optionally linkedin.pdf)."
            )
        logger.info(
            "Loaded profile: resume=%d chars, linkedin=%d chars, skills=%d",
            len(profile.resume_text), len(profile.linkedin_text), len(profile.skills),
        )
        return profile

    # ── Text extraction per format ──────────────────────────────────────────

    def _extract_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        try:
            if suffix in {".txt", ".md"}:
                return path.read_text(encoding="utf-8", errors="ignore")
            if suffix == ".pdf":
                return self._extract_pdf(path)
            if suffix == ".docx":
                return self._extract_docx(path)
        except Exception as exc:
            logger.warning("Could not read %s: %s", path.name, exc)
        return ""

    @staticmethod
    def _extract_pdf(path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover
            raise ImportError("pip install pypdf to parse PDF resumes") from exc
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    @staticmethod
    def _extract_docx(path: Path) -> str:
        try:
            import docx  # python-docx
        except ImportError as exc:  # pragma: no cover
            raise ImportError("pip install python-docx to parse .docx resumes") from exc
        document = docx.Document(str(path))
        return "\n".join(p.text for p in document.paragraphs)

    # ── Lightweight structured extraction (no LLM needed) ───────────────────

    def _auto_extract(self, profile: CandidateProfile) -> None:
        text = profile.combined_text
        if not text:
            return
        if not profile.email:
            m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
            profile.email = m.group(0) if m else None
        if not profile.phone:
            m = re.search(r"(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}", text)
            profile.phone = m.group(0) if m else None
        if not profile.titles:
            profile.titles = self._guess_titles(text)
        if not profile.keywords:
            # Cheap default keyword set powers the scrape-time search gate.
            # Prefer guessed titles; otherwise fall back to any role-words that
            # actually appear in the profile (handles paragraph-style resumes).
            kws = list(dict.fromkeys(profile.titles))
            if not kws:
                kws = self._role_words_present(text)
            profile.keywords = kws[:12]

    @classmethod
    def _guess_titles(cls, text: str) -> list[str]:
        """Pull likely job titles from resume lines (heuristic, best-effort)."""
        found: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if 1 <= len(line.split()) <= 7 and any(
                w in line.lower() for w in cls._ROLE_WORDS
            ):
                found.append(line)
        # De-dupe, keep order, cap length
        seen, out = set(), []
        for t in found:
            key = t.lower()
            if key not in seen:
                seen.add(key)
                out.append(t)
        return out[:15]

    # Role-words used both to spot titles and to seed search keywords.
    _ROLE_WORDS = (
        "manager director coordinator analyst specialist engineer technician "
        "administrator officer supervisor assistant clerk planner inspector "
        "accountant developer designer nurse paramedic operator deputy "
        "representative associate lead consultant"
    ).split()

    @classmethod
    def _role_words_present(cls, text: str) -> list[str]:
        low = text.lower()
        return [w for w in cls._ROLE_WORDS if w in low]

    @staticmethod
    def _apply_overrides(profile: CandidateProfile, overrides: dict) -> None:
        for key, value in (overrides or {}).items():
            if hasattr(profile, key) and value:
                setattr(profile, key, value)

    @staticmethod
    def _load_yaml(path: Path) -> dict:
        try:
            return yaml.safe_load(path.read_text()) or {}
        except Exception as exc:
            logger.warning("Could not parse %s: %s", path.name, exc)
            return {}
