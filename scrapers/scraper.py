"""
Base Scraper class that defines the interface for all scrapers.

Each scraper should subclass this and implement the abstract methods.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
import os
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

    @property
    def download_path(self) -> str:
        """Return the base directory to store the downloaded files."""
        return os.getenv(
            f"DOWNLOAD_DOCUMENTS_PATH/{self.name}",
            f"../data/data-collector/{self.name}",
        )

    def download_filepath(self, filename: str) -> str:
        return os.path.join(self.download_path, filename)

    def create_storage_location(self) -> bool:
        """
        Create the storage location where documents will be stored.

        For local filesystem scrapers, this creates a directory.
        For cloud scrapers, this can create/verify a bucket or prefix.

        Returns:
            True if storage location was created or already exists, False on error
        """
        try:
            # Get download path from environment variable
            output_dir = Path(self.download_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"{self.name}: created storage directory at {output_dir}")
            return True
        except Exception as e:
            logger.error(
                f"{self.name}: failed to create storage location at {output_dir}: {e}"
            )
            return False

    def file_exists(self, output_filename: str) -> bool:
        """
        Check if a file exists at the specified location.

        This method provides a unified interface for checking file existence that can be
        extended later to support cloud storage (S3, GCS, etc.) in addition to
        local filesystem storage.

        Args:
            output_filename: Name of the file to check

        Returns:
            True if the file exists, False otherwise
        """
        file_path = Path(self.download_path) / output_filename
        return file_path.exists()

    async def store_file(
        self,
        content: Union[str, bytes],
        file_name: Path,
        encoding: Optional[str] = "utf-8",
    ) -> bool:
        """
        Store file content to a specific path.

        This method provides a unified interface for storing files that can be
        extended later to support cloud storage (S3, GCS, etc.) in addition to
        local filesystem storage.

        Args:
            content: The file content (string for text files, bytes for binary)
            file_name: name where the file should be stored. It will be concatenated
                to the scraper name as base directory.
            encoding: Character encoding for text files (ignored for bytes). Default: utf-8

        Returns:
            True if storage was successful, False otherwise
        """
        try:
            # Ensure parent directory exists
            file_path = Path(self.download_path) / file_name
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
    async def download_document(self, document: ScrapedDocument) -> DownloadResult:
        """
        Download a specific document and save it to disk.

        Args:
            document: The ScrapedDocument to download

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
