from playwright.sync_api import sync_playwright
import pandas as pd
import re
from urllib.parse import urljoin


# =========================================================
# SETTINGS
# =========================================================

URL = "https://www.amazon.de/s?k=laptop"
OUTPUT_FILE = "laptops.csv"

# تعداد صفحات برای استخراج
MAX_PAGES = 3

# مسیر Chrome نصب‌شده روی ویندوز
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def clean_text(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()


def extract_price(text):
    """
    مثال:
    549,99 €  -> 549.99
    1.299,99 € -> 1299.99
    """

    if not text:
        return None

    match = re.search(r"[\d.,]+", text)

    if not match:
        return None

    value = match.group(0)

    try:

        if "," in value:

            # German format
            value = value.replace(".", "")
            value = value.replace(",", ".")

        elif value.count(".") > 1:

            value = value.replace(".", "")

        return float(value)

    except ValueError:

        return None


def extract_rating(text):

    if not text:
        return None

    match = re.search(
        r"([0-5](?:[.,][0-9])?)",
        text
    )

    if not match:
        return None

    try:

        return float(
            match.group(1).replace(",", ".")
        )

    except ValueError:

        return None


def extract_reviews(text):

    if not text:
        return None

    match = re.search(
        r"[\d.,]+",
        text
    )

    if not match:
        return None

    value = match.group(0)

    try:

        return int(
            value
            .replace(".", "")
            .replace(",", "")
        )

    except ValueError:

        return None


# =========================================================
# SCRAPE ONE PAGE
# =========================================================

def scrape_current_page(page):

    products = []

    # Amazon search result cards
    cards = page.locator(
        'div[data-component-type="s-search-result"]'
    )

    count = cards.count()

    print(f"Product cards found: {count}")

    for i in range(count):

        card = cards.nth(i)

        try:

            # -------------------------------------------------
            # ASIN
            # -------------------------------------------------

            asin = card.get_attribute(
                "data-asin"
            )

            if not asin:
                continue

            # -------------------------------------------------
            # TITLE
            # -------------------------------------------------

            title = ""

            title_locator = card.locator(
                "h2 span"
            )

            if title_locator.count() > 0:

                title = clean_text(
                    title_locator.first.inner_text()
                )

            if not title:

                title_locator = card.locator(
                    "h2"
                )

                if title_locator.count() > 0:

                    title = clean_text(
                        title_locator.first.inner_text()
                    )

            # -------------------------------------------------
            # PRODUCT URL
            # -------------------------------------------------

            product_url = ""

            link_locator = card.locator(
                "h2 a"
            )

            if link_locator.count() > 0:

                href = link_locator.first.get_attribute(
                    "href"
                )

                if href:

                    product_url = urljoin(
                        "https://www.amazon.de",
                        href
                    )

            # -------------------------------------------------
            # PRICE
            # -------------------------------------------------

            price = None

            price_locator = card.locator(
                ".a-price .a-offscreen"
            )

            if price_locator.count() > 0:

                price_text = (
                    price_locator.first.inner_text()
                )

                price = extract_price(
                    price_text
                )

            # -------------------------------------------------
            # RATING
            # -------------------------------------------------

            rating = None

            rating_locator = card.locator(
                "span.a-icon-alt"
            )

            if rating_locator.count() > 0:

                rating_text = (
                    rating_locator.first.inner_text()
                )

                rating = extract_rating(
                    rating_text
                )

            # -------------------------------------------------
            # REVIEW COUNT
            # -------------------------------------------------

            reviews = None

            review_locator = card.locator(
                'a[href*="#customerReviews"]'
            )

            if review_locator.count() > 0:

                review_text = (
                    review_locator.first.inner_text()
                )

                reviews = extract_reviews(
                    review_text
                )

            # -------------------------------------------------
            # IMAGE URL
            # -------------------------------------------------

            image_url = ""

            image_locator = card.locator(
                "img.s-image"
            )

            if image_locator.count() > 0:

                image_url = image_locator.first.get_attribute(
                    "src"
                )

                if not image_url:

                    image_url = (
                        image_locator.first.get_attribute(
                            "data-src"
                        )
                    )

            # -------------------------------------------------
            # PRODUCT
            # -------------------------------------------------

            product = {

                "asin": asin,

                "title": title,

                "price_eur": price,

                "rating": rating,

                "reviews": reviews,

                "product_url": product_url,

                "image_url": image_url

            }

            products.append(product)

        except Exception as e:

            print(
                f"Error extracting product {i}: {e}"
            )

    return products


# =========================================================
# MAIN SCRAPER
# =========================================================

def scrape():

    all_products = []

    with sync_playwright() as p:

        print()
        print("=" * 60)
        print("STARTING AMAZON SCRAPER")
        print("=" * 60)

        # -----------------------------------------------------
        # Launch Chrome
        # -----------------------------------------------------

        browser = p.chromium.launch(
            headless=False,
            executable_path=CHROME_PATH
        )

        page = browser.new_page(

            viewport={
                "width": 1440,
                "height": 900
            },

            locale="de-DE"

        )

        # -----------------------------------------------------
        # Open Amazon
        # -----------------------------------------------------

        print()
        print("Opening Amazon...")

        try:

            page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

        except Exception as e:

            print()
            print("ERROR opening Amazon:")
            print(e)

            browser.close()

            return

        # -----------------------------------------------------
        # Wait for page
        # -----------------------------------------------------

        page.wait_for_timeout(5000)

        print()
        print("PAGE TITLE:")
        print(page.title())

        print()
        print("CURRENT URL:")
        print(page.url)

        # -----------------------------------------------------
        # Pages
        # -----------------------------------------------------

        for page_number in range(
            1,
            MAX_PAGES + 1
        ):

            print()
            print("=" * 60)
            print(f"PAGE {page_number}")
            print("=" * 60)

            # Wait for products
            page.wait_for_timeout(3000)

            # Extract
            products = scrape_current_page(page)

            print(
                f"Products extracted from page {page_number}: "
                f"{len(products)}"
            )

            all_products.extend(products)

            # -------------------------------------------------
            # Next page
            # -------------------------------------------------

            if page_number >= MAX_PAGES:
                break

            next_button = page.locator(
                "a.s-pagination-next"
            )

            if next_button.count() == 0:

                print(
                    "Next page button not found."
                )

                break

            try:

                disabled = (
                    next_button.get_attribute(
                        "aria-disabled"
                    )
                )

                if disabled == "true":

                    print(
                        "Next page is disabled."
                    )

                    break

                print(
                    "Going to next page..."
                )

                next_button.click()

                page.wait_for_load_state(
                    "domcontentloaded"
                )

                page.wait_for_timeout(4000)

            except Exception as e:

                print(
                    "Could not go to next page:"
                )

                print(e)

                break

        # -----------------------------------------------------
        # Close browser
        # -----------------------------------------------------

        browser.close()

    # =========================================================
    # DATA CLEANING
    # =========================================================

    print()
    print("=" * 60)
    print("CLEANING DATA")
    print("=" * 60)

    df = pd.DataFrame(
        all_products
    )

    if df.empty:

        print()
        print("NO PRODUCTS FOUND!")
        print()
        print(
            "Amazon page loaded, but no product cards "
            "were detected."
        )

        return

    # Remove duplicates
    df = df.drop_duplicates(
        subset=["asin"]
    )

    # Reset index
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
    print("=" * 60)
    print("SCRAPING FINISHED")
    print("=" * 60)

    print()
    print(
        f"Total products: {len(df)}"
    )

    print()
    print(
        f"Dataset saved as: {OUTPUT_FILE}"
    )

    print()
    print("Columns:")
    print(
        list(df.columns)
    )

    print()
    print("First 10 products:")
    print(
        df.head(10).to_string()
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    scrape()