import json
import re
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

STOCKS_PATH = DATA_DIR / "stocks.json"
EVIDENCE_PATH = DATA_DIR / "company_evidence.json"

CANDIDATES_PATH = (
    DATA_DIR /
    "company_evidence_candidates.json"
)


# =========================================================
# SETTINGS
# =========================================================

TODAY = datetime.now(
    timezone.utc
).date()

RUN_DATE = TODAY.isoformat()

LOOKBACK_DAYS = 365

REQUEST_DELAY = 0.15
REQUEST_TIMEOUT = 20

# First production-safe batch.
MAX_SYMBOLS_PER_RUN = 350

# Keep only strongest/latest useful evidence
# per company and trigger.
MAX_CAPEX_EVENTS_PER_STOCK = 1
MAX_TAILWIND_EVENTS_PER_STOCK = 1

# Strict automatic verification.
AUTO_VERIFY_CAPEX_CLASSES = {
    "CAPACITY_EXPANSION",
    "COMMISSIONING_OR_PRODUCTION",
}
AUTO_VERIFY_CAPEX_MIN_STRENGTH = 90

# Tailwind stays review-only until stronger validation is added.
AUTO_VERIFY_TAILWIND = False


# =========================================================
# NSE
# =========================================================

NSE_HOME = "https://www.nseindia.com"

NSE_ANNOUNCEMENT_API = (
    "https://www.nseindia.com/api/"
    "corporate-announcements"
)

NSE_ANNOUNCEMENT_PAGE = (
    "https://www.nseindia.com/"
    "companies-listing/"
    "corporate-filings-announcements"
)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/124.0.0.0 "
        "Safari/537.36"
    ),
    "Accept": (
        "application/json,"
        "text/plain,*/*"
    ),
    "Accept-Language":
        "en-US,en;q=0.9",
    "Referer":
        NSE_ANNOUNCEMENT_PAGE,
    "Connection":
        "keep-alive",
