"""
Web scraper modules for Domain.com.au property data.

Handles fetching and parsing property listings from Domain.
"""

from baulkandcastle.scraper.domain_scraper import DomainScraper
from baulkandcastle.scraper.parsers import parse_listing_html, parse_sold_html

__all__ = [
    "DomainScraper",
    "parse_listing_html",
    "parse_sold_html",
]
