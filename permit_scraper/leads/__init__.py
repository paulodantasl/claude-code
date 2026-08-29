"""
Issued-permit lead generation.

Scans municipal portals for permits that reach ISSUED status (commercial +
residential projects), and turns each one into a sales lead with the general
contractor of record and the owner as outreach contacts — exported as a CSV
call-list and (optionally) a Google Sheet.

    from permit_scraper.leads import build_pipeline

    pipeline = build_pipeline()
    summary = pipeline.run(days_back=30, csv_path="leads.csv")
    print(summary["new_leads"], "new leads")
"""
from .classifier import LeadClassifier
from .exporters import export_google_sheet, to_sheet_rows, write_csv
from .models import Lead, LeadConfig
from .pipeline import LeadPipeline, build_pipeline, load_lead_config
from .store import LeadStore

__all__ = [
    "Lead",
    "LeadConfig",
    "LeadClassifier",
    "LeadPipeline",
    "LeadStore",
    "build_pipeline",
    "load_lead_config",
    "write_csv",
    "to_sheet_rows",
    "export_google_sheet",
]
