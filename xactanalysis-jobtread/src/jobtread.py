"""Minimal JobTread Open API (Pave) client.

JobTread's public API is a single endpoint (https://api.jobtread.com/pave)
that takes a JSON "Pave" query; arguments live under the "$" key and the
grant key is passed in the query body. Docs:
https://app.jobtread.com/help/utilizing-jobtreads-open-api

Lead creation is three linked writes:
  createAccount (customer) -> createLocation (loss address) -> createJob

Field names below follow JobTread's published examples. If your organization
uses custom fields for pipeline stage (e.g. a "Stage: New Lead" field on
jobs), verify the field IDs in JobTread's API explorer and extend
create_lead() accordingly — the claim details always land in the job
description regardless, so no data is lost in the meantime.
"""

import json
import logging
from typing import Optional

import requests

from .parser import ClaimLead

log = logging.getLogger(__name__)


class JobTreadError(RuntimeError):
    pass


class JobTreadClient:
    def __init__(self, grant_key: str, org_id: str, api_url: str = "https://api.jobtread.com/pave"):
        self.grant_key = grant_key
        self.org_id = org_id
        self.api_url = api_url

    def _query(self, query: dict) -> dict:
        payload = {"query": {"$": {"grantKey": self.grant_key}, **query}}
        response = requests.post(self.api_url, json=payload, timeout=30)
        if response.status_code != 200:
            raise JobTreadError(
                f"JobTread API HTTP {response.status_code}: {response.text[:500]}"
            )
        data = response.json()
        if isinstance(data, dict) and data.get("errors"):
            raise JobTreadError(f"JobTread API errors: {json.dumps(data['errors'])[:500]}")
        return data

    def check_connection(self) -> dict:
        """Verify the grant key works; returns the raw response."""
        return self._query(
            {
                "currentGrant": {
                    "id": {},
                }
            }
        )

    def create_lead(self, lead: ClaimLead, account_type: str = "customer") -> dict:
        """Create customer + location + job for a parsed claim.

        Returns {"account_id": ..., "location_id": ..., "job_id": ...}.
        """
        insured = lead.insured_name or f"Unknown insured (claim {lead.claim_number or '?'})"

        account = self._query(
            {
                "createAccount": {
                    "$": {
                        "organizationId": self.org_id,
                        "name": insured,
                        "type": account_type,
                    },
                    "createdAccount": {"id": {}, "name": {}},
                }
            }
        )
        account_id = _dig(account, "createAccount", "createdAccount", "id")
        if not account_id:
            raise JobTreadError(f"createAccount returned no id: {json.dumps(account)[:500]}")

        location_args = {
            "accountId": account_id,
            "name": insured,
        }
        if lead.loss_address:
            location_args["address"] = lead.loss_address
        location = self._query(
            {
                "createLocation": {
                    "$": location_args,
                    "createdLocation": {"id": {}},
                }
            }
        )
        location_id = _dig(location, "createLocation", "createdLocation", "id")
        if not location_id:
            raise JobTreadError(f"createLocation returned no id: {json.dumps(location)[:500]}")

        job = self._query(
            {
                "createJob": {
                    "$": {
                        "locationId": location_id,
                        "name": lead.job_name(),
                        "description": lead.description(),
                    },
                    "createdJob": {"id": {}, "name": {}},
                }
            }
        )
        job_id = _dig(job, "createJob", "createdJob", "id")
        if not job_id:
            raise JobTreadError(f"createJob returned no id: {json.dumps(job)[:500]}")

        log.info(
            "Created JobTread lead: account=%s location=%s job=%s (%s)",
            account_id,
            location_id,
            job_id,
            lead.job_name(),
        )
        return {"account_id": account_id, "location_id": location_id, "job_id": job_id}


def _dig(data: dict, *keys: str) -> Optional[str]:
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current
