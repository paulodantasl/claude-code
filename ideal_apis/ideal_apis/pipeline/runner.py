from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ideal_apis.client import IdealAPIs
from ideal_apis.pipeline.enrich import enrich_leads
from ideal_apis.pipeline.jobtread_export import (
    JobTreadClient,
    write_jobtread_csv,
    write_leads_json,
    write_summary_md,
)
from ideal_apis.pipeline.ledger import LeadLedger
from ideal_apis.pipeline.models import LeadRecord
from ideal_apis.pipeline.sources import LeadSources

CONTACT_SOURCES = {"nppes", "yelp"}


class DailyLeadPipeline:
    """End-to-end daily lead pipeline: fetch → enrich → dedupe → export → JobTread."""

    def __init__(self, config_path: Path | None = None, api: IdealAPIs | None = None):
        root = Path(__file__).resolve().parents[2]
        self.config_path = config_path or root / "config" / "pipeline.yaml"
        self.api = api or IdealAPIs()
        self.config = self._load_config()
        self.ledger = LeadLedger(self._resolve_path(self.config.get("ledger_path", "data/leads_ledger.json")))
        self.output_dir = self._resolve_path(self.config.get("output_dir", "data/output"))
        self.sources = LeadSources(self.api)

    def _resolve_path(self, rel: str) -> Path:
        root = Path(__file__).resolve().parents[2]
        p = Path(rel)
        return p if p.is_absolute() else root / p

    def _load_config(self) -> dict[str, Any]:
        with open(self.config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _safe_fetch(self, source: str, fn) -> list[LeadRecord]:
        try:
            return fn()
        except Exception as exc:
            return [
                LeadRecord(
                    id=f"error_{source}",
                    source="manual",
                    brand="ideal_cgc",
                    name=f"{source} fetch failed",
                    priority="low",
                    notes=str(exc)[:240],
                )
            ]

    def run(
        self,
        *,
        push_jobtread: bool | None = None,
        dry_run: bool | None = None,
        skip_yelp: bool = False,
    ) -> dict[str, Any]:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        fetched: list[LeadRecord] = []

        for spec in self.config.get("nppes_searches", []):
            fetched.extend(self.sources.fetch_nppes(spec))

        if not skip_yelp:
            for spec in self.config.get("yelp_searches", []):
                try:
                    fetched.extend(self.sources.fetch_yelp(spec))
                except Exception as exc:
                    fetched.append(
                        LeadRecord(
                            id=f"yelp_error_{spec.get('term', 'unknown')}",
                            source="yelp",
                            brand=spec.get("brand", "ideal_cgc"),
                            name=f"Yelp fetch skipped: {spec.get('term')}",
                            priority="low",
                            notes=str(exc)[:200],
                        )
                    )

        fetched.extend(self._safe_fetch("openfema", lambda: self.sources.fetch_openfema(self.config.get("openfema", {}))))

        gov_cfg = self.config.get("government", {})
        fetched.extend(self._safe_fetch(
            "usaspending",
            lambda: self.sources.fetch_usaspending(limit=int(gov_cfg.get("usaspending_limit", 10))),
        ))
        fetched.extend(self._safe_fetch(
            "federal_contracts",
            lambda: self.sources.fetch_federal_contracts(
                state=gov_cfg.get("federal_contracts_state", "FL"),
                limit=int(gov_cfg.get("federal_contracts_limit", 10)),
            ),
        ))
        fetched.extend(self._safe_fetch("weather", lambda: self.sources.fetch_weather(self.config.get("weather", {}))))

        enriched = enrich_leads(self.api, fetched, validate=True)

        new_leads: list[LeadRecord] = []
        intel_leads: list[LeadRecord] = []
        skipped = 0
        for lead in enriched:
            key = lead.dedupe_key()
            if self.ledger.seen(key):
                skipped += 1
                continue
            self.ledger.mark_seen(key, lead.to_dict())
            if lead.source in CONTACT_SOURCES and lead.has_contact_channel():
                new_leads.append(lead)
            else:
                intel_leads.append(lead)

        self.ledger.save()

        jt_cfg = self.config.get("jobtread", {})
        org_id = jt_cfg.get("org_id", "22P6bRn5p6Pn")
        min_priority = jt_cfg.get("push_min_priority", "high")
        priority_rank = {"high": 3, "medium": 2, "low": 1}
        min_rank = priority_rank.get(min_priority, 2)

        jt_client = JobTreadClient.from_env(org_id)
        use_dry_run = jt_cfg.get("dry_run", True) if dry_run is None else dry_run
        do_push = push_jobtread if push_jobtread is not None else jt_client.available()

        jobtread_results: list[dict[str, Any]] = []
        push_candidates = [
            lead for lead in new_leads
            if priority_rank.get(lead.priority, 0) >= min_rank
            and not self.ledger.is_jobtread_pushed(lead.dedupe_key())
        ]

        for lead in push_candidates:
            if do_push and jt_client.available():
                result = jt_client.push_lead(lead, dry_run=use_dry_run)
                jobtread_results.append(result)
                if result.get("account_id"):
                    self.ledger.mark_jobtread(lead.dedupe_key(), result["account_id"])
            else:
                jobtread_results.append({"dry_run": True, "would_create": lead.name})

        if jobtread_results:
            self.ledger.save()

        out_json = self.output_dir / f"daily_leads_{stamp}.json"
        out_csv = self.output_dir / f"jobtread_import_{stamp}.csv"
        out_md = self.output_dir / f"summary_{stamp}.md"

        write_leads_json(out_json, new_leads + intel_leads)
        write_jobtread_csv(new_leads, out_csv)
        write_summary_md(
            out_md,
            new_leads=new_leads,
            intel_leads=intel_leads,
            skipped=skipped,
            jobtread_results=jobtread_results,
        )

        return {
            "date": stamp,
            "fetched": len(fetched),
            "new_contactable": len(new_leads),
            "intel": len(intel_leads),
            "skipped_dedupe": skipped,
            "jobtread_candidates": len(push_candidates),
            "outputs": {
                "json": str(out_json),
                "csv": str(out_csv),
                "summary": str(out_md),
                "ledger": str(self.ledger.path),
            },
            "jobtread_dry_run": use_dry_run,
            "jobtread_available": jt_client.available(),
        }
