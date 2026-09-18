import calendar
import csv
import io
import json
import math
import time
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

MAX_LOOKBACK_DAYS = 15
REQUEST_TIMEOUT = 45
MAX_RETRIES = 3

WEIGHT_3M = 0.40
WEIGHT_6M = 0.20
WEIGHT_9M = 0.20
WEIGHT_12M = 0.20


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com/all-reports",
}


# =========================================================
# SESSION
# =========================================================

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# =========================================================
# JSON
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
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


# =========================================================
# NUMBERS
# =========================================================

def safe_float(value):
    try:
        if value is None:
            return None

        if isinstance(value, str):
            value = (
                value
                .replace(",", "")
                .replace("%", "")
                .strip()
            )

        if value == "":
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
# DATE
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
        value = row.get("priceDate")

        if not value:
            continue

        try:
            dates.append(
                datetime.strptime(
                    str(value)[:10],
                    "%Y-%m-%d",
                ).date()
            )
        except Exception:
            pass

    if dates:
        return max(dates)

    return datetime.now(
        timezone.utc
    ).date()


# =========================================================
# NSE URL
# =========================================================

def bhavcopy_url(date_obj):
    yyyymmdd = date_obj.strftime("%Y%m%d")

    return (
        "https://nsearchives.nseindia.com/"
        "content/cm/"
        f"BhavCopy_NSE_CM_0_0_0_{yyyymmdd}_F_0000.csv.zip"
    )


# =========================================================
# NSE SESSION WARMUP
# =========================================================

def warmup_nse_session():
    urls = [
        "https://www.nseindia.com/",
        "https://www.nseindia.com/all-reports",
    ]

    for url in urls:
        try:
            response = SESSION.get(
                url,
                timeout=20,
            )

            print(
                "NSE warmup:",
                url,
                response.status_code,
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
# PARSE BHAVCOPY ZIP
# =========================================================

def parse_bhavcopy_zip(content, date_obj, url):
    if not content:
        raise RuntimeError(
            "Empty NSE response"
        )

    if len(content) < 500:
        raise RuntimeError(
            f"NSE response too small: {len(content)} bytes"
        )

    try:
        archive = zipfile.ZipFile(
            io.BytesIO(content)
        )
    except Exception as exc:
        raise RuntimeError(
            f"Invalid NSE ZIP: {exc}"
        )

    with archive:
        names = archive.namelist()

        csv_names = [
            name
            for name in names
            if name.lower().endswith(".csv")
        ]

        if not csv_names:
            raise RuntimeError(
                "CSV not found in NSE ZIP"
            )

        text = (
            archive
            .read(csv_names[0])
            .decode(
                "utf-8-sig",
                errors="ignore",
            )
        )

    reader = csv.DictReader(
        io.StringIO(text)
    )

    prices = {}
    symbol_only = {}

    for record in reader:
        clean = {
            str(k).strip().upper():
            str(v).strip()
            for k, v in record.items()
        }

        symbol = (
            clean.get("TCKRSYMB")
            or clean.get("SYMBOL")
            or ""
        ).strip().upper()

        series = (
            clean.get("SCTYSRS")
            or clean.get("SERIES")
            or ""
        ).strip().upper()

        close = (
            clean.get("CLSPRIC")
            or clean.get("CLOSE")
            or clean.get("CLOSE_PRICE")
        )

        close = safe_float(close)

        if not symbol or close is None:
            continue

        prices[
            (
                symbol,
                series,
            )
        ] = close

        existing = symbol_only.get(
            symbol
        )

        if (
            existing is None
            or series == "EQ"
        ):
            symbol_only[
                symbol
            ] = close

    if not prices:
        raise RuntimeError(
            "No valid securities found in NSE bhavcopy"
        )

    return {
        "date": date_obj,
        "url": url,
        "prices": prices,
        "symbolOnly": symbol_only,
        "count": len(prices),
    }


# =========================================================
# DOWNLOAD BHAVCOPY
# =========================================================

def download_bhavcopy(date_obj):
    url = bhavcopy_url(date_obj)

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        try:
            response = SESSION.get(
                url,
                headers={
                    **HEADERS,
                    "Accept": (
                        "application/zip,"
                        "application/octet-stream,"
                        "*/*"
                    ),
                    "Referer":
                        "https://www.nseindia.com/all-reports",
                },
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )

            status = response.status_code

            if status == 200:
                return parse_bhavcopy_zip(
                    response.content,
                    date_obj,
                    url,
                )

            last_error = RuntimeError(
                f"HTTP {status}"
            )

            print(
                f"NSE archive attempt "
                f"{attempt}/{MAX_RETRIES} "
                f"{date_obj}: HTTP {status}"
            )

            if status in (
                401,
                403,
                429,
            ):
                warmup_nse_session()

            time.sleep(
                min(
                    2 * attempt,
                    6,
                )
            )

        except Exception as exc:
            last_error = exc

            print(
                f"NSE archive attempt "
                f"{attempt}/{MAX_RETRIES} "
                f"{date_obj}: {exc}"
            )

            time.sleep(
                min(
                    2 * attempt,
                    6,
                )
            )

    raise RuntimeError(
        f"NSE bhavcopy download failed "
        f"for {date_obj}: {last_error}"
    )


# =========================================================
# CACHE
# =========================================================

BHAVCOPY_CACHE = {}


def load_exact_bhavcopy_cached(date_obj):
    key = date_obj.isoformat()

    if key in BHAVCOPY_CACHE:
        cached = BHAVCOPY_CACHE[key]

        if isinstance(
            cached,
            Exception,
        ):
            raise cached

        return cached

    try:
        result = download_bhavcopy(
            date_obj
        )

        BHAVCOPY_CACHE[
            key
        ] = result

        return result

    except Exception as exc:
        BHAVCOPY_CACHE[
            key
        ] = exc

        raise


# =========================================================
# FIND NEAREST BHAVCOPY
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
            timedelta(days=back)
        )

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
                f"{d.isoformat()}: "
                f"{exc}"
            )

    raise RuntimeError(
        f"No NSE bhavcopy available near "
        f"{target_date}. "
        f"Last error: {last_error}"
    )


