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
    db: Session = Depends(get_db)
):
    """
    Returns a list of all documents in the database.

    Args:
        dataset_name: Optional dataset name to filter documents by
        db: Database session

    Returns:
        List of documents with their metadata
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

    # Execute query
    documents = query.all()

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
        "total": len(documents_list),
        "dataset_name": dataset_name,
        "documents": documents_list
    }
