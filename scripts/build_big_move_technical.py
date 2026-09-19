import csv
import io
import json
import math
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "data"

STOCKS_PATH = DATA / "stocks.json"

SCANNER_PATH = DATA / "big_move_scanner.json"


# =========================================================
# CONFIG
# =========================================================

# Approx 1 year of trading sessions.
REQUIRED_SESSIONS = 260

# Calendar lookback allows weekends / holidays.
MAX_CALENDAR_LOOKBACK = 390

# Parallel archive downloads.
MAX_WORKERS = 8

REQUEST_TIMEOUT = 35

MIN_PRIOR_MOVE_PCT = 30.0

# Prior peak should normally be followed by at least
# a few sessions of consolidation.
MIN_POST_PEAK_SESSIONS = 5

# Search previous peaks up to ~5 months back.
PEAK_SEARCH_SESSIONS = 105

# Search the move-start low up to ~6 months before peak.
MOVE_START_LOOKBACK = 126

# Base quality windows.
BASE_WINDOW = 10

TURNOVER_AVG_WINDOW = 20


# =========================================================
# HTTP
# =========================================================

HEADERS = {
    "User-Agent":
        "Mozilla/5.0 "
        "(compatible; MY-MARKET-RESEARCH/2.0)",

    "Accept":
        "text/csv,application/zip,*/*",

    "Accept-Language":
        "en-US,en;q=0.9",
}


# =========================================================
# BASIC HELPERS
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

            value = (
                value
                .replace(",", "")
                .replace("%", "")
                .replace("₹", "")
                .replace("x", "")
                .strip()
            )

            if not value:
                return None

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


def round_or_none(
    value,
    decimals=2,
):

    value = safe_float(
        value
    )

    if value is None:
        return None

    return round(
        value,
        decimals,
    )


def mean(values):

    clean = [
        safe_float(x)
        for x in values
    ]

    clean = [
        x
        for x in clean
        if x is not None
    ]

    if not clean:
        return None

    return (
        sum(clean)
        /
        len(clean)
    )


def clamp(
    value,
    low,
    high,
):

    return max(
        low,
        min(
            high,
            value,
        ),
    )


def normalize_symbol(value):

    return str(
        value
        or ""
    ).strip().upper()


def normalize_series(value):

    return str(
        value
        or ""
    ).strip().upper()


# =========================================================
# MARKET DATE
# =========================================================

def detect_market_date(stocks):

    dates = []

    for row in stocks:

        for field in [
            "priceDate",
            "rsDate",
            "marketDate",
        ]:

            value = row.get(
                field
            )

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
        return max(
            dates
        )

    return (
        datetime.now(
            timezone.utc
        )
        .date()
    )


# =========================================================
# NSE UDiFF URL
# =========================================================

def bhavcopy_url(date_obj):

    yyyymmdd = (
        date_obj.strftime(
            "%Y%m%d"
        )
    )

    return (
        "https://nsearchives.nseindia.com/"
        "content/cm/"
        f"BhavCopy_NSE_CM_0_0_0_{yyyymmdd}_F_0000.csv.zip"
    )


# =========================================================
# PARSE UDiFF
# =========================================================

