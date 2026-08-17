#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the SCRAPING environment.
# Covers the lead-generation / scraping side of the repo:
#   - permit_scraper/        (commercial building-permit intelligence pipeline)
#   - planhub_gc_scraper.py  (PlanHub GC/bid-board scraper — uses the root requirements)
# Installs into its own virtualenv (.venv-permit) so it never collides with the
# estimating environment.
set -euo pipefail

cd "$(dirname "$0")/.."

# The base image ships Python 3.12 but not the venv module; add it once.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends python3-venv
fi

if [ ! -x .venv-permit/bin/python ]; then
  python3 -m venv .venv-permit
fi
# shellcheck disable=SC1091
. .venv-permit/bin/activate

python -m pip install --upgrade pip

# Root deps (selenium/pandas/webdriver-manager) power planhub_gc_scraper.py.
pip install -r requirements.txt
# permit_scraper package deps.
pip install -r permit_scraper/requirements.txt

# Chromium for permit_scraper's Playwright-based portal scrapers.
python -m playwright install --with-deps chromium

echo "Scraping env ready. Activate with: source .venv-permit/bin/activate"
