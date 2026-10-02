import calendar
import csv
import io
import json
import math
import time
import zipfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from statistics import median

import pandas as pd
import requests
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
NIFTY500 = "^CRSLDX"
RUN_DATE = datetime.now(timezone.utc).date().isoformat()

METHODOLOGY = {
    "macro": "methodology.html#macro",
    "valueMigration": "methodology.html#value-migration",
}


# =========================================================
# BASIC HELPERS
# =========================================================

def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def safe_float(value):
    try:
        if value is None:
            return None

        value = float(value)

        if pd.isna(value):
            return None

        return value

    except Exception:
        return None


def percentile(value, values):
    value = safe_float(value)

    if value is None:
        return None

    clean = sorted(
        float(v)
        for v in values
        if safe_float(v) is not None
    )

    if not clean:
        return None

    count = sum(
        1
        for v in clean
        if v <= value
    )

    return round(
        count / len(clean) * 100,
        2
    )


def percentile_1_99(value, values):
    """
    Cross-sectional rating:
    lowest available observation = 1
    highest available observation = 99
    """

    value = safe_float(value)

    if value is None:
        return None
