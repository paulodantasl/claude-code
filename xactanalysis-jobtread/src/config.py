"""Environment-based configuration for the XactAnalysis → JobTread bridge.

All secrets come from the environment (or a local .env file). The bridge
holds credentials for two things only: the company's own claims mailbox
(IMAP, read) and the JobTread API (grant key). It never holds XactAnalysis
portal credentials — see docs/INTEGRATION_OPTIONS.md.
"""

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(
            f"Missing required environment variable {name}. "
            "Copy .env.example to .env and fill it in."
        )
    return value


@dataclass
class Config:
    # --- Claims mailbox (your inbox, e.g. claims@yourdomain) ---
    imap_host: str = field(default_factory=lambda: _require("IMAP_HOST"))
    imap_port: int = field(default_factory=lambda: int(os.environ.get("IMAP_PORT", "993")))
    imap_user: str = field(default_factory=lambda: _require("IMAP_USER"))
    imap_password: str = field(default_factory=lambda: _require("IMAP_PASSWORD"))
    imap_folder: str = field(default_factory=lambda: os.environ.get("IMAP_FOLDER", "INBOX"))
    # Only process mail whose From header contains one of these substrings.
    # Empty string disables the filter (useful for a truly dedicated inbox).
    sender_filter: list = field(
        default_factory=lambda: [
            s.strip().lower()
            for s in os.environ.get(
                "SENDER_FILTER", "xactanalysis.com,xactware.com,verisk.com"
            ).split(",")
            if s.strip()
        ]
    )

    # --- JobTread ---
    jobtread_grant_key: str = field(default_factory=lambda: _require("JOBTREAD_GRANT_KEY"))
    jobtread_org_id: str = field(default_factory=lambda: _require("JOBTREAD_ORG_ID"))
    jobtread_api_url: str = field(
        default_factory=lambda: os.environ.get(
            "JOBTREAD_API_URL", "https://api.jobtread.com/pave"
        )
    )
    # Account type for the insured; JobTread convention is "customer".
    jobtread_account_type: str = field(
        default_factory=lambda: os.environ.get("JOBTREAD_ACCOUNT_TYPE", "customer")
    )

    # --- Bridge behavior ---
    poll_seconds: int = field(default_factory=lambda: int(os.environ.get("POLL_SECONDS", "300")))
    state_file: str = field(
        default_factory=lambda: os.environ.get("STATE_FILE", "state.json")
    )
    archive_dir: str = field(
        default_factory=lambda: os.environ.get("ARCHIVE_DIR", "processed")
    )
