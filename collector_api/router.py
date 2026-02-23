from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from scrapers import ScraperRegistry

router = APIRouter(prefix="/api", tags=["scrapers"])


class ListDocumentsRequest(BaseModel):
    """Request body for listing documents."""
    page_size: int = 20
    page_limit: Optional[int] = None


@router.get("/list-scrapers")
def list_scrapers():
    """Returns a list of available scrapers."""
    registered_scrapers = ScraperRegistry.list_all()

    scrapers_list = []
    for name, scraper_class in registered_scrapers.items():
        scraper = scraper_class()
        scrapers_list.append({
            "id": name,
            "name": name.title(),
            "base_url": scraper.base_url
        })

    return {"scrapers": scrapers_list}


@router.post("/scrapers/{scraper_name}/list")
async def list_documents(scraper_name: str, request: ListDocumentsRequest):
    """
    Trigger a scraper to list available documents.

    Args:
        scraper_name: Name of the scraper to use
        request: Pagination parameters

    Returns:
        List of documents found by the scraper
    """
    try:
        scraper = ScraperRegistry.get(scraper_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        documents = await scraper.list_documents(
            page_size=request.page_size,
            page_limit=request.page_limit
        )

        return {
            "scraper": scraper_name,
            "count": len(documents),
            "documents": [
                {
                    "document_id": doc.document_id,
                    "source_url": doc.source_url,
                    "title": doc.title,
                    "metadata": doc.metadata,
                    "document_urls": doc.document_urls
                }
                for doc in documents
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listing documents: {str(e)}"
        )
