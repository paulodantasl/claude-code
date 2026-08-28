from __future__ import annotations

import re
from typing import Iterable

from ideal_apis.client import IdealAPIs
from ideal_apis.exceptions import MissingAPIKeyError
from ideal_apis.pipeline.models import LeadRecord


def enrich_leads(api: IdealAPIs, leads: Iterable[LeadRecord], *, validate: bool = True) -> list[LeadRecord]:
    enriched: list[LeadRecord] = []
    for lead in leads:
        if validate:
            _validate_lead(api, lead)
        enriched.append(lead)
    return enriched


def _validate_lead(api: IdealAPIs, lead: LeadRecord) -> None:
    if lead.phone:
        digits = re.sub(r"\D", "", lead.phone)
        if len(digits) >= 10:
            try:
                result = api.validation.validate_phone(f"+1{digits[-10:]}")
                lead.phone_valid = bool(result.get("valid", True))
                if result.get("valid") is False:
                    lead.phone = None
            except MissingAPIKeyError:
                lead.phone_valid = None
            except Exception:
                lead.phone_valid = None

    if lead.email:
        try:
            result = api.validation.validate_email(lead.email)
            disposable = result.get("disposable")
            if disposable is True:
                lead.email_disposable = True
                lead.email = None
            else:
                lead.email_disposable = False
        except Exception:
            lead.email_disposable = None

    if lead.street and lead.city and lead.state and lead.zip_code:
        try:
            api.address.validate(lead.street, lead.city, lead.state, lead.zip_code)
            lead.address_validated = True
        except MissingAPIKeyError:
            lead.address_validated = None
        except Exception:
            lead.address_validated = False

    # Government intel rows often have no phone — keep them
    if lead.source in ("openfema", "usaspending", "federal_contracts", "weather"):
        return
    if not lead.has_contact_channel():
        lead.priority = "low"
