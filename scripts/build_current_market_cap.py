import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote

import requests


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

STOCKS_PATH = DATA / "stocks.json"
CACHE_PATH = DATA / "shares_outstanding.json"


# =========================================================
# SETTINGS
# =========================================================

NSE_HOME = "https://www.nseindia.com"

NSE_QUOTE_API = (
    "https://www.nseindia.com/api/quote-equity"
)

CACHE_DAYS = 30

REQUEST_DELAY = 0.20

MAX_RETRIES = 3


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}


# =========================================================
# HELPERS
# =========================================================

def load_json(path, default):
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return default


def save_json(path, data, indent=None):
    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":")
            if indent is None
            else None,
            indent=indent,
        ),
        encoding="utf-8",
    )


def safe_float(value):
    try:
        if value is None:
            return None

        number = float(value)

        if number <= 0:
            return None

        return number

    except Exception:
        return None


def utc_today():
    return (
        datetime.now(timezone.utc)
        .date()
        .isoformat()
    )


def cache_is_fresh(record):
    if not record:
        return False

    updated = record.get(
        "updated"
    )

    if not updated:
        return False

    try:
        updated_date = (
            datetime
            .fromisoformat(updated)
            .date()
        )

        today = (
            datetime.now(timezone.utc)
            .date()
        )

        age = (
            today - updated_date
        ).days

        return age <= CACHE_DAYS

    except Exception:
        return False


# =========================================================
# NSE SESSION
# =========================================================

def create_nse_session():

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    try:

        response = session.get(
            NSE_HOME,
            timeout=30,
        )

        print(
            "NSE session:",
            response.status_code,
        )

    except Exception as exc:

        print(
            "WARNING: NSE homepage session failed:",
            exc,
        )

    return session


# =========================================================
# EXTRACT ISSUED SIZE
# =========================================================

def extract_issued_size(payload):

    if not isinstance(
        payload,
        dict,
    ):
        return None


    # -----------------------------------------------------
    # Primary NSE location
    # -----------------------------------------------------

    security_info = (
        payload.get(
            "securityInfo"
        )
        or {}
    )

    issued_size = safe_float(
        security_info.get(
            "issuedSize"
        )
    )

    if issued_size is not None:
        return issued_size


    # -----------------------------------------------------
    # Defensive fallback search
    # -----------------------------------------------------

    possible_keys = [
        "issuedSize",
        "issued_size",
        "issuedShares",
        "sharesOutstanding",
    ]


    for key in possible_keys:

        value = safe_float(
            payload.get(key)
        )

        if value is not None:
            return value


    return None


# =========================================================
# FETCH SHARES OUTSTANDING FROM NSE
# =========================================================

def fetch_issued_size(
    session,
    symbol,
):

    url = (
        NSE_QUOTE_API
        + "?symbol="
        + quote(
            symbol,
            safe="",
        )
    )


    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:

            response = session.get(
                url,
                timeout=30,
            )


            # -------------------------------------------------
            # Session / rate-limit recovery
            # -------------------------------------------------

            if response.status_code in (
                401,
                403,
                429,
            ):

                print(
                    f"{symbol}: HTTP "
                    f"{response.status_code}, "
                    "refreshing NSE session"
                )

                try:

                    session.get(
                        NSE_HOME,
                        timeout=20,
                    )

                except Exception:
                    pass

                time.sleep(
                    1.5 * attempt
                )

                continue


            response.raise_for_status()


            payload = (
                response.json()
            )


            issued_size = (
                extract_issued_size(
                    payload
                )
            )


            if issued_size is None:

                return (
                    None,
                    "issuedSize not found",
                )


            return (
                issued_size,
                None,
            )


        except Exception as exc:

            if attempt < MAX_RETRIES:

                time.sleep(
                    1.5 * attempt
                )

                continue


            return (
                None,
                str(exc),
            )


    return (
        None,
        "unknown fetch error",
    )


# =========================================================
# CURRENT MARKET CAP
# =========================================================

def calculate_market_cap_cr(
    price,
    shares,
):

    price = safe_float(
        price
    )

    shares = safe_float(
        shares
    )


    if (
        price is None
        or shares is None
    ):
        return None


    # -----------------------------------------------------
    # Price ₹ × number of shares
    #
    # ₹1 Crore = ₹10,000,000
    # -----------------------------------------------------

    market_cap_cr = (
        price
        *
        shares
        /
        10_000_000
    )


    if market_cap_cr <= 0:
        return None


    return round(
        market_cap_cr,
        2,
    )


# =========================================================
# MAIN
# =========================================================

