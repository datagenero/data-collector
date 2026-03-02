"""
SAIJ (Sistema Argentino de Información Jurídica) scraper - migrated to use the Scraper base class.

Scrapes legal rulings ("Fallos") from the SAIJ website.
"""

import json
import logging
import os
import re
from typing import List, Optional
from pathlib import Path
import httpx
from playwright.async_api import async_playwright
from scrapers.scraper import Scraper, ScrapedDocument
from scrapers import ScraperRegistry

logger = logging.getLogger(__name__)


@ScraperRegistry.register
class SAIJScraper(Scraper):
    """Scraper for SAIJ legal documents."""

    @property
    def name(self) -> str:
        return "saij"

    @property
    def base_url(self) -> str:
        return "https://www.saij.gob.ar"

    @staticmethod
    def _strip_html(text: str) -> str:
        """
        Remove HTML tags and collapse whitespace from an HTML string.

        Migrated from strip_html() in the original script.
        """
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()

    @staticmethod
    def _ruling_id(title: str) -> str:
        """
        Derive a filesystem-safe ID from a ruling's title.

        Strips punctuation characters and replaces runs of whitespace with underscores.
        Migrated from _ruling_id() in the original script.
        """
        clean = re.sub(r"[,./;]", "", title)
        return re.sub(r"\s+", "_", clean).strip("_")

    async def _process_detail_page(self, browser, href: str) -> dict:
        """
        Open a ruling detail page and extract structured data.

        Migrated from process_page() in the original script.

        Args:
            browser: A Playwright Browser instance
            href: Full URL of the ruling detail page

        Returns:
            Dict with title, sumario, and full_text_links
        """
        page = await browser.new_page()
        try:
            await page.goto(href)
            await page.wait_for_load_state("networkidle")

            title = await page.locator("h1.p-titulo").inner_text()

            sumario_html = await page.locator(
                "#texto-sumario p.p-descriptor-sumario"
            ).inner_html()
            sumario = self._strip_html(sumario_html)

            # Get all href from all <a> elements inside div#partes
            full_text_links = []
            try:
                await page.wait_for_selector("#partes", state="attached", timeout=10000)

                partes_links = page.locator("#partes a")
                links_count = await partes_links.count()

                for i in range(links_count):
                    link_href = await partes_links.nth(i).get_attribute("href")
                    if link_href and link_href.startswith("/descarga-archivo"):
                        full_text_links.append(link_href)

            except Exception as e:
                logger.error(f"saij: error getting links from #partes for {href}: {e}")
                full_text_links = []

            return {
                "href": href,
                "title": title,
                "sumario": sumario,
                "full_text_links": full_text_links,
            }
        finally:
            await page.close()

    async def list_documents(
        self,
        page_limit: Optional[int] = None
    ) -> List[ScrapedDocument]:
        """
        Collect all document metadata from the listing pages.

        Migrated from collect_hrefs() and main() in the original script.
        This method navigates through pagination and processes detail pages to get metadata.
        """
        logger.info(f"saij: starting scraper (page_limit={page_limit})")
        all_documents = []
        max_pages = page_limit if page_limit else None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(self.base_url)
            await page.wait_for_load_state("networkidle")

            # Select "Fallo" in the tipoDocumento dropdown
            select_locator = page.locator("#tipoDocumento")
            await select_locator.select_option(label="Fallo")
            await page.locator("#btn-search-fallo").wait_for(state="visible", timeout=10000)

            # Click the search button
            await page.click("#btn-search-fallo")
            await page.wait_for_load_state("networkidle")

            # Paginate through results
            current_page = 0
            while max_pages is None or current_page < max_pages:
                current_page += 1
                logger.info(f"saij: processing page {current_page}")

                # Get all result links on this page
                links = page.locator("div.resultado-busqueda li.result-item a")
                count = await links.count()

                # Collect hrefs
                page_hrefs = []
                for i in range(count):
                    href = await links.nth(i).get_attribute("href")
                    if href and href.startswith("http"):
                        page_hrefs.append(href)

                # Process all hrefs on this page in parallel to get detailed metadata
                import asyncio
                page_results = await asyncio.gather(
                    *(self._process_detail_page(browser, href) for href in page_hrefs)
                )

                # Convert to ScrapedDocument objects
                for result in page_results:
                    ruling_id = self._ruling_id(result["title"])
                    doc = ScrapedDocument(
                        source_url=result["href"],
                        document_id=ruling_id,
                        title=result["title"],
                        metadata={
                            "sumario": result["sumario"],
                            "full_text_links": result["full_text_links"],
                            "page": current_page
                        },
                        document_urls=[
                            f"{self.base_url}{link}" for link in result["full_text_links"]
                        ]
                    )
                    all_documents.append(doc)

                # Try to go to the next page
                next_button = page.locator("#paginador #paginador-boton-siguiente")
                if await next_button.is_visible():
                    await next_button.click()
                    await page.wait_for_load_state("networkidle")
                else:
                    logger.info("saij: no more pages available")
                    break

            await browser.close()

        logger.info(f"saij: total documents collected: {len(all_documents)}")
        return all_documents

    async def download_document(
        self,
        document: ScrapedDocument,
        output_dir: Path
    ) -> bool:
        """
        Download all files for a specific document and save metadata.

        Migrated from download_files() and _download_one() in the original script.
        """
        ruling_id = document.document_id

        # Save metadata first
        meta_path = output_dir / f"{ruling_id}.json"
        if not meta_path.exists():
            with open(meta_path, "w", encoding="utf-8") as mf:
                json.dump({
                    "href": document.source_url,
                    "title": document.title,
                    "sumario": document.metadata.get("sumario", ""),
                    "full_text_links": document.metadata.get("full_text_links", [])
                }, mf, ensure_ascii=False, indent=2)

        # Download all files
        download_urls = document.document_urls or []
        if not download_urls:
            logger.warning(f"saij: no download URLs for {ruling_id}")
            return True

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
                for index, download_url in enumerate(download_urls):
                    await self._download_one(client, ruling_id, index, download_url, output_dir)
            return True
        except Exception as e:
            logger.error(f"saij: error downloading {ruling_id}: {e}")
            return False

    async def _download_one(
        self,
        client: httpx.AsyncClient,
        ruling_id: str,
        index: int,
        download_url: str,
        output_dir: Path
    ):
        """
        Download a single file via HTTP client and save it to output_dir.

        Migrated from _download_one() in the original script.
        """
        try:
            async with client.stream("GET", download_url) as response:
                response.raise_for_status()

                # Derive extension from Content-Disposition or URL
                disposition = response.headers.get("content-disposition", "")
                cd_match = re.search(r'filename="?([^";]+)"?', disposition)
                if cd_match:
                    ext = os.path.splitext(cd_match.group(1))[-1]
                else:
                    ext = os.path.splitext(download_url.rsplit("/", 1)[-1])[-1] or ".bin"

                dest = output_dir / f"{ruling_id}_{index}{ext}"
                with open(dest, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)

        except Exception as e:
            logger.error(f"saij: error downloading {download_url}: {e}")
