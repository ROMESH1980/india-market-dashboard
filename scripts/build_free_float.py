import io
import json
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "data"

STOCKS_PATH = DATA / "stocks.json"

CACHE_PATH = DATA / "free_float_cache.json"


# =========================================================
# CONFIG
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


# =========================================================
# HEADERS
# =========================================================

HEADERS = {

    "User-Agent":
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/152.0.0.0 "
        "Safari/537.36",

    "Accept":
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8",

    "Accept-Language":
        "en-US,en;q=0.9",

    "Referer":
        "https://www.nseindia.com/",

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


def safe_float(value):

    try:

        if value is None:
            return None

        if isinstance(
            value,
            str,
        ):

            text = (
                value
                .replace(",", "")
                .replace("%", "")
                .replace("₹", "")
                .strip()
            )

            if (
                not text
                or
                text.lower()
                in {
                    "-",
                    "—",
                    "na",
                    "n/a",
                    "none",
                    "nil",
                }
            ):

                return None

            value = text

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


def safe_int(value):

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


def normalize_symbol(value):

    return str(
        value
        or ""
    ).strip().upper()


def normalize_text(value):

    return (
        str(
            value
            or ""
        )
        .replace("\xa0", " ")
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
    )


def normalized_column(value):

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        normalize_text(
            value
        ).lower(),
    ).strip()


def parse_date(value):

    text = normalize_text(
        value
    )

    if not text:
        return None

    formats = [

        "%d-%b-%Y",

        "%d-%B-%Y",

        "%Y-%m-%d",

        "%d/%m/%Y",

    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                text,
                fmt,
            ).date()

        except Exception:

            pass

    return None


# =========================================================
# CACHE
# =========================================================

def cache_is_fresh(
    record,
):

    fetched_at = (
        record.get(
            "fetchedAt"
        )
    )

    if not fetched_at:
        return False

    try:

        dt = datetime.fromisoformat(
            fetched_at.replace(
                "Z",
                "+00:00",
            )
        )

        age = (
            datetime.now(
                timezone.utc
            )
            -
            dt
        ).days

        return (
            age
            <=
            CACHE_MAX_AGE_DAYS
        )

    except Exception:

        return False


# =========================================================
# HTTP SESSION
# =========================================================

def build_session():

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    try:

        session.get(
            "https://www.nseindia.com/",
            timeout=
                REQUEST_TIMEOUT,
        )

    except Exception:

        pass

    return session


# =========================================================
# SHAREHOLDING PAGE URL
# =========================================================

def shareholding_url(
    symbol,
    tab,
):

    return (

        SHAREHOLDING_PAGE

        +
        f"?symbol={symbol}"
        +
        f"&tabIndex={tab}"

    )


# =========================================================
# EXTRACT XBRL LINKS
# =========================================================

def extract_xbrl_candidates(
    html,
):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    candidates = []


    for link in soup.find_all(
        "a"
    ):

        href = normalize_text(
            link.get(
                "href"
            )
        )

        if not href:
            continue


        href_lower = (
            href.lower()
        )


        if (
            "ixbrl"
            not in href_lower
            and
            "xbrl"
            not in href_lower
        ):

            continue


        if href.startswith(
            "//"
        ):

            href = (
                "https:"
                +
                href
            )

        elif href.startswith(
            "/"
        ):

            href = (
                BASE_URL
                +
                href
            )


        if not href.startswith(
            "http"
        ):

            continue


        parent_text = ""

        parent = (
            link.parent
        )

        for _ in range(
            4
        ):

            if parent is None:
                break

            parent_text += (
                " "
                +
                normalize_text(
                    parent.get_text(
                        " ",
                        strip=True,
                    )
                )
            )

            parent = (
                parent.parent
            )


        candidates.append({

            "url":
                href,

            "context":
                parent_text,

        })


    # De-duplicate URLs.
    final = []

    seen = set()


    for item in candidates:

        url = item[
            "url"
        ]

        if url in seen:
            continue

        seen.add(
            url
        )

        final.append(
            item
        )


    return final


