"""
Jujuy scraper - migrated to use the Scraper base class.

Scrapes documents from the Jujuy judiciary website.
"""

import logging
import re
from typing import List, Optional
from pathlib import Path
from playwright.async_api import async_playwright
from scrapers.scraper import Scraper, ScrapedDocument
from scrapers import ScraperRegistry

logger = logging.getLogger(__name__)


@ScraperRegistry.register
class JujuyScraper(Scraper):
    """Scraper for Jujuy judicial documents."""

    @property
    def name(self) -> str:
        return "pj_jujuy"

    @property
    def base_url(self) -> str:
        return "https://jurisprudencia.justiciajujuy.gov.ar"

    async def list_documents(
        self, page_limit: Optional[int] = None
    ) -> List[ScrapedDocument]:
        """
        Collect all document hrefs from the listing pages.

        Migrated from collect_hrefs() in the original script.
        """
        logger.info(f"pj_jujuy: starting scraper (page_limit={page_limit})")
        all_documents = []
        max_pages = page_limit if page_limit else 5

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(f"{self.base_url}/public/buscador")
            await page.locator('button[type="submit"]').click()
            await page.wait_for_load_state("networkidle")

            # Iterate through pages
            for page_num in range(1, max_pages + 1):
                logger.info(f"pj_jujuy: processing page {page_num}")
                # Get all document links on current page
                table = page.locator("#print_list tbody")
                links = table.locator('a[title="Ver Detalle"]')

                hrefs = await links.evaluate_all(
                    "els => els.map(e => e.getAttribute('href'))"
                )

                # Convert hrefs to ScrapedDocument objects
                for href in hrefs:
                    # Extract ID from href (e.g., documento-sentencia?id=507835 -> 507835)
                    match = re.search(r"id=(\d+)", href)
                    if match:
                        doc_id = match.group(1)
                        doc = ScrapedDocument(
                            source_url=f"{self.base_url}/{href}",
                            document_id=doc_id,
                            title=f"Jujuy Document {doc_id}",
                            metadata={"href": href, "page": page_num},
                        )
                        all_documents.append(doc)

                # Click next page button if not on last page
                if page_num < max_pages:
                    next_button = page.locator('button[aria-label="Next page"]')

                    # Check if next button exists and is enabled
                    if await next_button.count() > 0:
                        await next_button.click()
                        await page.wait_for_load_state("networkidle")
                    else:
                        logger.info(
                            f"pj_jujuy: No more pages available (stopped at page {page_num})"
                        )
                        break

            await browser.close()

        logger.info(f"pj_jujuy: total documents collected: {len(all_documents)}")
        return all_documents

    async def download_document(
        self, document: ScrapedDocument, output_dir: Path
    ) -> bool:
        """
        Download a single document and save its content.

        Migrated from scrape_document() in the original script.
        """
        output_file = output_dir / f"{document.document_id}.html"

        # Skip if file already exists
        if output_file.exists():
            return True

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(document.source_url)
                await page.wait_for_load_state("networkidle")

                # Get content from div#contentToPrint
                content_div = page.locator("#contentToPrint")
                content = await content_div.inner_html()

                # Save to file
                output_file.write_text(content, encoding="utf-8")
                return True

            except Exception as e:
                logger.error(f"pj_jujuy: error scraping {document.document_id}: {e}")
                return False
            finally:
                await page.close()
                await browser.close()
