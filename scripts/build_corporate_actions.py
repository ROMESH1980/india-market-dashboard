#!/usr/bin/env python3
"""
Build corporate-action adjustment factors for historical stock prices.

Purpose
-------
Raw NSE bhavcopy closing prices are NOT a continuous adjusted-price series.
After a Bonus / Stock Split / Sub-Division, comparing today's post-action
price directly with an old pre-action raw close creates a false return.

This script downloads NSE corporate actions and creates:

    data/corporate_action_adjustments.json

Supported automatically:
    - Bonus
    - Stock Split / Face Value Split / Sub-Division

NOT automatically adjusted:
    - Dividend
    - Rights
    - Demerger
    - Merger / Scheme
    - Capital reduction
    - Other complex actions

For a historical price before an ex-date:

    adjusted_old_price = raw_old_price / cumulative_factor

Examples
--------
Bonus 1:1
    factor = (1 + 1) / 1 = 2

Bonus 2:1
    factor = (2 + 1) / 1 = 3

Split FV 10 -> FV 2
    factor = 10 / 2 = 5

So an old raw price of 500 before a 10->2 split becomes:

    500 / 5 = 100

IMPORTANT
---------
Only confidently parsed Bonus/Split actions are written as AUTO adjustments.
Ambiguous actions are preserved in skipped records for audit.
"""

from __future__ import annotations

import json
import math
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

STOCKS_PATH = DATA / "stocks.json"
OUTPUT_PATH = DATA / "corporate_action_adjustments.json"


# =========================================================
# SETTINGS
# =========================================================

REQUEST_TIMEOUT = 45
MAX_RETRIES = 3

# RS currently needs maximum 12M history.
# Extra buffer protects actions close to the boundary.
LOOKBACK_DAYS = 450

NSE_HOME = "https://www.nseindia.com/"

CORPORATE_ACTION_API = (
    "https://www.nseindia.com/api/corporates-corporateActions"
)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": (
        "https://www.nseindia.com/"
        "companies-listing/corporate-filings-actions"
    ),
    "Connection": "keep-alive",
}


SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# =========================================================
# BASIC HELPERS
# =========================================================

def load_json(path: Path, default):
    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return default


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def safe_float(value):
    try:
        if value is None:
            return None

        value = str(value).replace(",", "").strip()

        if not value:
            return None

        number = float(value)

        if not math.isfinite(number):
            return None

        if number <= 0:
            return None

        return number

    except Exception:
        return None


def clean_text(value) -> str:
    return " ".join(
        str(value or "")
        .replace("\n", " ")
        .replace("\r", " ")
        .split()
    )


def normalise_symbol(value) -> str:
    return clean_text(value).upper()


# =========================================================
# DATE HELPERS
# =========================================================

DATE_FORMATS = [
    "%d-%b-%Y",
    "%d-%B-%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%d/%m/%Y",
]


def parse_date(value):
    text = clean_text(value)

    if not text:
        return None

    text = text[:20]

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(
                text,
                fmt,
            ).date()
        except Exception:
            pass

    return None


# =========================================================
# NSE SESSION
# =========================================================

def warmup_nse():
    urls = [
        NSE_HOME,
        (
            "https://www.nseindia.com/"
            "companies-listing/corporate-filings-actions"
        ),
    ]

    for url in urls:
        try:
            response = SESSION.get(
                url,
                timeout=20,
            )

            print(
                "NSE warmup:",
                response.status_code,
                url,
            )

            if response.status_code == 200:
                return True

        except Exception as exc:
            print(
                "NSE warmup warning:",
                exc,
            )

    return False


# =========================================================
# NSE CORPORATE ACTION DOWNLOAD
# =========================================================

def request_actions(from_date, to_date):
    """
    NSE corporate-action API.

    NSE endpoints sometimes change parameter behaviour.
    Therefore several compatible request forms are attempted.
    """

    from_text = from_date.strftime("%d-%m-%Y")
    to_text = to_date.strftime("%d-%m-%Y")

    attempts = [
        {
            "index": "equities",
            "from_date": from_text,
            "to_date": to_text,
        },
        {
            "index": "equities",
            "from_date": from_text,
            "to_date": to_text,
            "subject": "",
        },
    ]

    last_error = None

    for params in attempts:

        for attempt in range(
            1,
            MAX_RETRIES + 1,
        ):
            try:
                response = SESSION.get(
                    CORPORATE_ACTION_API,
                    params=params,
                    headers=HEADERS,
                    timeout=REQUEST_TIMEOUT,
                )

                print(
                    "Corporate actions request:",
                    response.status_code,
                    response.url,
                )

                if response.status_code == 200:
                    payload = response.json()

                    if isinstance(payload, list):
                        return payload

                    if isinstance(payload, dict):
                        for key in [
                            "data",
                            "records",
                            "results",
                        ]:
                            value = payload.get(key)

                            if isinstance(value, list):
                                return value

                        # Some NSE responses may themselves
                        # contain action dictionaries.
                        if payload:
                            return [payload]

                    return []

                last_error = RuntimeError(
                    f"HTTP {response.status_code}"
                )

                if response.status_code in (
                    401,
                    403,
                    429,
                ):
                    warmup_nse()

                time.sleep(
                    min(2 * attempt, 6)
                )

            except Exception as exc:
                last_error = exc

                print(
                    "Corporate action request warning:",
                    exc,
                )

                time.sleep(
                    min(2 * attempt, 6)
                )

    raise RuntimeError(
        "Unable to download NSE corporate actions: "
        f"{last_error}"
    )