# =========================================================
# GET LATEST XBRL
# =========================================================

def choose_latest_xbrl(
    candidates,
):

    if not candidates:
        return None


    scored = []


    for item in candidates:

        context = (
            item.get(
                "context"
            )
            or ""
        )


        dates = []


        patterns = [

            r"\b\d{2}-[A-Za-z]{3}-\d{4}\b",

            r"\b\d{2}/\d{2}/\d{4}\b",

            r"\b\d{4}-\d{2}-\d{2}\b",

        ]


        for pattern in patterns:

            for match in re.findall(
                pattern,
                context,
            ):

                parsed = (
                    parse_date(
                        match
                    )
                )

                if parsed:

                    dates.append(
                        parsed
                    )


        filing_date = (
            max(
                dates
            )
            if dates
            else None
        )


        scored.append(
            (
                filing_date,
                item,
            )
        )


    dated = [

        item

        for item
        in scored

        if item[0]
        is not None

    ]


    if dated:

        return max(
            dated,
            key=lambda x:
                x[0]
        )[1]


    # NSE normally displays latest filing first.
    return candidates[0]


# =========================================================
# FLATTEN TABLE
# =========================================================

def flatten_columns(
    dataframe,
):

    df = dataframe.copy()


    if isinstance(
        df.columns,
        pd.MultiIndex,
    ):

        df.columns = [

            " | ".join(

                normalize_text(
                    part
                )

                for part
                in column

                if normalize_text(
                    part
                )
                and
                not normalize_text(
                    part
                ).lower()
                .startswith(
                    "unnamed"
                )

            )

            for column
            in df.columns

        ]

    else:

        df.columns = [

            normalize_text(
                column
            )

            for column
            in df.columns

        ]


    return df


# =========================================================
# FIND COLUMN
# =========================================================

def find_column(
    df,
    required_terms,
):

    for column in df.columns:

        normalized = (
            normalized_column(
                column
            )
        )


        if all(
            term
            in normalized
            for term
            in required_terms
        ):

            return column


    return None


# =========================================================
# ROW TEXT
# =========================================================

def row_text(row):

    return " ".join(

        normalize_text(
            value
        )

        for value
        in row.tolist()

    ).lower()


# =========================================================
# FIND PUBLIC TABLE
# =========================================================

def find_public_table(
    tables,
):

    for table in tables:

        df = flatten_columns(
            table
        )


        columns_text = " ".join(
            normalized_column(
                column
            )
            for column
            in df.columns
        )


        body_text = " ".join(

            row_text(
                row
            )

            for _,
            row
            in df.iterrows()

        )


        combined = (
            columns_text
            +
            " "
            +
            body_text
        )


        if (
            "public shareholder"
            in combined
            and
            "total nos shares held"
            in combined
        ):

            return df


    return None


# =========================================================
# PUBLIC TOTAL ROW
# =========================================================

def find_public_total_row(
    df,
):

    preferred_phrases = [

        "total public shareholding",

        "total public shareholder",

        "public shareholding b",

        "total b",

    ]


    for phrase in preferred_phrases:

        for _,
        row in df.iterrows():

            text = row_text(
                row
            )

            if phrase in text:

                return row


    # Fallback:
    # usually final row of Table III is total.
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
            "public"
            in text
        ):

            return row


    return None


# =========================================================
# EXTRACT PUBLIC SHARES
# =========================================================

