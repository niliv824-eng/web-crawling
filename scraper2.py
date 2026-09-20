
from playwright.sync_api import sync_playwright
import pandas as pd
import re
import time
from urllib.parse import urljoin


# =========================================================
# SETTINGS
# =========================================================

BASE_URL = "https://www.amazon.de"
SEARCH_URL = "https://www.amazon.de/s?k=laptop"

OUTPUT_FILE = "laptops_amazon.csv"

# تعداد صفحات
MAX_PAGES = 10

# Chrome نصب شده روی ویندوز
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


# =========================================================
# TEXT HELPERS
# =========================================================

def clean_text(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()


def parse_german_number(text):
    """
    تبدیل:
    1.299,99 -> 1299.99
    299,99   -> 299.99
    999      -> 999
    """

    if not text:
        return None

    text = text.strip()

    # فقط اعداد و جداکننده‌ها
    text = re.sub(r"[^\d,.]", "", text)

    if not text:
        return None

    try:

        if "," in text:
            # German format
            text = text.replace(".", "")
            text = text.replace(",", ".")

        return float(text)

    except:
        return None


# =========================================================
# PRICE
# =========================================================

def extract_price(card):

    selectors = [
        ".a-price .a-offscreen",
        ".a-price-whole"
    ]

    for selector in selectors:

        locator = card.locator(selector)

        if locator.count() == 0:
            continue

        try:

            text = locator.first.inner_text()

            price = parse_german_number(text)

            if price is not None:
                return price

        except:
            pass

    return None


# =========================================================
# RATING
# =========================================================

def extract_rating(card):

    locator = card.locator(
        "span.a-icon-alt"
    )

    if locator.count() == 0:
        return None

    try:

        text = locator.first.inner_text()

        match = re.search(
            r"([0-5](?:[.,][0-9])?)",
            text
        )

        if match:

            return float(
                match.group(1).replace(",", ".")
            )

    except:
        pass

    return None


# =========================================================
# REVIEWS
# =========================================================

def extract_reviews(card):

    selectors = [
        'a[href*="#customerReviews"]',
        'a[href*="customerReviews"]'
    ]

    for selector in selectors:

        locator = card.locator(selector)

        if locator.count() == 0:
            continue

        try:

            text = locator.first.inner_text()

            # حذف کاراکترهای غیر عددی
            numbers = re.findall(
                r"\d[\d.,]*",
                text
            )

            if numbers:

                value = numbers[0]

                value = (
                    value
                    .replace(".", "")
                    .replace(",", "")
                )

                return int(value)

        except:
            pass

    return None


# =========================================================
# TITLE
# =========================================================

def extract_title(card):

    locator = card.locator("h2 span")

    if locator.count() > 0:

        try:
            return clean_text(
                locator.first.inner_text()
            )
        except:
            pass

    locator = card.locator("h2")

    if locator.count() > 0:

        try:
            return clean_text(
                locator.first.inner_text()
            )
        except:
            pass

    return ""


# =========================================================
# PRODUCT URL
# =========================================================

def extract_product_url(card):

    # اول لینک داخل h2
    locator = card.locator("h2 a")

    if locator.count() > 0:

        try:

            href = locator.first.get_attribute("href")

            if href:

                return urljoin(
                    BASE_URL,
                    href
                )

        except:
            pass

    # روش دوم
    locator = card.locator(
        'a[href*="/dp/"]'
    )

    if locator.count() > 0:

        try:

            href = locator.first.get_attribute(
                "href"
            )

            if href:

                return urljoin(
                    BASE_URL,
                    href
                )

        except:
            pass

    return ""


# =========================================================
# IMAGE
# =========================================================

def extract_image(card):

    locator = card.locator(
        "img.s-image"
    )

    if locator.count() == 0:
        return ""

    try:

        src = locator.first.get_attribute(
            "src"
        )

        if src:
            return src

        return locator.first.get_attribute(
            "data-src"
        ) or ""

    except:
        return ""


# =========================================================
# SPEC EXTRACTION FROM TITLE
# =========================================================

def extract_specs(title):

    text = title.lower()

    result = {

        "brand": None,

        "cpu": None,

        "ram_gb": None,

        "storage_gb": None,

        "storage_type": None,

        "screen_size": None,

        "resolution": None,

        "gpu": None,

        "operating_system": None,

        "keyboard": None,

        "touchscreen": False,

        "gaming": False
    }


    # -------------------------------------------------------
    # BRAND
    # -------------------------------------------------------

    brands = [
        "HP",
        "Lenovo",
        "ASUS",
        "Acer",
        "Dell",
        "Apple",
        "Samsung",
        "MSI",
        "Huawei",
        "Microsoft",
        "MEDION",
        "LG",
        "Gigabyte",
        "Razer",
        "Fujitsu",
        "BMAX",
        "Jumper",
        "Molegar",
        "Auusda"
    ]

    for brand in brands:

        if re.search(
            r"\b" + re.escape(brand.lower()) + r"\b",
            text
        ):

            result["brand"] = brand
            break


    # -------------------------------------------------------
    # CPU
    # -------------------------------------------------------

    cpu_patterns = [

        r"(intel\s+core\s+ultra\s+\d\s*\d*\w*)",
        r"(intel\s+core\s+i[3579][-\s]?\d+\w*)",
        r"(intel\s+core\s+\d\s+\d+\w*)",
        r"(intel\s+celeron\s+[a-z0-9-]+)",
        r"(intel\s+pentium\s+[a-z0-9-]+)",
        r"(intel\s+n\d{3,4})",
        r"(amd\s+ryzen\s+ai\s+\d\s+\d+\w*)",
        r"(amd\s+ryzen\s+[3579]\s+\d+\w*)",
        r"(ryzen\s+[3579]\s+\d+\w*)",
        r"(snapdragon\s+x\s+\w+)",
        r"(apple\s+m[1-9]\s*(?:pro|max|ultra)?)"
    ]

    for pattern in cpu_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            result["cpu"] = match.group(1)
            break


    # -------------------------------------------------------
    # RAM
    # -------------------------------------------------------

    ram_patterns = [

        r"(\d+)\s*gb\s*(?:ddr\d|lpddr\d)?\s*ram",
        r"(\d+)\s*gb\s*ram",
        r"(\d+)\s*gb\s*(?:ddr\d|lpddr\d)"
    ]

    for pattern in ram_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            result["ram_gb"] = int(
                match.group(1)
            )

            break


    # -------------------------------------------------------
    # STORAGE
    # -------------------------------------------------------

    storage_match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(tb|gb)\s*(ssd|nvme|emmc|ufs)?",
        text,
        re.IGNORECASE
    )

    if storage_match:

        value = float(
            storage_match.group(1)
            .replace(",", ".")
        )

        unit = storage_match.group(2).lower()

        if unit == "tb":
            value *= 1024

        result["storage_gb"] = int(value)

        storage_type = storage_match.group(3)

        if storage_type:

            result["storage_type"] = (
                storage_type.upper()
            )


    # -------------------------------------------------------
    # SCREEN SIZE
    # -------------------------------------------------------

    screen_match = re.search(
        r'(\d{1,2}(?:[.,]\d)?)\s*(?:zoll|")',
        text,
        re.IGNORECASE
    )

    if screen_match:

        result["screen_size"] = float(
            screen_match.group(1)
            .replace(",", ".")
        )


    # -------------------------------------------------------
    # RESOLUTION
    # -------------------------------------------------------

    resolution_patterns = [

        r"(\d{3,4}\s*x\s*\d{3,4})",

        r"(full\s*hd)",

        r"(wuxga)",

        r"(qhd)",

        r"(uhd)",

        r"(4k)"
    ]

    for pattern in resolution_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            result["resolution"] = (
                match.group(1)
            )

            break


    # -------------------------------------------------------
    # GPU
    # -------------------------------------------------------

    gpu_patterns = [

        r"(rtx\s*\d{3,4})",

        r"(gtx\s*\d{3,4})",

        r"(intel\s+arc\s+\w+)",

        r"(intel\s+iris\s+xe)",

        r"(intel\s+uhd\s+graphics\s*\w*)",

        r"(amd\s+radeon\s+\w+\s*\d*)",

        r"(radeon\s+\d+\w*)"
    ]

    for pattern in gpu_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            result["gpu"] = (
                match.group(1)
            )

            break


    # -------------------------------------------------------
    # OPERATING SYSTEM
    # -------------------------------------------------------

    if "windows 11 pro" in text:
        result["operating_system"] = "Windows 11 Pro"

    elif "windows 11 home" in text:
        result["operating_system"] = "Windows 11 Home"

    elif "windows 11" in text:
        result["operating_system"] = "Windows 11"

    elif "windows 10" in text:
        result["operating_system"] = "Windows 10"

    elif "chromeos" in text or "chrome os" in text:
        result["operating_system"] = "ChromeOS"

    elif "macos" in text:
        result["operating_system"] = "macOS"


    # -------------------------------------------------------
    # KEYBOARD
    # -------------------------------------------------------

    if "qwertz" in text:

        result["keyboard"] = "QWERTZ"

    elif "qwerty" in text:

        result["keyboard"] = "QWERTY"


    # -------------------------------------------------------
    # TOUCHSCREEN
    # -------------------------------------------------------

    if (
        "touchscreen" in text
        or "touch screen" in text
        or "touchdisplay" in text
        or "touch display" in text
    ):

        result["touchscreen"] = True


    # -------------------------------------------------------
    # GAMING
    # -------------------------------------------------------

    gaming_words = [
        "gaming",
        "gamer",
        "nitro",
        "rog",
        "tuf gaming",
        "legion"
    ]

    for word in gaming_words:

        if word in text:

            result["gaming"] = True
            break


    return result