# =========================================================
# PRICE LOOKUP
# =========================================================

def lookup_price(stock, bhavcopy):
    symbol = str(
        stock.get("symbol")
        or ""
    ).strip().upper()

    series = str(
        stock.get("series")
        or ""
    ).strip().upper()

    if not symbol:
        return None

    prices = bhavcopy["prices"]
    symbol_only = bhavcopy[
        "symbolOnly"
    ]

    exact = prices.get(
        (
            symbol,
            series,
        )
    )

    if exact is not None:
        return exact

    eq = prices.get(
        (
            symbol,
            "EQ",
        )
    )

    if eq is not None:
        return eq

    return symbol_only.get(
        symbol
    )


# =========================================================
# RETURN
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
        or old_price is None
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
# RAW RS
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
        WEIGHT_3M * return_3m
        +
        WEIGHT_6M * return_6m
        +
        WEIGHT_9M * return_9m
        +
        WEIGHT_12M * return_12m
    )


# =========================================================
# PERCENTILE
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
        raw = safe_numeric(
            row.get(raw_field)
        )

        if raw is None:
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

    total = len(eligible)

    if total == 0:
        return 0

    if total == 1:
        records[
            eligible[0][1]
        ][rating_field] = 99

        return 1

    position = 0

    while position < total:
        start = position
        raw_score = eligible[
            position
        ][0]

        while (
            position + 1 < total
            and eligible[
                position + 1
            ][0] == raw_score
        ):
            position += 1

        end = position

        average_rank = (
            start + end
        ) / 2

        percentile = (
            average_rank
            /
            (total - 1)
        )

        rating = (
            1
            +
            round(
                percentile * 98
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
                eligible[i][1]
            )

            records[
                stock_index
            ][rating_field] = rating

        position += 1

    return total


def assign_rs_ratings(stocks):
    return assign_percentile_ratings(
        stocks,
        "rsRawScore",
        "rsRating",
    )


# =========================================================
# LABEL
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
# PRESERVE EXISTING RS
# =========================================================

RS_FIELDS = [
    "rsRating",
    "rsRawScore",
    "rsReturn3M",
    "rsReturn6M",
    "rsReturn9M",
    "rsReturn12M",
    "rsLabel",
    "rsStatus",
    "rsDate",
    "rsMethod",
    "rsSource",
    "rsBenchmarkUniverse",
]


def snapshot_existing_rs(stocks):
    snapshots = []

    for row in stocks:
        snapshots.append({
            field: row.get(field)
            for field in RS_FIELDS
        })

    return snapshots


def restore_existing_rs(
    stocks,
    snapshots,
):
    for row, snapshot in zip(
        stocks,
        snapshots,
    ):
        for field, value in (
            snapshot.items()
        ):
            if value is None:
                row.pop(
                    field,
                    None,
                )
            else:
                row[
                    field
                ] = value


# =========================================================
# CALCULATE CURRENT RS
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
        "stocks": len(stocks),
        "eligible": 0,
        "missingCurrentPrice": 0,
        "missing3M": 0,
        "missing6M": 0,
        "missing9M": 0,
        "missing12M": 0,
    }

    for row in stocks:
        row["rsRating"] = None
        row["rsRawScore"] = None
        row["rsReturn3M"] = None
        row["rsReturn6M"] = None
        row["rsReturn9M"] = None
        row["rsReturn12M"] = None
        row["rsLabel"] = "Pending"

        current_price = safe_float(
            row.get("price")
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
            stats["missing3M"] += 1

        if price_6m is None:
            stats["missing6M"] += 1

        if price_9m is None:
            stats["missing9M"] += 1

        if price_12m is None:
            stats["missing12M"] += 1

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
        ] = latest_date.isoformat()

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

        # Remove old RS Improving fields.
        for field in [
            "rsRating1MAgo",
            "rsRating2WAgo",
            "rsRating1WAgo",
            "rsImprovement",
            "rsImproving",
            "rsImprovingStatus",
            "rsImprovingMethod",
            "rsImprovingSource",
        ]:
            row.pop(
                field,
                None,
            )

    stats["rated"] = rated_count

    return {
        "stats": stats,
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
# DISTRIBUTION
# =========================================================

def build_distribution(stocks):
    distribution = {
        "RS90-99": 0,
        "RS80-89": 0,
        "RS70-79": 0,
        "RS50-69": 0,
        "RS30-49": 0,
        "RS1-29": 0,
        "Pending": 0,
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
# MAIN
# =========================================================

def main():
    stocks = load_json(
        STOCKS_PATH,
        [],
    )

    if (
        not isinstance(
            stocks,
            list,
        )
        or not stocks
    ):
        raise RuntimeError(
            "stocks.json is missing or empty"
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

    print()

    # Save existing valid RS before any download.
    existing_rs = (
        snapshot_existing_rs(
            stocks
        )
    )

    warmup_nse_session()

    try:
        current_result = (
            calculate_current_rs(
                stocks,
                latest_date,
            )
        )

        rs_update_status = (
            "UPDATED"
        )

        save_json(
            STOCKS_PATH,
            stocks,
        )

    except Exception as exc:
        # -------------------------------------------------
        # IMPORTANT:
        # Temporary NSE 403/429/server failure must NOT
        # erase the last valid RS data and must NOT stop
        # the complete dashboard workflow.
        # -------------------------------------------------

        print()
        print(
            "WARNING: RS update unavailable."
        )

        print(
            "Reason:",
            exc,
        )

        print(
            "Preserving previous valid RS data."
        )

        restore_existing_rs(
            stocks,
            existing_rs,
        )

        save_json(
            STOCKS_PATH,
            stocks,
        )

        current_result = {
            "stats": {
                "stocks":
                    len(stocks),
                "eligible":
                    sum(
                        1
                        for row in stocks
                        if row.get(
                            "rsRating"
                        )
                        is not None
                    ),
                "rated":
                    sum(
                        1
                        for row in stocks
                        if row.get(
                            "rsRating"
                        )
                        is not None
                    ),
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
            },
            "historyDates": {},
        }

        rs_update_status = (
            "PRESERVED_PREVIOUS"
        )

    current_stats = (
        current_result.get(
            "stats",
            {},
        )
    )

    rated_count = (
        current_stats.get(
            "rated",
            0,
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

    stats = {
        "stocks":
            len(stocks),

        "eligible":
            current_stats.get(
                "eligible",
                0,
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
                0,
            ),

        "missing3M":
            current_stats.get(
                "missing3M",
                0,
            ),

        "missing6M":
            current_stats.get(
                "missing6M",
                0,
            ),

        "missing9M":
            current_stats.get(
                "missing9M",
                0,
            ),

        "missing12M":
            current_stats.get(
                "missing12M",
                0,
            ),

        "distribution":
            distribution,

        "historyDates":
            current_result.get(
                "historyDates",
                {},
            ),

        "updateStatus":
            rs_update_status,
    }

    print()

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
        "RS Rating uses official NSE UDiFF EOD bhavcopy."
    )

    print(
        "Current RS is based on "
        "40% 3M + 20% 6M + "
        "20% 9M + 20% 12M returns."
    )

    print(
        "Rating is converted to a "
        "cross-sectional percentile from 1 to 99."
    )

    print(
        "Temporary NSE archive failure preserves "
        "the previous valid RS instead of deleting it."
    )

    print(
        "MarketSmith's exact proprietary "
        "formula is not claimed or copied."
    )

    print(
        "RS Improving and historical "
        "RS snapshot logic are removed."
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
