# PlanHub General Contractor Scraper

Automated tool to extract general contractor (GC) contact information from all PlanHub projects and export to a spreadsheet.

## Features

- ✓ Automatic login to PlanHub
- ✓ Scrapes all projects for GC information
- ✓ Extracts name, phone, email for each GC
- ✓ Removes duplicate records
- ✓ Exports to Excel spreadsheet with project details
- ✓ Timestamps each scraping run

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Credentials

Create a `.env` file in the project root with your PlanHub credentials:

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

Or set environment variables:
```bash
export PLANHUB_EMAIL="your@email.com"
export PLANHUB_PASSWORD="your_password"
```

**⚠️ Security Note:** The `.env` file is in `.gitignore` and will never be committed to git. Always use `.env` for credentials, never hardcode them.

## Usage

### Run the Scraper

```bash
python planhub_gc_scraper.py
```

Or provide credentials via command line:
```bash
PLANHUB_EMAIL="your@email.com" PLANHUB_PASSWORD="password" python planhub_gc_scraper.py
```

### Output

The script generates `planhub_gc_contacts.xlsx` with columns:
- **project_name** - Name of the project
- **gc_name** - General contractor name
- **gc_phone** - General contractor phone number
- **gc_email** - General contractor email
- **project_url** - Link to the project on PlanHub
- **scraped_date** - When the data was collected

## How It Works

1. **Login** - Authenticates to PlanHub using your credentials
2. **Fetch Projects** - Gets list of all your projects
3. **Extract GC Info** - For each project, extracts contractor information
4. **Deduplicate** - Removes duplicate records based on email/phone
5. **Export** - Saves results to Excel spreadsheet

## Troubleshooting

### Login fails
- Verify email and password are correct
- Check if PlanHub requires 2FA (not currently supported)
- Ensure your account has access to projects

### No GC data found
- PlanHub may have different page structure
- GC information might be in different fields
- Update selectors in `extract_gc_info_from_project()` method

### Slow scraping
- Add more `time.sleep()` calls if page load times vary
- Increase waits in `WebDriverWait` timeouts

## Next Steps

Once you have the GC spreadsheet, you can:
- Import into CRM (Salesforce, HubSpot)
- Use for cold calling campaigns
- Build mailing lists
- Track outreach status

## Maintenance

- Update selectors if PlanHub redesigns their UI
- Add additional data fields as needed
- Consider API integration if PlanHub releases one
