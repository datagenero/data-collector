from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["scrapers"])


@router.get("/list-scrapers")
def list_scrapers():
    """Returns a hardcoded list of available scrapers."""
    return {
        "scrapers": [
            {
                "id": "jujuy",
                "name": "Jujuy Scraper",
                "description": "Scraper for Jujuy judicial data"
            },
            {
                "id": "saij",
                "name": "SAIJ Scraper",
                "description": "Scraper for SAIJ judicial information"
            }
        ]
    }
