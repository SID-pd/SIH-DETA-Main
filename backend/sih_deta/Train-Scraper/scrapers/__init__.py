"""
Scrapers package for Indian Railways train data extraction.
"""

from .confirmtkt_scraper import ConfirmTktScraper
from .etrain_scraper import ETrainScraper
from .dataset_loader import DatasetLoader

__all__ = ["ConfirmTktScraper", "ETrainScraper", "DatasetLoader"]
