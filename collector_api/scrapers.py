import os
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel
from typing import Optional

import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from collector_api.database import get_db
from collector_api.models import Document, Dataset
from scrapers import ScraperRegistry
from scrapers.scraper import DownloadStatus, DownloadResult


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["scrapers"])


def _update_download_timestamp(
    db: Session,
    document_title: str,
    dataset_id: int,
    document_id: str,
    file_path: Optional[str] = None
) -> bool:
    """
    Update the last_downloaded timestamp and document_url for a document in the database.

    Args:
        db: Database session
        document_title: Title of the document to update
        dataset_id: ID of the dataset the document belongs to
        document_id: ID of the document (for logging)
        file_path: Optional path where the document was saved

    Returns:
        True if the document was found and updated, False otherwise
    """
    db_doc = (
        db.query(Document)
        .filter(
            func.lower(Document.title) == func.lower(document_title),
            Document.dataset_id == dataset_id,
        )
        .first()
    )

    if db_doc:
        db_doc.last_downloaded = datetime.utcnow()
        if file_path:
            db_doc.document_url = file_path
        logger.debug(f"scrapers: updated last_downloaded for {document_id}")
        return True
    else:
        logger.warning(
            f"scrapers: document {document_id} not found in database for timestamp update"
        )
        return False


class ListDocumentsRequest(BaseModel):
    """Request body for listing documents."""

    page_limit: Optional[int] = 1


@router.get("/list-scrapers")
def list_scrapers():
    """Returns a list of available scrapers."""
    registered_scrapers = ScraperRegistry.list_all()

    scrapers_list = []
    for name, scraper_class in registered_scrapers.items():
        scraper = scraper_class()
        scrapers_list.append(
            {"id": name, "name": name.title(), "base_url": scraper.base_url}
        )

    return {"scrapers": scrapers_list}


@router.post("/scrapers/{scraper_name}/list")
async def scrape_documents(
    scraper_name: str,
    request: ListDocumentsRequest,
    download: bool = Query(False, description="Whether to download document files"),
    db: Session = Depends(get_db),
):
    """
    Trigger a scraper to list available documents and store them in the database.

    Args:
        scraper_name: Name of the scraper to use
        request: Pagination parameters
        download: Whether to download the actual document files (default: False)
        db: Database session

    Returns:
        List of documents found by the scraper
    """
    try:
        scraper = ScraperRegistry.get(scraper_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        documents = await scraper.list_documents(page_limit=request.page_limit)

        # Get or create dataset (using scraper name as dataset name for now)
        dataset = db.query(Dataset).filter(Dataset.name == scraper_name).first()
        if not dataset:
            dataset = Dataset(name=scraper_name)
            db.add(dataset)
            db.flush()

        # Process each document
        new_count = 0
        updated_count = 0

        for doc in documents:
            # Check if document exists by matching title (case-insensitive)
            existing_doc = (
                db.query(Document)
                .filter(
                    func.lower(Document.title) == func.lower(doc.title),
                    Document.dataset_id == dataset.id,
                )
                .first()
            )

            if existing_doc:
                # Update last_seen
                existing_doc.last_seen = datetime.utcnow()
                existing_doc.source_url = doc.source_url
                existing_doc.metadata_ = doc.metadata
                updated_count += 1
            else:
                # Create new document
                new_doc = Document(
                    source_url=doc.source_url,
                    document_url=doc.document_urls[0] if doc.document_urls else None,
                    title=doc.title,
                    metadata_=doc.metadata,
                    dataset_id=dataset.id,
                    last_seen=datetime.utcnow(),
                )
                db.add(new_doc)
                new_count += 1
        db.commit()

        # Download documents if requested
        downloaded_count = 0
        download_errors = 0
        skipped_count = 0
        if download:
            logger.info(
                f"scrapers: starting download of {len(documents)} documents for {scraper_name}"
            )

            # Get download path from environment variable
            output_dir = Path(os.getenv(
                f"DOWNLOAD_DOCUMENTS_PATH/{scraper_name}",
                f"../data/data-collector/{scraper_name}",
            ))

            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"scrapers: downloading to {output_dir}")

            # Download documents and update last_downloaded timestamp
            download_results = []
            for doc in documents:
                try:
                    result = await scraper.download_document(doc, output_dir)
                    download_results.append(result)

                    if result.status == DownloadStatus.SUCCESS:
                        downloaded_count += 1
                        # Update last_downloaded timestamp and document_url in database
                        _update_download_timestamp(
                            db, doc.title, dataset.id, doc.document_id, result.file_path
                        )
                    elif result.status == DownloadStatus.SKIP:
                        skipped_count += 1
                    elif result.status == DownloadStatus.FAILURE:
                        download_errors += 1

                except Exception as e:
                    logger.error(f"scrapers: error downloading {doc.document_id}: {e}")
                    download_results.append(DownloadResult(status=DownloadStatus.FAILURE))
                    download_errors += 1

            # Commit download timestamp updates
            db.commit()

            logger.info(
                f"scrapers: download complete - {downloaded_count} successful, "
                f"{skipped_count} skipped, {download_errors} errors"
            )

        return {
            "scraper": scraper_name,
            "total_found": len(documents),
            "new_documents": new_count,
            "updated_documents": updated_count,
            "downloaded": downloaded_count if download else None,
            "skipped": skipped_count if download else None,
            "download_errors": download_errors if download else None,
            "documents": [
                {
                    "document_id": doc.document_id,
                    "source_url": doc.source_url,
                    "title": doc.title,
                    "metadata": doc.metadata,
                    "document_urls": doc.document_urls,
                }
                for doc in documents
            ],
        }
    except Exception as e:
        db.rollback()
        logger.error("router: error retrieveing documents: %s", str(e))
        raise HTTPException(
            status_code=500, detail=f"Error listing documents: {str(e)}"
        )
