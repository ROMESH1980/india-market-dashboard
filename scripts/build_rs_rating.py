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


# Search backward around any target date.
MAX_LOOKBACK_DAYS = 10


# MarketSmith-style recent-performance weighting.
WEIGHT_3M = 0.40
WEIGHT_6M = 0.20
WEIGHT_9M = 0.20
WEIGHT_12M = 0.20


# =========================================================
# RS IMPROVING SETTINGS
# =========================================================

# Historical anchor offsets.
RS_1W_DAYS = 7
RS_2W_DAYS = 14
RS_1M_MONTHS = 1


# Final RS Improving conditions.
RS_IMPROVING_MAX_1M_AGO = 60
RS_IMPROVING_MIN_CURRENT = 70
RS_IMPROVING_MIN_GAIN = 20


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


def safe_numeric(value):

    try:

        if value is None:
            return None

        value = float(value)

        if not math.isfinite(value):
            return None

        return value

    except Exception:

        return None


def round_or_none(
    value,
    decimals=2,
):

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

def subtract_months(
    date_obj,
    months,
):

    year = date_obj.year

    month = (
        date_obj.month
        -
        months
    )

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
        datetime.now(
            timezone.utc
        )
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
            z.read(
                csv_name
            )
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

        # -------------------------------------------------
        # SYMBOL-ONLY FALLBACK
        #
        # Prefer EQ series when same symbol appears
        # in multiple series.
        # -------------------------------------------------

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
# BHAVCOPY CACHE
# =========================================================

BHAVCOPY_CACHE = {}


def load_exact_bhavcopy_cached(
    date_obj,
):

    key = date_obj.isoformat()

    if key in BHAVCOPY_CACHE:

        return BHAVCOPY_CACHE[
            key
        ]

    result = download_bhavcopy(
        date_obj
    )

    BHAVCOPY_CACHE[
        key
    ] = result

    return result


# =========================================================
# FIND NEAREST AVAILABLE BHAVCOPY
# =========================================================

