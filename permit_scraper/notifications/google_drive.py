"""
Google Drive / Sheets integration for permit match output.

Supports two auth methods — pick whichever fits your setup:

  1. Service Account (recommended for automation / servers)
     - Create a service account in Google Cloud Console
     - Download the JSON key file
     - Set GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/key.json
     - Share your target Drive folder with the service account email

  2. OAuth2 / user credentials (for personal Google accounts)
     - Create an OAuth2 "Desktop app" credential in Google Cloud Console
     - Download client_secret.json
     - Set GOOGLE_OAUTH_CLIENT_FILE=/path/to/client_secret.json
     - First run opens a browser for consent; token cached in ~/.permit_scraper_token.json

Quick start (service account):
    exporter = GoogleDriveExporter.from_env()
    url = exporter.export_matches(matched_rows, sheet_title="Tampa Bay Permits 2025+")
    print("Sheet URL:", url)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Column definitions: (header_label, data_key, width_px, format)
COLUMNS = [
    ("Filed Date",       "filed_date",      90,  "date"),
    ("Permit #",         "permit_number",   130, "text"),
    ("County",           "county",          180, "text"),
    ("City",             "city",            110, "text"),
    ("Address",          "address",         220, "text"),
    ("ZIP",              "zip_code",         65, "text"),
    ("Permit Type",      "permit_type",     185, "text"),
    ("Status",           "status",          130, "status"),
    ("Applicant (Filed)","applicant_name",  220, "text"),
    ("Owner of Record",  "owner_name",      200, "text"),
    ("GC / Contractor",  "contractor_name", 200, "text"),
    ("Description",      "description",     350, "text"),
    ("Est. Value",       "est_value",       110, "currency"),
    ("Sq Ft",            "sqft",             90, "number"),
    ("Parcel #",         "parcel_number",   140, "text"),
    ("Matched Company",  "matched_company", 140, "company"),
    ("Match Score",      "match_score",      90, "text"),
]

# Status badge colors
STATUS_COLORS = {
    "Permit Issued":        {"red": 0.78, "green": 0.91, "blue": 0.78},  # light green
    "Plan Review":          {"red": 1.00, "green": 0.95, "blue": 0.78},  # light yellow
    "Application Received": {"red": 0.78, "green": 0.88, "blue": 0.98},  # light blue
    "Expired":              {"red": 0.95, "green": 0.78, "blue": 0.78},  # light red
}

# Company highlight colors (light tints)
COMPANY_COLORS = {
    "Amazon":       {"red": 1.00, "green": 0.95, "blue": 0.70},
    "Meta / Facebook": {"red": 0.75, "green": 0.85, "blue": 1.00},
    "Microsoft":    {"red": 0.75, "green": 0.90, "blue": 1.00},
    "Publix":       {"red": 0.78, "green": 0.95, "blue": 0.78},
    "Walmart":      {"red": 0.80, "green": 0.90, "blue": 1.00},
    "Target":       {"red": 1.00, "green": 0.82, "blue": 0.82},
    "Costco":       {"red": 1.00, "green": 0.87, "blue": 0.78},
    "FedEx":        {"red": 0.85, "green": 0.78, "blue": 1.00},
    "UPS":          {"red": 0.95, "green": 0.85, "blue": 0.65},
    "Home Depot":   {"red": 1.00, "green": 0.85, "blue": 0.70},
    "HCA Healthcare": {"red": 0.85, "green": 0.95, "blue": 0.85},
    "Marriott":     {"red": 0.95, "green": 0.90, "blue": 0.78},
    "Chick-fil-A":  {"red": 1.00, "green": 0.92, "blue": 0.70},
    "McDonald's":   {"red": 1.00, "green": 0.95, "blue": 0.70},
}

WHITE  = {"red": 1.0, "green": 1.0, "blue": 1.0}
HEADER = {"red": 0.20, "green": 0.29, "blue": 0.49}   # dark navy


def _build_credentials(
    service_account_file: str | None = None,
    oauth_client_file: str | None = None,
    token_cache: str = "~/.permit_scraper_token.json",
):
    """Return Google credentials object from service account or OAuth2."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
    ]

    if service_account_file:
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_file(
            service_account_file, scopes=scopes
        )

    if oauth_client_file:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        cache_path = Path(token_cache).expanduser()
        if cache_path.exists():
            creds = Credentials.from_authorized_user_file(str(cache_path), scopes)
            if creds and creds.valid:
                return creds
            if creds and creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                cache_path.write_text(creds.to_json())
                return creds

        flow = InstalledAppFlow.from_client_secrets_file(oauth_client_file, scopes)
        creds = flow.run_local_server(port=0)
        cache_path.write_text(creds.to_json())
        return creds

    raise ValueError(
        "No Google credentials found. Set GOOGLE_SERVICE_ACCOUNT_FILE or "
        "GOOGLE_OAUTH_CLIENT_FILE in your environment / .env file."
    )