def main():

    DATA.mkdir(
        exist_ok=True
    )


    stocks = load_json(
        STOCKS_PATH,
        [],
    )


    if not isinstance(
        stocks,
        list,
    ):

        raise RuntimeError(
            "stocks.json must contain a list"
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


    print(
        "=============================================="
    )

    print(
        "BUILD CURRENT MARKET CAP"
    )

    print(
        "=============================================="
    )

    print(
        "Stocks:",
        len(stocks),
    )

    print(
        "Cached share records:",
        len(cache),
    )


    session = create_nse_session()


    today = utc_today()


    stats = {

        "stocks":
            len(stocks),

        "cacheFresh":
            0,

        "cacheStaleUsed":
            0,

        "nseFetched":
            0,

        "nseFailed":
            0,

        "marketCapCalculated":
            0,

        "missingPrice":
            0,

        "missingShares":
            0,

    }


    # =====================================================
    # PROCESS EACH STOCK
    # =====================================================

    for index, row in enumerate(
        stocks,
        start=1,
    ):

        symbol = str(
            row.get(
                "symbol"
            )
            or ""
        ).strip()


        isin = str(
            row.get(
                "isin"
            )
            or ""
        ).strip()


        if not symbol:
            continue


        # -------------------------------------------------
        # CACHE KEY
        #
        # Prefer ISIN because symbols may occasionally
        # change after company name/symbol changes.
        # -------------------------------------------------

        cache_key = (
            isin
            or symbol
        )


        cached = (
            cache.get(
                cache_key
            )
            or {}
        )


        cached_shares = (
            safe_float(
                cached.get(
                    "issuedSize"
                )
            )
        )


        issued_size = None

        shares_source_date = None

        shares_status = None


        # =================================================
        # USE FRESH CACHE
        # =================================================

        if (
            cached_shares is not None
            and
            cache_is_fresh(
                cached
            )
        ):

            issued_size = (
                cached_shares
            )

            shares_source_date = (
                cached.get(
                    "updated"
                )
            )

            shares_status = (
                "CACHE_FRESH"
            )

            stats[
                "cacheFresh"
            ] += 1


        # =================================================
        # FETCH FROM NSE
        # =================================================

        else:

            issued_size_new, error = (
                fetch_issued_size(
                    session,
                    symbol,
                )
            )


            if (
                issued_size_new
                is not None
            ):

                issued_size = (
                    issued_size_new
                )

                shares_source_date = (
                    today
                )

                shares_status = (
                    "NSE_FETCHED"
                )


                cache[
                    cache_key
                ] = {

                    "symbol":
                        symbol,

                    "isin":
                        isin,

                    "issuedSize":
                        issued_size,

                    "updated":
                        today,

                    "source":
                        (
                            "NSE quote-equity "
                            "securityInfo.issuedSize"
                        ),

                }


                stats[
                    "nseFetched"
                ] += 1


            else:

                stats[
                    "nseFailed"
                ] += 1


                # -----------------------------------------
                # If live refresh fails but old issued-size
                # cache exists, keep using it.
                #
                # Issued share capital changes much less
                # frequently than daily market price.
                # -----------------------------------------

                if (
                    cached_shares
                    is not None
                ):

                    issued_size = (
                        cached_shares
                    )

                    shares_source_date = (
                        cached.get(
                            "updated"
                        )
                    )

                    shares_status = (
                        "CACHE_STALE"
                    )

                    stats[
                        "cacheStaleUsed"
                    ] += 1


                else:

                    issued_size = None

                    shares_status = (
                        "MISSING"
                    )


                if (
                    index <= 30
                    or
                    index % 100 == 0
                ):

                    print(
                        f"{symbol}: "
                        f"NSE issuedSize failed - "
                        f"{error}"
                    )


            # ---------------------------------------------
            # Avoid hitting NSE too fast
            # ---------------------------------------------

            time.sleep(
                REQUEST_DELAY
            )


        # =================================================
        # CURRENT PRICE
        # =================================================

        price = safe_float(
            row.get(
                "price"
            )
        )


        if price is None:

            stats[
                "missingPrice"
            ] += 1


        if issued_size is None:

            stats[
                "missingShares"
            ] += 1


        # =================================================
        # CALCULATE CURRENT MARKET CAP ₹ CR
        # =================================================

        market_cap_cr = (
            calculate_market_cap_cr(
                price,
                issued_size,
            )
        )


        # =================================================
        # SAVE STOCK FIELDS
        # =================================================

        row[
            "sharesOutstanding"
        ] = (

            round(
                issued_size
            )

            if issued_size
            is not None

            else None
        )


        row[
            "sharesOutstandingSource"
        ] = (

            "NSE quote-equity "
            "securityInfo.issuedSize"

            if issued_size
            is not None

            else None
        )


        row[
            "sharesOutstandingDate"
        ] = (
            shares_source_date
        )


        row[
            "sharesOutstandingStatus"
        ] = (
            shares_status
        )


        row[
            "marketCapCr"
        ] = (
            market_cap_cr
        )


        row[
            "marketCapDate"
        ] = (

            row.get(
                "priceDate"
            )

            if market_cap_cr
            is not None

            else None
        )


        row[
            "marketCapSource"
        ] = (

            (
                "NSE EOD close price × "
                "NSE issuedSize"
            )

            if market_cap_cr
            is not None

            else None
        )


        if (
            market_cap_cr
            is not None
        ):

            stats[
                "marketCapCalculated"
            ] += 1


        # =================================================
        # PERIODIC CACHE SAVE
        #
        # Protect progress if NSE/API fails later.
        # =================================================

        if (
            index % 100 == 0
        ):

            save_json(
                CACHE_PATH,
                cache,
                indent=2,
            )

            print(
                f"Processed {index}/{len(stocks)} | "
                f"marketCap={stats['marketCapCalculated']} | "
                f"NSE fetched={stats['nseFetched']} | "
                f"failed={stats['nseFailed']}"
            )


    # =====================================================
    # FINAL SAVE
    # =====================================================

    save_json(
        CACHE_PATH,
        cache,
        indent=2,
    )


    save_json(
        STOCKS_PATH,
        stocks,
    )


    # =====================================================
    # REPORT
    # =====================================================

    coverage = 0.0

    if len(stocks):

        coverage = (
            stats[
                "marketCapCalculated"
            ]
            /
            len(stocks)
            *
            100
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
        "CURRENT MARKET CAP COMPLETE"
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
        "FORMULA:"
    )

    print(
        "marketCapCr = "
        "price × issuedSize / 10,000,000"
    )

    print()

    print(
        "PRICE SOURCE:"
    )

    print(
        "Official NSE UDiFF EOD close price"
    )

    print()

    print(
        "SHARES SOURCE:"
    )

    print(
        "NSE quote-equity securityInfo.issuedSize"
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "AMFI average market cap is NOT used "
        "in current marketCapCr."
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