def extract_public_metrics(
    xbrl_html,
):

    try:

        tables = pd.read_html(
            io.StringIO(
                xbrl_html
            )
        )

    except Exception as exc:

        raise RuntimeError(
            f"Unable to parse XBRL tables: {exc}"
        )


    if not tables:

        raise RuntimeError(
            "No XBRL tables found"
        )


    public_df = (
        find_public_table(
            tables
        )
    )


    if public_df is None:

        raise RuntimeError(
            "Public Shareholder table not found"
        )


    total_row = (
        find_public_total_row(
            public_df
        )
    )


    if total_row is None:

        raise RuntimeError(
            "Public total row not found"
        )


    total_shares_column = (
        find_column(
            public_df,
            [
                "total",
                "shares",
                "held",
            ],
        )
    )


    holding_pct_column = (
        find_column(
            public_df,
            [
                "shareholding",
                "percentage",
            ],
        )
    )


    if holding_pct_column is None:

        holding_pct_column = (
            find_column(
                public_df,
                [
                    "shareholding",
                ],
            )
        )


    locked_column = (
        find_column(
            public_df,
            [
                "locked",
                "shares",
            ],
        )
    )


    public_shares = None

    public_pct = None

    locked_public_shares = 0


    if total_shares_column:

        public_shares = (
            safe_int(
                total_row[
                    total_shares_column
                ]
            )
        )


    if holding_pct_column:

        public_pct = (
            safe_float(
                total_row[
                    holding_pct_column
                ]
            )
        )


    if locked_column:

        locked_value = (
            safe_int(
                total_row[
                    locked_column
                ]
            )
        )

        if locked_value is not None:

            locked_public_shares = (
                max(
                    0,
                    locked_value,
                )
            )


    # -----------------------------------------------------
    # FALLBACK:
    # if locked column extraction accidentally points to
    # a % field, protect against impossible values.
    # -----------------------------------------------------

    if (
        public_shares is not None
        and
        locked_public_shares
        >
        public_shares
    ):

        locked_public_shares = 0


    tradable_public_shares = None


    if public_shares is not None:

        tradable_public_shares = max(

            0,

            public_shares
            -
            locked_public_shares,

        )


    tradable_pct = None


    if (
        public_pct is not None
        and
        public_shares
        not in (
            None,
            0,
        )
        and
        tradable_public_shares
        is not None
    ):

        unlocked_ratio = (

            tradable_public_shares
            /
            public_shares

        )


        tradable_pct = (

            public_pct
            *
            unlocked_ratio

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
                if
                public_pct
                is not None
                else None
            ),

        "publicLockedShares":
            locked_public_shares,

        "tradablePublicShares":
            tradable_public_shares,

        "tradablePublicPct":
            (
                round(
                    tradable_pct,
                    4,
                )
                if
                tradable_pct
                is not None
                else None
            ),

    }


# =========================================================
# FETCH ONE COMPANY
# =========================================================

