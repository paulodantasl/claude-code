---
description: Build the 13-tab bank construction-loan package workbook (Sources & Uses, AIA G703 SOV, draw schedule, Gantt).
argument-hint: <project name or path to the project folder>
allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob
---

Build the bank construction-loan package for: **$ARGUMENTS**

Delegate to the `cost-estimator` subagent — it owns the cost data and the Excel builders,
and knows where its knowledge base and scripts live.

1. **Require a priced estimate.** `lineitems.csv` and `markups.csv` must exist in the
   project folder. If they do not, run `/estimate` first — the loan package is a
   presentation of the estimate, not an independent source of numbers.
2. **Set up the config.** The builder reads `loan-package-config.json` from the project
   folder. Copy the bundled `loan-package-config.template.json` in and fill it out with the
   user: company block (name, license, contact), project block (address, county, SF,
   stories, occupancy, construction type, flood zone/BFE, wind speed, FBC edition), owner,
   architect, engineer, geotech, lender, schedule (start date, duration, retainage), and the
   loan assumptions (land cost, soft-cost percentages, owner equity, contingency).
   **Ask the user for anything you do not have — never invent a lender, a license number, a
   sealed date, or a loan number.** Leave unknown fields as explicit placeholders.
3. **Optional branding.** A `logo.png` in the project folder (or `company.logo` in the
   config) is picked up automatically. The workbook builds fine without one.
4. **Delegate the build.** Run the bundled `build_loan_package_xlsx.py` against the project
   folder to produce `construction-loan-package.xlsx` — Cover, Inputs, Executive Summary,
   Sources & Uses, Budget Detail, Budget Summary, AIA G703 Schedule of Values, Draw
   Schedule, Timeline/Gantt, Scope, Allowances, Alternates, and Documents.

When it returns, report: total project cost, the sources-and-uses split (loan vs. equity),
the draw schedule shape against the stated duration, and every field still carrying a
placeholder. Flag that retainage, contingency, and draw timing are lender-negotiable.

Requires `openpyxl` (`pip install openpyxl`). This is the loan-package stage only; `/bid`
runs the full precon pipeline.