def parse_bhavcopy(
    content,
    date_obj,
    wanted_symbols,
):

    with zipfile.ZipFile(
        io.BytesIO(
            content
        )
    ) as archive:

        names = (
            archive.namelist()
        )

        if not names:

            raise ValueError(
                "Empty ZIP"
            )


        csv_name = None

        for name in names:

            if name.lower().endswith(
                ".csv"
            ):

                csv_name = name

                break


        if csv_name is None:

            raise ValueError(
                "CSV not found in ZIP"
            )


        text = (
            archive
            .read(
                csv_name
            )
            .decode(
                "utf-8-sig",
                errors="ignore",
            )
        )


    reader = csv.DictReader(
        io.StringIO(
            text
        )
    )


    result = {}


    for source_row in reader:

        clean = {

            str(key)
            .strip()
            .upper():

            str(value)
            .strip()

            for (
                key,
                value
            )
            in source_row.items()

        }


        stock_symbol = (
            clean.get(
                "TCKRSYMB"
            )
            or
            clean.get(
                "SYMBOL"
            )
            or
            ""
        ).upper()


        if (
            not stock_symbol
            or
            stock_symbol
            not in wanted_symbols
        ):

            continue


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
        ).upper()


        open_price = safe_float(
            clean.get(
                "OPNPRIC"
            )
            or
            clean.get(
                "OPEN"
            )
            or
            clean.get(
                "OPEN_PRICE"
            )
        )


        high_price = safe_float(
            clean.get(
                "HGHPRIC"
            )
            or
            clean.get(
                "HIGH"
            )
            or
            clean.get(
                "HIGH_PRICE"
            )
        )


        low_price = safe_float(
            clean.get(
                "LWPRIC"
            )
            or
            clean.get(
                "LOW"
            )
            or
            clean.get(
                "LOW_PRICE"
            )
        )


        close_price = safe_float(
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


        volume = safe_float(
            clean.get(
                "TTLTRADGVOL"
            )
            or
            clean.get(
                "TTLTRADGQTY"
            )
            or
            clean.get(
                "TOTTRDQTY"
            )
            or
            clean.get(
                "TOTAL_TRADED_QUANTITY"
            )
        )


        traded_value = safe_float(
            clean.get(
                "TTLTRFVAL"
            )
            or
            clean.get(
                "TOTTRDVAL"
            )
            or
            clean.get(
                "TOTAL_TRADED_VALUE"
            )
        )


        if (
            close_price is None
            or
            close_price <= 0
        ):

            continue


        if (
            open_price is None
            or
            open_price <= 0
        ):

            open_price = (
                close_price
            )


        if (
            high_price is None
            or
            high_price <= 0
        ):

            high_price = (
                max(
                    open_price,
                    close_price,
                )
            )


        if (
            low_price is None
            or
            low_price <= 0
        ):

            low_price = (
                min(
                    open_price,
                    close_price,
                )
            )


        if (
            traded_value is None
            and
            volume is not None
        ):

            traded_value = (
                close_price
                *
                volume
            )


        record = {

            "date":
                date_obj.isoformat(),

            "symbol":
                stock_symbol,

            "series":
                series,

            "open":
                open_price,

            "high":
                high_price,

            "low":
                low_price,

            "close":
                close_price,

            "volume":
                volume,

            "tradedValue":
                traded_value,

        }


        result[
            (
                stock_symbol,
                series,
            )
        ] = record


        # Generic symbol fallback.
        #
        # EQ / BE migration and series differences should not
        # make the history disappear.
        generic_key = (
            stock_symbol,
            "",
        )


        existing = result.get(
            generic_key
        )


        if existing is None:

            result[
                generic_key
            ] = record

        else:

            # Prefer EQ, otherwise preserve first usable record.
            if (
                series == "EQ"
                and
                existing.get(
                    "series"
                ) != "EQ"
            ):

                result[
                    generic_key
                ] = record


    if not result:

        raise ValueError(
            "No wanted securities found"
        )


    return result


# =========================================================
# DOWNLOAD ONE SESSION
# =========================================================

def build_nse_session():

    session = requests.Session()

    session.headers.update({
        "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/153.0.0.0 Safari/537.36",

        "Accept":
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8",

        "Accept-Language":
            "en-US,en;q=0.9",

        "Cache-Control":
            "no-cache",

        "Pragma":
            "no-cache",

        "Referer":
            "https://www.nseindia.com/all-reports",
    })

    # Warm up NSE cookies before requesting archive files.
    for warmup_url in (
        "https://www.nseindia.com/",
        "https://www.nseindia.com/all-reports",
    ):

        try:

            session.get(
                warmup_url,
                timeout=REQUEST_TIMEOUT,
            )

        except Exception:

            pass

    return session


# =========================================================
# DOWNLOAD ONE SESSION
# =========================================================

def fetch_session(
    date_obj,
    wanted_symbols,
    session=None,
):

    if date_obj.weekday() >= 5:

        return None


    url = bhavcopy_url(
        date_obj
    )


    own_session = False

    if session is None:

        session = build_nse_session()

        own_session = True


    archive_headers = {
        "Accept":
            "application/zip,application/octet-stream,*/*",

        "Referer":
            "https://www.nseindia.com/all-reports",

        "Sec-Fetch-Dest":
            "document",

        "Sec-Fetch-Mode":
            "navigate",

        "Sec-Fetch-Site":
            "same-site",
    }


    try:

        for attempt in range(1, 4):

            try:

                response = session.get(
                    url,
                    headers=archive_headers,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True,
                )


                if response.status_code == 200:

                    content = response.content

                    if (
                        len(content) >= 1000
                        and
                        content[:2] == b"PK"
                    ):

                        parsed = parse_bhavcopy(
                            content,
                            date_obj,
                            wanted_symbols,
                        )

                        return {
                            "date": date_obj,
                            "records": parsed,
                        }


                # NSE sometimes refreshes its anti-bot cookie.
                if response.status_code in (
                    401,
                    403,
                    429,
                ):

                    try:

                        session.get(
                            "https://www.nseindia.com/all-reports",
                            timeout=REQUEST_TIMEOUT,
                        )

                    except Exception:

                        pass


                time.sleep(
                    0.8 * attempt
                )


            except (
                requests.RequestException,
                zipfile.BadZipFile,
                ValueError,
            ):

                time.sleep(
                    0.8 * attempt
                )


        return None


    finally:

        if own_session:

            session.close()


# =========================================================
# LOAD HISTORICAL SESSIONS
# =========================================================

def load_history(
    market_date,
    wanted_symbols,
):

    print()

    print(
        "Downloading official NSE "
        "UDiFF OHLCV history..."
    )


    candidate_dates = []


    for back in range(
        0,
        MAX_CALENDAR_LOOKBACK + 1,
    ):

        d = (
            market_date
            -
            timedelta(
                days=back
            )
        )


        if d.weekday() >= 5:
            continue


        candidate_dates.append(
            d
        )


    sessions = []

    session = build_nse_session()


    try:

        consecutive_failures = 0


        for index, date_obj in enumerate(
            candidate_dates,
            start=1,
        ):

            if (
                len(sessions)
                >= REQUIRED_SESSIONS
            ):

                break


            result = fetch_session(
                date_obj,
                wanted_symbols,
                session=session,
            )


            if result:

                sessions.append(
                    result
                )

                consecutive_failures = 0


            else:

                consecutive_failures += 1


            if (
                index == 1
                or
                index % 10 == 0
                or
                result
            ):

                print(
                    f"History progress: "
                    f"{len(sessions)}/"
                    f"{REQUIRED_SESSIONS} sessions "
                    f"(checked {index})"
                )


            # If GitHub runner receives repeated 403/429 responses,
            # refresh cookies rather than hammering the archive host.
            if consecutive_failures >= 8:

                try:

                    session.close()

                except Exception:

                    pass


                time.sleep(2.0)

                session = build_nse_session()

                consecutive_failures = 0


            # Gentle pacing is more reliable on NSE archive endpoints.
            time.sleep(0.12)


    finally:

        try:

            session.close()

        except Exception:

            pass


    sessions.sort(
        key=lambda x:
            x["date"]
    )


    if len(
        sessions
    ) < 60:

        raise RuntimeError(
            "Insufficient NSE OHLCV history. "
            f"Only {len(sessions)} sessions loaded."
        )


    print()

    print({
        "historySessions":
            len(sessions),

        "firstDate":
            sessions[0][
                "date"
            ].isoformat(),

        "lastDate":
            sessions[-1][
                "date"
            ].isoformat(),
    })


    return sessions


# =========================================================
# STOCK HISTORY
# =========================================================

def build_stock_history(
    stock,
    sessions,
):

    stock_symbol = normalize_symbol(
        stock.get(
            "symbol"
        )
    )


    stock_series = normalize_series(
        stock.get(
            "series"
        )
    )


    rows = []


    for session in sessions:

        records = session[
            "records"
        ]


        record = records.get(
            (
                stock_symbol,
                stock_series,
            )
        )


        if record is None:

            record = records.get(
                (
                    stock_symbol,
                    "EQ",
                )
            )


        if record is None:

            record = records.get(
                (
                    stock_symbol,
                    "",
                )
            )


        if record is not None:

            rows.append(
                record
            )


    rows.sort(
        key=lambda x:
            x["date"]
    )


    return rows


# =========================================================
# 1 WEEK RETURN
# =========================================================
#
# Latest close vs close 5 trading sessions earlier.
# Uses the same official NSE UDiFF history already loaded.
#
# =========================================================

def calculate_return_1w(history):

    if not history or len(history) < 6:
        return None

    current_close = safe_float(
        history[-1].get("close")
    )

    close_5_sessions_ago = safe_float(
        history[-6].get("close")
    )

    if (
        current_close is None
        or close_5_sessions_ago is None
        or close_5_sessions_ago <= 0
    ):
        return None

    return (
        (
            current_close
            /
            close_5_sessions_ago
        )
        -
        1
    ) * 100


# =========================================================
# DAILY RANGE %
# =========================================================

def daily_range_pct(record):

    high = safe_float(
        record.get(
            "high"
        )
    )

    low = safe_float(
        record.get(
            "low"
        )
    )

    close = safe_float(
        record.get(
            "close"
        )
    )


    if (
        high is None
        or
        low is None
        or
        close in (
            None,
            0,
        )
    ):

        return None


    return (
        (
            high - low
        )
        /
        close
        *
        100
    )


# =========================================================
# TURNOVER
# =========================================================

def record_turnover(record):

    value = safe_float(
        record.get(
            "tradedValue"
        )
    )


    if value is not None:

        return value


    close = safe_float(
        record.get(
            "close"
        )
    )

    volume = safe_float(
        record.get(
            "volume"
        )
    )


    if (
        close is None
        or
        volume is None
    ):

        return None


    return (
        close
        *
        volume
    )


# =========================================================
# PRIOR MOVE DETECTION
# =========================================================
#
# We deliberately avoid using today's new high as the
# "prior peak".
#
# Candidate peak must normally be at least
# MIN_POST_PEAK_SESSIONS behind current session.
#
# This allows us to detect:
#
# move -> peak -> base -> breakout
#
# rather than treating today's breakout as the old peak.
#
# =========================================================

def detect_prior_move(history):

    n = len(history)

    if n < 30:
        return None

    current_index = n - 1

    latest_peak_index = (
        current_index
        - MIN_POST_PEAK_SESSIONS
    )

    if latest_peak_index < 10:
        return None

    earliest_peak_index = max(
        10,
        latest_peak_index
        - PEAK_SEARCH_SESSIONS,
    )

    candidates = []

    # Detect the move from a meaningful recent swing low instead of
    # blindly using the absolute lowest low in the whole lookback.
    #
    # A swing low is a local low relative to nearby sessions. For each
    # candidate prior peak we prefer the most recent valid swing low that
    # still produced the required >=30% advance. This better represents:
    #
    # swing low -> strong move -> prior peak -> base -> breakout
    #
    # If no local swing low qualifies, we fall back to the lowest valid
    # low so that genuine straight-line advances are not lost.
    SWING_RADIUS = 3

    for peak_index in range(
        earliest_peak_index,
        latest_peak_index + 1,
    ):

        peak_record = history[peak_index]

        peak_price = safe_float(
            peak_record.get("high")
        )

        if (
            peak_price is None
            or peak_price <= 0
        ):
            continue

        start_search_index = max(
            0,
            peak_index - MOVE_START_LOOKBACK,
        )

        if (
            peak_index
            - start_search_index
            < 5
        ):
            continue

        valid_lows = []
        swing_lows = []

        for actual_index in range(
            start_search_index,
            peak_index,
        ):

            record = history[actual_index]

            low_price = safe_float(
                record.get("low")
            )

            if (
                low_price is None
                or low_price <= 0
            ):
                continue

            # Need some real move duration.
            if (
                peak_index
                - actual_index
                < 4
            ):
                continue

            valid_lows.append(
                (
                    low_price,
                    actual_index,
                )
            )

            left_index = max(
                start_search_index,
                actual_index - SWING_RADIUS,
            )

            right_index = min(
                peak_index - 1,
                actual_index + SWING_RADIUS,
            )

            neighbour_lows = []

            for neighbour_index in range(
                left_index,
                right_index + 1,
            ):

                if neighbour_index == actual_index:
                    continue

                neighbour_low = safe_float(
                    history[neighbour_index].get("low")
                )

                if (
                    neighbour_low is not None
                    and neighbour_low > 0
                ):
                    neighbour_lows.append(
                        neighbour_low
                    )

            is_swing_low = (
                neighbour_lows
                and
                low_price <= min(neighbour_lows)
            )

            if not is_swing_low:
                continue

            move_pct = (
                (
                    peak_price
                    / low_price
                )
                - 1
            ) * 100

            if move_pct >= MIN_PRIOR_MOVE_PCT:
                swing_lows.append(
                    (
                        low_price,
                        actual_index,
                        move_pct,
                    )
                )

        if not valid_lows:
            continue

        if swing_lows:
            # Prefer the most recent qualifying swing low. If two lows
            # occur on the same session (defensive tie handling), prefer
            # the stronger move.
            start_price, start_index, prior_move_pct = max(
                swing_lows,
                key=lambda x: (
                    x[1],
                    x[2],
                ),
            )
        else:
            # Fallback for clean advances where a textbook local swing
            # low is not present in the available history.
            start_price, start_index = min(
                valid_lows,
                key=lambda x: x[0],
            )

            prior_move_pct = (
                (
                    peak_price
                    / start_price
                )
                - 1
            ) * 100

        if prior_move_pct < MIN_PRIOR_MOVE_PCT:
            continue

        sessions_since_peak = (
            current_index
            - peak_index
        )

        move_duration = (
            peak_index
            - start_index
        )

        # Prefer a strong move, but give recent prior peaks a meaningful
        # advantage so an old giant move does not dominate a cleaner and
        # more relevant recent setup.
        recency_factor = max(
            0.50,
            1.0
            - (
                sessions_since_peak
                * 0.005
            ),
        )

        # Avoid allowing extremely large historical advances to dominate
        # candidate selection purely because of their percentage size.
        capped_move_for_quality = min(
            prior_move_pct,
            150.0,
        )

        quality = (
            capped_move_for_quality
            * recency_factor
        )

        candidates.append({
            "quality": quality,
            "startIndex": start_index,
            "peakIndex": peak_index,
            "startPrice": start_price,
            "peakPrice": peak_price,
            "priorMovePct": prior_move_pct,
            "moveDuration": move_duration,
            "sessionsSincePeak": sessions_since_peak,
        })

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda x: x["quality"]
    )


