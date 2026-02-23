"""
Scraper registry for managing available scrapers.
"""
from typing import Dict, Type
from scrapers.scraper import Scraper


class ScraperRegistry:
    """Registry to manage and retrieve scrapers by name."""

    _scrapers: Dict[str, Type[Scraper]] = {}

    @classmethod
    def register(cls, scraper_class: Type[Scraper]):
        """Register a scraper class."""
        # Instantiate to get the name
        instance = scraper_class()
        cls._scrapers[instance.name] = scraper_class
        return scraper_class

    @classmethod
    def get(cls, name: str) -> Scraper:
        """Get a scraper instance by name."""
        scraper_class = cls._scrapers.get(name)
        if not scraper_class:
            raise ValueError(f"Scraper '{name}' not found")
        return scraper_class()

    @classmethod
    def list_all(cls) -> Dict[str, Type[Scraper]]:
        """List all registered scrapers."""
        return cls._scrapers.copy()
