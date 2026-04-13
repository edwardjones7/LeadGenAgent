"""Manta scraper — currently disabled. Manta changed their search URL structure
and returns 400 for all search queries as of April 2026."""

import logging

logger = logging.getLogger(__name__)


async def scrape_manta(category: str, location: str, pages: int = 1) -> list[dict]:
    """Manta search is currently broken — returns empty list."""
    logger.warning("Manta scraper is disabled — site no longer supports search queries")
    return []
