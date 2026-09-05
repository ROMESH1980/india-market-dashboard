import calendar
import csv
import io
import json
import math
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

STOCKS_PATH = DATA / "stocks.json"


# =========================================================
# SETTINGS
# =========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,*/*",
}


# How many calendar days backward we search
# around each 3M / 6M / 9M / 12M target date.
MAX_LOOKBACK_DAYS = 10


# MarketSmith-like recent-performance weighting
WEIGHT_3M = 0.40
WEIGHT_6M = 0.20
WEIGHT_9M = 0.20
WEIGHT_12M = 0.20


# =========================================================
# JSON HELPERS
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


def save_json(path, data):

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


# =========================================================
# NUMBER HELPERS
# =========================================================

def safe_float(value):

    try:

        if value is None:
            return None

        value = float(value)

        if not math.isfinite(value):
            return None

        if value <= 0:
            return None

        return value

    except Exception:

        return None


def round_or_none(value, decimals=2):

    if value is None:
        return None

    try:

        return round(
            float(value),
            decimals,
        )

    except Exception:

        return None


# =========================================================
# DATE HELPERS
# =========================================================

def subtract_months(date_obj, months):

    year = date_obj.year
    month = date_obj.month - months

    while month <= 0:
        month += 12
        year -= 1

    day = min(
        date_obj.day,
        calendar.monthrange(
            year,
            month,
        )[1],
    )

    return date_obj.replace(
        year=year,
        month=month,
        day=day,
    )


def get_latest_stock_date(stocks):

    dates = []

    for row in stocks:

        value = row.get(
            "priceDate"
        )

        if not value:
            continue

        try:

            d = datetime.strptime(
                value,
                "%Y-%m-%d",
            ).date()

            dates.append(d)

        except Exception:

            pass

    if dates:

        return max(dates)

    return (
        datetime.now(timezone.utc)
        .date()
    )


# =========================================================
# NSE UDIF BHAVCOPY URL
# =========================================================

def bhavcopy_url(date_obj):

    yyyymmdd = date_obj.strftime(
        "%Y%m%d"
    )

    return (
        "https://nsearchives.nseindia.com/"
        "content/cm/"
        f"BhavCopy_NSE_CM_0_0_0_{yyyymmdd}_F_0000.csv.zip"
    )


# =========================================================
# DOWNLOAD + PARSE BHAVCOPY
# =========================================================

def download_bhavcopy(date_obj):

    url = bhavcopy_url(
        date_obj
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=45,
    )

    response.raise_for_status()

    with zipfile.ZipFile(
        io.BytesIO(
            response.content
        )
    ) as z:

        names = z.namelist()

        if not names:

            raise RuntimeError(
                "Empty NSE bhavcopy ZIP"
            )

        csv_name = names[0]

        text = (
            z.read(csv_name)
            .decode(
                "utf-8-sig",
                errors="ignore",
            )
        )

    rows = list(
        csv.DictReader(
            io.StringIO(text)
        )
    )

    prices = {}

    symbol_only = {}

    for record in rows:

        clean = {

            str(k)
            .strip()
            .upper():
                str(v)
                .strip()

            for k, v
            in record.items()
        }

        symbol = (
            clean.get(
                "TCKRSYMB"
            )
            or
            clean.get(
                "SYMBOL"
            )
            or
            ""
        ).strip()

        series = (
            clean.get(
                "SCTYSRS"
            )
            or
            clean.get(
                "SERIES"
            )
            or
            ""
        ).strip()

        close = (
            clean.get(
                "CLSPRIC"
            )
            or
            clean.get(
                "CLOSE"
            )
            or
            clean.get(
                "CLOSE_PRICE"
            )
        )

        close = safe_float(
            close
        )

        if (
            not symbol
            or
            close is None
        ):

            continue

        key = (
            symbol.upper(),
            series.upper(),
        )

        prices[
            key
        ] = close

        # Symbol-only fallback.
        #
        # Prefer EQ series if same symbol
        # appears in multiple series.
        sym = symbol.upper()

        if (
            sym not in symbol_only
            or
            series.upper() == "EQ"
        ):

            symbol_only[
                sym
            ] = close

    return {

        "date":
            date_obj,

        "url":
            url,

        "prices":
            prices,

        "symbolOnly":
            symbol_only,

        "count":
            len(prices),
    }


