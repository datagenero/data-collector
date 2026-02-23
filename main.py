import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from collector_api.router import router as collector_router

# Import scrapers to register them
import scrapers.mock_scraper  # noqa: F401
import scrapers.pj_jujuy  # noqa: F401
import scrapers.saij  # noqa: F401

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Collector")

# Include API router
app.include_router(collector_router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Hardcoded datasets
DATASETS = [
    {
        "id": "news-articles",
        "name": "News Articles",
        "description": "Collection of news articles from major publications. Includes headlines, content, and metadata from various news sources."
    },
    {
        "id": "research-papers",
        "name": "Research Papers",
        "description": "Academic research papers and publications. Scraped from open access repositories and academic databases."
    },
    {
        "id": "product-reviews",
        "name": "Product Reviews",
        "description": "Customer reviews and ratings for various products. Aggregated from e-commerce platforms and review sites."
    },
    {
        "id": "legal-documents",
        "name": "Legal Documents",
        "description": "Public legal documents, court cases, and regulatory filings. Sourced from government and legal databases."
    }
]


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main page showing all datasets as cards"""
    logger.info("Rendering home page")
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "datasets": DATASETS}
    )


@app.get("/dataset/{dataset_id}", response_class=HTMLResponse)
async def dataset_detail(request: Request, dataset_id: str):
    """Detail page for a specific dataset showing all documents"""
    logger.info(f"Accessing dataset: {dataset_id}")

    # Find the dataset
    dataset = next((d for d in DATASETS if d["id"] == dataset_id), None)

    if not dataset:
        logger.warning(f"Dataset not found: {dataset_id}")
        return templates.TemplateResponse(
            "404.html",
            {"request": request},
            status_code=404
        )

    # Placeholder documents - will be replaced with actual scraped data later
    documents = []

    return templates.TemplateResponse(
        "dataset.html",
        {
            "request": request,
            "dataset": dataset,
            "documents": documents
        }
    )


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Data Collector application")
    uvicorn.run(app, host="0.0.0.0", port=8000)