class GoogleDriveExporter:
    """
    Exports permit match data to a formatted Google Sheet and
    optionally uploads CSVs to a Google Drive folder.
    """

    def __init__(self, credentials, drive_folder_id: str | None = None):
        from googleapiclient.discovery import build
        self.sheets = build("sheets", "v4", credentials=credentials)
        self.drive  = build("drive",  "v3", credentials=credentials)
        self.folder_id = drive_folder_id

    @classmethod
    def from_env(cls) -> "GoogleDriveExporter":
        sa_file    = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
        oauth_file = os.environ.get("GOOGLE_OAUTH_CLIENT_FILE")
        folder_id  = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
        creds = _build_credentials(sa_file, oauth_file)
        return cls(creds, folder_id)

    # ── Public API ──────────────────────────────────────────────────────────

    def export_matches(
        self,
        matched_rows: list[dict],
        all_rows: list[dict] | None = None,
        sheet_title: str | None = None,
    ) -> str:
        """
        Create a Google Sheets workbook with:
          - 'Matches'  tab — company-matched permits, formatted and color-coded
          - 'All Permits' tab — full dataset
          - 'Summary' tab — pivot by company and county

        Returns the URL of the created spreadsheet.
        """
        title = sheet_title or f"Permit Intelligence — Central West FL — {datetime.now().strftime('%Y-%m-%d')}"
        logger.info("Creating Google Sheet: %s", title)

        # Create the spreadsheet
        spreadsheet = self.sheets.spreadsheets().create(body={
            "properties": {"title": title},
            "sheets": [
                {"properties": {"title": "Matches",     "index": 0, "sheetId": 0}},
                {"properties": {"title": "All Permits", "index": 1, "sheetId": 1}},
                {"properties": {"title": "Summary",     "index": 2, "sheetId": 2}},
            ],
        }).execute()

        spreadsheet_id = spreadsheet["spreadsheetId"]
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        logger.info("Sheet created: %s", url)

        requests: list[dict] = []

        # ── Tab 0: Matches ─────────────────────────────────────────────
        requests += self._write_permit_tab(matched_rows, sheet_id=0, tab_name="Matches")

        # ── Tab 1: All Permits ─────────────────────────────────────────
        if all_rows:
            requests += self._write_permit_tab(all_rows, sheet_id=1, tab_name="All Permits")

        # ── Tab 2: Summary ─────────────────────────────────────────────
        requests += self._write_summary_tab(matched_rows, sheet_id=2)

        # Apply all formatting in one batch
        self.sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()

        # Move to target folder if specified
        if self.folder_id:
            self._move_to_folder(spreadsheet_id)

        logger.info("Export complete: %s", url)
        return url

    def upload_csv(self, csv_path: str | Path, filename: str | None = None) -> str:
        """Upload a CSV file to the configured Drive folder. Returns the file URL."""
        from googleapiclient.http import MediaFileUpload

        path = Path(csv_path)
        name = filename or path.name

        meta = {"name": name, "mimeType": "text/csv"}
        if self.folder_id:
            meta["parents"] = [self.folder_id]

        media = MediaFileUpload(str(path), mimetype="text/csv")
        f = self.drive.files().create(
            body=meta, media_body=media, fields="id, webViewLink"
        ).execute()
        url = f.get("webViewLink", f"https://drive.google.com/file/d/{f['id']}")
        logger.info("Uploaded %s → %s", name, url)
        return url

    # ── Internal builders ───────────────────────────────────────────────────

    def _write_permit_tab(self, rows: list[dict], sheet_id: int, tab_name: str) -> list[dict]:
        """Return batchUpdate requests to populate and format one permit tab."""
        reqs: list[dict] = []
        if not rows:
            return reqs

        headers = [c[0] for c in COLUMNS]
        keys    = [c[1] for c in COLUMNS]
        widths  = [c[2] for c in COLUMNS]
        n_cols  = len(COLUMNS)
        n_rows  = len(rows) + 1   # +1 for header

        # 1. Write values
        values = [headers] + [[r.get(k, "") for k in keys] for r in rows]
        reqs.append({
            "updateCells": {
                "range":  {"sheetId": sheet_id, "startRowIndex": 0, "startColumnIndex": 0},
                "rows":   self._cells_from_values(values),
                "fields": "userEnteredValue",
            }
        })

        # 2. Header row formatting (navy bg, white bold text)
        reqs.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                "cell":  {
                    "userEnteredFormat": {
                        "backgroundColor": HEADER,
                        "textFormat":      {"foregroundColor": WHITE, "bold": True, "fontSize": 10},
                        "verticalAlignment": "MIDDLE",
                        "horizontalAlignment": "CENTER",
                        "wrapStrategy": "CLIP",
                    }
                },
                "fields": "userEnteredFormat",
            }
        })

        # 3. Freeze header row + first column
        reqs.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 1},
                },
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
            }
        })

        # 4. Column widths
        for i, px in enumerate(widths):
            reqs.append({
                "updateDimensionProperties": {
                    "range":  {"sheetId": sheet_id, "dimension": "COLUMNS",
                               "startIndex": i, "endIndex": i + 1},
                    "properties": {"pixelSize": px},
                    "fields": "pixelSize",
                }
            })

        # 5. Row height for data rows
        if len(rows) > 0:
            reqs.append({
                "updateDimensionProperties": {
                    "range":  {"sheetId": sheet_id, "dimension": "ROWS",
                               "startIndex": 1, "endIndex": n_rows},
                    "properties": {"pixelSize": 22},
                    "fields": "pixelSize",
                }
            })

        # 6. Per-row company + status coloring
        company_col_idx = keys.index("matched_company") if "matched_company" in keys else -1
        status_col_idx  = keys.index("status")          if "status"          in keys else -1

        for i, row in enumerate(rows, start=1):
            company = row.get("matched_company", "")
            status  = row.get("status", "")
            bg = COMPANY_COLORS.get(company)

            if bg:
                reqs.append({
                    "repeatCell": {
                        "range": {"sheetId": sheet_id,
                                  "startRowIndex": i, "endRowIndex": i + 1,
                                  "startColumnIndex": 0, "endColumnIndex": n_cols},
                        "cell":  {"userEnteredFormat": {"backgroundColor": bg}},
                        "fields": "userEnteredFormat.backgroundColor",
                    }
                })

            if status_col_idx >= 0:
                status_bg = STATUS_COLORS.get(status)
                if status_bg:
                    reqs.append({
                        "repeatCell": {
                            "range": {"sheetId": sheet_id,
                                      "startRowIndex": i, "endRowIndex": i + 1,
                                      "startColumnIndex": status_col_idx,
                                      "endColumnIndex": status_col_idx + 1},
                            "cell":  {"userEnteredFormat": {
                                "backgroundColor": status_bg,
                                "textFormat": {"bold": True},
                            }},
                            "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat.bold",
                        }
                    })

        # 7. Auto filter on header row
        reqs.append({
            "setBasicFilter": {
                "filter": {
                    "range": {"sheetId": sheet_id,
                              "startRowIndex": 0, "endRowIndex": n_rows,
                              "startColumnIndex": 0, "endColumnIndex": n_cols},
                }
            }
        })

        # 8. Alternating row banding (zebra) — subtle grey for un-colored rows
        reqs.append({
            "addBanding": {
                "bandedRange": {
                    "bandedRangeId": sheet_id * 10 + 1,
                    "range": {"sheetId": sheet_id,
                              "startRowIndex": 1, "endRowIndex": n_rows,
                              "startColumnIndex": 0, "endColumnIndex": n_cols},
                    "rowProperties": {
                        "headerColor":      {"red": 0.95, "green": 0.95, "blue": 0.95},
                        "firstBandColor":   {"red": 1.00, "green": 1.00, "blue": 1.00},
                        "secondBandColor":  {"red": 0.96, "green": 0.96, "blue": 0.96},
                    },
                }
            }
        })

        return reqs

    def _write_summary_tab(self, rows: list[dict], sheet_id: int) -> list[dict]:
        """Build a summary pivot by company and by county."""
        from collections import defaultdict

        def to_float(s: str) -> float:
            return float(s.replace("$", "").replace(",", "")) if s and s != "—" else 0.0

        by_company: dict[str, list] = defaultdict(list)
        by_county:  dict[str, list] = defaultdict(list)
        for r in rows:
            by_company[r.get("matched_company", "Unknown")].append(r)
            by_county[r.get("county", "Unknown")].append(r)

        company_rows = sorted(by_company.items(), key=lambda x: -sum(to_float(r["est_value"]) for r in x[1]))
        county_rows  = sorted(by_county.items(),  key=lambda x: -sum(to_float(r["est_value"]) for r in x[1]))

        values: list[list] = []
        values.append([f"Permit Intelligence Summary — Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
        values.append([])
        values.append(["BY COMPANY", "", "", ""])
        values.append(["Company", "# Permits", "Total Est. Value", "Avg Value"])
        for company, rs in company_rows:
            total = sum(to_float(r["est_value"]) for r in rs)
            avg   = total / len(rs) if rs else 0
            values.append([company, len(rs), f"${total:,.0f}", f"${avg:,.0f}"])

        values.append([])
        values.append(["BY COUNTY", "", "", ""])
        values.append(["County", "# Permits", "Total Est. Value", "Avg Value"])
        for county, rs in county_rows:
            total = sum(to_float(r["est_value"]) for r in rs)
            avg   = total / len(rs) if rs else 0
            values.append([county, len(rs), f"${total:,.0f}", f"${avg:,.0f}"])

        grand_total = sum(to_float(r["est_value"]) for r in rows)
        values.append([])
        values.append(["TOTAL", len(rows), f"${grand_total:,.0f}", ""])

        reqs: list[dict] = []

        # Write values
        reqs.append({
            "updateCells": {
                "range":  {"sheetId": sheet_id, "startRowIndex": 0, "startColumnIndex": 0},
                "rows":   self._cells_from_values(values),
                "fields": "userEnteredValue",
            }
        })

        # Title row bold + navy
        reqs.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                "cell":  {"userEnteredFormat": {
                    "backgroundColor": HEADER,
                    "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 12},
                }},
                "fields": "userEnteredFormat",
            }
        })

        # Col widths
        for i, px in enumerate([200, 90, 160, 130]):
            reqs.append({
                "updateDimensionProperties": {
                    "range":  {"sheetId": sheet_id, "dimension": "COLUMNS",
                               "startIndex": i, "endIndex": i + 1},
                    "properties": {"pixelSize": px},
                    "fields": "pixelSize",
                }
            })

        return reqs

    @staticmethod
    def _cells_from_values(values: list[list]) -> list[dict]:
        """Convert a 2D list of strings/ints to Sheets API cell format."""
        rows = []
        for row in values:
            cells = []
            for v in row:
                if isinstance(v, (int, float)):
                    cells.append({"userEnteredValue": {"numberValue": v}})
                else:
                    cells.append({"userEnteredValue": {"stringValue": str(v)}})
            rows.append({"values": cells})
        return rows

    def _move_to_folder(self, file_id: str) -> None:
        """Move a Drive file into the configured folder."""
        f = self.drive.files().get(fileId=file_id, fields="parents").execute()
        previous_parents = ",".join(f.get("parents", []))
        self.drive.files().update(
            fileId=file_id,
            addParents=self.folder_id,
            removeParents=previous_parents,
            fields="id, parents",
        ).execute()
