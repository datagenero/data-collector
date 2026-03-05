"""
Base Scraper class that defines the interface for all scrapers.

Each scraper should subclass this and implement the abstract methods.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class DownloadStatus(Enum):
    """Status codes for document download operations."""

    SUCCESS = "success"
    FAILURE = "failure"
    SKIP = "skip"


@dataclass
class DownloadResult:
    """Result of a document download operation."""

    status: DownloadStatus
    file_path: Optional[str] = None


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

    def file_exists(self, output_dir: Path, output_filename: str) -> bool:
        """
        Check if a file exists at the specified location.

        This method provides a unified interface for checking file existence that can be
        extended later to support cloud storage (S3, GCS, etc.) in addition to
        local filesystem storage.

        Args:
            output_dir: Directory where the file should be located
            output_filename: Name of the file to check

        Returns:
            True if the file exists, False otherwise
        """
        file_path = output_dir / output_filename
        return file_path.exists()

    async def store_file(
        self,
        content: Union[str, bytes],
        file_path: Path,
        encoding: Optional[str] = "utf-8",
    ) -> bool:
        """
        Store file content to a specific path.

        This method provides a unified interface for storing files that can be
        extended later to support cloud storage (S3, GCS, etc.) in addition to
        local filesystem storage.

        Args:
            content: The file content (string for text files, bytes for binary)
            file_path: Path where the file should be stored
            encoding: Character encoding for text files (ignored for bytes). Default: utf-8

        Returns:
            True if storage was successful, False otherwise
        """
        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write content based on type
            if isinstance(content, bytes):
                # Binary content (PDF, images, etc.)
                with open(file_path, "wb") as f:
                    f.write(content)
            else:
                # Text content (HTML, JSON, etc.)
                with open(file_path, "w", encoding=encoding) as f:
                    f.write(content)

            logger.debug(f"{self.name}: stored file at {file_path}")
            return True

        except Exception as e:
            logger.error(f"{self.name}: failed to store file at {file_path}: {e}")
            return False

    @abstractmethod
    async def list_documents(
        self, page_limit: Optional[int] = None
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
        self, document: ScrapedDocument, output_dir: Path
    ) -> DownloadResult:
        """
        Download a specific document and save it to disk.

        Args:
            document: The ScrapedDocument to download
            output_dir: Directory where files should be saved

        Returns:
            DownloadResult with:
                - status: DownloadStatus (SUCCESS, FAILURE, or SKIP)
                - file_path: Path where the file was saved (only for SUCCESS)
        """
        pass

    async def run(
        self,
        output_dir: Path,
        page_limit: Optional[int] = None,
        max_concurrent: int = 5,
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
            *[download_with_semaphore(doc) for doc in documents], return_exceptions=True
        )

        successful = sum(
            1
            for r in results
            if isinstance(r, DownloadResult) and r.status == DownloadStatus.SUCCESS
        )
        skipped = sum(
            1
            for r in results
            if isinstance(r, DownloadResult) and r.status == DownloadStatus.SKIP
        )
        failed = sum(
            1
            for r in results
            if isinstance(r, Exception)
            or (isinstance(r, DownloadResult) and r.status == DownloadStatus.FAILURE)
        )
        print(
            f"Downloaded {successful}/{len(documents)} documents successfully ({skipped} skipped, {failed} failed)"
        )
