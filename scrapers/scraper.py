"""
Base Scraper class that defines the interface for all scrapers.

Each scraper should subclass this and implement the abstract methods.
"""
import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ScrapedDocument:
    """Represents a document found by a scraper."""
    source_url: str
    document_id: str
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    content: Optional[str] = None
    document_urls: Optional[List[str]] = None  # URLs to downloadable files


class Scraper(ABC):
    """
    Abstract base class for all scrapers.

    Subclasses must implement:
    - name: A unique identifier for this scraper
    - base_url: The base URL for the data source
    - list_documents: Method to discover and list available documents
    - download_document: Method to download a specific document
    """

    def __init__(self):
        """Initialize the scraper."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of this scraper (e.g., 'saij', 'jujuy')."""
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Return the base URL for this data source."""
        pass

    @abstractmethod
    async def list_documents(
        self,
        page_limit: Optional[int] = None
    ) -> List[ScrapedDocument]:
        """
        Discover and list available documents from the source.

        Args:
            page_limit: Maximum number of pages to scrape (None for all)

        Returns:
            List of ScrapedDocument objects with metadata about each document
        """
        pass

    @abstractmethod
    async def download_document(
        self,
        document: ScrapedDocument,
        output_dir: Path
    ) -> bool:
        """
        Download a specific document and save it to disk.

        Args:
            document: The ScrapedDocument to download
            output_dir: Directory where files should be saved

        Returns:
            True if download was successful, False otherwise
        """
        pass

    async def run(
        self,
        output_dir: Path,
        page_limit: Optional[int] = None,
        max_concurrent: int = 5
    ):
        """
        Run the complete scraping workflow: list documents and download them.

        Args:
            output_dir: Directory where files should be saved
            page_limit: Maximum number of pages to scrape
            max_concurrent: Maximum number of concurrent downloads
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # List all documents
        documents = await self.list_documents(page_limit=page_limit)

        # Download each document
        semaphore = asyncio.Semaphore(max_concurrent)

        async def download_with_semaphore(doc):
            async with semaphore:
                return await self.download_document(doc, output_dir)

        results = await asyncio.gather(
            *[download_with_semaphore(doc) for doc in documents],
            return_exceptions=True
        )

        successful = sum(1 for r in results if r is True)
        print(f"Downloaded {successful}/{len(documents)} documents successfully")
