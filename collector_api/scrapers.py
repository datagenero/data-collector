from datetime import datetime
from pydantic import BaseModel
from typing import Optional

import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from collector_api.database import get_db
from collector_api.models import Document, Dataset
from scrapers import ScraperRegistry


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["scrapers"])


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
    scraper_name: str, request: ListDocumentsRequest, db: Session = Depends(get_db)
):
    """
    Trigger a scraper to list available documents and store them in the database.

    Args:
        scraper_name: Name of the scraper to use
        request: Pagination parameters
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

        return {
            "scraper": scraper_name,
            "total_found": len(documents),
            "new_documents": new_count,
            "updated_documents": updated_count,
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