# =========================================================
# FIND NEAREST AVAILABLE BHAVCOPY
# =========================================================

def load_nearest_bhavcopy(target_date):

    last_error = None

    for back in range(
        0,
        MAX_LOOKBACK_DAYS + 1,
    ):

        d = (
            target_date
            -
            timedelta(
                days=back
            )
        )

        # Saturday / Sunday
        if d.weekday() >= 5:
            continue

        try:

            result = download_bhavcopy(
                d
            )

            print(
                f"Loaded NSE bhavcopy "
                f"{d.isoformat()} "
                f"({result['count']} securities)"
            )

            return result

        except Exception as exc:

            last_error = exc

            print(
                f"Bhavcopy unavailable "
                f"{d.isoformat()}: {exc}"
            )

    raise RuntimeError(
        f"No NSE bhavcopy available near "
        f"{target_date}. "
        f"Last error: {last_error}"
    )


# =========================================================
# STOCK PRICE LOOKUP
# =========================================================

def lookup_price(
    stock,
    bhavcopy,
):

    symbol = str(
        stock.get(
            "symbol"
        )
        or ""
    ).strip().upper()

    series = str(
        stock.get(
            "series"
        )
        or ""
    ).strip().upper()

    if not symbol:
        return None

    prices = bhavcopy[
        "prices"
    ]

    symbol_only = bhavcopy[
        "symbolOnly"
    ]

    # Exact symbol + series
    exact = prices.get(
        (
            symbol,
            series,
        )
    )

    if exact is not None:
        return exact

    # EQ fallback
    eq = prices.get(
        (
            symbol,
            "EQ",
        )
    )

    if eq is not None:
        return eq

    # Symbol-only fallback
    return symbol_only.get(
        symbol
    )


# =========================================================
# RETURN CALCULATION
# =========================================================

def calculate_return(
    current_price,
    old_price,
):

    current_price = safe_float(
        current_price
    )

    old_price = safe_float(
        old_price
    )

    if (
        current_price is None
        or
        old_price is None
    ):

        return None

    return (
        (
            current_price
            /
            old_price
        )
        -
        1
    ) * 100


# =========================================================
# RAW RS SCORE
# =========================================================

def calculate_raw_rs(
    return_3m,
    return_6m,
    return_9m,
    return_12m,
):

    values = [
        return_3m,
        return_6m,
        return_9m,
        return_12m,
    ]

    if any(
        value is None
        for value in values
    ):

        return None

    return (
        WEIGHT_3M
        *
        return_3m

        +
        WEIGHT_6M
        *
        return_6m

        +
        WEIGHT_9M
        *
        return_9m

        +
        WEIGHT_12M
        *
        return_12m
    )


# =========================================================
# PERCENTILE RATING 1-99
# =========================================================

def assign_rs_ratings(
    stocks,
):

    eligible = []

    for index, row in enumerate(
        stocks
    ):

        raw = row.get(
            "rsRawScore"
        )

        if raw is None:
            continue

        try:

            raw = float(raw)

        except Exception:

            continue

        if not math.isfinite(raw):
            continue

        eligible.append(
            (
                raw,
                index,
            )
        )

    eligible.sort(
        key=lambda x: x[0]
    )

    total = len(
        eligible
    )

    if total == 0:
        return 0

    if total == 1:

        stocks[
            eligible[0][1]
        ][
            "rsRating"
        ] = 99

        return 1

    # -----------------------------------------------------
    # TIE-AWARE AVERAGE RANK
    # -----------------------------------------------------

    position = 0

    while position < total:

        start = position

        raw_score = eligible[
            position
        ][0]

        while (
            position + 1
            <
            total
            and
            eligible[
                position + 1
            ][0]
            ==
            raw_score
        ):

            position += 1

        end = position

        average_rank = (
            start
            +
            end
        ) / 2

        percentile = (
            average_rank
            /
            (
                total - 1
            )
        )

        rating = (
            1
            +
            round(
                percentile
                *
                98
            )
        )

        rating = max(
            1,
            min(
                99,
                rating,
            ),
        )

        for i in range(
            start,
            end + 1,
        ):

            stock_index = (
                eligible[
                    i
                ][1]
            )

            stocks[
                stock_index
            ][
                "rsRating"
            ] = rating

        position += 1

    return total


