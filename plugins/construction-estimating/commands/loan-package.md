---
description: Build the 13-tab bank construction-loan package workbook (Cover, Sources & Uses, AIA G703 SOV, Draw Schedule, Gantt, …) for a priced project.
argument-hint: <project name or path under estimating-projects/>
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(mkdir:*)
---

Build the bank construction-loan package for: **$ARGUMENTS**

Inputs live in the project folder `estimating-projects/<slug>/` under the current working
directory. The builder needs `lineitems.csv` + `markups.csv` + `loan-package-config.json`
— NOT `estimate.xlsx` (the workbook recomputes from the CSVs).

1. **Verify inputs.** Confirm `lineitems.csv` and `markups.csv` exist (if not, run the
   estimate stage first — `/bid` or the `cost-estimator` agent). Confirm `markups.csv`
   carries all 7 waterfall keys; missing keys silently default and will disagree with
   the estimate workbook.
2. **Config.** If `loan-package-config.json` is missing, copy
   `${CLAUDE_PLUGIN_ROOT}/templates/loan-package-config.template.json` into the project
   folder and fill it in — ask the user for borrower/owner identity, loan terms (amount,
   LTC, interest reserve), target start date, and construction duration. Never invent these.
3. **Logo (optional).** `logo.png` in the project folder or `company.logo` in the config
   brands the package; the workbook builds fine without it.
4. **Build:** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/build_loan_package_xlsx.py estimating-projects/<slug>/`
5. **Confirm** the 13 tabs built and report: loan amount vs Sources & Uses, the draw
   count/period, SOV total (must equal the estimate BID TOTAL from `estimate-summary.md`
   — flag any mismatch), and any placeholder the user still must fill.