def load_nearest_bhavcopy(
    target_date,
):

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

            result = (
                load_exact_bhavcopy_cached(
                    d
                )
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

    # Exact symbol + series.
    exact = prices.get(
        (
            symbol,
            series,
        )
    )

    if exact is not None:
        return exact

    # EQ fallback.
    eq = prices.get(
        (
            symbol,
            "EQ",
        )
    )

    if eq is not None:
        return eq

    # Symbol-only fallback.
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
# GENERIC PERCENTILE RATING
# =========================================================

def assign_percentile_ratings(
    records,
    raw_field,
    rating_field,
):

    eligible = []

    for index, row in enumerate(
        records
    ):

        raw = row.get(
            raw_field
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

        records[
            eligible[0][1]
        ][
            rating_field
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

            records[
                stock_index
            ][
                rating_field
            ] = rating

        position += 1

    return total


# =========================================================
# CURRENT RS WRAPPER
# =========================================================

def assign_rs_ratings(
    stocks,
):

    return assign_percentile_ratings(
        stocks,
        "rsRawScore",
        "rsRating",
    )


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
# HISTORICAL ANCHOR DATE HELPERS
# =========================================================

def build_anchor_dates(
    latest_date,
):

    return {

        "1MAgo":
            subtract_months(
                latest_date,
                RS_1M_MONTHS,
            ),

        "2WAgo":
            latest_date
            -
            timedelta(
                days=RS_2W_DAYS
            ),

        "1WAgo":
            latest_date
            -
            timedelta(
                days=RS_1W_DAYS
            ),

        "Current":
            latest_date,
    }


# =========================================================
# LOAD RS BHAVCOPIES FOR ONE ANCHOR
# =========================================================

def load_rs_bhavcopies_for_anchor(
    anchor_date,
):

    target_3m = subtract_months(
        anchor_date,
        3,
    )

    target_6m = subtract_months(
        anchor_date,
        6,
    )

    target_9m = subtract_months(
        anchor_date,
        9,
    )

    target_12m = subtract_months(
        anchor_date,
        12,
    )


    print(
        "----------------------------------------------"
    )

    print(
        "Loading RS anchor:",
        anchor_date.isoformat(),
    )

    print({
        "anchor":
            anchor_date.isoformat(),

        "3M":
            target_3m.isoformat(),

        "6M":
            target_6m.isoformat(),

        "9M":
            target_9m.isoformat(),

        "12M":
            target_12m.isoformat(),
    })


    anchor_bhav = load_nearest_bhavcopy(
        anchor_date
    )

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


    return {

        "anchor":
            anchor_bhav,

        "3M":
            bhav_3m,

        "6M":
            bhav_6m,

        "9M":
            bhav_9m,

        "12M":
            bhav_12m,
    }


# =========================================================
# CALCULATE ONE HISTORICAL RS SNAPSHOT
# =========================================================

def calculate_rs_snapshot(
    stocks,
    anchor_name,
    bundle,
):

    raw_field = (
        f"_rsRaw_{anchor_name}"
    )

    rating_field = (
        f"_rsRating_{anchor_name}"
    )


    stats = {

        "anchor":
            anchor_name,

        "anchorDate":
            bundle[
                "anchor"
            ][
                "date"
            ].isoformat(),

        "eligible":
            0,

        "missingAnchorPrice":
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


    for row in stocks:

        row[
            raw_field
        ] = None

        row[
            rating_field
        ] = None


        anchor_price = lookup_price(
            row,
            bundle[
                "anchor"
            ],
        )


        if anchor_price is None:

            stats[
                "missingAnchorPrice"
            ] += 1

            continue


        price_3m = lookup_price(
            row,
            bundle[
                "3M"
            ],
        )

        price_6m = lookup_price(
            row,
            bundle[
                "6M"
            ],
        )

        price_9m = lookup_price(
            row,
            bundle[
                "9M"
            ],
        )

        price_12m = lookup_price(
            row,
            bundle[
                "12M"
            ],
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
            anchor_price,
            price_3m,
        )

        return_6m = calculate_return(
            anchor_price,
            price_6m,
        )

        return_9m = calculate_return(
            anchor_price,
            price_9m,
        )

        return_12m = calculate_return(
            anchor_price,
            price_12m,
        )


        raw_rs = calculate_raw_rs(
            return_3m,
            return_6m,
            return_9m,
            return_12m,
        )


        row[
            raw_field
        ] = round_or_none(
            raw_rs,
            4,
        )


        if raw_rs is not None:

            stats[
                "eligible"
            ] += 1


    rated = assign_percentile_ratings(
        stocks,
        raw_field,
        rating_field,
    )


    stats[
        "rated"
    ] = rated


    return {

        "rawField":
            raw_field,

        "ratingField":
            rating_field,

        "stats":
            stats,
    }
    # =========================================================
# RS IMPROVING LOGIC
# =========================================================

def calculate_rs_improving_fields(
    stocks,
):

    improving_count = 0

    history_ready_count = 0


    for row in stocks:

        rs_1m = safe_numeric(
            row.get(
                "rsRating1MAgo"
            )
        )

        rs_2w = safe_numeric(
            row.get(
                "rsRating2WAgo"
            )
        )

        rs_1w = safe_numeric(
            row.get(
                "rsRating1WAgo"
            )
        )

        current_rs = safe_numeric(
            row.get(
                "rsRating"
            )
        )


        row[
            "rsImprovement"
        ] = None

        row[
            "rsImproving"
        ] = False


        if (
            rs_1m is None
            or
            rs_2w is None
            or
            rs_1w is None
            or
            current_rs is None
        ):

            row[
                "rsImprovingStatus"
            ] = "INSUFFICIENT_HISTORY"

            continue


        history_ready_count += 1


        improvement = (
            current_rs
            -
            rs_1m
        )


        row[
            "rsImprovement"
        ] = round(
            improvement,
            2,
        )


        improving = (
            rs_1m
            <=
            RS_IMPROVING_MAX_1M_AGO

            and

            rs_2w
            >
            rs_1m

            and

            rs_1w
            >
            rs_2w

            and

            current_rs
            >
            rs_1w

            and

            current_rs
            >=
            RS_IMPROVING_MIN_CURRENT

            and

            improvement
            >=
            RS_IMPROVING_MIN_GAIN
        )


        row[
            "rsImproving"
        ] = bool(
            improving
        )


        if improving:

            row[
                "rsImprovingStatus"
            ] = "YES"

            improving_count += 1

        else:

            row[
                "rsImprovingStatus"
            ] = "NO"


    return {

        "historyReady":
            history_ready_count,

        "improvingCount":
            improving_count,
    }


# =========================================================
# COPY SNAPSHOT RATINGS TO FINAL PUBLIC FIELDS
# =========================================================

def map_snapshot_ratings_to_public_fields(
    stocks,
    snapshot_results,
):

    mapping = {

        "1MAgo":
            "rsRating1MAgo",

        "2WAgo":
            "rsRating2WAgo",

        "1WAgo":
            "rsRating1WAgo",
    }


    for anchor_name, public_field in mapping.items():

        snapshot = snapshot_results.get(
            anchor_name,
            {}
        )


        internal_rating_field = snapshot.get(
            "ratingField"
        )


        if not internal_rating_field:

            continue


        for row in stocks:

            rating = row.get(
                internal_rating_field
            )


            row[
                public_field
            ] = (
                int(rating)
                if rating is not None
                else None
            )


# =========================================================
# REMOVE INTERNAL TEMPORARY SNAPSHOT FIELDS
# =========================================================

def cleanup_internal_snapshot_fields(
    stocks,
):

    prefixes = (
        "_rsRaw_",
        "_rsRating_",
    )


    for row in stocks:

        keys_to_delete = []

        for key in row.keys():

            if key.startswith(
                prefixes
            ):

                keys_to_delete.append(
                    key
                )


        for key in keys_to_delete:

            row.pop(
                key,
                None
            )


# =========================================================
# CURRENT RS CALCULATION
# =========================================================

def calculate_current_rs(
    stocks,
    latest_date,
):

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


    for row in stocks:

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


    rated_count = assign_rs_ratings(
        stocks
    )


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


    stats[
        "rated"
    ] = rated_count


    return {

        "stats":
            stats,

        "historyDates": {

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
        },
    }


# =========================================================
# DISTRIBUTION HELPER
# =========================================================

def build_distribution(
    stocks,
):

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


    return distribution


# =========================================================
# RS HISTORY DATE METADATA
# =========================================================

def build_rs_history_metadata(
    snapshot_results,
):

    history = {}


    for anchor_name in [
        "1MAgo",
        "2WAgo",
        "1WAgo",
    ]:

        snapshot = snapshot_results.get(
            anchor_name,
            {}
        )


        stats = snapshot.get(
            "stats",
            {}
        )


        history[
            anchor_name
        ] = {

            "anchorDate":
                stats.get(
                    "anchorDate"
                ),

            "rated":
                stats.get(
                    "rated",
                    0
                ),

            "eligible":
                stats.get(
                    "eligible",
                    0
                ),
        }


    return history


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
        "BUILD RELATIVE STRENGTH RATING + RS IMPROVING"
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


    print()


    # =====================================================
    # CURRENT RS
    # =====================================================

    current_result = calculate_current_rs(
        stocks,
        latest_date,
    )


    # =====================================================
    # HISTORICAL RS SNAPSHOTS
    # =====================================================

    anchors = build_anchor_dates(
        latest_date
    )


    snapshot_results = {}


    for anchor_name in [
        "1MAgo",
        "2WAgo",
        "1WAgo",
    ]:

        anchor_date = anchors[
            anchor_name
        ]


        bundle = (
            load_rs_bhavcopies_for_anchor(
                anchor_date
            )
        )


        snapshot_results[
            anchor_name
        ] = (
            calculate_rs_snapshot(
                stocks,
                anchor_name,
                bundle,
            )
        )


    # =====================================================
    # COPY HISTORICAL RATINGS
    # =====================================================

    map_snapshot_ratings_to_public_fields(
        stocks,
        snapshot_results,
    )


    # =====================================================
    # RS IMPROVEMENT + RS IMPROVING
    # =====================================================

    improving_stats = (
        calculate_rs_improving_fields(
            stocks
        )
    )


    # =====================================================
    # CLEAN INTERNAL TEMP FIELDS
    # =====================================================

    cleanup_internal_snapshot_fields(
        stocks
    )
        # =====================================================
    # FINAL METADATA
    # =====================================================

    for row in stocks:

        row[
            "rsImprovingMethod"
        ] = (
            "RS 1M Ago <= 60; "
            "RS 2W Ago > RS 1M Ago; "
            "RS 1W Ago > RS 2W Ago; "
            "Current RS > RS 1W Ago; "
            "Current RS >= 70; "
            "Current RS - RS 1M Ago >= 20"
        )

        row[
            "rsImprovingSource"
        ] = (
            "Official NSE UDiFF EOD bhavcopy; "
            "historical RS independently calculated "
            "at 1M, 2W and 1W anchors"
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

    current_stats = (
        current_result.get(
            "stats",
            {}
        )
    )


    rated_count = (
        current_stats.get(
            "rated",
            0
        )
    )


    coverage = 0


    if stocks:

        coverage = (
            rated_count
            /
            len(stocks)
            *
            100
        )


    distribution = (
        build_distribution(
            stocks
        )
    )


    history_metadata = (
        build_rs_history_metadata(
            snapshot_results
        )
    )


    stats = {

        "stocks":
            len(stocks),

        "eligible":
            current_stats.get(
                "eligible",
                0
            ),

        "rated":
            rated_count,

        "coveragePct":
            round(
                coverage,
                2,
            ),

        "missingCurrentPrice":
            current_stats.get(
                "missingCurrentPrice",
                0
            ),

        "missing3M":
            current_stats.get(
                "missing3M",
                0
            ),

        "missing6M":
            current_stats.get(
                "missing6M",
                0
            ),

        "missing9M":
            current_stats.get(
                "missing9M",
                0
            ),

        "missing12M":
            current_stats.get(
                "missing12M",
                0
            ),

        "distribution":
            distribution,

        "historyDates":
            current_result.get(
                "historyDates",
                {}
            ),

        "rsHistory":
            history_metadata,

        "rsImprovingHistoryReady":
            improving_stats.get(
                "historyReady",
                0
            ),

        "rsImprovingCount":
            improving_stats.get(
                "improvingCount",
                0
            ),

        "rsImprovingConditions": {

            "max1MAgo":
                RS_IMPROVING_MAX_1M_AGO,

            "minCurrent":
                RS_IMPROVING_MIN_CURRENT,

            "minGain":
                RS_IMPROVING_MIN_GAIN,

            "continuousRise":
                True,
        },
    }


    # =====================================================
    # LOG SUMMARY
    # =====================================================

    print()

    print(
        "=============================================="
    )

    print(
        "RS RATING + RS IMPROVING COMPLETE"
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


    # =====================================================
    # RS SCALE
    # =====================================================

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


    # =====================================================
    # RS IMPROVING SCALE
    # =====================================================

    print(
        "RS IMPROVING CONDITION:"
    )


    print(
        "1M Ago <= 60"
    )


    print(
        "2W Ago > 1M Ago"
    )


    print(
        "1W Ago > 2W Ago"
    )


    print(
        "Current RS > 1W Ago"
    )


    print(
        "Current RS >= 70"
    )


    print(
        "Current RS - 1M Ago >= 20"
    )


    print()


    # =====================================================
    # EXAMPLE COUNTS
    # =====================================================

    print(
        "RS Improving history ready:",
        improving_stats.get(
            "historyReady",
            0
        ),
    )


    print(
        "RS Improving stocks:",
        improving_stats.get(
            "improvingCount",
            0
        ),
    )


    print()


    # =====================================================
    # IMPORTANT
    # =====================================================

    print(
        "IMPORTANT:"
    )


    print(
        "Historical RS ratings are independently "
        "calculated at each anchor date."
    )


    print(
        "They are NOT reverse-calculated "
        "from current RS."
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
