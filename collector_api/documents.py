import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from collector_api.database import get_db
from collector_api.models import Document, Dataset


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])


@router.get("/documents")
def list_documents(
    dataset_name: Optional[str] = Query(None, description="Filter documents by dataset name"),
    page_start: int = Query(0, ge=0, description="Starting index for pagination (0-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of documents per page (max 100)"),
    db: Session = Depends(get_db)
):
    """
    Returns a list of documents in the database with pagination support.

    Args:
        dataset_name: Optional dataset name to filter documents by
        page_start: Starting index for pagination (default: 0)
        page_size: Number of documents to return (default: 20, max: 100)
        db: Database session

    Returns:
        Paginated list of documents with their metadata
    """
    # Build query
    query = db.query(Document)

    # Filter by dataset_name if provided
    if dataset_name is not None:
        # Verify dataset exists
        dataset = db.query(Dataset).filter(Dataset.name == dataset_name).first()
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset '{dataset_name}' not found")

        query = query.filter(Document.dataset_id == dataset.id)

    # Get total count before pagination
    total_count = query.count()

    # Apply pagination
    documents = query.offset(page_start).limit(page_size).all()

    # Format response
    documents_list = []
    for doc in documents:
        documents_list.append({
            "id": doc.id,
            "title": doc.title,
            "source_url": doc.source_url,
            "document_url": doc.document_url,
            "dataset_id": doc.dataset_id,
            "dataset_name": doc.dataset.name,
            "last_seen": doc.last_seen.isoformat() if doc.last_seen else None,
            "last_downloaded": doc.last_downloaded.isoformat() if doc.last_downloaded else None,
            "metadata": doc.metadata_
        })

    return {
        "total": total_count,
        "page_start": page_start,
        "page_size": page_size,
        "returned": len(documents_list),
        "dataset_name": dataset_name,
        "documents": documents_list
    }
