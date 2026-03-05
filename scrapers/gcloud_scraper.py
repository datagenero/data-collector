"""
GCloud Scraper class that extends the base Scraper with Google Cloud Storage support.

This class overrides the file storage methods to upload files to Google Cloud Storage
instead of (or in addition to) local filesystem storage.
"""

import logging
import os
from pathlib import Path
from typing import Optional, Union

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

from scrapers.scraper import Scraper

logger = logging.getLogger(__name__)


class GCloudScraper(Scraper):
    """
    Abstract base class for scrapers that store files in Google Cloud Storage.

    Subclasses must still implement:
    - name: A unique identifier for this scraper
    - base_url: The base URL for the data source
    - list_documents: Method to discover and list available documents
    - download_document: Method to download a specific document

    This class provides GCS-specific implementations of:
    - store_file: Uploads files to Google Cloud Storage
    - file_exists: Checks if files exist in Google Cloud Storage
    """

    def __init__(self):
        """Initialize the GCloud scraper with storage client."""
        super().__init__()
        self._storage_client = None
        self._bucket = None

    @property
    def download_path(self) -> str:
        """Return the base directory to store the downloaded files."""
        return self.name

    def download_filepath(self, filename: str) -> str:
        """
        Return the base URL path for accessing downloaded files.

        For GCS, returns a gs:// URL that can be used to access the files.
        Format: gs://bucket-name/scraper-name
        """
        bucket_name = os.getenv("GCLOUD_STORAGE_BUCKET", "unknown-bucket")
        return f"gs://{bucket_name}/{self.name}/{filename}"

    @property
    def storage_client(self):
        """Lazy-load the Google Cloud Storage client."""
        if self._storage_client is None:
            self._storage_client = storage.Client()
        return self._storage_client

    @property
    def bucket(self):
        """Lazy-load the Google Cloud Storage bucket."""
        if self._bucket is None:
            bucket_name = os.getenv("GCLOUD_STORAGE_BUCKET")
            if not bucket_name:
                raise ValueError(
                    "GCLOUD_STORAGE_BUCKET environment variable is not set"
                )
            self._bucket = self.storage_client.bucket(bucket_name)
            logger.info(f"{self.name}: using GCS bucket '{bucket_name}'")
        return self._bucket

    def create_storage_location(self) -> bool:
        """
        Create or verify the storage location in Google Cloud Storage.

        For GCS, this ensures the bucket exists and is accessible.
        Note: GCS doesn't require creating "directories" - they're just prefixes.

        Returns:
            True if bucket exists and is accessible, False on error
        """
        try:
            # Check if bucket exists and is accessible
            bucket_name = os.getenv("GCLOUD_STORAGE_BUCKET")
            if not bucket_name:
                logger.error(f"{self.name}: GCLOUD_STORAGE_BUCKET environment variable not set")
                return False

            # Accessing self.bucket will trigger lazy-loading and verification
            bucket_exists = self.bucket.exists()

            if bucket_exists:
                logger.info(f"{self.name}: verified GCS bucket '{bucket_name}' exists and is accessible")
                return True
            else:
                logger.error(f"{self.name}: GCS bucket '{bucket_name}' does not exist")
                return False

        except GoogleCloudError as e:
            logger.error(f"{self.name}: failed to access GCS bucket: {e}")
            return False
        except Exception as e:
            logger.error(f"{self.name}: unexpected error verifying GCS bucket: {e}")
            return False

    def file_exists(self, output_filename: str) -> bool:
        """
        Check if a file exists in Google Cloud Storage.

        Args:
            output_filename: Name of the file to check

        Returns:
            True if the file exists in GCS, False otherwise
        """
        try:
            blob_path = f"{self.name}/{output_filename}"
            blob = self.bucket.blob(blob_path)
            exists = blob.exists()
            logger.debug(f"{self.name}: checked GCS blob '{blob_path}', exists={exists}")
            return exists
        except GoogleCloudError as e:
            logger.error(f"{self.name}: error checking if file exists in GCS: {e}")
            return False

    async def store_file(
        self,
        content: Union[str, bytes],
        file_path: Path,
        encoding: Optional[str] = "utf-8",
    ) -> bool:
        """
        Store file content to Google Cloud Storage.

        This method uploads files to GCS instead of storing them locally.

        Args:
            content: The file content (string for text files, bytes for binary)
            file_path: Path used to determine the blob name in GCS
            encoding: Character encoding for text files (ignored for bytes). Default: utf-8

        Returns:
            True if upload was successful, False otherwise
        """
        try:
            blob_path = f"{self.name}/{file_path}"
            blob = self.bucket.blob(blob_path)

            # Upload content based on type
            if isinstance(content, bytes):
                # Binary content (PDF, images, etc.)
                blob.upload_from_string(content, content_type="application/octet-stream")
            else:
                # Text content (HTML, JSON, etc.)
                blob.upload_from_string(
                    content,
                    content_type="text/plain; charset=utf-8"
                )

            logger.debug(f"{self.name}: stored file to GCS at gs://{self.bucket.name}/{blob_path}")
            return True

        except GoogleCloudError as e:
            logger.error(f"{self.name}: failed to store file to GCS at {blob_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"{self.name}: unexpected error storing file to GCS: {e}")
            return False
