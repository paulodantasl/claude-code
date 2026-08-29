"""job_reviewer — review government job postings against your resume.

Scrapes governmentjobs.com (NEOGOV) postings for the cities and counties of
Pasco, Hillsborough, and Pinellas (FL), scores each against your resume +
LinkedIn, drafts tailored application materials, and flags the best fits for
your review. It never submits an application on its own.
"""
from __future__ import annotations

__version__ = "0.1.0"

from .pipeline import JobReviewPipeline

__all__ = ["JobReviewPipeline", "__version__"]
