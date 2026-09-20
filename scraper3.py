
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError
)

import pandas as pd
import re
import time
import random
import json
import os
from urllib.parse import urljoin


# =========================================================
# SETTINGS
# =========================================================

BASE_URL = "https://www.amazon.de"

SEARCH_URL = "https://www.amazon.de/s?k=laptop"

OUTPUT_FILE = "laptops_amazon.csv"

MAX_PAGES = 20

# None = scrape all products found
MAX_PRODUCTS = None

# Enter every product detail page
SCRAPE_PRODUCT_DETAILS = True

# Delay between product detail pages
MIN_DELAY = 0.7
MAX_DELAY = 1.5

PAGE_TIMEOUT = 60000
DETAIL_TIMEOUT = 30000

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


# =========================================================
# TEXT HELPERS
# =========================================================

def clean_text(text):
    """
    Clean scraped text:
    - remove non-breaking spaces
    - replace multiple spaces/newlines with one space
    """

    if not text:
        return ""

    text = str(text)

    text = text.replace("\xa0", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def safe_text(locator):
    """
    Safely get text from a Playwright locator.
    """

    try:
        if locator.count() == 0:
            return ""

        return clean_text(
            locator.first.inner_text(timeout=5000)
        )

    except Exception:
        return ""


# =========================================================
# DELAY
# =========================================================

def random_delay():
    """
    Small random delay between requests.
    """

    time.sleep(
        random.uniform(
            MIN_DELAY,
            MAX_DELAY
        )
    )


# =========================================================
# GERMAN NUMBER / PRICE
# =========================================================

def parse_german_number(value):
    """
    Examples:

    1.299,99 -> 1299.99
    15,6     -> 15.6
    999      -> 999
    """

    if value is None:
        return None

    try:

        value = str(value)

        value = value.replace("€", "")
        value = value.replace("EUR", "")
        value = value.strip()

        # German decimal format
        if "," in value:

            value = value.replace(".", "")
            value = value.replace(",", ".")

        else:

            # If there are several dots,
            # they are probably thousands separators.
            if value.count(".") > 1:
                value = value.replace(".", "")

        return float(value)

    except Exception:
        return None


# =========================================================
# AMAZON PAGE CHECK
# =========================================================

def check_amazon_page(page, response=None):

    try:

        # HTTP status
        if response is not None:

            try:
                if response.status >= 500:

                    print(
                        f"   ❌ HTTP error: {response.status}"
                    )

                    return False

            except Exception:
                pass

        body_text = ""

        try:
            body_text = clean_text(
                page.locator("body").inner_text(timeout=5000)
            ).lower()

        except Exception:
            pass

        # General Amazon error messages
        error_phrases = [
            "something went wrong",
            "technischer fehler",
            "ein fehler ist aufgetreten",
            "sorry! something went wrong"
        ]

        for phrase in error_phrases:

            if phrase in body_text:

                print(
                    f"   ❌ Amazon error detected: {phrase}"
                )

                return False

        # CAPTCHA / bot detection
        verification_phrases = [
            "captcha",
            "robot check",
            "are you a human",
            "verify you're human",
            "geben sie die zeichen",
            "sicherheitsprüfung"
        ]

        for phrase in verification_phrases:

            if phrase in body_text:

                print(
                    f"   ❌ Verification/CAPTCHA detected: {phrase}"
                )

                try:
                    page.screenshot(
                        path="amazon_blocked.png",
                        full_page=True
                    )
                except Exception:
                    pass

                return False

        return True

    except Exception:
        return True


# =========================================================
# SEARCH PAGE EXTRACTION
# =========================================================

def extract_price(card):

    selectors = [
        ".a-price .a-offscreen",
        ".a-price-whole",
        "span.a-price"
    ]

    for selector in selectors:

        try:

            locator = card.locator(selector)

            if locator.count() == 0:
                continue

            text = safe_text(locator)

            if not text:
                continue

            match = re.search(
                r"(\d[\d.]*(?:,\d{1,2})?)",
                text
            )

            if match:

                price = parse_german_number(
                    match.group(1)
                )

                if price is not None:
                    return price

        except Exception:
            continue

    return None


def extract_rating(card):

    selectors = [
        "span.a-icon-alt",
        "[aria-label*='Sterne']",
        "[aria-label*='star']"
    ]

    for selector in selectors:

        try:

            locator = card.locator(selector)

            if locator.count() == 0:
                continue

            text = (
                locator.first.get_attribute("aria-label")
                or safe_text(locator)
            )

            if not text:
                continue

            match = re.search(
                r"([0-5](?:[.,][0-9])?)",
                text
            )

            if match:

                value = match.group(1).replace(",", ".")

                return float(value)

        except Exception:
            continue

    return None


def extract_reviews(card):

    selectors = [
        "a[href*='#customerReviews']",
        "a[href*='customerReviews']",
        "span.a-size-base"
    ]

    for selector in selectors:

        try:

            locator = card.locator(selector)

            count = locator.count()

            for i in range(min(count, 5)):

                text = clean_text(
                    locator.nth(i).inner_text(
                        timeout=3000
                    )
                )

                if not text:
                    continue

                match = re.search(
                    r"([\d.]+)",
                    text
                )

                if match:

                    number = match.group(1)

                    number = number.replace(".", "")

                    try:
                        return int(number)
                    except Exception:
                        pass

        except Exception:
            continue

    return None


def extract_title(card):

    selectors = [
        "h2 a span",
        "h2 span",
        "h2"
    ]

    for selector in selectors:

        try:

            locator = card.locator(selector)

            text = safe_text(locator)

            if text:
                return text

        except Exception:
            continue

    return ""


def extract_product_url(card):

    selectors = [
        "h2 a",
        "a[href*='/dp/']"
    ]

    for selector in selectors:

        try:

            locator = card.locator(selector)

            if locator.count() == 0:
                continue

            href = locator.first.get_attribute("href")

            if href and "/dp/" in href:

                return urljoin(
                    BASE_URL,
                    href
                )

        except Exception:
            continue

    return ""


# =========================================================
# DETAIL PAGE PRICE / RATING / REVIEWS
# =========================================================

def extract_detail_price(page):

    selectors = [
        "#corePriceDisplay_desktop_feature_div .a-offscreen",
        "#corePrice_feature_div .a-offscreen",
        ".priceToPay .a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        "#priceblock_saleprice",
        "span.a-price .a-offscreen"
    ]

    for selector in selectors:

        try:

            locator = page.locator(selector)

            count = locator.count()

            for i in range(min(count, 5)):

                text = clean_text(
                    locator.nth(i).inner_text(
                        timeout=3000
                    )
                )

                if not text:
                    continue

                match = re.search(
                    r"(\d[\d.]*(?:,\d{1,2})?)",
                    text
                )

                if match:

                    price = parse_german_number(
                        match.group(1)
                    )

                    if price is not None:
                        return price

        except Exception:
            continue

    return None


def extract_detail_rating(page):

    selectors = [
        "#acrPopover",
        "span[data-hook='rating-out-of-text']",
        "i.a-icon-star span.a-icon-alt",
        "span.a-icon-alt"
    ]

    for selector in selectors:

        try:

            locator = page.locator(selector)

            count = locator.count()

            for i in range(min(count, 5)):

                text = (
                    locator.nth(i).get_attribute("title")
                    or locator.nth(i).get_attribute("aria-label")
                    or safe_text(locator.nth(i))
                )

                if not text:
                    continue

                match = re.search(
                    r"([0-5](?:[.,][0-9])?)",
                    text
                )

                if match:

                    return float(
                        match.group(1).replace(",", ".")
                    )

        except Exception:
            continue

    return None


def extract_detail_reviews(page):

    selectors = [
        "#acrCustomerReviewLink",
        "[data-hook='total-review-count']",
        "span[data-hook='total-review-count']"
    ]

    for selector in selectors:

        try:

            locator = page.locator(selector)

            count = locator.count()

            for i in range(min(count, 5)):

                text = safe_text(
                    locator.nth(i)
                )

                if not text:
                    continue

                match = re.search(
                    r"([\d.]+)",
                    text
                )

                if match:

                    number = match.group(1)

                    number = number.replace(".", "")

                    try:
                        return int(number)
                    except Exception:
                        pass

        except Exception:
            continue

    return None


# =========================================================
# BRAND
# =========================================================

def extract_brand_from_detail(page, title=""):

    # -----------------------------------------------------
    # 1. Amazon byline
    # -----------------------------------------------------

    selectors = [
        "#bylineInfo",
        "#brand",
        "[data-brand]"
    ]

    for selector in selectors:

        try:

            locator = page.locator(selector)

            if locator.count() == 0:
                continue

            text = (
                locator.first.get_attribute("data-brand")
                or safe_text(locator)
            )

            text = clean_text(text)

            if text:

                text = re.sub(
                    r"^besuchen sie den .*?[-:]\s*",
                    "",
                    text,
                    flags=re.I
                )

                return text

        except Exception:
            continue

    # -----------------------------------------------------
    # 2. Technical tables
    # -----------------------------------------------------

    try:

        rows = page.locator(
            "#productDetails tr"
        )

        for i in range(rows.count()):

            row_text = clean_text(
                rows.nth(i).inner_text(
                    timeout=3000
                )
            )

            lower = row_text.lower()

            if "marke" in lower or "brand" in lower:

                parts = re.split(
                    r"\s*[:]\s*",
                    row_text,
                    maxsplit=1
                )

                if len(parts) == 2:

                    brand = clean_text(parts[1])

                    if brand:
                        return brand

    except Exception:
        pass

    # -----------------------------------------------------
    # 3. JSON-LD
    # -----------------------------------------------------

    try:

        scripts = page.locator(
            "script[type='application/ld+json']"
        )

        for i in range(scripts.count()):

            raw = scripts.nth(i).inner_text(
                timeout=3000
            )

            if not raw:
                continue

            try:

                data = json.loads(raw)

                items = (
                    data
                    if isinstance(data, list)
                    else [data]
                )

                for item in items:

                    if not isinstance(item, dict):
                        continue

                    brand_data = item.get("brand")

                    if isinstance(
                        brand_data,
                        dict
                    ):

                        name = brand_data.get("name")

                        if name:
                            return clean_text(name)

                    elif isinstance(
                        brand_data,
                        str
                    ):

                        if brand_data.strip():
                            return clean_text(brand_data)

            except Exception:
                continue

    except Exception:
        pass

    # -----------------------------------------------------
    # 4. Known brand fallback from title
    # -----------------------------------------------------

    known_brands = [
        "Acer",
        "Apple",
        "ASUS",
        "Dell",
        "HP",
        "Huawei",
        "Lenovo",
        "Microsoft",
        "MSI",
        "Razer",
        "Samsung",
        "Gigabyte",
        "Medion",
        "Fujitsu"
    ]

    title_lower = title.lower()

    for brand in known_brands:

        if brand.lower() in title_lower:

            return brand

    return ""


# =========================================================
# SPECIFICATION TEXT EXTRACTION
# =========================================================

def extract_specs_from_text(text):

    text = clean_text(text)

    result = {
        "cpu": "",
        "ram_gb": None,
        "storage_gb": None,
        "screen_size_inch": None,
        "resolution": "",
        "gpu": "",
        "os": "",
        "keyboard": "",
        "touchscreen": False,
        "gaming": False
    }

    if not text:
        return result

    lower = text.lower()

    # =====================================================
    # CPU
    # =====================================================

    cpu_patterns = [

        # Intel Core Ultra
        r"\bIntel\s+Core\s+Ultra\s+[3579]\s*[\w-]*",

        # Intel Core 7 / Core 5 / etc.
        r"\bIntel\s+Core\s+[3579]\s*[\w-]*",

        # Intel Core i3/i5/i7/i9
        r"\bIntel\s+Core\s+i[3579]\s*[\w-]*",

        # Intel Processor N100 / N200 etc.
        r"\bIntel\s+Processor\s+[A-Z]?\d{3,4}[\w-]*",

        # Intel Celeron / Pentium
        r"\bIntel\s+(?:Celeron|Pentium)\s+[\w-]+",

        # Intel Xeon
        r"\bIntel\s+Xeon\s+[\w-]+",

        # AMD Ryzen AI
        r"\bAMD\s+Ryzen\s+AI\s+[\w-]+",

        # AMD Ryzen 3/5/7/9
        r"\bAMD\s+Ryzen\s+[3579]\s*[\w-]*",

        # AMD Athlon
        r"\bAMD\s+Athlon\s+[\w-]+",

        # Apple M-series
        r"\bApple\s+M[1-5](?:\s+(?:Pro|Max|Ultra))?"
    ]

    for pattern in cpu_patterns:

        match = re.search(
            pattern,
            text,
            re.I
        )

        if match:

            result["cpu"] = clean_text(
                match.group(0)
            )

            break

    # =====================================================
    # RAM
    # =====================================================

    ram_patterns = [

        r"\b(\d{1,3})\s*GB\s+(?:DDR[345]\s*)?(?:RAM|Arbeitsspeicher|Speicher)\b",

        r"\b(\d{1,3})\s*GB\s+DDR[345]\b",

        r"\b(\d{1,3})\s*GB\s+RAM\b",

        r"\bRAM\s*[:\-]?\s*(\d{1,3})\s*GB\b",

        r"\bArbeitsspeicher\s*[:\-]?\s*(\d{1,3})\s*GB\b"
    ]

    for pattern in ram_patterns:

        match = re.search(
            pattern,
            text,
            re.I
        )

        if match:

            try:

                result["ram_gb"] = int(
                    match.group(1)
                )

                break

            except Exception:
                pass

    # =====================================================
    # STORAGE
    # =====================================================

    storage_patterns = [

        # 1 TB SSD
        r"\b(\d+(?:[.,]\d+)?)\s*TB\s*(?:SSD|NVMe|PCIe|HDD|Festplatte|Speicher)\b",

        # SSD 1000 GB
        r"\b(?:SSD|NVMe|Festplatte|Speicher)\s*[:\-]?\s*(\d{3,5})\s*GB\b",

        # 1000 GB SSD
        r"\b(\d{3,5})\s*GB\s*(?:SSD|NVMe|PCIe|HDD)\b",

        # 512 GB / 256 GB SSD style
        r"\b(\d{3,5})\s*GB\b(?=[^.]*(?:SSD|NVMe|PCIe|HDD))"
    ]

    for pattern in storage_patterns:

        match = re.search(
            pattern,
            text,
            re.I
        )

        if match:

            try:

                value = float(
                    match.group(1).replace(",", ".")
                )

                # TB -> GB
                if "tb" in match.group(0).lower():

                    value *= 1024

                result["storage_gb"] = int(value)

                break

            except Exception:
                pass

    # =====================================================
    # SCREEN SIZE
    # =====================================================

    screen_patterns = [
    r'\b(\d{1,2}(?:[.,]\d)?)\s*(?:Zoll|inch|")\b',
    r'\b(\d{1,2}(?:[.,]\d)?)[- ]?Zoll\b'
]
    for pattern in screen_patterns:

        match = re.search(
            pattern,
            text,
            re.I
        )

        if match:

            try:

                result["screen_size_inch"] = float(
                    match.group(1).replace(",", ".")
                )

                break

            except Exception:
                pass

    # =====================================================
    # RESOLUTION
    # =====================================================

    resolution_patterns = [
        r"\b(3840\s*[x×]\s*2160)\b",
        r"\b(2560\s*[x×]\s*1600)\b",
        r"\b(2560\s*[x×]\s*1440)\b",
        r"\b(1920\s*[x×]\s*1200)\b",
        r"\b(1920\s*[x×]\s*1080)\b",
        r"\b(1366\s*[x×]\s*768)\b"
    ]

    for pattern in resolution_patterns:

        match = re.search(
            pattern,
            text,
            re.I
        )

        if match:

            result["resolution"] = (
                match.group(1)
                .replace(" ", "")
                .replace("×", "x")
            )

            break

    # Generic resolution fallback
    if not result["resolution"]:

        match = re.search(
            r"\b(\d{3,4}\s*[x×]\s*\d{3,4})\b",
            text,
            re.I
        )

        if match:

            result["resolution"] = (
                match.group(1)
                .replace(" ", "")
                .replace("×", "x")
            )

    # =====================================================
    # GPU
    # =====================================================

    gpu_patterns = [

        r"\bNVIDIA\s+GeForce\s+RTX\s+[\w-]+",

        r"\bNVIDIA\s+GeForce\s+GTX\s+[\w-]+",

        r"\bNVIDIA\s+GeForce\s+MX\s+[\w-]+",

        r"\bNVIDIA\s+RTX\s+[\w-]+",

        r"\bAMD\s+Radeon\s+RX\s+[\w-]+",

        r"\bAMD\s+Radeon\s+[\w-]+",

        r"\bIntel\s+Arc\s+[\w-]+",

        r"\bIntel\s+Iris\s+Xe\b",

        r"\bIntel\s+UHD\s+Graphics\b"
    ]

    for pattern in gpu_patterns:

        match = re.search(
            pattern,
            text,
            re.I
        )

        if match:

            result["gpu"] = clean_text(
                match.group(0)
            )

            break

    # =====================================================
    # OPERATING SYSTEM
    # =====================================================

    os_patterns = [

        r"\bWindows\s+11\s+(?:Home|Pro|S)?\b",

        r"\bWindows\s+10\s+(?:Home|Pro|S)?\b",

        r"\bUbuntu\s+\d+(?:\.\d+)?\b",

        r"\bChrome\s+OS\b",

        r"\bmacOS\b"
    ]

    for pattern in os_patterns:

        match = re.search(
            pattern,
            text,
            re.I
        )

        if match:

            result["os"] = clean_text(
                match.group(0)
            )

            break

    # =====================================================
    # KEYBOARD
    # =====================================================

    if "qwertz" in lower:

        result["keyboard"] = "QWERTZ"

    elif "qwerty" in lower:

        result["keyboard"] = "QWERTY"

    elif "azerty" in lower:

        result["keyboard"] = "AZERTY"

    # =====================================================
    # TOUCHSCREEN
    # =====================================================

    touchscreen_positive = [
        "touchscreen",
        "touch screen",
        "touchdisplay",
        "touch display",
        "touch-funktion",
        "touchfunktion",
        "berührungs"
    ]

    for phrase in touchscreen_positive:

        if phrase in lower:

            result["touchscreen"] = True
            break

    # =====================================================
    # GAMING
    # =====================================================

    gaming_words = [
        "gaming",
        "gamer",
        "gaming laptop",
        "gaming-laptop"
    ]

    for phrase in gaming_words:

        if phrase in lower:

            result["gaming"] = True
            break

    return result


# =========================================================
# DETAIL PAGE SPEC EXTRACTION
# =========================================================

def extract_specs_from_detail(page):

    chunks = []

    # -----------------------------------------------------
    # Targeted sections first
    # -----------------------------------------------------

    selectors = [

        "#productDetails",

        "#productDetails_techSpec_section_1",

        "#productDetails_detailBullets_sections1",

        "#detailBullets_feature_div",

        "#feature-bullets",

        "#technicalSpecifications",

        "#productOverview",

        "#prodDetails"
    ]

    for selector in selectors:

        try:

            locator = page.locator(selector)

            count = locator.count()

            for i in range(min(count, 5)):

                text = safe_text(
                    locator.nth(i)
                )

                if text:
                    chunks.append(text)

        except Exception:
            continue

    # -----------------------------------------------------
    # Table rows
    # -----------------------------------------------------

    try:

        rows = page.locator(
            "#productDetails tr, "
            "#productDetails table tr, "
            "#prodDetails tr"
        )

        for i in range(rows.count()):

            text = safe_text(
                rows.nth(i)
            )

            if text:
                chunks.append(text)

    except Exception:
        pass

    # -----------------------------------------------------
    # Feature bullets
    # -----------------------------------------------------

    try:

        bullets = page.locator(
            "#feature-bullets li"
        )

        for i in range(
            min(bullets.count(), 100)
        ):

            text = safe_text(
                bullets.nth(i)
            )

            if text:
                chunks.append(text)

    except Exception:
        pass

    # -----------------------------------------------------
    # First extraction from targeted text
    # -----------------------------------------------------

    targeted_text = clean_text(
        " ".join(chunks)
    )

    result = extract_specs_from_text(
        targeted_text
    )

    # -----------------------------------------------------
    # FALLBACK:
    # Only read the whole body if important fields
    # are still missing.
    #
    # This saves time compared with reading the body
    # of every product unnecessarily.
    # -----------------------------------------------------

    important_missing = (
        not result["cpu"]
        or result["ram_gb"] is None
        or result["storage_gb"] is None
        or not result["gpu"]
    )

    if important_missing:

        try:

            body_text = clean_text(
                page.locator("body").inner_text(
                    timeout=7000
                )
            )

            fallback_result = extract_specs_from_text(
                body_text
            )

            # Only fill missing values.
            if not result["cpu"]:
                result["cpu"] = fallback_result["cpu"]

            if result["ram_gb"] is None:
                result["ram_gb"] = fallback_result["ram_gb"]

            if result["storage_gb"] is None:
                result["storage_gb"] = fallback_result["storage_gb"]

            if not result["gpu"]:
                result["gpu"] = fallback_result["gpu"]

            if not result["os"]:
                result["os"] = fallback_result["os"]

            if not result["resolution"]:
                result["resolution"] = (
                    fallback_result["resolution"]
                )

            if result["screen_size_inch"] is None:
                result["screen_size_inch"] = (
                    fallback_result["screen_size_inch"]
                )

            if not result["keyboard"]:
                result["keyboard"] = (
                    fallback_result["keyboard"]
                )

            if not result["touchscreen"]:
                result["touchscreen"] = (
                    fallback_result["touchscreen"]
                )

            if not result["gaming"]:
                result["gaming"] = (
                    fallback_result["gaming"]
                )

        except Exception:
            pass

    return result


# =========================================================
# SEARCH PAGE
# =========================================================

def scrape_search_page(page, page_number):

    print(
        f"\n🔎 Scraping search page {page_number}..."
    )

    try:

        page.wait_for_selector(
            "div[data-component-type='s-search-result']",
            state="attached",
            timeout=15000
        )

    except PlaywrightTimeoutError:

        print(
            "   ⚠️ Product cards did not appear."
        )

        return []

    if not check_amazon_page(page):

        return []

    cards = page.locator(
        "div[data-component-type='s-search-result']"
    )

    count = cards.count()

    print(
        f"   Found {count} product cards."
    )

    records = []

    for i in range(count):

        try:

            card = cards.nth(i)

            asin = (
                card.get_attribute("data-asin")
                or ""
            ).strip()

            if not asin:
                continue

            title = extract_title(card)

            product_url = extract_product_url(
                card
            )

            price = extract_price(card)

            rating = extract_rating(card)

            reviews = extract_reviews(card)

            record = {
                "asin": asin,
                "title": title,
                "product_url": product_url,
                "price_eur": price,
                "rating": rating,
                "reviews": reviews,

                "brand": "",

                "cpu": "",
                "ram_gb": None,
                "storage_gb": None,
                "screen_size_inch": None,
                "resolution": "",
                "gpu": "",
                "os": "",
                "keyboard": "",

                "touchscreen": False,
                "gaming": False,

                "search_page": page_number
            }

            records.append(record)

        except Exception as e:

            print(
                f"   ⚠️ Card {i + 1} error: {e}"
            )

    return records


# =========================================================
# DETAIL PAGE
# =========================================================

def scrape_product_details(page, record):

    url = record.get(
        "product_url",
        ""
    )

    if not url:

        return record

    title = record.get(
        "title",
        ""
    )

    print(
        f"\n   Opening detail page: {title[:100]}"
    )

    try:

        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=DETAIL_TIMEOUT
        )

        # =================================================
        # IMPORTANT:
        # Do NOT use only "#productTitle"
        #
        # Amazon can have more than one element with
        # this ID, including a hidden input.
        #
        # :visible selects the visible one.
        # =================================================

        title_locator = page.locator(
            "#productTitle:visible"
        ).first

        try:

            title_locator.wait_for(
                state="visible",
                timeout=10000
            )

        except PlaywrightTimeoutError:

            print(
                "   ⚠️ Visible product title not found."
            )

        if not check_amazon_page(
            page,
            response
        ):

            return record

        # =================================================
        # TITLE
        # =================================================

        if not title:

            title = safe_text(
                title_locator
            )

            if title:

                record["title"] = title

        # =================================================
        # PRICE
        # =================================================

        detail_price = extract_detail_price(
            page
        )

        if detail_price is not None:

            record["price_eur"] = detail_price

        # =================================================
        # RATING
        # =================================================

        detail_rating = extract_detail_rating(
            page
        )

        if detail_rating is not None:

            record["rating"] = detail_rating

        # =================================================
        # REVIEWS
        # =================================================

        detail_reviews = extract_detail_reviews(
            page
        )

        if detail_reviews is not None:

            record["reviews"] = detail_reviews

        # =================================================
        # BRAND
        # =================================================

        record["brand"] = (
            extract_brand_from_detail(
                page,
                title
            )
        )

        # =================================================
        # SPECS
        # =================================================

        specs = extract_specs_from_detail(
            page
        )

        record.update(
            specs
        )

        print(
            "   ✅ Detail scraped"
        )

        return record

    except PlaywrightTimeoutError as e:

        print(
            f"   ❌ Detail timeout: {e}"
        )

        return record

    except Exception as e:

        print(
            f"   ❌ Detail error: {e}"
        )

        return record