# =========================================================
# MOVE PERIOD
# =========================================================

def classify_move_period(
    duration,
):

    if duration <= 25:
        return "1M"

    if duration <= 65:
        return "3M"

    if duration <= 130:
        return "6M"

    return "52W"


# =========================================================
# RETRACEMENT
# =========================================================

def calculate_retracement(
    history,
    move,
):

    if (
        not history
        or not move
    ):

        return None

    start_price = safe_float(
        move.get("startPrice")
    )

    peak_price = safe_float(
        move.get("peakPrice")
    )

    peak_index = move.get(
        "peakIndex"
    )

    if (
        start_price is None
        or peak_price is None
        or peak_index is None
    ):

        return None

    move_range = (
        peak_price
        -
        start_price
    )

    if move_range <= 0:

        return None

    # Measure the actual base pullback AFTER the prior peak.
    # Exclude the current session so breakout-day intraday action
    # does not rewrite the completed base retracement.
    post_peak_rows = history[
        peak_index + 1:
        -1
    ]

    if not post_peak_rows:

        return 0.0

    post_peak_lows = [
        safe_float(
            row.get("low")
        )
        for row in post_peak_rows
    ]

    post_peak_lows = [
        value
        for value in post_peak_lows
        if (
            value is not None
            and value > 0
        )
    ]

    if not post_peak_lows:

        return None

    base_low = min(
        post_peak_lows
    )

    retracement = (
        (
            peak_price
            -
            base_low
        )
        /
        move_range
        *
        100
    )

    if retracement < 0:

        retracement = 0

    return clamp(
        retracement,
        0,
        200,
    )


