"""Parse XactAnalysis assignment-notification emails into a ClaimLead.

Notification templates vary by carrier and program, so extraction is
defensive: each field tries several label spellings, and the full email body
always travels with the lead so nothing is lost when a template doesn't
match. If a new carrier's template slips past a pattern, the lead still
lands in JobTread with the complete text — add the new label here and drop a
redacted sample into tests/sample_emails/.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ClaimLead:
    claim_number: Optional[str] = None
    insured_name: Optional[str] = None
    loss_address: Optional[str] = None
    phone: Optional[str] = None
    carrier: Optional[str] = None
    type_of_loss: Optional[str] = None
    date_of_loss: Optional[str] = None
    policy_number: Optional[str] = None
    deductible: Optional[str] = None
    adjuster_name: Optional[str] = None
    adjuster_phone: Optional[str] = None
    adjuster_email: Optional[str] = None
    raw_body: str = ""
    subject: str = ""
    message_id: str = ""

    @property
    def is_assignment(self) -> bool:
        """An email is worth turning into a lead if it has a claim number or
        looks like an assignment notice by subject."""
        if self.claim_number:
            return True
        return bool(re.search(r"(?i)\b(new\s+assignment|work\s+assignment)\b", self.subject))

    def job_name(self) -> str:
        parts = []
        if self.claim_number:
            parts.append(f"Claim {self.claim_number}")
        if self.insured_name:
            parts.append(self.insured_name)
        if self.type_of_loss:
            parts.append(self.type_of_loss)
        return " — ".join(parts) or f"XactAnalysis assignment ({self.subject or 'no subject'})"

    def description(self) -> str:
        lines = ["New lead auto-created from XactAnalysis assignment notification.", ""]
        labeled = [
            ("Claim number", self.claim_number),
            ("Insured", self.insured_name),
            ("Phone", self.phone),
            ("Loss address", self.loss_address),
            ("Carrier", self.carrier),
            ("Type of loss", self.type_of_loss),
            ("Date of loss", self.date_of_loss),
            ("Policy number", self.policy_number),
            ("Deductible", self.deductible),
            ("Adjuster", self.adjuster_name),
            ("Adjuster phone", self.adjuster_phone),
            ("Adjuster email", self.adjuster_email),
        ]
        for label, value in labeled:
            if value:
                lines.append(f"{label}: {value}")
        lines += ["", "--- Original notification ---", self.raw_body.strip()]
        return "\n".join(lines)


# Each field: list of alternative label patterns, tried in order.
# Labels match at line start, case-insensitive, followed by : or - separator.
_FIELD_PATTERNS = {
    "claim_number": [
        r"claim\s*(?:number|no\.?|num|#)",
        r"claim\s*id",
        r"assignment\s*(?:number|#)",
        r"file\s*(?:number|#)",
    ],
    "insured_name": [
        r"insured(?:\s*name)?",
        r"policy\s*holder(?:\s*name)?",
        r"policyholder(?:\s*name)?",
        r"customer(?:\s*name)?",
    ],
    "loss_address": [
        r"(?:loss|risk|property|damage)\s*(?:location|address)",
        r"address\s*of\s*loss",
        r"job\s*address",
    ],
    "phone": [
        r"(?:insured|home|contact|primary|cell(?:ular)?|mobile)\s*(?:phone|telephone|#)?\s*(?:number)?",
        r"phone(?:\s*number)?",
    ],
    "carrier": [
        r"(?:insurance\s*)?(?:carrier|company|insurer)(?:\s*name)?",
    ],
    "type_of_loss": [
        r"(?:type|cause)\s*of\s*loss",
        r"loss\s*type",
        r"peril",
    ],
    "date_of_loss": [
        r"date\s*of\s*loss",
        r"loss\s*date",
    ],
    "policy_number": [
        r"policy\s*(?:number|no\.?|#)",
    ],
    "deductible": [
        r"deductible",
    ],
    "adjuster_name": [
        r"(?:claim\s*rep(?:resentative)?|adjuster|estimator|examiner)(?:\s*name)?",
    ],
    "adjuster_phone": [
        r"(?:adjuster|claim\s*rep(?:resentative)?)\s*phone",
    ],
    "adjuster_email": [
        r"(?:adjuster|claim\s*rep(?:resentative)?)\s*e-?mail",
    ],
}

_SEPARATOR = r"\s*[:\-–]\s*"


def _find_field(text: str, patterns: list) -> Optional[str]:
    for label in patterns:
        match = re.search(
            rf"(?im)^[\s>*•]*{label}{_SEPARATOR}(?P<value>.+?)\s*$", text
        )
        if match:
            value = match.group("value").strip().strip(".,;")
            if value and value.lower() not in ("n/a", "none", "-"):
                return value
    return None


def parse_assignment_email(body: str, subject: str = "", message_id: str = "") -> ClaimLead:
    lead = ClaimLead(raw_body=body, subject=subject, message_id=message_id)

    for field_name, patterns in _FIELD_PATTERNS.items():
        setattr(lead, field_name, _find_field(body, patterns))

    # Subject-line fallbacks: many templates carry "Claim #XYZ" in the subject.
    if not lead.claim_number:
        match = re.search(r"(?i)claim\s*(?:number|no\.?|#)?\s*[:#]?\s*([A-Z0-9][A-Z0-9\-]{3,})", subject)
        if match:
            lead.claim_number = match.group(1).strip()

    # Loss address often spans two lines (street / city-state-zip).
    if lead.loss_address:
        lead.loss_address = _extend_address(body, lead.loss_address)

    return lead


def _extend_address(body: str, first_line: str) -> str:
    """If the line after the matched address looks like 'City, ST 12345',
    append it."""
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if first_line in line and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if re.match(r"^[A-Za-z .'-]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?$", next_line):
                return f"{first_line}, {next_line}"
            break
    return first_line
