#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for this repository.
# Prepares a Python virtualenv for the two runnable apps in this repo:
#   - estimating/  (Florida precon toolkit: workbook builder + deterministic validator)
#   - permit_scraper/  (commercial building-permit intelligence pipeline)
set -euo pipefail

cd "$(dirname "$0")/.."

# The base image ships Python 3.12 but not the venv module; add it once.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends python3-venv
fi

# Create the virtualenv only if it is missing (keeps re-runs fast).
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate

python -m pip install --upgrade pip

# App dependencies. Both requirement sets are safe to reinstall repeatedly.
pip install -r requirements.txt
pip install -r permit_scraper/requirements.txt

# Chromium for permit_scraper's Playwright-based portal scrapers.
# --with-deps installs the OS libraries the browser needs.
python -m playwright install --with-deps chromium

echo "Environment ready. Activate with: source .venv/bin/activate"
