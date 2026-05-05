#!/usr/bin/env python3
"""
PlanHub General Contractor Information Scraper

Automates login to PlanHub and extracts general contractor contact information
from all projects, exporting to a spreadsheet.
"""

import os
import time
import json
from datetime import datetime
from typing import List, Dict
import pandas as pd
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service

# Load environment variables from .env file
load_dotenv()


def find_chromedriver():
    """Find chromedriver in common locations"""
    import subprocess

    # Try to find chromedriver via which command (installed via brew)
    try:
        result = subprocess.run(["which", "chromedriver"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass

    # Try common installation paths
    common_paths = [
        "/usr/local/bin/chromedriver",
        "/opt/homebrew/bin/chromedriver",
        os.path.expanduser("~/.wdm/drivers/chromedriver/mac64/chromedriver"),
    ]

    for path in common_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path

    raise FileNotFoundError(
        "ChromeDriver not found. Install it with: brew install chromedriver"
    )


class PlanhubGCScraper:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.driver = None
        self.gc_data = []
        self.base_url = "https://www.planhub.com"

    def setup_driver(self, headless=False):
        """Initialize Chrome WebDriver"""
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")

        if headless:
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")

        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        try:
            chromedriver_path = find_chromedriver()
            service = Service(chromedriver_path)
        except FileNotFoundError as e:
            print(f"✗ {e}")
            raise

        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_window_size(1280, 720)
        print("✓ WebDriver initialized")

    def login(self):
        """Log into PlanHub"""
        try:
            print(f"Logging into PlanHub as {self.email}...")
            self.driver.get(f"{self.base_url}/login")
            time.sleep(2)

            # Find and fill email field
            email_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            email_input.clear()
            email_input.send_keys(self.email)

            # Find and fill password field
            password_input = self.driver.find_element(By.NAME, "password")
            password_input.clear()
            password_input.send_keys(self.password)

            # Click login button
            login_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Login') or contains(text(), 'Sign In')]")
            login_button.click()

            # Wait for dashboard to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//div[@class='dashboard'] | //main | //body[contains(@class, 'authenticated')]"))
            )
            print("✓ Successfully logged in")
            time.sleep(2)

        except TimeoutException:
            print("✗ Login timeout - check credentials or page structure")
            raise
        except Exception as e:
            print(f"✗ Login failed: {e}")
            raise

    def get_projects(self) -> List[str]:
        """Get all project links from dashboard"""
        try:
            print("Fetching projects list...")
            projects = []

            # Wait for projects to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href, '/projects/') or contains(@class, 'project')]"))
            )

            # Get all project links
            project_elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/projects/')]")

            for element in project_elements:
                href = element.get_attribute("href")
                if href and "/projects/" in href:
                    projects.append(href)

            # Remove duplicates while preserving order
            projects = list(dict.fromkeys(projects))
            print(f"✓ Found {len(projects)} projects")
            return projects

        except Exception as e:
            print(f"✗ Error fetching projects: {e}")
            return []

    def extract_gc_info_from_project(self, project_url: str) -> List[Dict]:
        """Extract GC information from a single project"""
        try:
            self.driver.get(project_url)
            time.sleep(2)

            gcs = []

            # Look for general contractor information in various common locations
            gc_selectors = [
                "//div[contains(text(), 'General Contractor')] //following-sibling::div",
                "//div[contains(text(), 'GC')] //following-sibling::div",
                "//label[contains(text(), 'General Contractor')] //following-sibling::*",
                "//span[contains(text(), 'General Contractor')] //following-sibling::*",
                "//div[@class='gc-info'] | //div[@class='general-contractor']",
                "//table//tr[contains(., 'General Contractor')]",
            ]

            # Try to find GC name, phone, email
            try:
                gc_name = self.driver.find_element(By.XPATH,
                    "//div[contains(text(), 'General Contractor')] | //label[contains(text(), 'General Contractor')] | //span[contains(text(), 'Contractor')]").text
                gc_name = gc_name.replace("General Contractor", "").replace("GC", "").strip()
            except:
                gc_name = ""

            # Try to find contact info
            try:
                contact_text = self.driver.find_element(By.XPATH, "//body").text
            except:
                contact_text = ""

            # Look for phone and email patterns
            gc_phone = self._extract_phone(contact_text)
            gc_email = self._extract_email(contact_text)

            # Get project name
            try:
                project_name = self.driver.find_element(By.XPATH, "//h1 | //h2[@class='project-name']").text
            except:
                project_name = project_url.split("/")[-1]

            if gc_name or gc_phone or gc_email:
                gcs.append({
                    "project_name": project_name,
                    "gc_name": gc_name,
                    "gc_phone": gc_phone,
                    "gc_email": gc_email,
                    "project_url": project_url,
                    "scraped_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

            return gcs

        except Exception as e:
            print(f"  ✗ Error extracting GC info from {project_url}: {e}")
            return []

    def _extract_phone(self, text: str) -> str:
        """Extract phone number from text"""
        import re
        pattern = r'\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})'
        match = re.search(pattern, text)
        return f"({match.group(1)}) {match.group(2)}-{match.group(3)}" if match else ""

    def _extract_email(self, text: str) -> str:
        """Extract email from text"""
        import re
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        match = re.search(pattern, text)
        return match.group(0) if match else ""

    def scrape_all_projects(self):
        """Scrape all projects for GC information"""
        try:
            projects = self.get_projects()
            total = len(projects)

            for idx, project_url in enumerate(projects, 1):
                print(f"[{idx}/{total}] Scraping {project_url}")
                gc_info = self.extract_gc_info_from_project(project_url)
                self.gc_data.extend(gc_info)
                time.sleep(1)  # Rate limiting

            print(f"\n✓ Scraped {len(self.gc_data)} GC records")

        except Exception as e:
            print(f"✗ Error during scraping: {e}")

    def export_to_spreadsheet(self, filename: str = "planhub_gc_contacts.xlsx"):
        """Export scraped data to Excel spreadsheet"""
        try:
            if not self.gc_data:
                print("No data to export")
                return

            df = pd.DataFrame(self.gc_data)

            # Reorder columns
            columns = ["project_name", "gc_name", "gc_phone", "gc_email", "project_url", "scraped_date"]
            df = df[columns]

            # Remove duplicates
            df = df.drop_duplicates(subset=["gc_email", "gc_phone"], keep="first")

            # Save to Excel
            df.to_excel(filename, index=False, sheet_name="GC Contacts")

            print(f"✓ Exported {len(df)} unique GC records to {filename}")
            return filename

        except Exception as e:
            print(f"✗ Error exporting to spreadsheet: {e}")

    def close(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()
            print("✓ WebDriver closed")


def main():
    # Get credentials from environment
    email = os.getenv("PLANHUB_EMAIL")
    password = os.getenv("PLANHUB_PASSWORD")

    if not email or not password:
        print("✗ Missing credentials!")
        print("Please set PLANHUB_EMAIL and PLANHUB_PASSWORD in .env file")
        return

    print(f"Starting PlanHub scraper...")
    print(f"Email: {email}")
    print()

    scraper = PlanhubGCScraper(email, password)

    try:
        # Check if running in headless mode (no display server)
        headless = os.getenv("HEADLESS", "false").lower() == "true"
        scraper.setup_driver(headless=headless)
        scraper.login()
        scraper.scrape_all_projects()
        scraper.export_to_spreadsheet()
        print("\n✓ Scraping completed successfully!")

    except KeyboardInterrupt:
        print("\n✗ Scraping interrupted by user")
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
