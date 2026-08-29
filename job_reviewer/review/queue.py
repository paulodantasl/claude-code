"""
The human review queue.

This is the heart of the human-in-the-loop guarantee: every flagged job lands
here for you to review, edit the draft packet, and decide. Nothing leaves the
queue as "submitted" unless you mark it so (or run the browser pre-fill assist,
which still stops at the final submit screen for you).

Exports the queue as a ranked CSV and a Markdown digest.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from ..storage import Job, get_session

logger = logging.getLogger(__name__)


class ReviewQueue:
    def list(
        self,
        min_score: float = 0.0,
        statuses: list[str] | None = None,
        county: str | None = None,
        limit: int | None = None,
    ) -> list[Job]:
        with get_session() as session:
            q = session.query(Job)
            if min_score:
                q = q.filter(Job.fit_score >= min_score)
            if statuses:
                q = q.filter(Job.review_status.in_(statuses))
            if county:
                q = q.filter(Job.county == county)
            q = q.order_by(Job.fit_score.desc().nullslast())
            if limit:
                q = q.limit(limit)
            return q.all()

    def set_status(self, job_id: str, status: str) -> bool:
        valid = {"new", "flagged", "prefilled", "reviewed", "submitted", "dismissed"}
        if status not in valid:
            raise ValueError(f"status must be one of {sorted(valid)}")
        with get_session() as session:
            job = session.get(Job, job_id)
            if not job:
                return False
            job.review_status = status
            return True

    def export_csv(self, path: Path, min_score: float = 0.0) -> Path:
        jobs = self.list(min_score=min_score)
        path = Path(path)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "fit_score", "recommendation", "title", "agency", "county",
                    "salary", "closing_date", "status", "apply_url", "packet_path",
                ]
            )
            for j in jobs:
                writer.writerow(
                    [
                        f"{j.fit_score:.0f}" if j.fit_score is not None else "",
                        j.recommendation or "",
                        j.title or "",
                        j.agency_name or "",
                        j.county or "",
                        j.salary_raw or "",
                        j.closing_date.strftime("%Y-%m-%d") if j.closing_date else "",
                        j.review_status,
                        j.apply_url or "",
                        j.packet_path or "",
                    ]
                )
        logger.info("Exported %d queued jobs → %s", len(jobs), path)
        return path

    def export_markdown(self, path: Path, min_score: float = 0.0) -> Path:
        jobs = self.list(min_score=min_score)
        path = Path(path)
        lines = ["# Job application review queue", ""]
        lines.append(f"_{len(jobs)} jobs flagged for your review. Nothing is auto-submitted._")
        lines.append("")
        for j in jobs:
            lines += [
                f"## {j.fit_score:.0f}/100 — {j.title}" if j.fit_score is not None else f"## {j.title}",
                f"**{j.agency_name}** · {j.county or ''} · {j.salary_raw or ''}  ",
                f"Recommendation: **{j.recommendation or 'n/a'}** · Status: {j.review_status}  ",
                f"[Apply / view posting]({j.apply_url})  " if j.apply_url else "",
                (f"Draft packet: `{j.packet_path}`  " if j.packet_path else ""),
                "",
                (j.fit_reasons or "").strip(),
                "",
            ]
        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Exported review digest → %s", path)
        return path
