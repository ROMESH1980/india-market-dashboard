import io
import json
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

STOCKS_PATH = DATA_DIR / "stocks.json"
CACHE_PATH = DATA_DIR / "free_float_cache.json"


# =========================================================
# CONFIG
# =========================================================

BASE_URL = "https://www.nseindia.com"

SHAREHOLDING_PAGE = (
    "https://www.nseindia.com/"
    "companies-listing/"
    "corporate-filings-shareholding-pattern"
)

# Parallelism intentionally kept moderate so NSE is not hammered.
MAX_WORKERS = 8

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 10

MAX_RETRIES = 2
RETRY_SLEEP = 0.75

# Successful filings normally change quarterly.
READY_CACHE_MAX_AGE_DAYS = 120

# Failed lookup should not be retried twice every day forever.
# A short cache helps keep the daily workflow fast.
PENDING_CACHE_MAX_AGE_DAYS = 1

SAVE_CACHE_EVERY = 50


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com/",
}


# =========================================================
# THREAD-LOCAL SESSION
# =========================================================

_thread_local = threading.local()


def get_session():
    """
    One requests.Session per worker thread.

    requests.Session is not shared across threads.
    """

    session = getattr(
        _thread_local,
        "session",
        None,
    )

    if session is not None:
        return session

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    # Warm NSE cookies once for this worker.
    try:
        session.get(
            BASE_URL,
            timeout=(
                CONNECT_TIMEOUT,
                READ_TIMEOUT,
            ),
        )
    except Exception:
        pass

    _thread_local.session = session

    return session


# =========================================================
# JSON
# =========================================================

def load_json(
    path,
    default,
):
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return default