# =========================================================
# SCRAPE CURRENT PAGE
# =========================================================

def scrape_page(page, page_number):

    products = []

    cards = page.locator(
        'div[data-component-type="s-search-result"]'
    )

    count = cards.count()

    print()
    print(
        f"PAGE {page_number} "
        f"-> {count} product cards found"
    )

    for i in range(count):

        try:

            card = cards.nth(i)

            # ASIN
            asin = card.get_attribute(
                "data-asin"
            )

            if not asin:
                continue


            # Title
            title = extract_title(card)

            if not title:
                continue


            # Price
            price = extract_price(card)


            # Rating
            rating = extract_rating(card)


            # Reviews
            reviews = extract_reviews(card)


            # URL
            product_url = extract_product_url(
                card
            )


            # Image
            image_url = extract_image(
                card
            )


            # Specs
            specs = extract_specs(
                title
            )


            product = {

                "asin": asin,

                "title": title,

                "brand": specs["brand"],

                "price_eur": price,

                "rating": rating,

                "reviews": reviews,

                "cpu": specs["cpu"],

                "ram_gb": specs["ram_gb"],

                "storage_gb": specs["storage_gb"],

                "storage_type": specs["storage_type"],

                "screen_size": specs["screen_size"],

                "resolution": specs["resolution"],

                "gpu": specs["gpu"],

                "operating_system":
                    specs["operating_system"],

                "keyboard":
                    specs["keyboard"],

                "touchscreen":
                    specs["touchscreen"],

                "gaming":
                    specs["gaming"],

                "product_url":
                    product_url,

                "image_url":
                    image_url,

                "page":
                    page_number
            }


            products.append(
                product
            )

            print(
                f"  [{i + 1}/{count}] "
                f"{title[:80]}"
            )

        except Exception as e:

            print(
                f"  Error on product {i}: {e}"
            )


    return products


