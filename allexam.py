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


# ---------------- DRIVER SETUP ----------------
def create_driver():
    options = Options()

    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Remove this line if running on Windows
    options.binary_location = "/usr/bin/chromium"

    service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)
    return driver


# ---------------- SCROLL FUNCTION ----------------
def scroll_to_bottom(driver, scroll_times=3, pause=2):
    for _ in range(scroll_times):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)

BASE = "https://www.shiksha.com"
LISTING_URL = "https://www.shiksha.com/mba/exams-pc-101"


# ---------------- LISTING SCRAPER ----------------
def scrape_listing_page(driver,page_no=1):
    if page_no == 1:
        url = LISTING_URL
    else:
        url = f"{LISTING_URL}?pageNo={page_no}"

    driver.get(url)

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CLASS_NAME, "uilp_exam_card"))
    )

    scroll_to_bottom(driver)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    exams = []

    cards = soup.select(".uilp_exam_card")

    for card in cards:
        result = {}

        exam_title = card.select_one(".exam_title")

        if exam_title:
            result["exam_short_name"] = exam_title.get_text(strip=True)

            relative_link = exam_title.get("href")
            result["exam_relative_url"] = relative_link
            result["exam_full_url"] = urljoin(BASE, relative_link)

            # 🔥 Base URL for further pattern/syllabus scraping
            result["base_url"] = urljoin(BASE, relative_link).rstrip("/")
        else:
            continue

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

        exams.append(result)

    return exams



# 🔥 Scrape Multiple Pages
# all_exams = []

# for page in range(1, 5):   # 1 se 4 tak
#     print(f"Scraping page {page}")
#     data = scrape_listing_page(driver, page)
#     all_exams.extend(data)

# print("Total exams scraped:", len(all_exams))

