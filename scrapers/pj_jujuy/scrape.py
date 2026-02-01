import argparse
import asyncio
import re
from pathlib import Path
from playwright.async_api import async_playwright

BASE_URL = "https://jurisprudencia.justiciajujuy.gov.ar"


async def scrape_document(browser, url, href, output_dir, semaphore):
    """Scrape a single document and save its content. Returns True if successful."""
    # Extract ID from href (e.g., documento-sentencia?id=507835 -> 507835)
    match = re.search(r"id=(\d+)", href)
    if not match:
        print(f"Could not extract ID from href: {href}")
        return False

    doc_id = match.group(1)
    output_file = output_dir / f"{doc_id}.html"

    async with semaphore:
        page = await browser.new_page()
        try:
            full_url = f"{url}/{href}"

            await page.goto(full_url)
            await page.wait_for_load_state("networkidle")

            # Get content from div#contentToPrint
            content_div = page.locator("#contentToPrint")
            content = await content_div.inner_html()

            # Save to file
            output_file.write_text(content, encoding="utf-8")
            return True

        except Exception as e:
            print(f"Error scraping {doc_id}: {e}")
            return False
        finally:
            await page.close()


async def collect_hrefs(url, max_pages=5):
    """Collect all document hrefs from the first N pages."""
    all_hrefs = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(f"{url}/public/buscador")
        await page.locator('button[type="submit"]').click()
        await page.wait_for_load_state("networkidle")

        # Iterate through pages
        for page_num in range(1, max_pages + 1):
            print(f"Collecting hrefs from page {page_num}...")

            # Get all document links on current page
            table = page.locator("#print_list tbody")
            links = table.locator('a[title="Ver Detalle"]')

            hrefs = await links.evaluate_all(
                "els => els.map(e => e.getAttribute('href'))"
            )

            all_hrefs.extend(hrefs)
            print(f"  Found {len(hrefs)} documents on page {page_num}")

            # Click next page button if not on last page
            if page_num < max_pages:
                next_button = page.locator('button[aria-label="Next page"]')

                # Check if next button exists and is enabled
                if await next_button.count() > 0:
                    await next_button.click()
                    await page.wait_for_load_state("networkidle")
                else:
                    print(f"  No more pages available (stopped at page {page_num})")
                    break

        await browser.close()

    print(f"\nTotal documents collected: {len(all_hrefs)}")
    return all_hrefs


async def download_documents(url, hrefs, output_dir, max_concurrent=10):
    """Download all documents in parallel with concurrency limit."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create semaphore to limit concurrent downloads
    semaphore = asyncio.Semaphore(max_concurrent)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Process all documents in parallel (limited by semaphore)
        tasks = [
            scrape_document(browser, url, href, output_dir, semaphore) for href in hrefs
        ]
        results = await asyncio.gather(*tasks)

        await browser.close()

    # Count successful downloads
    successful_downloads = sum(1 for result in results if result)
    failed_downloads = len(results) - successful_downloads

    print(f"\nScraping completed!")
    print(f"Successfully downloaded: {successful_downloads}/{len(hrefs)} documents")
    if failed_downloads > 0:
        print(f"Failed: {failed_downloads} documents")


def filter_new_documents(hrefs, output_dir, overwrite=False):
    """Filter out documents that already exist (unless overwrite is True)."""
    if overwrite:
        return hrefs

    new_hrefs = []
    for href in hrefs:
        match = re.search(r"id=(\d+)", href)
        if match:
            doc_id = match.group(1)
            output_file = output_dir / f"{doc_id}.html"
            if not output_file.exists():
                new_hrefs.append(href)

    return new_hrefs


async def main(url, output_dir, page_limit=5, overwrite=False):
    # Step 1: Collect all hrefs from specified number of pages
    hrefs = await collect_hrefs(url, max_pages=page_limit)

    # Step 2: Filter new documents to download
    output_dir.mkdir(parents=True, exist_ok=True)
    hrefs_to_download = filter_new_documents(hrefs, output_dir, overwrite)

    existing_count = len(hrefs) - len(hrefs_to_download)
    print(f"\nDocuments already downloaded: {existing_count}")
    print(f"New documents to download: {len(hrefs_to_download)}")

    # Step 3: Ask user for confirmation
    if len(hrefs_to_download) == 0:
        print("No new documents to download.")
        return

    response = (
        input(f"\nDo you want to download {len(hrefs_to_download)} documents? (y/n): ")
        .strip()
        .lower()
    )
    if response != "y":
        print("Download cancelled.")
        return

    # Step 4: Download all documents in parallel
    await download_documents(url, hrefs_to_download, output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape documents from Jujuy judiciary website"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("../data/"),
        help="Directory to save scraped HTML files (default: ../data/)",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=5,
        help="Number of pages to scrape (default: 5)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing downloaded documents (default: skip existing files)",
    )
    args = parser.parse_args()

    asyncio.run(main(f"{BASE_URL}", args.output_dir, args.page_limit, args.overwrite))
