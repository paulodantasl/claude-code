"""
Bid Tracker — public construction bidding tracker and submittal prep.

Weekly pipeline that:
  1. Pulls open public solicitations from configured sources (SAM.gov, RSS
     procurement feeds, agency portals).
  2. Qualifies each opportunity against the company's criteria (NAICS, project
     type, geography, contract value, bonding capacity, set-asides, keywords).
  3. Builds an organised bid package folder for every qualified opportunity:
     opportunity summary, requirements checklist, submittal checklist, the
     downloaded solicitation documents, and a first-draft proposal.
  4. Alerts the team (console / Slack / email).
"""

__version__ = "0.1.0"