# =========================================================
# RECORD FIELD HELPERS
# =========================================================

def get_first(record, names):
    upper_map = {
        str(k).upper(): v
        for k, v in record.items()
    }

    for name in names:
        if name in record:
            value = record.get(name)

            if value not in (
                None,
                "",
            ):
                return value

        value = upper_map.get(
            str(name).upper()
        )

        if value not in (
            None,
            "",
        ):
            return value

    return None


def action_symbol(record):
    return normalise_symbol(
        get_first(
            record,
            [
                "symbol",
                "SYMBOL",
                "sm_symbol",
                "smSymbol",
            ],
        )
    )


def action_purpose(record):
    return clean_text(
        get_first(
            record,
            [
                "purpose",
                "PURPOSE",
                "subject",
                "description",
                "desc",
            ],
        )
    )


def action_ex_date(record):
    value = get_first(
        record,
        [
            "exDate",
            "ex_date",
            "EX_DATE",
            "exdate",
        ],
    )

    return parse_date(value)


# =========================================================
# BONUS PARSER
# =========================================================

def parse_bonus_factor(purpose):
    """
    NSE examples:
        Bonus 1:1
        Bonus 2:1
        Bonus Issue 3:5

    Bonus A:B means A new shares for B existing shares.

    Adjustment factor:
        (A + B) / B
    """

    text = clean_text(purpose).upper()

    if "BONUS" not in text:
        return None

    patterns = [
        r"BONUS[^0-9]{0,30}(\d+(?:\.\d+)?)\s*[:/]\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*[:/]\s*(\d+(?:\.\d+)?)[^A-Z0-9]{0,20}BONUS",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        a = safe_float(match.group(1))
        b = safe_float(match.group(2))

        if (
            a is None
            or b is None
            or b == 0
        ):
            continue

        factor = (a + b) / b

        if 1 < factor <= 100:
            return {
                "type": "BONUS",
                "factor": factor,
                "ratioA": a,
                "ratioB": b,
                "method": "(A+B)/B",
            }

    return None


# =========================================================
# SPLIT PARSER
# =========================================================

def parse_split_factor(purpose):
    """
    Common NSE descriptions include:

        Face Value Split From Rs 10 To Rs 2
        Sub-Division From Rs 10/- To Rs 2/-
        Stock Split From Face Value Rs 10 To Rs 1
        Split Rs 10 To Rs 5

    Historical pre-split price adjustment:

        factor = OLD_FACE_VALUE / NEW_FACE_VALUE
    """

    text = clean_text(purpose).upper()

    split_words = [
        "SPLIT",
        "SUB-DIVISION",
        "SUB DIVISION",
        "SUBDIVISION",
        "FACE VALUE",
    ]

    if not any(
        word in text
        for word in split_words
    ):
        return None

    patterns = [
        (
            r"(?:FROM|FV|FACE VALUE)"
            r"[^0-9]{0,25}"
            r"(?:RS\.?|RE\.?|₹)?\s*"
            r"(\d+(?:\.\d+)?)"
            r"[^0-9]{0,40}"
            r"(?:TO|INTO)"
            r"[^0-9]{0,25}"
            r"(?:RS\.?|RE\.?|₹)?\s*"
            r"(\d+(?:\.\d+)?)"
        ),
        (
            r"(?:SPLIT|SUB[- ]?DIVISION)"
            r"[^0-9]{0,30}"
            r"(\d+(?:\.\d+)?)"
            r"[^0-9]{1,30}"
            r"(\d+(?:\.\d+)?)"
        ),
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        old_fv = safe_float(
            match.group(1)
        )

        new_fv = safe_float(
            match.group(2)
        )

        if (
            old_fv is None
            or new_fv is None
            or new_fv == 0
        ):
            continue

        factor = old_fv / new_fv

        # This automatic file is intended mainly for
        # ordinary stock splits, not consolidation.
        if factor <= 1:
            continue

        if factor > 100:
            continue

        return {
            "type": "SPLIT",
            "factor": factor,
            "oldFaceValue": old_fv,
            "newFaceValue": new_fv,
            "method": "oldFaceValue/newFaceValue",
        }

    return None


# =========================================================
# CLASSIFY ACTION
# =========================================================

def classify_action(purpose):
    bonus = parse_bonus_factor(
        purpose
    )

    if bonus:
        return bonus

    split = parse_split_factor(
        purpose
    )

    if split:
        return split

    return None


# =========================================================
# BUILD STOCK SYMBOL SET
# =========================================================

def dashboard_symbols():
    stocks = load_json(
        STOCKS_PATH,
        [],
    )

    symbols = set()

    if isinstance(stocks, list):
        for row in stocks:
            symbol = normalise_symbol(
                row.get("symbol")
            )

            if symbol:
                symbols.add(symbol)

    return symbols


# =========================================================
# MAIN
# =========================================================

def main():
    print(
        "=============================================="
    )
    print(
        "BUILD CORPORATE ACTION ADJUSTMENTS"
    )
    print(
        "=============================================="
    )

    symbols = dashboard_symbols()

    print(
        "Dashboard symbols:",
        len(symbols),
    )

    today = date.today()

    from_date = (
        today
        -
        timedelta(days=LOOKBACK_DAYS)
    )

    to_date = today + timedelta(days=7)

    print(
        "Corporate action window:",
        from_date,
        "to",
        to_date,
    )

    warmup_nse()

    records = request_actions(
        from_date,
        to_date,
    )

    print(
        "NSE action records downloaded:",
        len(records),
    )

    adjustments = {}
    skipped = []
    accepted_count = 0

    for record in records:

        if not isinstance(
            record,
            dict,
        ):
            continue

        symbol = action_symbol(
            record
        )

        purpose = action_purpose(
            record
        )

        ex_date = action_ex_date(
            record
        )

        if not symbol:
            continue

        # Only stocks in our dashboard universe.
        if (
            symbols
            and symbol not in symbols
        ):
            continue

        upper_purpose = purpose.upper()

        potentially_relevant = any(
            word in upper_purpose
            for word in [
                "BONUS",
                "SPLIT",
                "SUB-DIVISION",
                "SUB DIVISION",
                "SUBDIVISION",
                "FACE VALUE",
            ]
        )

        if not potentially_relevant:
            continue

        parsed = classify_action(
            purpose
        )

        if (
            parsed is None
            or ex_date is None
        ):
            skipped.append({
                "symbol": symbol,
                "purpose": purpose,
                "exDate": (
                    ex_date.isoformat()
                    if ex_date
                    else None
                ),
                "reason":
                    "UNABLE_TO_PARSE_SAFELY",
            })

            continue

        factor = float(
            parsed["factor"]
        )

        item = {
            "symbol": symbol,
            "exDate": ex_date.isoformat(),
            "purpose": purpose,
            "type": parsed["type"],
            "factor": round(
                factor,
                10,
            ),
            "source": "NSE Corporate Actions",
            "status": "AUTO_VERIFIED_RATIO",
        }

        if parsed["type"] == "BONUS":
            item["ratioA"] = parsed[
                "ratioA"
            ]
            item["ratioB"] = parsed[
                "ratioB"
            ]
            item["method"] = parsed[
                "method"
            ]

        if parsed["type"] == "SPLIT":
            item["oldFaceValue"] = parsed[
                "oldFaceValue"
            ]
            item["newFaceValue"] = parsed[
                "newFaceValue"
            ]
            item["method"] = parsed[
                "method"
            ]

        adjustments.setdefault(
            symbol,
            [],
        ).append(item)

        accepted_count += 1

    # Chronological order is important because
    # multiple actions can occur within 12 months.
    for symbol in adjustments:
        adjustments[symbol].sort(
            key=lambda x: x["exDate"]
        )

    skipped.sort(
        key=lambda x: (
            x.get("symbol") or "",
            x.get("exDate") or "",
        )
    )

    output = {
        "meta": {
            "generatedAt":
                datetime.now(
                    timezone.utc
                ).isoformat(),
            "fromDate":
                from_date.isoformat(),
            "toDate":
                to_date.isoformat(),
            "source":
                "NSE Corporate Actions",
            "method":
                (
                    "Historical raw price divided by "
                    "cumulative Bonus/Split factor "
                    "for actions after historical date."
                ),
            "supportedActions": [
                "BONUS",
                "SPLIT",
            ],
            "unsupportedAutomaticActions": [
                "DIVIDEND",
                "RIGHTS",
                "DEMERGER",
                "MERGER",
                "SCHEME",
                "CAPITAL_REDUCTION",
            ],
            "dashboardSymbols":
                len(symbols),
            "downloadedRecords":
                len(records),
            "acceptedActions":
                accepted_count,
            "symbolsWithAdjustments":
                len(adjustments),
            "skippedAmbiguousActions":
                len(skipped),
        },
        "adjustments": adjustments,
        "skipped": skipped,
    }

    save_json(
        OUTPUT_PATH,
        output,
    )

    print()
    print(
        "Accepted actions:",
        accepted_count,
    )

    print(
        "Symbols with adjustments:",
        len(adjustments),
    )

    print(
        "Skipped ambiguous:",
        len(skipped),
    )

    # Special audit output while fixing MBAPL.
    mbapl = adjustments.get(
        "MBAPL",
        [],
    )

    print()
    print(
        "========== MBAPL CORPORATE ACTION DEBUG =========="
    )

    if mbapl:
        for action in mbapl:
            print(
                json.dumps(
                    action,
                    indent=2,
                )
            )
    else:
        print(
            "No automatically parsed MBAPL Bonus/Split action found."
        )

    print(
        "=================================================="
    )

    print()
    print(
        "Saved:",
        OUTPUT_PATH,
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
