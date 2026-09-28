import sys
from pathlib import Path

# Ensure experiment/scraper-erail is on sys.path
SCRAPER_ROOT = Path(__file__).resolve().parent
if str(SCRAPER_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRAPER_ROOT))
