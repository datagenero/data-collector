import asyncio
from playwright.async_api import async_playwright


async def main(url):
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

        # Collect hrefs from search results
        print("Collecting results...")
        result_items = page.locator("div.resultado-busqueda li.result-item a")
        # Get all hrefs
        count = await result_items.count()

        hrefs = []
        for i in range(count):
            href = await result_items.nth(i).get_attribute("href")
            print(href)
            hrefs.append(href)

            print(f"\nFound {len(hrefs)} results")

        await browser.close()


if __name__ == "__main__":
    # TODO: Replace with actual SAIJ URL
    url = "https://www.saij.gob.ar/"
    asyncio.run(main(url))