def fetch_company_float(
    session,
    symbol,
    preferred_tab,
):

    tabs = []


    if preferred_tab:

        tabs.append(
            preferred_tab
        )


    for fallback_tab in [
        "equity",
        "sme",
    ]:

        if fallback_tab not in tabs:

            tabs.append(
                fallback_tab
            )


    page_error = None


    for tab in tabs:

        url = shareholding_url(
            symbol,
            tab,
        )


        try:

            response = session.get(

                url,

                timeout=
                    REQUEST_TIMEOUT,

            )


            response.raise_for_status()


            candidates = (
                extract_xbrl_candidates(
                    response.text
                )
            )


            latest = (
                choose_latest_xbrl(
                    candidates
                )
            )


            if latest is None:

                continue


            xbrl_url = (
                latest[
                    "url"
                ]
            )


            time.sleep(
                REQUEST_DELAY
            )


            xbrl_response = (
                session.get(

                    xbrl_url,

                    timeout=
                        REQUEST_TIMEOUT,

                )
            )


            xbrl_response.raise_for_status()


            metrics = (
                extract_public_metrics(
                    xbrl_response.text
                )
            )


            if (
                metrics.get(
                    "publicShares"
                )
                is None
            ):

                continue


            # ---------------------------------------------
            # Extract filing date from context where possible.
            # ---------------------------------------------

            filing_date = None


            context = (
                latest.get(
                    "context"
                )
                or ""
            )


            for pattern in [

                r"\b\d{2}-[A-Za-z]{3}-\d{4}\b",

                r"\b\d{4}-\d{2}-\d{2}\b",

                r"\b\d{2}/\d{2}/\d{4}\b",

            ]:

                matches = (
                    re.findall(
                        pattern,
                        context,
                    )
                )


                parsed_dates = [

                    parse_date(
                        item
                    )

                    for item
                    in matches

                ]


                parsed_dates = [

                    item

                    for item
                    in parsed_dates

                    if item
                    is not None

                ]


                if parsed_dates:

                    filing_date = max(
                        parsed_dates
                    )

                    break


            now = (
                datetime.now(
                    timezone.utc
                )
                .replace(
                    microsecond=0
                )
                .isoformat()
            )


            return {

                "symbol":
                    symbol,

                "status":
                    "READY",

                "tab":
                    tab,

                "publicShares":
                    metrics[
                        "publicShares"
                    ],

                "publicHoldingPct":
                    metrics[
                        "publicHoldingPct"
                    ],

                "publicLockedShares":
                    metrics[
                        "publicLockedShares"
                    ],

                "tradablePublicShares":
                    metrics[
                        "tradablePublicShares"
                    ],

                "tradablePublicPct":
                    metrics[
                        "tradablePublicPct"
                    ],

                "filingDate":
                    (
                        filing_date
                        .isoformat()
                        if filing_date
                        else None
                    ),

                "xbrlUrl":
                    xbrl_url,

                "source":
                    "NSE Shareholding Pattern XBRL",

                "method":
                    (
                        "Exact Public Shares less "
                        "Locked-in Public Shares"
                    ),

                "isOfficialIndexFreeFloatFactor":
                    False,

                "fetchedAt":
                    now,

            }


        except Exception as exc:

            page_error = str(
                exc
            )


        time.sleep(
            REQUEST_DELAY
        )


    return {

        "symbol":
            symbol,

        "status":
            "UNAVAILABLE",

        "error":
            page_error,

        "fetchedAt":
            (
                datetime.now(
                    timezone.utc
                )
                .replace(
                    microsecond=0
                )
                .isoformat()
            ),

    }


# =========================================================
# BOARD / TAB
# =========================================================

def preferred_tab_for_stock(
    row,
):

    board = (
        normalize_text(
            row.get(
                "board"
            )
        )
        .upper()
    )


    series = (
        normalize_text(
            row.get(
                "series"
            )
        )
        .upper()
    )


    if (
        board == "SME"
        or
        "SME"
        in board
        or
        series
        in {
            "SM",
            "ST",
        }
    ):

        return "sme"


    return "equity"


# =========================================================
# APPLY TO STOCK
# =========================================================

