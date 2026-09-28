"""Scrapers package for scraper-erail."""
from scrapers.erail_scraper import ErailScraper
from scrapers.live_poller import LivePoller
from scrapers.ntes_scraper import NtesScraper

__all__ = ["ErailScraper", "NtesScraper", "LivePoller"]
