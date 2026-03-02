import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from collector_api.database import get_db
from collector_api.models import Document, Dataset


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["datasets"])


@router.get("/datasets")
def list_datasets(db: Session = Depends(get_db)):
    """Returns a list of all datasets in the database."""
    datasets = db.query(Dataset).all()

    datasets_list = []
    for dataset in datasets:
        # Count documents in this dataset
        document_count = db.query(Document).filter(
            Document.dataset_id == dataset.id
        ).count()

        datasets_list.append({
            "id": dataset.id,
            "name": dataset.name,
            "document_count": document_count
        })

    return {"datasets": datasets_list}
