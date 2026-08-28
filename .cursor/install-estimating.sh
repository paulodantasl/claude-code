#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the ESTIMATING environment.
# Covers the Florida precon toolkit in estimating/ (workbook builder,
# deterministic validator, loan-package builder, canonical<->derived sync).
# The toolkit's only third-party dependency is openpyxl; everything else is
# the Python standard library. Installs into its own virtualenv
# (.venv-estimating) so it never collides with the scraping environment.
set -euo pipefail

cd "$(dirname "$0")/.."

# The base image ships Python 3.12 but not the venv module; add it once.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends python3-venv
fi

if [ ! -x .venv-estimating/bin/python ]; then
  python3 -m venv .venv-estimating
fi
# shellcheck disable=SC1091
. .venv-estimating/bin/activate

python -m pip install --upgrade pip

# openpyxl version matches the pin in the repo's root requirements.txt.
pip install "openpyxl==3.1.5"

echo "Estimating env ready. Activate with: source .venv-estimating/bin/activate"
