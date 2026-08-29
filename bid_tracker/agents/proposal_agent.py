"""
Proposal drafter.

Produces a first-draft proposal (and cover letter) for a qualified opportunity,
populated from the company profile, the opportunity, and the extracted
requirements. Uses Claude when ANTHROPIC_API_KEY is set; otherwise renders a
structured template so a usable draft always lands in the package folder.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from jinja2 import Template

from ..sources.base import RawOpportunity

logger = logging.getLogger(__name__)

DRAFT_PROMPT = """You are a senior proposal writer for a construction firm. Draft a FIRST-DRAFT \
proposal for the public solicitation below. Use the company profile for all firm-specific facts; \
where information is missing, insert a clearly marked [PLACEHOLDER: ...] so staff can fill it in. \
Do not invent licenses, dollar figures, or past projects.

Write in Markdown with these sections:
1. Cover Letter
2. Executive Summary
3. Company Qualifications & Relevant Experience
4. Project Understanding & Approach
5. Proposed Project Team & Key Personnel
6. Preliminary Schedule
7. Safety & Quality Approach
8. Assumptions, Clarifications & Exclusions
9. Compliance Matrix (map each evaluation criterion to where it is addressed)

# Opportunity
Title: {title}
Agency: {agency}
Solicitation #: {sol}
Type: {otype}
Due: {due}
Location: {location}
Estimated value: {value}
Description:
{description}

# Extracted Requirements (JSON)
{requirements}

# Company Profile (YAML/JSON)
{company}
"""

COVER_LETTER_TEMPLATE = Template(
    """{{ today }}

{{ opp.contact_name or "Procurement Office" }}
{{ opp.agency or "" }}

RE: {{ opp.title }}{% if opp.solicitation_number %} (Solicitation {{ opp.solicitation_number }}){% endif %}

Dear {{ opp.contact_name or "Selection Committee" }}:

{{ company.get("legal_name", company.get("name", "Our firm")) }} is pleased to submit this \
proposal in response to {{ opp.title }}. {% if company.get("years_in_business") %}With \
{{ company.get("years_in_business") }} years delivering {{ (company.get("specialties") or ["construction"]) | join(", ") }} \
projects{% if opp.state %} in {{ opp.state }}{% endif %}, {% endif %}we are confident in our \
ability to meet the requirements and schedule of this solicitation.

We have reviewed the solicitation in full and acknowledge all requirements and any issued addenda. \
Our team is prepared to {% if opp.due_date %}meet the {{ opp.due_date.strftime("%B %d, %Y") }} deadline and {% endif %}\
deliver this project safely, on schedule, and within budget.

Please direct any questions to {{ company.get("contact_name", "[PLACEHOLDER: contact name]") }} at \
{{ company.get("contact_email", "[PLACEHOLDER: email]") }} or {{ company.get("contact_phone", "[PLACEHOLDER: phone]") }}.

Respectfully submitted,

{{ company.get("contact_name", "[PLACEHOLDER: authorized signer]") }}
{{ company.get("contact_title", "") }}
{{ company.get("legal_name", company.get("name", "")) }}
{{ company.get("address", "") }}
"""
)

OFFLINE_PROPOSAL_TEMPLATE = Template(
    """# Proposal — {{ opp.title }}

> **DRAFT** generated {{ today }}. Review every [PLACEHOLDER] before submission.

| | |
|---|---|
| Agency | {{ opp.agency or "—" }} |
| Solicitation # | {{ opp.solicitation_number or "—" }} |
| Type | {{ opp.opportunity_type or "—" }} |
| Due | {{ opp.due_date.strftime("%Y-%m-%d %H:%M") if opp.due_date else "See solicitation" }} |
| Location | {{ [opp.city, opp.state] | select | join(", ") or "—" }} |
| Est. value | {{ "${:,.0f}".format(opp.estimated_value) if opp.estimated_value else "—" }} |

## 1. Executive Summary
{{ company.get("legal_name", company.get("name", "Our firm")) }} proposes to perform the work
described in {{ opp.title }}. [PLACEHOLDER: 2–3 sentence win theme tailored to this project.]

