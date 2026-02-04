import argparse
import asyncio
import csv
from playwright.async_api import async_playwright


async def main(url, limit_pages, output_file):
    """Main scraper function."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"Navigating to {url}...")
        await page.goto(url)
        await page.wait_for_load_state("networkidle")

        print("Page loaded successfully!")

        # Select "Fallo" in the tipoDocumento dropdown and wait for the form to update
        print("Selecting 'Fallo' in tipoDocumento...")
        select_locator = page.locator("#tipoDocumento")
        await select_locator.select_option(label="Fallo")
        # Wait for the search button to become visible (client-side form update, no network request)
        await page.locator("#btn-search-fallo").wait_for(state="visible", timeout=10000)
        print("Form updated after selecting 'Fallo'.")

        # Click the search button
        print("Clicking search button...")
        await page.click("#btn-search-fallo")
        await page.wait_for_load_state("networkidle")
        print("Search results loaded!")

        # Collect hrefs across pages
        hrefs = []
        current_page = 0

        while limit_pages is None or current_page < limit_pages:
            current_page += 1
            print(f"\n--- Page {current_page} ---")

            result_items = page.locator("div.resultado-busqueda li.result-item a")
            count = await result_items.count()

            for i in range(count):
                href = await result_items.nth(i).get_attribute("href")
                hrefs.append(href)

            # Try to go to the next page
            next_button = page.locator("#paginador #paginador-boton-siguiente")
            if await next_button.is_visible():
                await next_button.click()
                await page.wait_for_load_state("networkidle")
            else:
                print("No more pages.")
                break

        print(f"\nFound {len(hrefs)} results total")

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["href"])
            writer.writerows([[href] for href in hrefs])
        print(f"Results saved to {output_file}")

        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape SAIJ documents")
    parser.add_argument(
        "--limit-pages",
        type=int,
        default=None,
        help="Maximum number of pages to scrape. No limit if not specified.",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output CSV filename to save the collected hrefs.",
    )
    args = parser.parse_args()

    url = "https://www.saij.gob.ar/"
    asyncio.run(main(url, args.limit_pages, args.output))