# =========================================================
# RS LABEL
# =========================================================

def rs_label(rating):

    if rating is None:
        return "Pending"

    if rating >= 90:
        return "Elite"

    if rating >= 80:
        return "Leader"

    if rating >= 70:
        return "Strong"

    if rating >= 50:
        return "Average"

    if rating >= 30:
        return "Weak"

    return "Very Weak"


# =========================================================
# MAIN
# =========================================================

def main():

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

    if not stocks:

        raise RuntimeError(
            "stocks.json is empty"
        )

    print(
        "=============================================="
    )

    print(
        "BUILD RELATIVE STRENGTH RATING"
    )

    print(
        "=============================================="
    )

    latest_date = (
        get_latest_stock_date(
            stocks
        )
    )

    print(
        "Latest market date:",
        latest_date,
    )

    target_3m = subtract_months(
        latest_date,
        3,
    )

    target_6m = subtract_months(
        latest_date,
        6,
    )

    target_9m = subtract_months(
        latest_date,
        9,
    )

    target_12m = subtract_months(
        latest_date,
        12,
    )

    print({
        "latest":
            latest_date.isoformat(),

        "3M":
            target_3m.isoformat(),

        "6M":
            target_6m.isoformat(),

        "9M":
            target_9m.isoformat(),

        "12M":
            target_12m.isoformat(),
    })

    print()

    # =====================================================
    # LOAD ONLY FOUR HISTORICAL BULK FILES
    #
    # Current price already exists in stocks.json from
    # official NSE UDiFF EOD bhavcopy.
    # =====================================================

    bhav_3m = load_nearest_bhavcopy(
        target_3m
    )

    bhav_6m = load_nearest_bhavcopy(
        target_6m
    )

    bhav_9m = load_nearest_bhavcopy(
        target_9m
    )

    bhav_12m = load_nearest_bhavcopy(
        target_12m
    )

    print()

    stats = {

        "stocks":
            len(stocks),

        "eligible":
            0,

        "missingCurrentPrice":
            0,

        "missing3M":
            0,

        "missing6M":
            0,

        "missing9M":
            0,

        "missing12M":
            0,
    }

    # =====================================================
    # CALCULATE RETURNS + RAW RS
    # =====================================================

    for row in stocks:

        # Clear previous values first
        row[
            "rsRating"
        ] = None

        row[
            "rsRawScore"
        ] = None

        row[
            "rsReturn3M"
        ] = None

        row[
            "rsReturn6M"
        ] = None

        row[
            "rsReturn9M"
        ] = None

        row[
            "rsReturn12M"
        ] = None

        row[
            "rsLabel"
        ] = "Pending"

        current_price = safe_float(
            row.get(
                "price"
            )
        )

        if current_price is None:

            stats[
                "missingCurrentPrice"
            ] += 1

            row[
                "rsStatus"
            ] = "MISSING_CURRENT_PRICE"

            continue

        price_3m = lookup_price(
            row,
            bhav_3m,
        )

        price_6m = lookup_price(
            row,
            bhav_6m,
        )

        price_9m = lookup_price(
            row,
            bhav_9m,
        )

        price_12m = lookup_price(
            row,
            bhav_12m,
        )

        if price_3m is None:
            stats[
                "missing3M"
            ] += 1

        if price_6m is None:
            stats[
                "missing6M"
            ] += 1

        if price_9m is None:
            stats[
                "missing9M"
            ] += 1

        if price_12m is None:
            stats[
                "missing12M"
            ] += 1

        return_3m = calculate_return(
            current_price,
            price_3m,
        )

        return_6m = calculate_return(
            current_price,
            price_6m,
        )

        return_9m = calculate_return(
            current_price,
            price_9m,
        )

        return_12m = calculate_return(
            current_price,
            price_12m,
        )

        raw_rs = calculate_raw_rs(
            return_3m,
            return_6m,
            return_9m,
            return_12m,
        )

        row[
            "rsReturn3M"
        ] = round_or_none(
            return_3m
        )

        row[
            "rsReturn6M"
        ] = round_or_none(
            return_6m
        )

        row[
            "rsReturn9M"
        ] = round_or_none(
            return_9m
        )

        row[
            "rsReturn12M"
        ] = round_or_none(
            return_12m
        )

        row[
            "rsRawScore"
        ] = round_or_none(
            raw_rs,
            4,
        )

        if raw_rs is not None:

            row[
                "rsStatus"
            ] = "READY"

            stats[
                "eligible"
            ] += 1

        else:

            row[
                "rsStatus"
            ] = "INSUFFICIENT_HISTORY"

    # =====================================================
    # CONVERT RAW SCORES TO 1-99 RELATIVE RANK
    # =====================================================

    rated_count = assign_rs_ratings(
        stocks
    )

    # =====================================================
    # LABELS + METADATA
    # =====================================================

    for row in stocks:

        rating = row.get(
            "rsRating"
        )

        row[
            "rsLabel"
        ] = rs_label(
            rating
        )

        row[
            "rsDate"
        ] = (
            latest_date
            .isoformat()
        )

        row[
            "rsMethod"
        ] = (
            "MarketSmith-style 12M relative "
            "price strength percentile; "
            "40% 3M + 20% 6M + "
            "20% 9M + 20% 12M"
        )

        row[
            "rsSource"
        ] = (
            "Official NSE UDiFF EOD bhavcopy"
        )

        row[
            "rsBenchmarkUniverse"
        ] = (
            "NSE Equity + NSE SME dashboard universe"
        )

    # =====================================================
    # SAVE
    # =====================================================

    save_json(
        STOCKS_PATH,
        stocks,
    )

    # =====================================================
    # SUMMARY
    # =====================================================

    coverage = 0

    if stocks:

        coverage = (
            rated_count
            /
            len(stocks)
            *
            100
        )

    distribution = {

        "RS90-99":
            0,

        "RS80-89":
            0,

        "RS70-79":
            0,

        "RS50-69":
            0,

        "RS30-49":
            0,

        "RS1-29":
            0,

        "Pending":
            0,
    }

    for row in stocks:

        rating = row.get(
            "rsRating"
        )

        if rating is None:

            distribution[
                "Pending"
            ] += 1

        elif rating >= 90:

            distribution[
                "RS90-99"
            ] += 1

        elif rating >= 80:

            distribution[
                "RS80-89"
            ] += 1

        elif rating >= 70:

            distribution[
                "RS70-79"
            ] += 1

        elif rating >= 50:

            distribution[
                "RS50-69"
            ] += 1

        elif rating >= 30:

            distribution[
                "RS30-49"
            ] += 1

        else:

            distribution[
                "RS1-29"
            ] += 1

    stats[
        "rated"
    ] = rated_count

    stats[
        "coveragePct"
    ] = round(
        coverage,
        2,
    )

    stats[
        "distribution"
    ] = distribution

    stats[
        "historyDates"
    ] = {

        "3M":
            bhav_3m[
                "date"
            ].isoformat(),

        "6M":
            bhav_6m[
                "date"
            ].isoformat(),

        "9M":
            bhav_9m[
                "date"
            ].isoformat(),

        "12M":
            bhav_12m[
                "date"
            ].isoformat(),
    }

    print(
        "=============================================="
    )

    print(
        "RS RATING COMPLETE"
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
        "RS SCALE:"
    )

    print(
        "90-99 = Elite"
    )

    print(
        "80-89 = Leader"
    )

    print(
        "70-79 = Strong"
    )

    print(
        "50-69 = Average"
    )

    print(
        "30-49 = Weak"
    )

    print(
        "1-29 = Very Weak"
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "This is a MarketSmith-style "
        "relative-strength model."
    )

    print(
        "MarketSmith's exact proprietary "
        "formula is not claimed or copied."
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
