import io
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlencode

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
# NSE CONFIG
# =========================================================

BASE_URL = "https://www.nseindia.com"

SHAREHOLDING_PAGE = (
    "https://www.nseindia.com/"
    "companies-listing/"
    "corporate-filings-shareholding-pattern"
)

REQUEST_TIMEOUT = 35
REQUEST_DELAY = 0.18

CACHE_MAX_AGE_DAYS = 120


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com/",
}


# =========================================================
# BASIC HELPERS
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

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
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
        cleaned = (
            value
            .replace(",", "")
            .replace("%", "")
            .replace("₹", "")
            .strip()
        )

        if not cleaned:
            return None

        if cleaned.lower() in {
            "-",
            "—",
            "na",
            "n/a",
            "none",
            "null",
            "pending",
        }:
            return None

        value = cleaned

    try:
        number = float(
            value
        )

        if pd.isna(
            number
        ):
            return None

        return number

    except Exception:
        return None


def safe_int(
    value,
):
    number = safe_float(
        value
    )

    if number is None:
        return None

    return int(
        round(
            number
        )
    )


def clean_text(
    value,
):
    if value is None:
        return ""

    text = str(
        value
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def normalized_text(
    value,
):
    return (
        clean_text(
            value
        )
        .lower()
        .replace("\xa0", " ")
    )


def normalize_column(
    column,
):
    if isinstance(
        column,
        tuple,
    ):
        column = " ".join(
            clean_text(
                item
            )
            for item in column
            if clean_text(
                item
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
    values = []

    try:
        iterator = row.tolist()

    except Exception:
        iterator = list(
            row
        )

    for value in iterator:
        text = normalized_text(
            value
        )

        if text:
            values.append(
                text
            )

    return " ".join(
        values
    )


# =========================================================
# DATE HELPERS
# =========================================================

def parse_date(
    value,
):
    if not value:
        return None

    text = clean_text(
        value
    )

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d-%b-%Y",
        "%d %b %Y",
        "%d-%B-%Y",
        "%d %B %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                text,
                fmt,
            )

        except Exception:
            pass

    match = re.search(
        r"(\d{1,2})[-/ ]"
        r"([A-Za-z]{3,9}|\d{1,2})[-/ ]"
        r"(\d{4})",
        text,
    )

    if match:
        raw = match.group(
            0
        )

        for fmt in formats:
            try:
                return datetime.strptime(
                    raw,
                    fmt,
                )

            except Exception:
                pass

    return None


def extract_date_from_text(
    value,
):
    text = clean_text(
        value
    )

    patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{1,2}-[A-Za-z]{3,9}-\d{4}\b",
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
        r"\b\d{1,2}-\d{1,2}-\d{4}\b",
    ]

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


def utc_now_iso():
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

def cache_entry_is_fresh(
    entry,
):
    if not isinstance(
        entry,
        dict,
    ):
        return False

    if entry.get(
        "status"
    ) != "READY":
        return False

    cached_at = entry.get(
        "cachedAt"
    )

    if not cached_at:
        return False

    try:
        timestamp = datetime.fromisoformat(
            cached_at.replace(
                "Z",
                "+00:00",
            )
        )

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(
                tzinfo=timezone.utc
            )

        age = (
            datetime.now(
                timezone.utc
            )
            -
            timestamp
        ).days

        return (
            age <=
            CACHE_MAX_AGE_DAYS
        )

    except Exception:
        return False


# =========================================================
# SESSION
# =========================================================

def build_session():
    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    try:
        session.get(
            BASE_URL,
            timeout=REQUEST_TIMEOUT,
        )

    except Exception as exc:
        print(
            f"NSE warmup warning: {exc}"
        )

    return session


# =========================================================
# BOARD / TAB
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
# SHAREHOLDING PAGE
# =========================================================

def shareholding_urls(
    symbol,
    tab,
):
    candidates = []

    query_sets = [
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

    for params in query_sets:
        candidates.append(
            SHAREHOLDING_PAGE
            +
            "?"
            +
            urlencode(
                params
            )
        )

    return candidates


def fetch_html(
    session,
    url,
):
    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return response.text


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
            context += " " + clean_text(
                parent.get_text(
                    " ",
                    strip=True,
                )
            )

        href_lower = href.lower()

        context_lower = context.lower()

        looks_xbrl = (
            "xbrl"
            in href_lower
            or
            "ixbrl"
            in href_lower
            or
            "xbrl"
            in context_lower
            or
            "xml"
            in href_lower
        )

        if not looks_xbrl:
            continue

        absolute = urljoin(
            page_url,
            href,
        )

        date_text = extract_date_from_text(
            context
        )

        parsed = parse_date(
            date_text
        )

        candidates.append(
            {
                "url":
                    absolute,

                "context":
                    context,

                "dateText":
                    date_text,

                "date":
                    parsed,
            }
        )

    # -----------------------------------------------------
    # Also scan raw HTML for absolute/relative XBRL URLs
    # -----------------------------------------------------

    raw_links = re.findall(
        r"""(?:href=["']?)?([^"'<> ]+(?:xbrl|ixbrl)[^"'<> ]*)""",
        html,
        flags=re.IGNORECASE,
    )

    for raw in raw_links:
        raw = clean_text(
            raw
        )

        if not raw:
            continue

        absolute = urljoin(
            page_url,
            raw,
        )

        if any(
            item["url"] ==
            absolute
            for item in candidates
        ):
            continue

        candidates.append(
            {
                "url":
                    absolute,

                "context":
                    "",

                "dateText":
                    None,

                "date":
                    None,
            }
        )

    return candidates


def choose_latest_xbrl(
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
        dated.sort(
            key=lambda item:
                item[
                    "date"
                ],
            reverse=True,
        )

        return dated[
            0
        ]

    return candidates[
        0
    ]


# =========================================================
# TABLE READING
# =========================================================

def read_html_tables(
    html,
):
    try:
        tables = pd.read_html(
            io.StringIO(
                html
            )
        )

        return tables

    except Exception:
        return []


def table_score(
    df,
):
    if df is None:
        return 0

    try:
        if df.empty:
            return 0

    except Exception:
        return 0

    column_text = " ".join(
        normalize_column(
            column
        )
        for column in df.columns
    )

    sample_rows = []

    try:
        for _, row in df.head(
            20
        ).iterrows():
            sample_rows.append(
                row_text(
                    row
                )
            )

    except Exception:
        pass

    body_text = " ".join(
        sample_rows
    )

    combined = (
        column_text
        +
        " "
        +
        body_text
    )

    score = 0

    if "public" in combined:
        score += 5

    if "shareholder" in combined:
        score += 4

    if "total no" in combined:
        score += 4

    if "shares held" in combined:
        score += 4

    if "locked" in combined:
        score += 3

    if "% of total" in combined:
        score += 2

    if "table iii" in combined:
        score += 6

    return score


def choose_public_table(
    tables,
):
    best_table = None
    best_score = 0

    for df in tables:
        score = table_score(
            df
        )

        if score > best_score:
            best_score = score
            best_table = df

    if (
        best_table is None
        or
        best_score < 5
    ):
        return None

    return best_table


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

    preferred_phrases = [
        "total public shareholding",
        "total public shareholder",
        "public shareholding b",
        "total b",
    ]

    # -----------------------------------------------------
    # Preferred phrases
    # -----------------------------------------------------

    for phrase in preferred_phrases:

        for _, row in df.iterrows():

            text = row_text(
                row
            )

            if (
                phrase
                in text
            ):
                return row

    # -----------------------------------------------------
    # Public + Total
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Search backwards
    # -----------------------------------------------------

    try:
        for index in range(
            len(df) - 1,
            -1,
            -1,
        ):

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
        pass

    return None


# =========================================================
# COLUMN MATCHING
# =========================================================

def column_map(
    df,
):
    result = {}

    for column in df.columns:
        result[
            column
        ] = normalize_column(
            column
        )

    return result


def find_column(
    df,
    groups,
):
    mapping = column_map(
        df
    )

    # Every string in a group must be present.
    for group in groups:

        for original, normalized in mapping.items():

            if all(
                token
                in normalized
                for token in group
            ):
                return original

    return None


# =========================================================
# ROW NUMERIC EXTRACTION
# =========================================================

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

    # MultiIndex / duplicate columns can yield Series.
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


def extract_public_values(
    df,
    row,
):
    # -----------------------------------------------------
    # Total no. shares held
    # -----------------------------------------------------

    shares_column = find_column(
        df,
        [
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
            (
                "shares held",
            ),
        ],
    )

    # -----------------------------------------------------
    # Public holding %
    # -----------------------------------------------------

    pct_column = find_column(
        df,
        [
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
            (
                "percentage",
                "shares",
            ),
        ],
    )

    # -----------------------------------------------------
    # Locked shares
    # -----------------------------------------------------

    locked_column = find_column(
        df,
        [
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
        ],
    )

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

    if locked_shares is None:
        locked_shares = 0

    # -----------------------------------------------------
    # If exact columns failed, intelligently scan row values.
    # -----------------------------------------------------

    if public_shares is None:

        candidate_numbers = []

        for value in row.tolist():

            number = safe_float(
                value
            )

            if number is None:
                continue

            candidate_numbers.append(
                number
            )

        large_numbers = [
            number
            for number in candidate_numbers
            if number >= 1000
        ]

        if large_numbers:
            public_shares = int(
                round(
                    max(
                        large_numbers
                    )
                )
            )

    if (
        public_pct is None
        or
        public_pct < 0
        or
        public_pct > 100
    ):
        pct_candidates = []

        for value in row.tolist():

            number = safe_float(
                value
            )

            if (
                number is not None
                and
                0 <= number <= 100
            ):
                pct_candidates.append(
                    number
                )

        if pct_candidates:
            # Shareholding % is normally a meaningful %
            # rather than zero.
            positive = [
                value
                for value in pct_candidates
                if value > 0
            ]

            if positive:
                public_pct = positive[
                    0
                ]

    if public_shares is None:
        return None

    if public_shares <= 0:
        return None

    if locked_shares < 0:
        locked_shares = 0

    if locked_shares > public_shares:
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
        public_shares > 0
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
# XBRL PROCESSING
# =========================================================

def parse_xbrl_document(
    html,
):
    tables = read_html_tables(
        html
    )

    if not tables:
        return None

    public_table = choose_public_table(
        tables
    )

    if public_table is None:
        return None

    public_row = find_public_total_row(
        public_table
    )

    if public_row is None:
        return None

    return extract_public_values(
        public_table,
        public_row,
    )


# =========================================================
# ONE STOCK FETCH
# =========================================================

def fetch_free_float_for_stock(
    session,
    stock,
):
    symbol = clean_text(
        stock.get(
            "symbol"
        )
    ).upper()

    if not symbol:
        return {
            "status":
                "PENDING",

            "reason":
                "Missing symbol",
        }

    tab = preferred_tab(
        stock
    )

    page_urls = shareholding_urls(
        symbol,
        tab,
    )

    last_reason = (
        "No XBRL filing found"
    )

    for page_url in page_urls:

        try:
            html = fetch_html(
                session,
                page_url,
            )

        except Exception as exc:
            last_reason = (
                "Shareholding page request failed: "
                +
                str(exc)
            )

            continue

        candidates = extract_xbrl_candidates(
            html,
            page_url,
        )

        if not candidates:
            last_reason = (
                "No XBRL link in shareholding page"
            )

            continue

        candidate = choose_latest_xbrl(
            candidates
        )

        if candidate is None:
            continue

        source_url = candidate[
            "url"
        ]

        try:
            xbrl_html = fetch_html(
                session,
                source_url,
            )

        except Exception as exc:
            last_reason = (
                "XBRL request failed: "
                +
                str(exc)
            )

            continue

        values = parse_xbrl_document(
            xbrl_html
        )

        if values is None:
            last_reason = (
                "Could not parse public shareholding table"
            )

            continue

        filing_date = (
            candidate.get(
                "dateText"
            )
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

        return {
            "status":
                "READY",

            **values,

            "freeFloatDate":
                filing_date,

            "freeFloatSource":
                "NSE Shareholding Pattern XBRL",

            "freeFloatSourceUrl":
                source_url,

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
                utc_now_iso(),
        }

    return {
        "status":
            "PENDING",

        "reason":
            last_reason,

        "freeFloatEstimated":
            False,

        "cachedAt":
            utc_now_iso(),
    }


# =========================================================
# APPLY RESULT TO STOCK
# =========================================================

FREE_FLOAT_FIELDS = [
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
]


def apply_result_to_stock(
    stock,
    result,
):
    status = result.get(
        "status",
        "PENDING",
    )

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

    else:

        # Do not convert unavailable values to zero.
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
# STOCKS PAYLOAD
# =========================================================

def normalize_stocks_payload(
    payload,
):
    if isinstance(
        payload,
        list,
    ):
        return payload, None

    if isinstance(
        payload,
        dict,
    ):
        for key in [
            "stocks",
            "rows",
            "data",
        ]:
            if isinstance(
                payload.get(
                    key
                ),
                list,
            ):
                return (
                    payload[
                        key
                    ],
                    key,
                )

    raise RuntimeError(
        "data/stocks.json must contain a list "
        "or a dict containing stocks/rows/data list"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "=============================================="
    )

    print(
        "BUILD FREE FLOAT"
    )

    print(
        "=============================================="
    )

    stocks_payload = load_json(
        STOCKS_PATH,
        None,
    )

    if stocks_payload is None:
        raise RuntimeError(
            "data/stocks.json not found or invalid"
        )

    stocks, list_key = normalize_stocks_payload(
        stocks_payload
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

    session = build_session()

    stats = {
        "stocks":
            len(
                stocks
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

    for index, stock in enumerate(
        stocks,
        start=1,
    ):

        if not isinstance(
            stock,
            dict,
        ):
            stats[
                "pending"
            ] += 1

            continue

        symbol = clean_text(
            stock.get(
                "symbol"
            )
        ).upper()

        if not symbol:
            stock[
                "freeFloatStatus"
            ] = "PENDING"

            stock[
                "freeFloatReason"
            ] = "Missing symbol"

            stats[
                "pending"
            ] += 1

            continue

        cached = cache.get(
            symbol
        )

        if cache_entry_is_fresh(
            cached
        ):

            result = cached

            stats[
                "cacheUsed"
            ] += 1

        else:

            try:
                result = fetch_free_float_for_stock(
                    session,
                    stock,
                )

                stats[
                    "fetched"
                ] += 1

            except Exception as exc:

                result = {
                    "status":
                        "PENDING",

                    "reason":
                        str(exc),

                    "freeFloatEstimated":
                        False,

                    "cachedAt":
                        utc_now_iso(),
                }

                stats[
                    "errors"
                ] += 1

            cache[
                symbol
            ] = result

            time.sleep(
                REQUEST_DELAY
            )

        apply_result_to_stock(
            stock,
            result,
        )

        if (
            result.get(
                "status"
            )
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
            index % 25
            ==
            0
        ):
            print(
                f"[{index}/{len(stocks)}] "
                f"ready={stats['ready']} "
                f"pending={stats['pending']} "
                f"cache={stats['cacheUsed']} "
                f"fetched={stats['fetched']}"
            )

            save_json(
                CACHE_PATH,
                cache,
            )

    # -----------------------------------------------------
    # Save stocks
    # -----------------------------------------------------

    if list_key is None:
        output_payload = stocks

    else:
        stocks_payload[
            list_key
        ] = stocks

        output_payload = (
            stocks_payload
        )

    save_json(
        STOCKS_PATH,
        output_payload,
    )

    save_json(
        CACHE_PATH,
        cache,
    )

    coverage_pct = (
        round(
            (
                stats[
                    "ready"
                ]
                /
                stats[
                    "stocks"
                ]
                *
                100
            ),
            2,
        )
        if stats[
            "stocks"
        ]
        else 0
    )

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
            {
                **stats,
                "coveragePct":
                    coverage_pct,
            },
            indent=2,
        )
    )

    print()
    print(
        "Method:"
    )

    print(
        "Free Float Shares = Exact Public Shares "
        "- Locked-in Public Shares"
    )

    print(
        "Source: NSE Shareholding Pattern XBRL"
    )

    print(
        "Important: this is a filing-derived tradable-public-"
        "shares proxy, NOT the NSE Indices official "
        "free-float factor."
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
