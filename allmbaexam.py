import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import json
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urljoin


url = "https://www.shiksha.com/mba/exams-pc-101"


# ---------------- DRIVER SETUP ----------------
def create_driver():
    options = Options()

    # options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Remove this line if running on Windows
    # options.binary_location = "/usr/bin/chromium"

    service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)
    return driver


# ---------------- SCROLL FUNCTION ----------------
def scroll_to_bottom(driver, scroll_times=3, pause=2):
    for _ in range(scroll_times):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)


# ---------------- SCRAPER FUNCTION ----------------
def scrape_exam_from_url(driver, url):
    driver.get(url)

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CLASS_NAME, "uilp_exam_card"))
    )

    scroll_to_bottom(driver)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    results = []

    exam_cards = soup.select(".uilp_exam_card")

    for card in exam_cards:
        result = {}

        exam_title = card.select_one(".exam_title")

        if exam_title:
            result["exam_short_name"] = exam_title.get_text(strip=True)

            # 🔹 HREF Extract
            relative_link = exam_title.get("href")
            result["exam_relative_url"] = relative_link

            # 🔹 Full Absolute URL
            result["exam_full_url"] = urljoin(url, relative_link)
        else:
            result["exam_short_name"] = None
            result["exam_relative_url"] = None
            result["exam_full_url"] = None

        # Full Exam Name
        full_name = card.select_one(".exam_flnm")
        result["exam_full_name"] = full_name.get_text(strip=True) if full_name else None

        # Important Dates
        result["important_dates"] = []

        rows = card.select(".exam_impdates table tr")

        for row in rows:
            date_col = row.select_one(".fix-tdwidth p")
            event_col = row.select_one(".fix-textlength p")

            if date_col and event_col:
                result["important_dates"].append({
                    "date": " ".join(date_col.get_text().split()),
                    "event": event_col.get_text(strip=True)
                })

        results.append(result)

    return results


if __name__ == "__main__":
    driver = create_driver()

    try:
        data = scrape_exam_from_url(driver, url)

        # 🔹 JSON file me save karna
        with open("exam_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        print("✅ Data successfully saved to exam_data.json")

    finally:
        driver.quit()