# =========================================================
# CONSOLIDATION DAYS
# =========================================================
#
# Count the completed base sessions after the detected prior peak.
#
# IMPORTANT:
# - The prior peak day itself is not a consolidation day.
# - The current session is excluded because it may be the breakout day.
# - Therefore:
#       prior peak -> completed base sessions -> current/breakout session
#
# Example:
# peak on day 0, 8 completed base sessions, breakout today
# => Consolidation Days = 8
#
# =========================================================

def calculate_consolidation_days(
    history,
    move,
):

    if (
        not history
        or not move
    ):

        return None

    peak_index = move.get(
        "peakIndex"
    )

    if peak_index is None:

        return None

    current_index = (
        len(history)
        - 1
    )

    # Sessions strictly between the prior peak and current session.
    completed_base_sessions = (
        current_index
        -
        peak_index
        -
        1
    )

    return max(
        0,
        completed_base_sessions,
    )


# =========================================================
# VOLUME CONTRACTION
# =========================================================

def calculate_volume_contraction(
    history,
    move,
):

    if len(
        history
    ) < 15:

        return (
            None,
            None,
        )


    # Exclude current session so breakout-day volume does not
    # destroy the base-contraction reading.
    base_rows = (
        history[
            max(
                0,
                len(history)
                -
                BASE_WINDOW
                -
                1
            ):
            -1
        ]
    )


    base_avg = mean(
        [
            row.get(
                "volume"
            )
            for row in base_rows
        ]
    )


    move_rows = (
        history[
            move[
                "startIndex"
            ]:
            move[
                "peakIndex"
            ]
            +
            1
        ]
    )


    move_avg = mean(
        [
            row.get(
                "volume"
            )
            for row in move_rows
        ]
    )


    if (
        base_avg is None
        or
        move_avg in (
            None,
            0,
        )
    ):

        return (
            None,
            None,
        )


    ratio = (
        base_avg
        /
        move_avg
    )


    contraction = (
        ratio
        <=
        0.75
    )


    return (
        contraction,
        ratio,
    )


# =========================================================
# VOLATILITY CONTRACTION
# =========================================================

def calculate_volatility_contraction(
    history,
    move,
):

    if len(
        history
    ) < 20:

        return (
            None,
            None,
        )


    base_rows = (
        history[
            max(
                0,
                len(history)
                -
                BASE_WINDOW
                -
                1
            ):
            -1
        ]
    )


    base_range = mean(
        [
            daily_range_pct(
                row
            )
            for row
            in base_rows
        ]
    )


    move_rows = (
        history[
            move[
                "startIndex"
            ]:
            move[
                "peakIndex"
            ]
            +
            1
        ]
    )


    move_range = mean(
        [
            daily_range_pct(
                row
            )
            for row
            in move_rows
        ]
    )


    if (
        base_range is None
        or
        move_range in (
            None,
            0,
        )
    ):

        return (
            None,
            None,
        )


    ratio = (
        base_range
        /
        move_range
    )


    contraction = (
        ratio
        <=
        0.75
    )


    return (
        contraction,
        ratio,
    )


# =========================================================
# TURNOVER EXPANSION
# =========================================================

