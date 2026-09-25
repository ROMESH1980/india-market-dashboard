import json
import math
from datetime import datetime, timezone
from pathlib import Path


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

STOCKS_PATH = DATA_DIR / "stocks.json"
OUTPUT_PATH = DATA_DIR / "big_move_scanner.json"


# =========================================================
# HELPERS
# =========================================================

def load_json(path, default):
    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def num(value):
    """
    Safe numeric conversion.

    IMPORTANT:
    None / blank / Pending / dash must remain None.
    Do NOT convert missing values to zero.
    """

    if value is None:
        return None

    if isinstance(value, str):
        text = (
            value
            .replace(",", "")
            .replace("%", "")
            .replace("₹", "")
            .strip()
        )

        if not text:
            return None

        if text.lower() in {
            "-",
            "—",
            "na",
            "n/a",
            "none",
            "null",
            "pending",
        }:
            return None

        value = text

    try:
        result = float(value)

        if not math.isfinite(result):
            return None

        return result

    except Exception:
        return None


def integer(value):
