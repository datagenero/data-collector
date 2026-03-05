import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from collector_api.scrapers import router as scrapers_router
from collector_api.datasets import router as datasets_router
from collector_api.documents import router as documents_router
from collector_api.database import get_db
from collector_api.models import Dataset, Document

# Load environment variables from .env file
load_dotenv()

# Import scrapers to register them
import scrapers.mock_scraper  # noqa: F401
import scrapers.pj_jujuy  # noqa: F401
import scrapers.saij  # noqa: F401


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Collector")

# Include API routers
app.include_router(scrapers_router)
app.include_router(datasets_router)
app.include_router(documents_router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    """Main page showing all datasets as cards with document counts"""
    logger.info("Rendering home page")

    # Get all datasets from database with document counts
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

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "datasets": datasets_list}
    )


@app.get("/dataset/{dataset_id}", response_class=HTMLResponse)
async def dataset_detail(
    request: Request,
    dataset_id: int,
    page: int = 0,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    """Detail page for a specific dataset showing all documents in a table"""
    logger.info(f"Accessing dataset: {dataset_id}, page: {page}")

    # Get the dataset
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()

    if not dataset:
        logger.warning(f"Dataset not found: {dataset_id}")
        return templates.TemplateResponse(
            "404.html",
            {"request": request},
            status_code=404
        )

    # Get total document count
    total_documents = db.query(Document).filter(
        Document.dataset_id == dataset_id
    ).count()

    # Get paginated documents
    documents = db.query(Document).filter(
        Document.dataset_id == dataset_id
    ).offset(page * page_size).limit(page_size).all()

    # Calculate pagination info
    total_pages = (total_documents + page_size - 1) // page_size  # Ceiling division
    has_previous = page > 0
    has_next = page < total_pages - 1

    return templates.TemplateResponse(
        "dataset.html",
        {
            "request": request,
            "dataset": dataset,
            "documents": documents,
            "total_documents": total_documents,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_previous": has_previous,
            "has_next": has_next,
        }
    )


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Data Collector application")
    uvicorn.run(app, host="0.0.0.0", port=8000)
