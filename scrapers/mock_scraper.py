"""
Mock scraper for testing purposes.
"""
import logging
from typing import List, Optional
from pathlib import Path
from scrapers.scraper import Scraper, ScrapedDocument
from scrapers import ScraperRegistry

logger = logging.getLogger(__name__)


@ScraperRegistry.register
class MockScraper(Scraper):
    """A mock scraper that returns fake data for testing."""

    @property
    def name(self) -> str:
        return "mock"

    @property
    def base_url(self) -> str:
        return "https://mock-scraper.example.com"

    async def list_documents(
        self,
        page_limit: Optional[int] = None
    ) -> List[ScrapedDocument]:
        """Return a list of mock documents."""
        logger.info(f"mock: starting scraper (page_limit={page_limit})")
        # Calculate total documents to return
        page_size = 20  # Fixed page size for mock scraper
        total_pages = page_limit if page_limit else 3
        total_docs = page_size * total_pages

        documents = []
        for i in range(total_docs):
            current_page = (i // page_size) + 1
            if i % page_size == 0:
                logger.info(f"mock: processing page {current_page}")

            doc = ScrapedDocument(
                source_url=f"{self.base_url}/document/{i+1}",
                document_id=f"MOCK-{i+1:05d}",
                title=f"Mock Document {i+1}",
                metadata={
                    "page": current_page,
                    "index": i,
                    "category": "test",
                    "year": 2024
                },
                document_urls=[
                    f"{self.base_url}/download/{i+1}.pdf",
                    f"{self.base_url}/download/{i+1}.html"
                ]
            )
            documents.append(doc)

        logger.info(f"mock: total documents collected: {len(documents)}")
        return documents

    async def download_document(
        self,
        document: ScrapedDocument,
        output_dir: Path
    ) -> bool:
        """Mock download - just creates a placeholder file."""
        output_file = output_dir / f"{document.document_id}.txt"
        output_file.write_text(
            f"Mock document: {document.title}\n"
            f"Source: {document.source_url}\n"
            f"Metadata: {document.metadata}\n"
        )
        return True
