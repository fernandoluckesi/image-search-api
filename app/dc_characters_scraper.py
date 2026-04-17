import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Set
from urllib.parse import urljoin, urlparse

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.dc.com/characters"
CARD_SELECTOR = "div.row div.col.col-custom"


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "character"


def build_page_url(page_number: int) -> str:
    if page_number <= 1:
        return BASE_URL
    return f"{BASE_URL}?page={page_number}"


def extract_cards_from_page(page) -> List[Dict[str, str]]:
    js = """
    (selector) => {
      const cards = [];
      const cols = document.querySelectorAll(selector);

            cols.forEach((col) => {
                const container = col.querySelector('div.card-container div.card-border.container-fluid');
                if (!container) return;

                const image = container.querySelector('img');
                const title = container.querySelector('div.card-title');
                const link = col.querySelector('a[href*="/characters/"]');

                if (!image) return;

                const imageUrl = image.getAttribute('src') || image.getAttribute('data-src') || '';
                const linkTitle = (link?.getAttribute('title') || '').trim();
                const ariaLabel = (link?.getAttribute('aria-label') || '').trim();
                const imgAlt = (image.getAttribute('alt') || '').trim();
                const titleText = (
                    (title?.textContent || '').trim() ||
                    linkTitle ||
                    ariaLabel ||
                    imgAlt
                );

        if (!imageUrl || !titleText) return;

                cards.push({ title: titleText, image_url: imageUrl });
      });

      return cards;
    }
    """
    return page.evaluate(js, CARD_SELECTOR)


def normalize_image_url(raw_url: str) -> str:
    return urljoin(BASE_URL, raw_url)


def download_image(session: requests.Session, image_url: str, output_path: Path) -> bool:
    try:
        response = session.get(image_url, timeout=30)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return True
    except requests.RequestException:
        return False


def scrape_dc_characters(max_pages: int, output_dir: Path) -> List[Dict[str, str]]:
    output_dir.mkdir(parents=True, exist_ok=True)

    seen_urls: Set[str] = set()
    collected: List[Dict[str, str]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for page_number in range(1, max_pages + 1):
            current_url = build_page_url(page_number)
            page.goto(current_url, wait_until="domcontentloaded", timeout=60000)

            try:
                page.wait_for_selector(CARD_SELECTOR, timeout=15000)
            except PlaywrightTimeoutError:
                if page_number == 1:
                    print("No cards found on first page. Check selectors/site structure.")
                break

            page.wait_for_timeout(1200)
            cards = extract_cards_from_page(page)

            if not cards:
                break

            page_new_items = 0
            for card in cards:
                image_url = normalize_image_url(card["image_url"])
                if image_url in seen_urls:
                    continue
                seen_urls.add(image_url)

                collected.append({
                    "title": card["title"],
                    "image_url": image_url,
                })
                page_new_items += 1

            print(f"Page {page_number}: {page_new_items} new cards")

            if page_new_items == 0:
                break

        browser.close()

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; dc-scraper/1.0)"})

    for idx, item in enumerate(collected, start=1):
        parsed = urlparse(item["image_url"])
        ext = Path(parsed.path).suffix or ".jpg"
        filename = f"{idx:04d}-{slugify(item['title'])}{ext}"
        file_path = output_dir / filename

        ok = download_image(session, item["image_url"], file_path)
        if ok:
            item["local_path"] = str(file_path)
            print(f"Downloaded: {item['title']}")
        else:
            item["local_path"] = ""
            print(f"Failed: {item['title']} ({item['image_url']})")

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(collected, indent=2), encoding="utf-8")

    print(f"Finished. Total unique cards: {len(collected)}")
    print(f"Manifest saved to: {manifest_path}")

    return collected


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape DC characters images")
    parser.add_argument("--max-pages", type=int, default=20, help="Max pages to try")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("images") / "dc_characters",
        help="Folder where images and manifest will be saved",
    )

    args = parser.parse_args()
    scrape_dc_characters(max_pages=args.max_pages, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