def calculate_turnover_expansion(
    history,
):

    if len(
        history
    ) < 10:

        return None


    current_turnover = (
        record_turnover(
            history[-1]
        )
    )


    previous_rows = (
        history[
            max(
                0,
                len(history)
                -
                TURNOVER_AVG_WINDOW
                -
                1
            ):
            -1
        ]
    )


    avg_turnover = mean(
        [
            record_turnover(
                row
            )
            for row
            in previous_rows
        ]
    )


    if (
        current_turnover is None
        or
        avg_turnover in (
            None,
            0,
        )
    ):

        return None


    return (
        current_turnover
        /
        avg_turnover
    )


# =========================================================
# BREAKOUT
# =========================================================

def calculate_breakout(
    current_price,
    peak_price,
):

    if (
        current_price is None
        or
        peak_price in (
            None,
            0,
        )
    ):

        return {

            "status":
                "Pending",

            "distancePct":
                None,

        }


    distance_pct = (
        (
            current_price
            /
            peak_price
        )
        -
        1
    ) * 100


    if (
        current_price
        >=
        peak_price
        *
        1.005
    ):

        status = (
            "Breakout Confirmed"
        )


    elif (
        current_price
        >=
        peak_price
        *
        0.97
    ):

        status = (
            "Near Breakout"
        )


    elif (
        current_price
        >=
        peak_price
        *
        0.90
    ):

        status = (
            "Base Building"
        )


    else:

        status = (
            "Below Trigger"
        )


    return {

        "status":
            status,

        "distancePct":
            distance_pct,

    }


# =========================================================
# TECHNICAL SCORE
# =========================================================
#
# Phase-2 Technical = maximum 45
#
# Prior Move             8
# Retracement Quality   10
# Consolidation          5
# Volume Contraction     6
# Volatility Contract.   6
# Breakout / Proximity   6
# Turnover Expansion     4
#
# =========================================================

def score_prior_move(value):

    value = safe_float(
        value
    )

    if value is None:
        return 0


    if value >= 100:
        return 8

    if value >= 70:
        return 7

    if value >= 50:
        return 6

    if value >= 40:
        return 5

    if value >= 30:
        return 4

    return 0


def score_retracement(value):

    value = safe_float(
        value
    )

    if value is None:
        return 0


    # Strong leaders can hold very tight.
    if 0 <= value <= 20:
        return 9

    # User's preferred healthy / ideal zone.
    if 20 < value <= 40:
        return 10

    if 40 < value <= 50:
        return 7

    if 50 < value <= 60:
        return 4

    return 0


def score_consolidation(days):

    days = safe_float(
        days
    )

    if days is None:
        return 0


    if 10 <= days <= 60:
        return 5

    if 5 <= days < 10:
        return 4

    if 60 < days <= 90:
        return 3

    if days > 90:
        return 1

    return 0


def score_breakout(status):

    text = str(
        status
        or ""
    ).lower()


    if (
        "breakout confirmed"
        in text
    ):
        return 6

    if (
        "near breakout"
        in text
    ):
        return 5

    if (
        "base building"
        in text
    ):
        return 3

    return 0


def score_turnover(value):

    value = safe_float(
        value
    )

    if value is None:
        return 0


    if value >= 2.0:
        return 4

    if value >= 1.5:
        return 3

    if value >= 1.2:
        return 2

    if value >= 1.0:
        return 1

    return 0


def technical_score(
    prior_move,
    retracement,
    consolidation_days,
    volume_contraction,
    volatility_contraction,
    breakout_status,
    turnover_expansion,
):

    score = 0


    score += (
        score_prior_move(
            prior_move
        )
    )


    score += (
        score_retracement(
            retracement
        )
    )


    score += (
        score_consolidation(
            consolidation_days
        )
    )


    if volume_contraction is True:
        score += 6


    if volatility_contraction is True:
        score += 6


    score += (
        score_breakout(
            breakout_status
        )
    )


    score += (
        score_turnover(
            turnover_expansion
        )
    )


    return score


# =========================================================
# PHASE-2 BIG MOVE SCORE
# =========================================================
#
# Existing Phase-1 Score is useful but technical confirmation
# must now materially affect final ranking.
#
# Phase-1 contributes max 55.
# Technical contributes max 45.
#
# Free Float is NOT included yet because we do not have
# a reliable quantity source connected.
#
# =========================================================

def phase2_score(
    old_score,
    tech_score,
):

    old_score = safe_float(
        old_score
    )


    if old_score is None:
        old_score = 0


    phase1_component = (
        old_score
        /
        100
        *
        55
    )


    final_score = (
        phase1_component
        +
        tech_score
    )


    return int(
        round(
            clamp(
                final_score,
                0,
                100,
            )
        )
    )


# =========================================================
# SETUP STATUS
# =========================================================

def setup_status(
    score,
    prior_move,
    retracement,
    consolidation_days,
    volume_contraction,
    volatility_contraction,
    breakout_status,
):

    prior_move = safe_float(
        prior_move
    )

    retracement = safe_float(
        retracement
    )

    consolidation_days = safe_float(
        consolidation_days
    )


    if (
        prior_move is None
        or
        prior_move
        <
        MIN_PRIOR_MOVE_PCT
    ):

        return "Developing"


    breakout_text = str(
        breakout_status
        or ""
    ).lower()


    if (
        "breakout confirmed"
        in breakout_text
    ):

        if score >= 65:

            return "Breakout"

        return "Developing"


    if (
        "near breakout"
        in breakout_text
    ):

        if (
            score >= 65
            and
            volume_contraction
            is True
            and
            volatility_contraction
            is True
        ):

            return "Near Breakout"


    healthy_retracement = (
        retracement
        is not None
        and
        0
        <=
        retracement
        <=
        50
    )


    enough_base = (
        consolidation_days
        is not None
        and
        consolidation_days
        >=
        5
    )


    if (
        score >= 75
        and
        healthy_retracement
        and
        enough_base
        and
        volume_contraction
        is True
        and
        volatility_contraction
        is True
    ):

        return "Strong Setup"


    if score >= 60:

        return "Watchlist"


    return "Developing"


# =========================================================
# MISSING CONDITIONS
# =========================================================