# =========================================================
# SAVE DATASET
# =========================================================

def save_dataset(records):

    if not records:

        print(
            "   ⚠️ Nothing to save."
        )

        return

    try:

        df = pd.DataFrame(records)

        # -------------------------------------------------
        # Remove duplicate ASINs
        # -------------------------------------------------

        if "asin" in df.columns:

            df = df.drop_duplicates(
                subset=["asin"],
                keep="last"
            )

        # -------------------------------------------------
        # Preferred column order
        # -------------------------------------------------

        preferred_columns = [

            "asin",
            "title",
            "brand",

            "price_eur",
            "rating",
            "reviews",

            "cpu",
            "ram_gb",
            "storage_gb",
            "gpu",

            "screen_size_inch",
            "resolution",

            "os",
            "keyboard",

            "touchscreen",
            "gaming",

            "product_url",
            "search_page"
        ]

        existing_columns = [
            column
            for column in preferred_columns
            if column in df.columns
        ]

        remaining_columns = [
            column
            for column in df.columns
            if column not in existing_columns
        ]

        df = df[
            existing_columns
            + remaining_columns
        ]

        # -------------------------------------------------
        # Save
        # -------------------------------------------------

        df.to_csv(
            OUTPUT_FILE,
            index=False,
            encoding="utf-8-sig"
        )

        print(
            f"   💾 Saved {len(df)} products -> "
            f"{OUTPUT_FILE}"
        )

    except Exception as e:

        print(
            f"   ❌ Save error: {e}"
        )