# =========================================================
# MAIN
# =========================================================

def scrape():

    all_products = []

    with sync_playwright() as p:

        print("=" * 70)
        print("AMAZON LAPTOP SCRAPER")
        print("=" * 70)

        print()
        print("Launching Google Chrome...")

        browser = p.chromium.launch(

            headless=False,

            executable_path=CHROME_PATH
        )


        context = browser.new_context(

            viewport={
                "width": 1440,
                "height": 900
            },

            locale="de-DE",

            timezone_id="Europe/Berlin",

            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/151.0.0.0 "
                "Safari/537.36"
            )
        )


        page = context.new_page()


        # =====================================================
        # OPEN AMAZON
        # =====================================================

        print()
        print("Opening Amazon...")

        try:

            page.goto(
                SEARCH_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

        except Exception as e:

            print()
            print("ERROR:")
            print(e)

            browser.close()

            return


        page.wait_for_timeout(5000)


        print()
        print("TITLE:")
        print(page.title())

        print()
        print("URL:")
        print(page.url)


        # =====================================================
        # CHECK CAPTCHA
        # =====================================================

        body_text = page.locator(
            "body"
        ).inner_text().lower()


        if (
            "captcha" in body_text
            or "robot check" in body_text
            or "verify" in body_text
        ):

            print()
            print("=" * 70)
            print("AMAZON CAPTCHA / VERIFICATION DETECTED")
            print("=" * 70)

            print(
                "Complete the verification in the browser."
            )

            input(
                "After finishing it, press ENTER here..."
            )


        # =====================================================
        # LOOP PAGES
        # =====================================================

        for page_number in range(
            1,
            MAX_PAGES + 1
        ):

            print()
            print("=" * 70)
            print(
                f"SCRAPING PAGE {page_number}/{MAX_PAGES}"
            )
            print("=" * 70)


            page.wait_for_timeout(
                3000
            )


            products = scrape_page(
                page,
                page_number
            )


            all_products.extend(
                products
            )


            print()
            print(
                f"Page {page_number}: "
                f"{len(products)} products"
            )


            # =================================================
            # NEXT PAGE
            # =================================================

            if page_number >= MAX_PAGES:
                break


            next_button = page.locator(
                "a.s-pagination-next"
            )


            if next_button.count() == 0:

                print(
                    "Next button not found."
                )

                break


            try:

                href = (
                    next_button
                    .first
                    .get_attribute("href")
                )


                if not href:

                    print(
                        "Next page href not found."
                    )

                    break


                next_url = urljoin(
                    BASE_URL,
                    href
                )


                print()
                print(
                    "Next page:"
                )

                print(
                    next_url
                )


                page.goto(
                    next_url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )


                page.wait_for_timeout(
                    4000
                )


            except Exception as e:

                print(
                    "Error going to next page:"
                )

                print(e)

                break


        # =====================================================
        # CLOSE
        # =====================================================

        browser.close()


    # =========================================================
    # DATAFRAME
    # =========================================================

    print()
    print("=" * 70)
    print("CREATING DATASET")
    print("=" * 70)


    if not all_products:

        print()
        print("NO PRODUCTS FOUND!")

        return


    df = pd.DataFrame(
        all_products
    )


    # Remove duplicate ASINs
    df = df.drop_duplicates(
        subset=["asin"],
        keep="first"
    )


    df = df.reset_index(
        drop=True
    )


    # =========================================================
    # SAVE CSV
    # =========================================================

    df.to_csv(

        OUTPUT_FILE,

        index=False,

        encoding="utf-8-sig"
    )


    print()
    print("=" * 70)
    print("DONE!")
    print("=" * 70)

    print()
    print(
        f"TOTAL UNIQUE PRODUCTS: {len(df)}"
    )

    print()
    print(
        f"CSV FILE: {OUTPUT_FILE}"
    )

    print()
    print("COLUMNS:")

    for column in df.columns:

        print(
            f" - {column}"
        )


    print()
    print("=" * 70)
    print("FIRST 5 PRODUCTS")
    print("=" * 70)

    print(
        df.head(5).to_string()
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    scrape()