TECHNICAL_MISSING_NAMES = {

    "Prior Move",
    "Retracement",
    "Consolidation",
    "Volume Contraction",
    "Volatility Contraction",
    "Breakout Analysis",
    "Turnover Expansion",

}


def rebuild_missing_conditions(
    row,
):

    old_list = (
        row.get(
            "missingConditionsList"
        )
    )


    if not isinstance(
        old_list,
        list,
    ):

        old_text = str(
            row.get(
                "missingConditions"
            )
            or ""
        )


        old_list = [

            item.strip()

            for item
            in old_text.split(
                "|"
            )

            if item.strip()
            and
            item.strip()
            != "None"

        ]


    cleaned = [

        item

        for item
        in old_list

        if item
        not in
        TECHNICAL_MISSING_NAMES

    ]


    # Technical fields are now calculated only if data exists.

    if (
        safe_float(
            row.get(
                "priorMovePct"
            )
        )
        is None
    ):

        cleaned.append(
            "Prior Move"
        )


    if (
        safe_float(
            row.get(
                "retracementPct"
            )
        )
        is None
    ):

        cleaned.append(
            "Retracement"
        )


    if (
        safe_float(
            row.get(
                "consolidationDays"
            )
        )
        is None
    ):

        cleaned.append(
            "Consolidation"
        )


    if (
        row.get(
            "volumeContraction"
        )
        is None
    ):

        cleaned.append(
            "Volume Contraction"
        )


    if (
        row.get(
            "volatilityContraction"
        )
        is None
    ):

        cleaned.append(
            "Volatility Contraction"
        )


    breakout = str(
        row.get(
            "breakoutStatus"
        )
        or ""
    )


    if (
        not breakout
        or
        breakout == "Pending"
    ):

        cleaned.append(
            "Breakout Analysis"
        )


    if (
        safe_float(
            row.get(
                "turnoverExpansion"
            )
        )
        is None
    ):

        cleaned.append(
            "Turnover Expansion"
        )


    # De-duplicate while preserving order.
    final = []


    for item in cleaned:

        if item not in final:

            final.append(
                item
            )


    row[
        "missingConditionsList"
    ] = final


    row[
        "missingConditions"
    ] = (
        " | ".join(
            final
        )
        if final
        else
        "None"
    )


# =========================================================
# ANALYZE ONE STOCK
# =========================================================

def analyze_stock(
    scanner_row,
    stock,
    sessions,
):

    history = (
        build_stock_history(
            stock,
            sessions,
        )
    )


    scanner_row[
        "return1W"
    ] = round_or_none(
        calculate_return_1w(
            history
        ),
        2,
    )


    scanner_row[
        "technicalHistorySessions"
    ] = len(
        history
    )


    scanner_row[
        "technicalHistoryStart"
    ] = (
        history[0][
            "date"
        ]
        if history
        else None
    )


    scanner_row[
        "technicalHistoryEnd"
    ] = (
        history[-1][
            "date"
        ]
        if history
        else None
    )


    scanner_row[
        "technicalSource"
    ] = (
        "Official NSE UDiFF EOD bhavcopy"
    )


    if len(
        history
    ) < 30:

        scanner_row[
            "priorMovePct"
        ] = None

        scanner_row[
            "movePeriod"
        ] = None

        scanner_row[
            "retracementPct"
        ] = None

        scanner_row[
            "consolidationDays"
        ] = None

        scanner_row[
            "volumeContraction"
        ] = None

        scanner_row[
            "volatilityContraction"
        ] = None

        scanner_row[
            "breakoutStatus"
        ] = "Pending"

        scanner_row[
            "breakoutDistancePct"
        ] = None

        scanner_row[
            "turnoverExpansion"
        ] = None

        scanner_row[
            "technicalScore"
        ] = None

        scanner_row[
            "technicalStatus"
        ] = "INSUFFICIENT_HISTORY"

        rebuild_missing_conditions(
            scanner_row
        )

        return scanner_row


    move = detect_prior_move(
        history
    )


    if move is None:

        scanner_row[
            "priorMovePct"
        ] = None

        scanner_row[
            "movePeriod"
        ] = None

        scanner_row[
            "moveStartDate"
        ] = None

        scanner_row[
            "movePeakDate"
        ] = None

        scanner_row[
            "moveStartPrice"
        ] = None

        scanner_row[
            "movePeakPrice"
        ] = None

        scanner_row[
            "retracementPct"
        ] = None

        scanner_row[
            "consolidationDays"
        ] = None

        scanner_row[
            "volumeContraction"
        ] = None

        scanner_row[
            "volatilityContraction"
        ] = None

        scanner_row[
            "breakoutStatus"
        ] = "Pending"

        scanner_row[
            "breakoutDistancePct"
        ] = None

        scanner_row[
            "turnoverExpansion"
        ] = (
            round_or_none(
                calculate_turnover_expansion(
                    history
                ),
                2,
            )
        )

        scanner_row[
            "technicalScore"
        ] = 0

        scanner_row[
            "technicalStatus"
        ] = "NO_PRIOR_30PCT_MOVE"

        scanner_row[
            "bigMoveScore"
        ] = phase2_score(
            scanner_row.get(
                "bigMoveScore"
            ),
            0,
        )

        scanner_row[
            "scorePhase"
        ] = "PHASE_2_TECHNICAL"

        scanner_row[
            "setupStatus"
        ] = "Developing"

        rebuild_missing_conditions(
            scanner_row
        )

        return scanner_row


    current_price = safe_float(
        history[-1].get(
            "close"
        )
    )


    prior_move_pct = (
        move[
            "priorMovePct"
        ]
    )


    retracement = (
        calculate_retracement(
            history,
            move,
        )
    )


    consolidation_days = (
        calculate_consolidation_days(
            history,
            move,
        )
    )


    (
        volume_contraction,
        volume_ratio,
    ) = calculate_volume_contraction(
        history,
        move,
    )


    (
        volatility_contraction,
        volatility_ratio,
    ) = calculate_volatility_contraction(
        history,
        move,
    )


    breakout = calculate_breakout(

        current_price,

        move[
            "peakPrice"
        ],

    )


    turnover_expansion = (
        calculate_turnover_expansion(
            history
        )
    )


    tech_score = technical_score(

        prior_move_pct,

        retracement,

        consolidation_days,

        volume_contraction,

        volatility_contraction,

        breakout[
            "status"
        ],

        turnover_expansion,

    )


    old_score = (
        scanner_row.get(
            "bigMoveScore"
        )
    )


    final_score = phase2_score(
        old_score,
        tech_score,
    )


    scanner_row[
        "phase1Score"
    ] = old_score


    scanner_row[
        "priorMovePct"
    ] = round(
        prior_move_pct,
        2,
    )


    scanner_row[
        "movePeriod"
    ] = classify_move_period(
        move[
            "moveDuration"
        ]
    )


    scanner_row[
        "moveStartDate"
    ] = history[
        move[
            "startIndex"
        ]
    ][
        "date"
    ]


    scanner_row[
        "movePeakDate"
    ] = history[
        move[
            "peakIndex"
        ]
    ][
        "date"
    ]


    scanner_row[
        "moveStartPrice"
    ] = round_or_none(
        move[
            "startPrice"
        ],
        2,
    )


    scanner_row[
        "movePeakPrice"
    ] = round_or_none(
        move[
            "peakPrice"
        ],
        2,
    )


    scanner_row[
        "retracementPct"
    ] = round_or_none(
        retracement,
        2,
    )


    scanner_row[
        "consolidationDays"
    ] = int(
        consolidation_days
    )


    scanner_row[
        "volumeContraction"
    ] = volume_contraction


    scanner_row[
        "volumeContractionRatio"
    ] = round_or_none(
        volume_ratio,
        3,
    )


    scanner_row[
        "volatilityContraction"
    ] = volatility_contraction


    scanner_row[
        "volatilityContractionRatio"
    ] = round_or_none(
        volatility_ratio,
        3,
    )


    scanner_row[
        "breakoutStatus"
    ] = breakout[
        "status"
    ]


    scanner_row[
        "breakoutDistancePct"
    ] = round_or_none(
        breakout[
            "distancePct"
        ],
        2,
    )


    scanner_row[
        "turnoverExpansion"
    ] = round_or_none(
        turnover_expansion,
        2,
    )


    scanner_row[
        "technicalScore"
    ] = tech_score


    scanner_row[
        "technicalScoreMax"
    ] = 45


    scanner_row[
        "bigMoveScore"
    ] = final_score


    scanner_row[
        "scorePhase"
    ] = "PHASE_2_TECHNICAL"


    scanner_row[
        "technicalStatus"
    ] = "READY"


    scanner_row[
        "setupStatus"
    ] = setup_status(

        final_score,

        prior_move_pct,

        retracement,

        consolidation_days,

        volume_contraction,

        volatility_contraction,

        breakout[
            "status"
        ],

    )


    scanner_row[
        "technicalDetails"
    ] = {

        "priorMoveScore":
            score_prior_move(
                prior_move_pct
            ),

        "retracementScore":
            score_retracement(
                retracement
            ),

        "consolidationScore":
            score_consolidation(
                consolidation_days
            ),

        "volumeContractionScore":
            (
                6
                if
                volume_contraction
                is True
                else 0
            ),

        "volatilityContractionScore":
            (
                6
                if
                volatility_contraction
                is True
                else 0
            ),

        "breakoutScore":
            score_breakout(
                breakout[
                    "status"
                ]
            ),

        "turnoverScore":
            score_turnover(
                turnover_expansion
            ),

    }


    rebuild_missing_conditions(
        scanner_row
    )


    return scanner_row