def save_json(
    path,
    data,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    temp_path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temp_path.replace(
        path
    )


# =========================================================
# SAFE VALUES
# =========================================================

def clean_text(
    value,
):
    if value is None:
        return ""

    value = str(
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def normalized_text(
    value,
):
    return (
        clean_text(
            value
        )
        .lower()
        .replace(
            "\xa0",
            " ",
        )
    )


def safe_float(
    value,
):
    if value is None:
        return None

    if isinstance(
        value,
        str,
    ):
        value = (
            value
            .replace(",", "")
            .replace("%", "")
            .replace("₹", "")
            .strip()
        )

        if not value:
            return None

        if value.lower() in {
            "-",
            "—",
            "na",
            "n/a",
            "none",
            "null",
            "pending",
            "nan",
        }:
            return None

    try:
        result = float(
            value
        )

        if not math.isfinite(
            result
        ):
            return None

        return result

    except Exception:
        return None


def safe_int(
    value,
):
    value = safe_float(
        value
    )

    if value is None:
        return None

    return int(
        round(
            value
        )
    )


def utc_now():
    return (
        datetime.now(
            timezone.utc
        )
        .replace(
            microsecond=0
        )
        .isoformat()
    )


# =========================================================
# CACHE
# =========================================================

def cache_age_days(
    entry,
):
    if not isinstance(
        entry,
        dict,
    ):
        return None

    cached_at = entry.get(
        "cachedAt"
    )

    if not cached_at:
        return None

    try:
        timestamp = datetime.fromisoformat(
            str(
                cached_at
            )
            .replace(
                "Z",
                "+00:00",
            )
        )

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(
                tzinfo=timezone.utc
            )

        return (
            datetime.now(
                timezone.utc
            )
            -
            timestamp
        ).total_seconds() / 86400

    except Exception:
        return None


def cache_entry_is_fresh(
    entry,
):
    age = cache_age_days(
        entry
    )

    if age is None:
        return False

    status = str(
        entry.get(
            "status",
            ""
        )
    ).upper()

    if status == "READY":
        return (
            age <=
            READY_CACHE_MAX_AGE_DAYS
        )

    if status == "PENDING":
        return (
            age <=
            PENDING_CACHE_MAX_AGE_DAYS
        )

    return False


# =========================================================
# STOCKS PAYLOAD
# =========================================================

def normalize_stocks_payload(
    payload,
):
    if isinstance(
        payload,
        list,
    ):
        return (
            payload,
            None,
        )

    if isinstance(
        payload,
        dict,
    ):
        for key in (
            "stocks",
            "rows",
            "data",
        ):
            value = payload.get(
                key
            )

            if isinstance(
                value,
                list,
            ):
                return (
                    value,
                    key,
                )

    raise RuntimeError(
        "data/stocks.json must be a list or contain "
        "a stocks / rows / data list"
    )


# =========================================================
# NSE BOARD
# =========================================================

def preferred_tab(
    stock,
):
    board = normalized_text(
        stock.get(
            "board"
        )
    )

    series = normalized_text(
        stock.get(
            "series"
        )
    )

    if (
        "sme"
        in board
        or
        series in {
            "sm",
            "st",
        }
    ):
        return "sme"

    return "equity"


# =========================================================
# HTTP
# =========================================================

def fetch_text(
    url,
):
    """
    HTTP GET with short timeout + retry.

    Returns:
        HTML text
    """

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        session = get_session()

        try:
            response = session.get(
                url,
                timeout=(
                    CONNECT_TIMEOUT,
                    READ_TIMEOUT,
                ),
            )

            if response.status_code in {
                401,
                403,
                429,
            }:
                raise RuntimeError(
                    f"NSE HTTP {response.status_code}"
                )

            response.raise_for_status()

            text = response.text

            if not text:
                raise RuntimeError(
                    "Empty NSE response"
                )

            return text

        except Exception as exc:
            last_error = exc

            if attempt < MAX_RETRIES:
                time.sleep(
                    RETRY_SLEEP
                    *
                    attempt
                )

                # recreate this worker's session after failure
                try:
                    _thread_local.session.close()
                except Exception:
                    pass

                _thread_local.session = None

    raise RuntimeError(
        str(
            last_error
        )
    )


# =========================================================
# SHAREHOLDING PAGE URLS
# =========================================================

def build_shareholding_urls(
    symbol,
    tab,
):
    query_variants = [
        {
            "symbol":
                symbol,
            "tabIndex":
                tab,
        },
        {
            "symbol":
                symbol,
            "tab":
                tab,
        },
        {
            "symbol":
                symbol,
        },
    ]

    return [
        SHAREHOLDING_PAGE
        +
        "?"
        +
        urlencode(
            params
        )
        for params
        in query_variants
    ]


# =========================================================
# DATE
# =========================================================

def parse_date(
    value,
):
    if not value:
        return None

    value = clean_text(
        value
    )

    formats = (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d-%b-%Y",
        "%d %b %Y",
        "%d-%B-%Y",
        "%d %B %Y",
    )

    for fmt in formats:
        try:
            return datetime.strptime(
                value,
                fmt,
            )
        except Exception:
            pass

    return None


def extract_date_text(
    text,
):
    text = clean_text(
        text
    )

    patterns = (
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{1,2}-[A-Za-z]{3,9}-\d{4}\b",
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
        r"\b\d{1,2}-\d{1,2}-\d{4}\b",
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
        )

        if match:
            return match.group(
                0
            )

    return None


# =========================================================
# XBRL LINK EXTRACTION
# =========================================================

def extract_xbrl_candidates(
    html,
    page_url,
):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    candidates = []
    seen = set()

    for anchor in soup.find_all(
        "a"
    ):
        href = clean_text(
            anchor.get(
                "href"
            )
        )

        if not href:
            continue

        context = clean_text(
            anchor.get_text(
                " ",
                strip=True,
            )
        )

        parent = anchor.parent

        if parent is not None:
            context += (
                " "
                +
                clean_text(
                    parent.get_text(
                        " ",
                        strip=True,
                    )
                )
            )

        search_text = (
            href
            +
            " "
            +
            context
        ).lower()

        if not any(
            token in search_text
            for token in (
                "xbrl",
                "ixbrl",
                ".xml",
            )
        ):
            continue

        url = urljoin(
            page_url,
            href,
        )

        if url in seen:
            continue

        seen.add(
            url
        )

        date_text = extract_date_text(
            context
        )

        candidates.append(
            {
                "url":
                    url,

                "dateText":
                    date_text,

                "date":
                    parse_date(
                        date_text
                    ),
            }
        )

    # Fallback scan from raw HTML
    links = re.findall(
        r"""["']([^"']*(?:xbrl|ixbrl)[^"']*)["']""",
        html,
        flags=re.IGNORECASE,
    )

    for raw_url in links:
        url = urljoin(
            page_url,
            raw_url,
        )

        if url in seen:
            continue

        seen.add(
            url
        )

        candidates.append(
            {
                "url":
                    url,

                "dateText":
                    None,

                "date":
                    None,
            }
        )

    return candidates


def choose_latest_candidate(
    candidates,
):
    if not candidates:
        return None

    dated = [
        item
        for item in candidates
        if item.get(
            "date"
        )
        is not None
    ]

    if dated:
        return max(
            dated,
            key=lambda item:
                item[
                    "date"
                ],
        )

    return candidates[
        0
    ]


# =========================================================
# TABLE HELPERS
# =========================================================

def normalize_column(
    column,
):
    if isinstance(
        column,
        tuple,
    ):
        column = " ".join(
            clean_text(
                part
            )
            for part in column
            if clean_text(
                part
            )
        )

    column = normalized_text(
        column
    )

    column = re.sub(
        r"[^a-z0-9%]+",
        " ",
        column,
    )

    column = re.sub(
        r"\s+",
        " ",
        column,
    )

    return column.strip()


def row_text(
    row,
):
    try:
        values = row.tolist()
    except Exception:
        values = list(
            row
        )

    return " ".join(
        normalized_text(
            value
        )
        for value in values
        if normalized_text(
            value
        )
    )


def read_tables(
    html,
):
    try:
        return pd.read_html(
            io.StringIO(
                html
            )
        )

    except Exception:
        return []


def score_table(
    df,
):
    try:
        if df.empty:
            return 0
    except Exception:
        return 0

    headers = " ".join(
        normalize_column(
            column
        )
        for column in df.columns
    )

    samples = []

    try:
        for _, row in df.head(
            30
        ).iterrows():
            samples.append(
                row_text(
                    row
                )
            )
    except Exception:
        pass

    text = (
        headers
        +
        " "
        +
        " ".join(
            samples
        )
    )

    score = 0

    conditions = (
        (
            "public",
            8,
        ),
        (
            "shareholder",
            5,
        ),
        (
            "total no",
            5,
        ),
        (
            "shares held",
            5,
        ),
        (
            "locked",
            4,
        ),
        (
            "table iii",
            8,
        ),
        (
            "% of total",
            3,
        ),
    )

    for token, points in conditions:
        if token in text:
            score += points

    return score


def choose_public_table(
    tables,
):
    best = None
    best_score = 0

    for table in tables:
        score = score_table(
            table
        )

        if score > best_score:
            best = table
            best_score = score

    if (
        best is None
        or
        best_score < 8
    ):
        return None

    return best


# =========================================================
# PUBLIC TOTAL ROW
# =========================================================

def find_public_total_row(
    df,
):
    if df is None:
        return None

    try:
        if df.empty:
            return None
    except Exception:
        return None

    preferred_phrases = (
        "total public shareholding",
        "total public shareholder",
        "public shareholding b",
        "total b",
    )

    for phrase in preferred_phrases:

        for _, row in df.iterrows():

            text = row_text(
                row
            )

            if phrase in text:
                return row

    for _, row in df.iterrows():

        text = row_text(
            row
        )

        if (
            "public"
            in text
            and
            "total"
            in text
        ):
            return row

    # Search backwards because total is often near table bottom.
    for index in range(
        len(df) - 1,
        -1,
        -1,
    ):
        try:
            row = df.iloc[
                index
            ]

            text = row_text(
                row
            )

            if (
                "total"
                in text
                and
                (
                    "public"
                    in text
                    or
                    "shareholding"
                    in text
                    or
                    "shareholder"
                    in text
                )
            ):
                return row

        except Exception:
            continue

    return None


# =========================================================
# COLUMN DETECTION
# =========================================================

def find_column(
    df,
    token_groups,
):
    normalized_columns = {
        column:
            normalize_column(
                column
            )
        for column
        in df.columns
    }

    for tokens in token_groups:

        for column, text in normalized_columns.items():

            if all(
                token in text
                for token in tokens
            ):
                return column

    return None


def numeric_from_row(
    row,
    column,
):
    if column is None:
        return None

    try:
        value = row[
            column
        ]
    except Exception:
        return None

    if isinstance(
        value,
        pd.Series,
    ):
        for item in value.tolist():

            number = safe_float(
                item
            )

            if number is not None:
                return number

        return None

    return safe_float(
        value
    )


# =========================================================
# EXACT PUBLIC VALUES
# =========================================================

def extract_public_values(
    df,
    row,
):
    shares_column = find_column(
        df,
        (
            (
                "total",
                "shares",
                "held",
            ),
            (
                "total no",
                "shares",
            ),
            (
                "total nos",
                "shares",
            ),
        ),
    )

    pct_column = find_column(
        df,
        (
            (
                "% of total",
                "shares",
            ),
            (
                "shareholding %",
            ),
            (
                "% calculated",
            ),
        ),
    )

    locked_column = find_column(
        df,
        (
            (
                "locked",
                "number",
                "shares",
            ),
            (
                "locked",
                "no",
                "shares",
            ),
            (
                "locked",
                "shares",
            ),
        ),
    )

    # -----------------------------------------------------
    # IMPORTANT
    #
    # Do not derive Total Shares from Market Cap / Price.
    # Only filing values are allowed here.
    # -----------------------------------------------------

    public_shares = safe_int(
        numeric_from_row(
            row,
            shares_column,
        )
    )

    public_pct = safe_float(
        numeric_from_row(
            row,
            pct_column,
        )
    )

    locked_shares = safe_int(
        numeric_from_row(
            row,
            locked_column,
        )
    )

    if public_shares is None:
        return None

    if public_shares <= 0:
        return None

    if locked_shares is None:
        locked_shares = 0

    if (
        locked_shares < 0
        or
        locked_shares >
        public_shares
    ):
        locked_shares = 0

    tradable_public_shares = (
        public_shares
        -
        locked_shares
    )

    if tradable_public_shares <= 0:
        return None

    tradable_public_pct = None

    if (
        public_pct is not None
        and
        0 <= public_pct <= 100
    ):
        tradable_public_pct = (
            public_pct
            *
            (
                tradable_public_shares
                /
                public_shares
            )
        )

    return {
        "publicShares":
            public_shares,

        "publicHoldingPct":
            (
                round(
                    public_pct,
                    4,
                )
                if public_pct is not None
                else None
            ),

        "publicLockedShares":
            locked_shares,

        "freeFloatShares":
            tradable_public_shares,

        "freeFloatPct":
            (
                round(
                    tradable_public_pct,
                    4,
                )
                if tradable_public_pct is not None
                else None
            ),
    }


# =========================================================
# PARSE FILING
# =========================================================

def parse_filing(
    html,
):
    tables = read_tables(
        html
    )

    if not tables:
        return None

    table = choose_public_table(
        tables
    )

    if table is None:
        return None

    public_row = find_public_total_row(
        table
    )

    if public_row is None:
        return None

    return extract_public_values(
        table,
        public_row,
    )


# =========================================================
# FETCH ONE STOCK
# =========================================================

def fetch_one_stock(
    stock,
):
    symbol = clean_text(
        stock.get(
            "symbol"
        )
    ).upper()

    if not symbol:
        return (
            symbol,
            {
                "status":
                    "PENDING",

                "reason":
                    "Missing symbol",

                "cachedAt":
                    utc_now(),

                "freeFloatEstimated":
                    False,
            },
        )

    tab = preferred_tab(
        stock
    )

    page_urls = build_shareholding_urls(
        symbol,
        tab,
    )

    reasons = []

    for page_url in page_urls:

        try:
            page_html = fetch_text(
                page_url
            )

        except Exception as exc:
            reasons.append(
                f"shareholding page: {exc}"
            )

            continue

        candidates = extract_xbrl_candidates(
            page_html,
            page_url,
        )

        if not candidates:
            reasons.append(
                "no XBRL link"
            )

            continue

        candidate = choose_latest_candidate(
            candidates
        )

        if candidate is None:
            reasons.append(
                "no usable XBRL candidate"
            )

            continue

        try:
            filing_html = fetch_text(
                candidate[
                    "url"
                ]
            )

        except Exception as exc:
            reasons.append(
                f"XBRL: {exc}"
            )

            continue

        values = parse_filing(
            filing_html
        )

        if values is None:
            reasons.append(
                "public total row / filing values not parsed"
            )

            continue

        filing_date = candidate.get(
            "dateText"
        )

        if (
            not filing_date
            and
            candidate.get(
                "date"
            )
            is not None
        ):
            filing_date = (
                candidate[
                    "date"
                ]
                .date()
                .isoformat()
            )

        result = {
            "status":
                "READY",

            **values,

            "freeFloatDate":
                filing_date,

            "freeFloatSource":
                "NSE Shareholding Pattern XBRL",

            "freeFloatSourceUrl":
                candidate[
                    "url"
                ],

            "freeFloatMethod":
                (
                    "Exact Public Shares less "
                    "Locked-in Public Shares"
                ),

            "freeFloatMethodologyNote":
                (
                    "Filing-derived tradable public shares proxy. "
                    "Not the NSE Indices official free-float factor."
                ),

            "freeFloatEstimated":
                False,

            "cachedAt":
                utc_now(),
        }

        return (
            symbol,
            result,
        )

    reason = (
        " | ".join(
            reasons[
                -3:
            ]
        )
        if reasons
        else
        "No filing data found"
    )

    return (
        symbol,
        {
            "status":
                "PENDING",

            "reason":
                reason,

            "freeFloatEstimated":
                False,

            "cachedAt":
                utc_now(),
        },
    )


# =========================================================
# APPLY RESULT
# =========================================================

FREE_FLOAT_FIELDS = (
    "publicShares",
    "publicHoldingPct",
    "publicLockedShares",
    "freeFloatShares",
    "freeFloatPct",
    "freeFloatDate",
    "freeFloatSource",
    "freeFloatSourceUrl",
    "freeFloatMethod",
    "freeFloatMethodologyNote",
    "freeFloatEstimated",
)


def apply_result(
    stock,
    result,
):
    status = str(
        result.get(
            "status",
            "PENDING",
        )
    ).upper()

    stock[
        "freeFloatStatus"
    ] = status

    if status == "READY":

        for field in FREE_FLOAT_FIELDS:

            stock[
                field
            ] = result.get(
                field
            )

        stock.pop(
            "freeFloatReason",
            None,
        )

        return

    # Missing values must stay None, never zero.
    for field in FREE_FLOAT_FIELDS:

        if field == "freeFloatEstimated":
            stock[
                field
            ] = False
        else:
            stock[
                field
            ] = None

    stock[
        "freeFloatReason"
    ] = result.get(
        "reason"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    start_time = time.time()

    print(
        "=============================================="
    )
    print(
        "BUILD FREE FLOAT - PARALLEL"
    )
    print(
        "=============================================="
    )
    print(
        f"Workers: {MAX_WORKERS}"
    )
    print(
        f"Timeout: {CONNECT_TIMEOUT}s connect / "
        f"{READ_TIMEOUT}s read"
    )
    print()

    payload = load_json(
        STOCKS_PATH,
        None,
    )

    if payload is None:
        raise RuntimeError(
            "data/stocks.json is missing or invalid"
        )

    stocks, list_key = normalize_stocks_payload(
        payload
    )

    cache = load_json(
        CACHE_PATH,
        {},
    )

    if not isinstance(
        cache,
        dict,
    ):
        cache = {}

    symbol_to_stock = {}

    for stock in stocks:

        if not isinstance(
            stock,
            dict,
        ):
            continue

        symbol = clean_text(
            stock.get(
                "symbol"
            )
        ).upper()

        if symbol:
            symbol_to_stock[
                symbol
            ] = stock

    stats = {
        "stocks":
            len(
                symbol_to_stock
            ),

        "cacheUsed":
            0,

        "fetched":
            0,

        "ready":
            0,

        "pending":
            0,

        "errors":
            0,
    }

    to_fetch = []

    # -----------------------------------------------------
    # APPLY FRESH CACHE FIRST
    # -----------------------------------------------------

    for symbol, stock in symbol_to_stock.items():

        cached = cache.get(
            symbol
        )

        if cache_entry_is_fresh(
            cached
        ):

            apply_result(
                stock,
                cached,
            )

            stats[
                "cacheUsed"
            ] += 1

            if (
                str(
                    cached.get(
                        "status",
                        ""
                    )
                ).upper()
                ==
                "READY"
            ):
                stats[
                    "ready"
                ] += 1

            else:
                stats[
                    "pending"
                ] += 1

        else:

            to_fetch.append(
                stock
            )

    print(
        f"Universe      : {stats['stocks']}"
    )

    print(
        f"Fresh cache   : {stats['cacheUsed']}"
    )

    print(
        f"Need fetch    : {len(to_fetch)}"
    )

    print()


    # -----------------------------------------------------
    # PARALLEL FETCH
    # -----------------------------------------------------

    completed = 0

    if to_fetch:

        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS
        ) as executor:

            future_map = {
                executor.submit(
                    fetch_one_stock,
                    stock,
                ):
                    clean_text(
                        stock.get(
                            "symbol"
                        )
                    ).upper()

                for stock in to_fetch
            }

            for future in as_completed(
                future_map
            ):

                fallback_symbol = future_map[
                    future
                ]

                completed += 1

                try:
                    symbol, result = future.result()

                    if not symbol:
                        symbol = fallback_symbol

                except Exception as exc:

                    symbol = fallback_symbol

                    result = {
                        "status":
                            "PENDING",

                        "reason":
                            f"Worker error: {exc}",

                        "freeFloatEstimated":
                            False,

                        "cachedAt":
                            utc_now(),
                    }

                    stats[
                        "errors"
                    ] += 1

                cache[
                    symbol
                ] = result

                stock = symbol_to_stock.get(
                    symbol
                )

                if stock is not None:

                    apply_result(
                        stock,
                        result,
                    )

                stats[
                    "fetched"
                ] += 1

                if (
                    str(
                        result.get(
                            "status",
                            ""
                        )
                    ).upper()
                    ==
                    "READY"
                ):
                    stats[
                        "ready"
                    ] += 1

                else:
                    stats[
                        "pending"
                    ] += 1

                if (
                    completed % 25
                    ==
                    0
                    or
                    completed
                    ==
                    len(
                        to_fetch
                    )
                ):

                    elapsed = (
                        time.time()
                        -
                        start_time
                    )

                    rate = (
                        completed
                        /
                        elapsed
                        if elapsed > 0
                        else 0
                    )

                    print(
                        f"[{completed}/{len(to_fetch)}] "
                        f"ready={stats['ready']} "
                        f"pending={stats['pending']} "
                        f"errors={stats['errors']} "
                        f"rate={rate:.2f}/sec",
                        flush=True,
                    )

                if (
                    completed % SAVE_CACHE_EVERY
                    ==
                    0
                ):
                    save_json(
                        CACHE_PATH,
                        cache,
                    )

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    save_json(
        CACHE_PATH,
        cache,
    )

    if list_key is None:

        output_payload = stocks

    else:

        payload[
            list_key
        ] = stocks

        output_payload = payload

    save_json(
        STOCKS_PATH,
        output_payload,
    )


    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------

    total = stats[
        "stocks"
    ]

    coverage_pct = (
        round(
            stats[
                "ready"
            ]
            /
            total
            *
            100,
            2,
        )
        if total
        else 0
    )

    elapsed_seconds = (
        time.time()
        -
        start_time
    )

    summary = {
        **stats,

        "coveragePct":
            coverage_pct,

        "elapsedSeconds":
            round(
                elapsed_seconds,
                2,
            ),

        "elapsedMinutes":
            round(
                elapsed_seconds
                /
                60,
                2,
            ),

        "workers":
            MAX_WORKERS,
    }

    print()
    print(
        "=============================================="
    )

    print(
        "FREE FLOAT SUMMARY"
    )

    print(
        "=============================================="
    )

    print(
        json.dumps(
            summary,
            indent=2,
        )
    )

    print()
    print(
        "Free Float Shares = "
        "Exact Public Shares - Locked-in Public Shares"
    )

    print(
        "Free Float % = filing-derived Public Holding % "
        "adjusted for locked public shares"
    )

    print(
        "Source = NSE Shareholding Pattern XBRL"
    )

    print(
        "No Market Cap / Price estimation is used."
    )

    print(
        "Methodology note: this is a filing-derived "
        "tradable-public-float proxy, not the NSE Indices "
        "official free-float factor."
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
