import argparse
import asyncio
import re
from pathlib import Path
from playwright.async_api import async_playwright

BASE_URL = "https://jurisprudencia.justiciajujuy.gov.ar"

async def scrape_document(browser, url, href, output_dir):
    """Scrape a single document and save its content."""
    # Extract ID from href (e.g., documento-sentencia?id=507835 -> 507835)
    match = re.search(r"id=(\d+)", href)
    if not match:
        print(f"Could not extract ID from href: {href}")
        return

    doc_id = match.group(1)
    output_file = output_dir / f"{doc_id}.html"

    # Skip if already downloaded
    if output_file.exists():
        print(f"Skipping {doc_id} (already exists)")
        return

    page = await browser.new_page()
    try:
        full_url = f"{url}/{href}"
        print(f"Scraping {doc_id} from {full_url}")

        await page.goto(full_url)
        await page.wait_for_load_state("networkidle")

        # Get content from div#contentToPrint
        content_div = page.locator("#contentToPrint")
        content = await content_div.inner_html()

        # Save to file
        output_file.write_text(content, encoding="utf-8")
        print(f"Saved {doc_id}.html")

    except Exception as e:
        print(f"Error scraping {doc_id}: {e}")
    finally:
        await page.close()


async def main(url, output_dir):
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get the list of documents
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(f"{url}/public/buscador")
        await page.locator('button[type="submit"]').click()
        await page.wait_for_load_state("networkidle")

        # Get all document links
        table = page.locator("#print_list tbody")
        links = table.locator('a[title="Ver Detalle"]')

        hrefs = await links.evaluate_all(
            "els => els.map(e => e.getAttribute('href'))"
        )

        print(f"Found {len(hrefs)} documents to scrape")
        await page.close()

        # Process all documents in parallel
        tasks = [scrape_document(browser, url, href, output_dir) for href in hrefs]
        await asyncio.gather(*tasks)

        await browser.close()
        print("Scraping completed!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape documents from Jujuy judiciary website"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("../data/"),
        help="Directory to save scraped HTML files (default: ../data/)"
    )
    args = parser.parse_args()

    asyncio.run(main(f"{BASE_URL}", args.output_dir))