# =========================================================
# SORT
# =========================================================

def sort_scanner_rows(rows):

    return sorted(

        rows,

        key=lambda row: (

            safe_float(
                row.get(
                    "bigMoveScore"
                )
            )
            or 0,

            safe_float(
                row.get(
                    "technicalScore"
                )
            )
            or 0,

            safe_float(
                row.get(
                    "rsRating"
                )
            )
            or 0,

            safe_float(
                row.get(
                    "stockMomentumRating"
                )
            )
            or 0,

        ),

        reverse=True,

    )


# =========================================================
# SUMMARY
# =========================================================

def build_summary(rows):

    return {

        "total":
            len(rows),

        "score80Plus":
            sum(
                1
                for row
                in rows
                if (
                    safe_float(
                        row.get(
                            "bigMoveScore"
                        )
                    )
                    or 0
                )
                >= 80
            ),

        "score70Plus":
            sum(
                1
                for row
                in rows
                if (
                    safe_float(
                        row.get(
                            "bigMoveScore"
                        )
                    )
                    or 0
                )
                >= 70
            ),

        "strongSetup":
            sum(
                1
                for row
                in rows
                if row.get(
                    "setupStatus"
                )
                ==
                "Strong Setup"
            ),

        "nearBreakout":
            sum(
                1
                for row
                in rows
                if row.get(
                    "setupStatus"
                )
                ==
                "Near Breakout"
            ),

        "breakout":
            sum(
                1
                for row
                in rows
                if row.get(
                    "setupStatus"
                )
                ==
                "Breakout"
            ),

        "watchlist":
            sum(
                1
                for row
                in rows
                if row.get(
                    "setupStatus"
                )
                ==
                "Watchlist"
            ),

        "technicalReady":
            sum(
                1
                for row
                in rows
                if row.get(
                    "technicalStatus"
                )
                ==
                "READY"
            ),

        "priorMoveReady":
            sum(
                1
                for row
                in rows
                if safe_float(
                    row.get(
                        "priorMovePct"
                    )
                )
                is not None
            ),

        "volumeContraction":
            sum(
                1
                for row
                in rows
                if row.get(
                    "volumeContraction"
                )
                is True
            ),

        "volatilityContraction":
            sum(
                1
                for row
                in rows
                if row.get(
                    "volatilityContraction"
                )
                is True
            ),

    }


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "=============================================="
    )

    print(
        "BUILD BIG MOVE TECHNICAL ENGINE"
    )

    print(
        "=============================================="
    )


    stocks = load_json(
        STOCKS_PATH,
        [],
    )


    scanner = load_json(
        SCANNER_PATH,
        {},
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


    if not isinstance(
        scanner,
        dict,
    ):

        raise RuntimeError(
            "big_move_scanner.json is invalid"
        )


    scanner_rows = (
        scanner.get(
            "rows"
        )
    )


    if (
        not isinstance(
            scanner_rows,
            list,
        )
        or
        not scanner_rows
    ):

        raise RuntimeError(
            "big_move_scanner.json has no rows"
        )


    print(
        "Stocks:",
        len(stocks),
    )


    print(
        "Scanner rows:",
        len(scanner_rows),
    )


    market_date = (
        detect_market_date(
            stocks
        )
    )


    print(
        "Market date:",
        market_date.isoformat(),
    )


    scanner_symbols = {

        normalize_symbol(
            row.get(
                "symbol"
            )
        )

        for row
        in scanner_rows

        if normalize_symbol(
            row.get(
                "symbol"
            )
        )

    }


    print(
        "Technical universe:",
        len(scanner_symbols),
    )


    # =====================================================
    # DOWNLOAD HISTORY
    # =====================================================

    sessions = load_history(

        market_date,

        scanner_symbols,

    )


    # =====================================================
    # STOCK LOOKUP
    # =====================================================

    stock_lookup = {}


    for stock in stocks:

        stock_symbol = (
            normalize_symbol(
                stock.get(
                    "symbol"
                )
            )
        )


        if stock_symbol:

            stock_lookup[
                stock_symbol
            ] = stock


    # =====================================================
    # ANALYZE
    # =====================================================

    updated_rows = []


    total = len(
        scanner_rows
    )


    for index, scanner_row in enumerate(
        scanner_rows,
        start=1,
    ):

        stock_symbol = (
            normalize_symbol(
                scanner_row.get(
                    "symbol"
                )
            )
        )


        stock = stock_lookup.get(
            stock_symbol
        )


        if stock is None:

            scanner_row[
                "technicalStatus"
            ] = "STOCK_NOT_FOUND"

            rebuild_missing_conditions(
                scanner_row
            )

            updated_rows.append(
                scanner_row
            )

            continue


        analyzed = analyze_stock(

            scanner_row,

            stock,

            sessions,

        )


        updated_rows.append(
            analyzed
        )


        if (
            index % 250
            ==
            0
        ):

            print(
                f"Technical analysis: "
                f"{index}/{total}"
            )


    # =====================================================
    # SORT
    # =====================================================

    updated_rows = (
        sort_scanner_rows(
            updated_rows
        )
    )


    summary = build_summary(
        updated_rows
    )


    # =====================================================
    # UPDATE PAYLOAD
    # =====================================================

    scanner[
        "rows"
    ] = updated_rows


    scanner[
        "phase"
    ] = (
        "PHASE_2_TECHNICAL"
    )


    scanner[
        "scannerVersion"
    ] = "2.0"


    scanner[
        "technicalGeneratedAt"
    ] = (
        datetime.now(
            timezone.utc
        )
        .replace(
            microsecond=0
        )
        .isoformat()
    )


    scanner[
        "technicalMarketDate"
    ] = (
        market_date.isoformat()
    )


    scanner[
        "technicalHistory"
    ] = {

        "source":
            "Official NSE UDiFF EOD bhavcopy",

        "sessions":
            len(sessions),

        "firstDate":
            sessions[0][
                "date"
            ].isoformat(),

        "lastDate":
            sessions[-1][
                "date"
            ].isoformat(),

    }


    scanner[
        "summary"
    ] = summary


    scanner[
        "methodology"
    ] = {

        "phase":
            "PHASE_2_TECHNICAL",

        "source":
            "Official NSE UDiFF EOD bhavcopy",

        "priorMove":
            (
                "Detect prior price advance >=30% "
                "from the most recent qualifying local swing low to a prior peak."
            ),

        "retracement":
            (
                "(Prior Peak - Lowest Post-Peak Base Low) / "
                "(Prior Peak - Move Start Price) × 100. "
                "Current session is excluded."
            ),

        "retracementInterpretation": {

            "0-20":
                "Very strong / tight hold",

            "20-40":
                "Ideal healthy retracement",

            "40-50":
                "Acceptable",

            "50-60":
                "Weakening",

            "Above60":
                "Poor base quality",

        },

        "consolidationDays":
            (
                "Completed trading sessions strictly between the detected "
                "prior peak and the current session. Prior peak day and "
                "current/breakout day are excluded."
            ),

        "volumeContraction":
            (
                "Recent base average volume <=75% "
                "of prior move average volume."
            ),

        "volatilityContraction":
            (
                "Recent average daily range <=75% "
                "of prior move average daily range."
            ),

        "breakout":
            {

                "Breakout Confirmed":
                    (
                        "Current close >= 100.5% "
                        "of prior peak."
                    ),

                "Near Breakout":
                    (
                        "Current close within 3% "
                        "below prior peak."
                    ),

                "Base Building":
                    (
                        "Current close within 10% "
                        "below prior peak."
                    ),

            },

        "turnoverExpansion":
            (
                "Current traded turnover divided by "
                "previous 20-session average turnover."
            ),

        "score": {

            "phase1Max":
                55,

            "technicalMax":
                45,

            "freeFloat":
                (
                    "Not yet included because reliable "
                    "Free Float Shares source is pending."
                ),

        },

    }


    # =====================================================
    # SAVE
    # =====================================================

    save_json(
        SCANNER_PATH,
        scanner,
    )


    # =====================================================
    # LOG
    # =====================================================

    print()

    print(
        "=============================================="
    )

    print(
        "BIG MOVE TECHNICAL SUMMARY"
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
        "Output:",
        SCANNER_PATH,
    )


    print(
        "=============================================="
    )


if __name__ == "__main__":

    main()
