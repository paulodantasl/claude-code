#!/bin/bash
# Double-click this file on your Mac to install and run the permit scraper.

cd "$(dirname "$0")"

echo "========================================="
echo "  Permit Scraper — Setup & Run"
echo "========================================="
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "ERROR: Python 3 is not installed."
  echo "Please go to https://www.python.org/downloads/ and install it, then try again."
  read -p "Press Enter to close..."
  exit 1
fi

echo "✓ Python found: $(python3 --version)"
echo ""

# Install dependencies
echo "Installing required packages (this may take a minute)..."
python3 -m pip install -q -r requirements.txt
if [ $? -ne 0 ]; then
  echo ""
  echo "ERROR: Failed to install packages."
  read -p "Press Enter to close..."
  exit 1
fi
echo "✓ Packages installed."
echo ""

# Set up .env if it doesn't exist
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "⚠️  A configuration file (.env) has been created in this folder."
  echo "    Please open it with a text editor and fill in your API keys before running."
  echo ""
  open .env
  read -p "Press Enter once you've saved your .env file..."
fi

echo ""
echo "Running permit scraper..."
echo "-----------------------------------------"
python3 -m permit_scraper run --google-sheet

echo ""
echo "-----------------------------------------"
echo "Done! Press Enter to close."
read