def apply_float_to_stock(
    stock,
    record,
):

    status = (
        record.get(
            "status"
        )
    )


    if status != "READY":

        stock[
            "freeFloatStatus"
        ] = "PENDING"

        return False


    public_shares = safe_int(
        record.get(
            "publicShares"
        )
    )


    public_pct = safe_float(
        record.get(
            "publicHoldingPct"
        )
    )


    locked_shares = safe_int(
        record.get(
            "publicLockedShares"
        )
    )


    tradable_shares = safe_int(
        record.get(
            "tradablePublicShares"
        )
    )


    tradable_pct = safe_float(
        record.get(
            "tradablePublicPct"
        )
    )


    # =====================================================
    # RAW OFFICIAL FILING VALUES
    # =====================================================

    stock[
        "publicShares"
    ] = public_shares


    stock[
        "publicHoldingPct"
    ] = public_pct


    stock[
        "publicLockedShares"
    ] = (
        locked_shares
        if locked_shares
        is not None
        else 0
    )


    # =====================================================
    # SCANNER FLOAT VALUES
    #
    # IMPORTANT:
    # These are NOT derived from market cap / price.
    #
    # Quantity comes directly from official shareholding
    # filing and locked public shares are removed.
    # =====================================================

    stock[
        "freeFloatShares"
    ] = tradable_shares


    stock[
        "freeFloatPct"
    ] = tradable_pct


    stock[
        "freeFloatDate"
    ] = (
        record.get(
            "filingDate"
        )
    )


    stock[
        "freeFloatSource"
    ] = (
        "NSE Shareholding Pattern XBRL"
    )


    stock[
        "freeFloatSourceUrl"
    ] = (
        record.get(
            "xbrlUrl"
        )
    )


    stock[
        "freeFloatMethod"
    ] = (
        "Exact Public Shares less "
        "Locked-in Public Shares"
    )


    stock[
        "freeFloatMethodologyNote"
    ] = (
        "Filing-derived tradable public shares proxy. "
        "Not the NSE Indices official free-float factor."
    )


    stock[
        "freeFloatEstimated"
    ] = False


    stock[
        "freeFloatStatus"
    ] = "READY"


    return True


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "=============================================="
    )

    print(
        "BUILD FREE FLOAT / PUBLIC FLOAT"
    )

    print(
        "=============================================="
    )


    stocks = load_json(
        STOCKS_PATH,
        [],
    )


    if (
        not isinstance(
            stocks,
            list,
        )
        or
        not stocks
    ):

        raise RuntimeError(
            "stocks.json is missing or empty"
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


    session = (
        build_session()
    )


    stats = {

        "stocks":
            len(stocks),

        "cacheUsed":
            0,

        "fetched":
            0,

        "ready":
            0,

        "pending":
            0,

        "main":
            0,

        "sme":
            0,

    }


    total = len(
        stocks
    )


    for index, stock in enumerate(
        stocks,
        start=1,
    ):

        symbol = normalize_symbol(
            stock.get(
                "symbol"
            )
        )


        if not symbol:

            stats[
                "pending"
            ] += 1

            continue


        preferred_tab = (
            preferred_tab_for_stock(
                stock
            )
        )


        if preferred_tab == "sme":

            stats[
                "sme"
            ] += 1

        else:

            stats[
                "main"
            ] += 1


        cached = (
            cache.get(
                symbol
            )
        )


        if (
            isinstance(
                cached,
                dict,
            )
            and
            cached.get(
                "status"
            )
            ==
            "READY"
            and
            cache_is_fresh(
                cached
            )
        ):

            record = cached

            stats[
                "cacheUsed"
            ] += 1


        else:

            record = (
                fetch_company_float(

                    session,

                    symbol,

                    preferred_tab,

                )
            )


            cache[
                symbol
            ] = record


            stats[
                "fetched"
            ] += 1


        if (
            apply_float_to_stock(
                stock,
                record,
            )
        ):

            stats[
                "ready"
            ] += 1

        else:

            stats[
                "pending"
            ] += 1


        if (
            index % 50
            ==
            0
        ):

            print({

                "progress":
                    f"{index}/{total}",

                "ready":
                    stats[
                        "ready"
                    ],

                "pending":
                    stats[
                        "pending"
                    ],

                "cacheUsed":
                    stats[
                        "cacheUsed"
                    ],

                "fetched":
                    stats[
                        "fetched"
                    ],

            })


            # Save progress.
            save_json(
                CACHE_PATH,
                cache,
            )


            save_json(
                STOCKS_PATH,
                stocks,
            )


    # =====================================================
    # FINAL SAVE
    # =====================================================

    save_json(
        CACHE_PATH,
        cache,
    )


    save_json(
        STOCKS_PATH,
        stocks,
    )


    coverage = (

        stats[
            "ready"
        ]
        /
        stats[
            "stocks"
        ]
        *
        100

        if stats[
            "stocks"
        ]

        else 0

    )


    stats[
        "coveragePct"
    ] = round(
        coverage,
        2,
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
            stats,
            indent=2,
        )
    )


    print()

    print(
        "IMPORTANT:"
    )


    print(
        "freeFloatShares is NOT estimated "
        "from Market Cap / Price."
    )


    print(
        "Source quantity is NSE Shareholding Pattern XBRL."
    )


    print(
        "Method = Public Shares - Locked-in Public Shares."
    )


    print(
        "This is a filing-derived tradable-public-float proxy, "
        "not the NSE Indices official free-float factor."
    )


    print(
        "=============================================="
    )


if __name__ == "__main__":

    main()