# =========================================================
# OPEN SEARCH PAGE
# =========================================================

def open_search_page(page):

    for attempt in range(1, 4):

        try:

            print(
                f"🌐 Opening Amazon search "
                f"(attempt {attempt}/3)..."
            )

            response = page.goto(
                SEARCH_URL,
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT
            )

            # Wait for actual product cards
            page.wait_for_selector(
                "div[data-component-type='s-search-result']",
                state="attached",
                timeout=15000
            )

            if not check_amazon_page(
                page,
                response
            ):

                raise Exception(
                    "Amazon page check failed"
                )

            print(
                "   ✅ Search page ready."
            )

            return True

        except PlaywrightTimeoutError:

            print(
                "   ⚠️ Page loading timeout."
            )

        except Exception as e:

            print(
                f"   ⚠️ Open page error: {e}"
            )

        if attempt < 3:

            wait_time = attempt * 3

            print(
                f"   Waiting {wait_time}s before retry..."
            )

            time.sleep(wait_time)

    return False


# =========================================================
# MAIN SCRAPER
# =========================================================

def scrape():

    all_records = []

    # ASINs that have already been seen
    existing_asins = set()

    print("=" * 70)
    print("Amazon.de Laptop Scraper")
    print("=" * 70)

    with sync_playwright() as p:

        # =================================================
        # BROWSER
        # =================================================

        launch_args = {
            "headless": False
        }

        if os.path.exists(CHROME_PATH):

            launch_args["executable_path"] = (
                CHROME_PATH
            )

        browser = p.chromium.launch(
            **launch_args
        )

        # =================================================
        # CONTEXT
        # =================================================

        context = browser.new_context(

            viewport={
                "width": 1440,
                "height": 900
            },

            locale="de-DE",

            timezone_id="Europe/Berlin"
        )

        # =================================================
        # PAGES
        # =================================================

        search_page = context.new_page()

        detail_page = context.new_page()

        search_page.set_default_timeout(
            10000
        )

        detail_page.set_default_timeout(
            10000
        )

        # =================================================
        # OPEN AMAZON
        # =================================================

        if not open_search_page(
            search_page
        ):

            print(
                "❌ Could not open Amazon."
            )

            browser.close()

            return

        # =================================================
        # PAGE LOOP
        # =================================================

        for page_number in range(
            1,
            MAX_PAGES + 1
        ):

            print("\n" + "=" * 70)

            print(
                f"PAGE {page_number}/{MAX_PAGES}"
            )

            print("=" * 70)

            # -------------------------------------------------
            # Check current page
            # -------------------------------------------------

            if not check_amazon_page(
                search_page
            ):

                print(
                    "❌ Current search page is not valid."
                )

                break

            # -------------------------------------------------
            # Scrape products from search page
            # -------------------------------------------------

            page_records = scrape_search_page(
                search_page,
                page_number
            )

            if not page_records:

                print(
                    "⚠️ No products found on this page."
                )

                break

            # -------------------------------------------------
            # IMPORTANT:
            #
            # Only keep NEW products.
            #
            # This prevents scraping the same product
            # detail page multiple times.
            # -------------------------------------------------

            new_records = []

            for record in page_records:

                asin = record.get(
                    "asin",
                    ""
                )

                if not asin:
                    continue

                if asin in existing_asins:
                    continue

                existing_asins.add(
                    asin
                )

                new_records.append(
                    record
                )

            print(
                f"   New products on this page: "
                f"{len(new_records)}"
            )

            # -------------------------------------------------
            # MAX PRODUCTS
            # -------------------------------------------------

            if MAX_PRODUCTS is not None:

                remaining = (
                    MAX_PRODUCTS
                    - len(all_records)
                )

                if remaining <= 0:

                    break

                new_records = new_records[
                    :remaining
                ]

            # -------------------------------------------------
            # Add to master list
            # -------------------------------------------------

            all_records.extend(
                new_records
            )

            # -------------------------------------------------
            # DETAIL PAGES
            #
            # IMPORTANT:
            # We ONLY process new_records.
            #
            # NOT all_records.
            #
            # This fixes the huge slowdown in the old code.
            # -------------------------------------------------

            if SCRAPE_PRODUCT_DETAILS:

                print(
                    f"\n   🔍 Scraping details for "
                    f"{len(new_records)} products..."
                )

                for index, record in enumerate(
                    new_records,
                    start=1
                ):

                    print(
                        f"\n   [{index}/{len(new_records)}]"
                    )

                    updated_record = (
                        scrape_product_details(
                            detail_page,
                            record
                        )
                    )

                    # Find the same record in all_records
                    asin = record.get(
                        "asin",
                        ""
                    )

                    for master_index, master_record in enumerate(
                        all_records
                    ):

                        if master_record.get(
                            "asin",
                            ""
                        ) == asin:

                            all_records[
                                master_index
                            ] = updated_record

                            break

                    # Small delay between products
                    if index < len(new_records):

                        random_delay()

            # -------------------------------------------------
            # SAVE ONCE PER SEARCH PAGE
            #
            # No save every 10 products.
            # -------------------------------------------------

            save_dataset(
                all_records
            )

            # -------------------------------------------------
            # Check MAX_PRODUCTS
            # -------------------------------------------------

            if (
                MAX_PRODUCTS is not None
                and len(all_records)
                >= MAX_PRODUCTS
            ):

                print(
                    "\n🎯 MAX_PRODUCTS reached."
                )

                break

            # -------------------------------------------------
            # NEXT PAGE
            # -------------------------------------------------

            if page_number >= MAX_PAGES:

                break

            print(
                "\n➡️ Looking for next page..."
            )

            try:

                next_locator = search_page.locator(
                    "a.s-pagination-next"
                )

                if next_locator.count() == 0:

                    print(
                        "   ℹ️ No next page button."
                    )

                    break

                next_button = (
                    next_locator.first
                )

                # Check disabled state
                aria_disabled = (
                    next_button.get_attribute(
                        "aria-disabled"
                    )
                )

                class_name = (
                    next_button.get_attribute(
                        "class"
                    )
                    or ""
                )

                if (
                    aria_disabled == "true"
                    or "s-pagination-disabled"
                    in class_name
                ):

                    print(
                        "   ℹ️ Next page is disabled."
                    )

                    break

                next_url = (
                    next_button.get_attribute(
                        "href"
                    )
                )

                if not next_url:

                    print(
                        "   ℹ️ Next page URL not found."
                    )

                    break

                next_url = urljoin(
                    BASE_URL,
                    next_url
                )

                random_delay()

                print(
                    f"   🌐 Opening page {page_number + 1}..."
                )

                response = search_page.goto(
                    next_url,
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT
                )

                # Smart wait:
                # wait for actual product cards
                search_page.wait_for_selector(
                    "div[data-component-type='s-search-result']",
                    state="attached",
                    timeout=15000
                )

                if not check_amazon_page(
                    search_page,
                    response
                ):

                    print(
                        "❌ Next page check failed."
                    )

                    break

            except PlaywrightTimeoutError as e:

                print(
                    f"❌ Next page timeout: {e}"
                )

                break

            except Exception as e:

                print(
                    f"❌ Next page error: {e}"
                )

                break

        # =================================================
        # FINAL SAVE
        # =================================================

        print(
            "\n💾 Final save..."
        )

        save_dataset(
            all_records
        )

        # =================================================
        # CLOSE
        # =================================================

        try:
            detail_page.close()
        except Exception:
            pass

        try:
            search_page.close()
        except Exception:
            pass

        browser.close()

    # =====================================================
    # SUMMARY
    # =====================================================

    print("\n" + "=" * 70)

    print(
        "SCRAPING FINISHED"
    )

    print("=" * 70)

    print(
        f"Total unique products: {len(all_records)}"
    )

    print(
        f"Output file: {OUTPUT_FILE}"
    )

    print("=" * 70)


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    scrape()