## 2. Company Qualifications & Relevant Experience
- **Firm:** {{ company.get("legal_name", company.get("name", "[PLACEHOLDER]")) }}
- **Years in business:** {{ company.get("years_in_business", "[PLACEHOLDER]") }}
- **Specialties:** {{ (company.get("specialties") or ["[PLACEHOLDER]"]) | join(", ") }}
- **Licenses:** {{ (company.get("licenses") or ["[PLACEHOLDER]"]) | join(", ") }}
- **Bonding capacity:** {{ company.get("bonding_capacity", "[PLACEHOLDER]") }}

### Relevant past projects
{% for p in company.get("past_projects", []) %}- {{ p.get("name", "Project") }} — {{ p.get("value", "") }} — {{ p.get("description", "") }}
{% else %}- [PLACEHOLDER: add 3–5 relevant past projects]
{% endfor %}

## 3. Project Understanding & Approach
[PLACEHOLDER: Summarize the scope from the solicitation and outline the construction approach,
phasing, and key risks.]

## 4. Proposed Project Team & Key Personnel
{% for k in company.get("key_personnel", []) %}- {{ k.get("name", "") }} — {{ k.get("role", "") }}{% if k.get("years") %} ({{ k.get("years") }} yrs){% endif %}
{% else %}- [PLACEHOLDER: list project manager, superintendent, safety officer]
{% endfor %}

## 5. Preliminary Schedule
[PLACEHOLDER: Milestone schedule from notice-to-proceed to substantial completion.]

## 6. Safety & Quality
- EMR: {{ company.get("emr", "[PLACEHOLDER]") }}
- Safety program: {{ company.get("safety_program", "[PLACEHOLDER]") }}
- [PLACEHOLDER: QA/QC plan summary]

## 7. Assumptions, Clarifications & Exclusions
- [PLACEHOLDER: list assumptions and exclusions]

## 8. Compliance Matrix
| Evaluation criterion | Where addressed |
|---|---|
{% for c in requirements.get("evaluation_criteria", []) %}| {{ c.get("criterion", "") }}{% if c.get("weight") %} ({{ c.get("weight") }}){% endif %} | [PLACEHOLDER: section reference] |
{% endfor %}
"""
)


class ProposalDrafter:
    """Generates a first-draft proposal and cover letter."""

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model

    def draft(
        self,
        opp: RawOpportunity,
        company: dict[str, Any],
        requirements: dict[str, Any],
    ) -> dict[str, str]:
        """Return {"proposal": markdown, "cover_letter": text, "engine": "claude"|"template"}."""
        cover_letter = COVER_LETTER_TEMPLATE.render(
            opp=opp, company=company, today=datetime.utcnow().strftime("%B %d, %Y")
        )

        if os.environ.get("ANTHROPIC_API_KEY"):
            proposal = self._draft_with_claude(opp, company, requirements)
            if proposal:
                return {"proposal": proposal, "cover_letter": cover_letter, "engine": "claude"}

        proposal = OFFLINE_PROPOSAL_TEMPLATE.render(
            opp=opp,
            company=company,
            requirements=requirements,
            today=datetime.utcnow().strftime("%B %d, %Y"),
        )
        return {"proposal": proposal, "cover_letter": cover_letter, "engine": "template"}

    def _draft_with_claude(
        self, opp: RawOpportunity, company: dict[str, Any], requirements: dict[str, Any]
    ) -> str | None:
        try:
            from anthropic import Anthropic
        except ImportError:
            logger.warning("anthropic not installed — using template proposal")
            return None

        import json

        try:
            client = Anthropic()
            message = client.messages.create(
                model=self.model,
                max_tokens=8192,
                messages=[{
                    "role": "user",
                    "content": DRAFT_PROMPT.format(
                        title=opp.title or "",
                        agency=opp.agency or "",
                        sol=opp.solicitation_number or "",
                        otype=opp.opportunity_type or "",
                        due=opp.due_date.strftime("%Y-%m-%d") if opp.due_date else "TBD",
                        location=", ".join(x for x in [opp.city, opp.state] if x),
                        value=f"${opp.estimated_value:,.0f}" if opp.estimated_value else "Not stated",
                        description=(opp.description or "")[:20000],
                        requirements=json.dumps(requirements, indent=2),
                        company=json.dumps(company, indent=2, default=str),
                    ),
                }],
            )
            return "".join(b.text for b in message.content if b.type == "text")
        except Exception as exc:
            logger.error("Claude proposal drafting failed: %s", exc)
            return None
