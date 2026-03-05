import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from collector_api.scrapers import router as scrapers_router
from collector_api.datasets import router as datasets_router
from collector_api.documents import router as documents_router

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


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Data Collector application")
    uvicorn.run(app, host="0.0.0.0", port=8000)
