"""Scrape modes — full vs incremental.

Full mode: scrape ALL pages (used for initial scrape + monthly refresh)
Incremental mode: scrape sorted by recent, stop when hitting known listings
"""

from enum import StrEnum


class ScrapeMode(StrEnum):
    FULL = "full"              # All pages, all listings
    INCREMENTAL = "incremental"  # Sort by recent, stop on known


# Default pages to check in incremental mode per state/operation
INCREMENTAL_MAX_PAGES = 5

# How many consecutive known listings before stopping a page scan
KNOWN_LISTING_STOP_THRESHOLD = 10