def extract_cat_exam_data(driver, URLS):
    driver.get(URLS["overviews"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_rich_content(container):

    if not container:
        return {"blocks": []}

    content = {"blocks": []}

    elements = container.find_all(
        ["h2", "h3", "h4", "p", "ul", "table", "iframe"],
        recursive=True
    )

    for element in elements:

        # HEADINGS
        if element.name in ["h2", "h3", "h4"]:
            text = element.get_text(" ", strip=True)
            if text:
                content["blocks"].append({
                    "type": "heading",
                    "value": text
                })

        # PARAGRAPH
        elif element.name == "p":
            if element.find_parent("table"):
                continue
            text = element.get_text(" ", strip=True)
            if text:
                content["blocks"].append({
                    "type": "paragraph",
                    "value": text
                })

        # LIST
        elif element.name == "ul":
            items = [
                li.get_text(" ", strip=True)
                for li in element.find_all("li", recursive=False)
            ]
            if items:
                content["blocks"].append({
                    "type": "list",
                    "value": items
                })

        # TABLE
        elif element.name == "table":
            table_data = []
            for row in element.find_all("tr"):
                cols = [
                    c.get_text(" ", strip=True)
                    for c in row.find_all(["th", "td"])
                ]
                if cols:
                    table_data.append(cols)

            if table_data:
                content["blocks"].append({
                    "type": "table",
                    "value": table_data
                })

        # IFRAME
        elif element.name == "iframe":
            src = element.get("src") or element.get("data-original")
            if src:
                content["blocks"].append({
                    "type": "iframe",
                    "value": src
                })

    return content

def extract_faqs(soup):

    faqs = []
    question_blocks = soup.find_all("strong", class_="flx-box")

    for q in question_blocks:
        question = q.get_text(" ", strip=True).replace("Q:", "").strip()

        answer_wrapper = q.find_parent().find_next_sibling("div")
        if not answer_wrapper:
            continue

        answer_div = answer_wrapper.find("div", class_="facb5f")
        if not answer_div:
            continue

        answer = answer_div.get_text(" ", strip=True).replace("A:", "").strip()

        faqs.append({
            "question": question,
            "answer": answer
        })

    return faqs

def extract_polls(soup):

    polls = []
    poll_containers = soup.find_all("div", class_="poll-container")

    for poll in poll_containers:
        question_div = poll.find("div", class_="poll-question")
        options = poll.find_all("div", class_="poll-option")
        votes_span = poll.find("span", string=lambda x: x and "votes" in x)

        if not question_div:
            continue

        poll_data = {
            "question": question_div.get_text(strip=True),
            "options": [
                opt.get_text(" ", strip=True)
                for opt in options
            ],
            "votes": votes_span.get_text(strip=True) if votes_span else None
        }

        polls.append(poll_data)

    return polls

def extract_result_data(driver, URLS):
    driver.get(URLS["results"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_cut_off_data(driver, URLS):
    driver.get(URLS["cut_off"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_app_form_data(driver, URLS):
    driver.get(URLS["app_form"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_sel_proccess_data(driver, URLS):
    driver.get(URLS["sel_proccess"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_answerkey_data(driver, URLS):
    driver.get(URLS["ans_key"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_Counselling_data(driver, URLS):
    driver.get(URLS["counselling"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_Analysis_data(driver, URLS):
    driver.get(URLS["analysis"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_question_paper_data(driver, URLS):
    driver.get(URLS["question_paper"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_admit_card_data(driver, URLS):
    driver.get(URLS["admit_card"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_dates_data(driver, URLS):
    driver.get(URLS["dates"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_mock_test_data(driver, URLS):
    driver.get(URLS["mock_test"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_registration_data(driver, URLS):
    driver.get(URLS["registration"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_syllabus_data(driver, URLS):
    driver.get(URLS["syllabus"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_pattern_data(driver, URLS):
    driver.get(URLS["pattern"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_preparation_data(driver, URLS):
    driver.get(URLS["preparation"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_books_data(driver, URLS):
    driver.get(URLS["books"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_notification_data(driver, URLS):
    driver.get(URLS["notification"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_center_data(driver, URLS):
    driver.get(URLS["centre"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_news_data(driver, URLS):
    driver.get(URLS["news"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_college_data(driver, URLS):
    driver.get(URLS["college"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

def extract_mca_data(driver, URLS):
    driver.get(URLS["mca"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data
def extract_me_lateral_entry_data(driver, URLS):
    driver.get(URLS["me-mtech-mtech-lateral-entry-985"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data
def extract_cat_MArch_data(driver, URLS):
    driver.get(URLS["march-986"])

    # Wait until page loads
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )

    # Scroll to bottom (for lazy loading content)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    data = {}

    # =====================================
    # TITLE
    # =====================================
    h1 = soup.find("h1")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # =====================================
    # UPDATED DATE
    # =====================================
    updated_span = soup.find("span", string=lambda x: x and "Updated" in x)
    data["updated_on"] = updated_span.get_text(strip=True) if updated_span else None

    # =====================================
    # AUTHOR INFO
    # =====================================
    author_data = {}
    author_block = soup.find("div", class_="ppBox")

    if author_block:
        author_link = author_block.find("a")
        img = author_block.find("img")
        role = author_block.find("p", class_="ePPDetail")

        author_data = {
            "name": author_link.get_text(strip=True) if author_link else None,
            "profile_url": author_link["href"] if author_link else None,
            "role": role.get_text(" ", strip=True) if role else None,
            "image": img["src"] if img else None
        }

    data["author"] = author_data

    # =====================================
    # ALL CONTENT SECTIONS
    # =====================================
    sections = soup.find_all("div", class_="sectionalWrapperClass")
    all_sections = []

    for sec in sections:
        content_blocks = extract_rich_content(sec)
        if content_blocks["blocks"]:
            all_sections.append(content_blocks)

    data["content_sections"] = all_sections

    # =====================================
    # FAQ SECTION
    # =====================================
    data["faqs"] = extract_faqs(soup)

    # =====================================
    # POLL SECTION
    # =====================================
    data["polls"] = extract_polls(soup)

    return data

# ---------------- MAIN ----------------
# if __name__ == "__main__":
#     driver = create_driver()

#     try:
#         final_data = []

#         # 🔹 Loop through listing pages
#         page = 1
#         while True:
#             print(f"Scraping listing page {page}")
            
#             exams = scrape_listing_page(driver, page)  # Make scrape_listing_page accept page param
            
#             if not exams:  # agar page empty ho, stop loop
#                 break


#         for exam in exams:

#             print(f"Processing: {exam['exam_short_name']}")

#             base_url = exam["base_url"].rstrip("/")

#             # 🔥 Auto-create URLs
#             URLS = {
#                 "overviews":base_url,
#                 "dates": base_url + "-dates",
#                 "ans_key": base_url + "-answer-key",
#                 "results": base_url + "-results",
#                 "question_paper": base_url + "-question-papers",
#                 "pattern": base_url + "-pattern",
#                 "cut_off": base_url + "-cutoff",
#                 "counselling": base_url + "-counselling",
#                 "app_form": base_url + "-application-form",
#                 "syllabus": base_url + "-syllabus",
#                 "books": base_url + "-books",
#                 "preparation": base_url + "-preparation",
#                 "admit_card": base_url + "-admit-card",
#                 "news": base_url + "-news",
#                 "analysis": base_url + "-analysis",
#                 "mock_test": base_url + "-mocktest",
#                 "registration": base_url + "-registration",
#                 "college": base_url + "-college",
#                 "centre": base_url + "-centre",
#                 "notification":base_url + "-notification",
#                 "mca": base_url + "/mca-984",
#                 "me-mtech-mtech-lateral-entry-985": base_url + "/me-mtech-mtech-lateral-entry-985",
#                 "MArch": base_url + "/march-986",
#             }

#             # 🔹 Copy all listing data
#             exam_data = exam.copy()

#             try:
#                 exam_data["overviews"] = extract_cat_exam_data(driver, URLS)
#             except Exception as e:
#                 print("overviews page error:", e)
#                 exam_data["overviews"] = None
#             try:
#                 exam_data["mca"] = extract_mca_data(driver, URLS)
#             except Exception as e:
#                 print("mca page error:", e)
#                 exam_data["mca"] = None
#             try:
#                 exam_data["me-mtech-mtech-lateral-entry-985"] = extract_me_lateral_entry_data(driver, URLS)
#             except Exception as e:
#                 print("me-mtech-mtech-lateral-entry-985 page error:", e)
#                 exam_data["me-mtech-mtech-lateral-entry-985"] = None
#             try:
#                 exam_data["MArch"] = extract_cat_MArch_data(driver, URLS)
#             except Exception as e:
#                 print("MArch page error:", e)
#                 exam_data["MArch"] = None
#             try:
#                 exam_data["dates"] = extract_dates_data(driver, URLS)
#             except Exception as e:
#                 print("dates page error:", e)
#                 exam_data["dates"] = None  
#             try:
#                 exam_data["ans_key"] = extract_answerkey_data(driver, URLS)
#             except Exception as e:
#                 print("ans_key page error:", e)
#                 exam_data["ans_key"] = None 

#             try:
#                 exam_data["results"] = extract_result_data(driver, URLS)
#             except Exception as e:
#                 print("results page error:", e)
#                 exam_data["results"] = None  

#             try:
#                 exam_data["question_paper"] = extract_question_paper_data(driver, URLS)
#             except Exception as e:
#                 print("question_paper page error:", e)
#                 exam_data["question_paper"] = None  

#             try:
#                 exam_data["pattern"] = extract_pattern_data(driver, URLS)
#             except Exception as e:
#                 print("Pattern page error:", e)
#                 exam_data["pattern"] = None
#             try:
#                 exam_data["cut_off"] = extract_cut_off_data(driver, URLS)
#             except Exception as e:
#                 print("cutoff page error:", e)
#                 exam_data["cut_off"] = None
#             try:
#                 exam_data["counselling"] = extract_Counselling_data(driver, URLS)
#             except Exception as e:
#                 print("counselling page error:", e)
#                 exam_data["counselling"] = None  
#             try:
#                 exam_data["app_form"] = extract_app_form_data(driver, URLS)
#             except Exception as e:
#                 print("app_form page error:", e)
#                 exam_data["app_form"] = None  


#             # 🔹 Scrape syllabus page
#             try:
#                 exam_data["syllabus"] = extract_syllabus_data(driver, URLS)
#             except Exception as e:
#                 print("Syllabus page error:", e)
#                 exam_data["syllabus"] = None
#             try:
#                 exam_data["books"] = extract_books_data(driver, URLS)
#             except Exception as e:
#                 print("books page error:", e)
#                 exam_data["books"] = None
#             # 🔹 Scrape pattern page
#             try:
#                 exam_data["preparation"] = extract_preparation_data(driver, URLS)
#             except Exception as e:
#                 print("preparation page error:", e)
#                 exam_data["preparation"] = None

#             # 🔹 Scrape syllabus page

#             try:
#                 exam_data["admit_card"] = extract_admit_card_data(driver, URLS)
#             except Exception as e:
#                 print("admit_card page error:", e)
#                 exam_data["admit_card"] = None
#             # 🔹 Scrape pattern page
#             try:
#                 exam_data["news"] = extract_news_data(driver, URLS)
#             except Exception as e:
#                 print("news page error:", e)
#                 exam_data["news"] = None
#             try:
#                 exam_data["analysis"] = extract_Analysis_data(driver, URLS)
#             except Exception as e:
#                 print("analysis page error:", e)
#                 exam_data["analysis"] = None
#             try:
#                 exam_data["mock_test"] = extract_mock_test_data(driver, URLS)
#             except Exception as e:
#                 print("mock_test page error:", e)
#                 exam_data["mock_test"] = None
#             try:
#                 exam_data["registration"] = extract_registration_data(driver, URLS)
#             except Exception as e:
#                 print("registration page error:", e)
#                 exam_data["registration"] = None
#             try:
#                 exam_data["notification"] = extract_notification_data(driver, URLS)
#             except Exception as e:
#                 print("notification page error:", e)
#                 exam_data["notification"] = None
#             try:
#                 exam_data["centre"] = extract_center_data(driver, URLS)
#             except Exception as e:
#                 print("centre page error:", e)
#                 exam_data["centre"] = None      
#             try:
#                 exam_data["college"] = extract_center_data(driver, URLS)
#             except Exception as e:
#                 print("college page error:", e)
#                 exam_data["college"] = None     
       

#             final_data.append(exam_data)

#         # Save JSON
#         with open("complete_exam_data.json", "w", encoding="utf-8") as f:
#             json.dump(final_data, f, indent=4, ensure_ascii=False)

#         print("✅ All data saved successfully!")

#     finally:
#         driver.quit()


if __name__ == "__main__":
    driver = create_driver()

    try:
        final_data = []

        # 🔹 Loop through listing pages
        page = 1
        while True:
            print(f"Scraping listing page {page}")
            
            exams = scrape_listing_page(driver, page)  # Make scrape_listing_page accept page param
            
            if not exams:  # agar page empty ho, stop loop
                break

            for exam in exams:
                print(f"Processing: {exam['exam_short_name']}")
                base_url = exam["base_url"].rstrip("/")

                URLS = {
                    "overviews": base_url,
                    "dates": base_url + "-dates",
                    "ans_key": base_url + "-answer-key",
                    "results": base_url + "-results",
                    "question_paper": base_url + "-question-papers",
                    "pattern": base_url + "-pattern",
                    "cut_off": base_url + "-cutoff",
                    "counselling": base_url + "-counselling",
                    "app_form": base_url + "-application-form",
                    "syllabus": base_url + "-syllabus",
                    "books": base_url + "-books",
                    "preparation": base_url + "-preparation",
                    "admit_card": base_url + "-admit-card",
                    "news": base_url + "-news",
                    "analysis": base_url + "-analysis",
                    "mock_test": base_url + "-mocktest",
                    "registration": base_url + "-registration",
                    "college": base_url + "-college",
                    "centre": base_url + "-centre",
                    "notification": base_url + "-notification",
                    "mca": base_url + "/mca-984",
                    "me-mtech-mtech-lateral-entry-985": base_url + "/me-mtech-mtech-lateral-entry-985",
                    "MArch": base_url + "/march-986",
                }

                exam_data = exam.copy()

                # 🔹 Wrap all scraping functions in try/except (aapka existing code)
                # Example for one function:
                try:
                    exam_data["overviews"] = extract_cat_exam_data(driver, URLS)
                except Exception as e:
                    print("overviews page error:", e)
                    exam_data["overviews"] = None
                try:
                    exam_data["mca"] = extract_mca_data(driver, URLS)
                except Exception as e:
                    print("mca page error:", e)
                    exam_data["mca"] = None
                try:
                    exam_data["me-mtech-mtech-lateral-entry-985"] = extract_me_lateral_entry_data(driver, URLS)
                except Exception as e:
                    print("me-mtech-mtech-lateral-entry-985 page error:", e)
                    exam_data["me-mtech-mtech-lateral-entry-985"] = None
                try:
                    exam_data["MArch"] = extract_cat_MArch_data(driver, URLS)
                except Exception as e:
                    print("MArch page error:", e)
                    exam_data["MArch"] = None
                try:
                    exam_data["dates"] = extract_dates_data(driver, URLS)
                except Exception as e:
                    print("dates page error:", e)
                    exam_data["dates"] = None  
                try:
                    exam_data["ans_key"] = extract_answerkey_data(driver, URLS)
                except Exception as e:
                    print("ans_key page error:", e)
                    exam_data["ans_key"] = None 

                try:
                    exam_data["results"] = extract_result_data(driver, URLS)
                except Exception as e:
                    print("results page error:", e)
                    exam_data["results"] = None  

                try:
                    exam_data["question_paper"] = extract_question_paper_data(driver, URLS)
                except Exception as e:
                    print("question_paper page error:", e)
                    exam_data["question_paper"] = None  

                try:
                    exam_data["pattern"] = extract_pattern_data(driver, URLS)
                except Exception as e:
                    print("Pattern page error:", e)
                    exam_data["pattern"] = None
                try:
                    exam_data["cut_off"] = extract_cut_off_data(driver, URLS)
                except Exception as e:
                    print("cutoff page error:", e)
                    exam_data["cut_off"] = None
                try:
                    exam_data["counselling"] = extract_Counselling_data(driver, URLS)
                except Exception as e:
                    print("counselling page error:", e)
                    exam_data["counselling"] = None  
                try:
                    exam_data["app_form"] = extract_app_form_data(driver, URLS)
                except Exception as e:
                    print("app_form page error:", e)
                    exam_data["app_form"] = None  


                # 🔹 Scrape syllabus page
                try:
                    exam_data["syllabus"] = extract_syllabus_data(driver, URLS)
                except Exception as e:
                    print("Syllabus page error:", e)
                    exam_data["syllabus"] = None
                try:
                    exam_data["books"] = extract_books_data(driver, URLS)
                except Exception as e:
                    print("books page error:", e)
                    exam_data["books"] = None
                # 🔹 Scrape pattern page
                try:
                    exam_data["preparation"] = extract_preparation_data(driver, URLS)
                except Exception as e:
                    print("preparation page error:", e)
                    exam_data["preparation"] = None

                # 🔹 Scrape syllabus page

                try:
                    exam_data["admit_card"] = extract_admit_card_data(driver, URLS)
                except Exception as e:
                    print("admit_card page error:", e)
                    exam_data["admit_card"] = None
                # 🔹 Scrape pattern page
                try:
                    exam_data["news"] = extract_news_data(driver, URLS)
                except Exception as e:
                    print("news page error:", e)
                    exam_data["news"] = None
                try:
                    exam_data["analysis"] = extract_Analysis_data(driver, URLS)
                except Exception as e:
                    print("analysis page error:", e)
                    exam_data["analysis"] = None
                try:
                    exam_data["mock_test"] = extract_mock_test_data(driver, URLS)
                except Exception as e:
                    print("mock_test page error:", e)
                    exam_data["mock_test"] = None
                try:
                    exam_data["registration"] = extract_registration_data(driver, URLS)
                except Exception as e:
                    print("registration page error:", e)
                    exam_data["registration"] = None
                try:
                    exam_data["notification"] = extract_notification_data(driver, URLS)
                except Exception as e:
                    print("notification page error:", e)
                    exam_data["notification"] = None
                try:
                    exam_data["centre"] = extract_center_data(driver, URLS)
                except Exception as e:
                    print("centre page error:", e)
                    exam_data["centre"] = None      
                try:
                    exam_data["college"] = extract_center_data(driver, URLS)
                except Exception as e:
                    print("college page error:", e)
                    exam_data["college"] = None    

                final_data.append(exam_data)

            page += 1  # next listing page

        # 🔹 Save JSON after all pages scraped
        with open("complete_exam_data.json", "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)

        print("✅ All data from all pages saved successfully!")

    finally:
        driver.quit()