import json
import math
import time
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote

import requests


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

META_FILE = DATA / "meta.json"
STOCKS_FILE = DATA / "stocks.json"


# =========================================================
# DIRECT MARKET ASSETS
#
# Yahoo history works reliably for these.
# =========================================================

DIRECT_ASSETS = {

    "nifty50": {
        "name": "NIFTY 50 / Largecap",
        "type": "equity",
        "symbols": [
            "^NSEI"
        ]
    },

    "midcap100": {
        "name": "NIFTY Midcap 100",
        "type": "equity",
        "symbols": [
            "NIFTY_MIDCAP_100.NS",
            "^CNXMIDCAP"
        ]
    },

    "gold": {
        "name": "GOLD",
        "type": "gold",
        "symbols": [
            "GC=F"
        ]
    }
}


# =========================================================
# HTTP
# =========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*"
}


# =========================================================
# BASIC HELPERS
# =========================================================

def safe_number(value):

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

        number = float(value)

        if math.isfinite(number):
            return number

    except Exception:
        pass

    return None


def clamp(
    value,
    low=0,
    high=100
):

    return max(
        low,
        min(
            high,
            value
        )
    )


def average(values):

    clean = []

    for value in values:

        number = safe_number(
            value
        )

        if number is not None:

            clean.append(
                number
            )

    if not clean:
        return None

    return (
        sum(clean)
        /
        len(clean)
    )


def median(values):

    clean = sorted(
        number
        for number in (
            safe_number(value)
            for value in values
        )
        if number is not None
    )

    if not clean:
        return None

    count = len(clean)

    middle = (
        count // 2
    )

    if count % 2:

        return clean[middle]

    return (
        clean[middle - 1]
        +
        clean[middle]
    ) / 2


def pct_change(
    current,
    previous
):

    current = safe_number(
        current
    )

    previous = safe_number(
        previous
    )

    if (
        current is None
        or previous is None
        or previous == 0
    ):
        return None

    return (
        (
            current /
            previous
        )
        - 1
    ) * 100


def load_json(
    path,
    default
):

    try:

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        return default


# =========================================================
# RSI
# =========================================================

def calculate_rsi(
    values,
    period=14
):

    clean = []

    for value in values:

        number = safe_number(
            value
        )

        if number is not None:

            clean.append(
                number
            )


    if (
        len(clean)
        <
        period + 1
    ):

        return None


    gains = []
    losses = []


    start_index = (
        len(clean)
        -
        period
    )


    for index in range(
        start_index,
        len(clean)
    ):

        change = (
            clean[index]
            -
            clean[index - 1]
        )


        if change > 0:

            gains.append(
                change
            )

            losses.append(
                0
            )

        else:

            gains.append(
                0
            )

            losses.append(
                abs(change)
            )


    avg_gain = average(
        gains
    )

    avg_loss = average(
        losses
    )


    if avg_gain is None:
        return None


    if avg_loss == 0:
        return 100


    rs = (
        avg_gain /
        avg_loss
    )


    return (
        100
        -
        (
            100 /
            (
                1 + rs
            )
        )
    )


# =========================================================
# REGIME LABEL
# =========================================================

def regime_label(
    score,
    asset_type="equity"
):

    score = safe_number(
        score
    )


    if score is None:

        return {
            "label": "Pending",
            "signal": "pending",
            "emoji": "⚪"
        }


    # =====================================================
    # GOLD
    # =====================================================

    if asset_type == "gold":

        if score >= 75:

            return {
                "label": "Very Strong",
                "signal": "aggressive",
                "emoji": "🟢🟢"
            }


        if score >= 65:

            return {
                "label": "Strong",
                "signal": "overweight",
                "emoji": "🟢"
            }


        if score >= 55:

            return {
                "label": "Positive",
                "signal": "selective",
                "emoji": "🟢"
            }


        if score >= 45:

            return {
                "label": "Neutral / Cautious",
                "signal": "warning",
                "emoji": "🟡"
            }


        if score >= 35:

            return {
                "label": "Weak / Correction",
                "signal": "reduce",
                "emoji": "🟠"
            }


        return {
            "label": "Defensive Weak",
            "signal": "defensive",
            "emoji": "🔴"
        }


    # =====================================================
    # EQUITY
    # =====================================================

    if score >= 75:

        return {
            "label": "Aggressive Stocks",
            "signal": "aggressive",
            "emoji": "🟢🟢"
        }


    if score >= 65:

        return {
            "label": "Stocks Overweight",
            "signal": "overweight",
            "emoji": "🟢"
        }


    if score >= 55:

        return {
            "label": "Selective Buying",
            "signal": "selective",
            "emoji": "🟢"
        }


    if score >= 45:

        return {
            "label": "Warning",
            "signal": "warning",
            "emoji": "🟡"
        }


    if score >= 35:

        return {
            "label": "Equity Reduce",
            "signal": "reduce",
            "emoji": "🟠"
        }


    return {
        "label": "G-Sec / Gold / Cash",
        "signal": "defensive",
        "emoji": "🔴"
    }


# =========================================================
# YAHOO HISTORY
# =========================================================

def yahoo_chart_url(
    symbol
):

    encoded_symbol = quote(
        symbol,
        safe=""
    )


    return (
        "https://query1.finance.yahoo.com/"
        "v8/finance/chart/"
        f"{encoded_symbol}"
        "?range=5y"
        "&interval=1d"
        "&events=history"
        "&includeAdjustedClose=true"
    )


def fetch_symbol_history(
    symbol
):

    response = requests.get(

        yahoo_chart_url(
            symbol
        ),

        headers=HEADERS,

        timeout=30
    )


    response.raise_for_status()


    payload = (
        response.json()
    )


    chart = (
        payload.get(
            "chart"
        )
        or {}
    )


    error = chart.get(
        "error"
    )


    if error:

        raise RuntimeError(
            str(error)
        )


    results = (
        chart.get(
            "result"
        )
        or []
    )


    if not results:

        raise RuntimeError(
            f"No Yahoo result for {symbol}"
        )


    result = (
        results[0]
    )


    timestamps = (
        result.get(
            "timestamp"
        )
        or []
    )


    indicators = (
        result.get(
            "indicators"
        )
        or {}
    )


    quote_data = (
        indicators.get(
            "quote"
        )
        or [{}]
    )[0]


    closes = (
        quote_data.get(
            "close"
        )
        or []
    )


    rows = []


    for (
        timestamp,
        close
    ) in zip(
        timestamps,
        closes
    ):

        close = safe_number(
            close
        )


        if close is None:
            continue


        dt = datetime.fromtimestamp(

            timestamp,

            tz=timezone.utc
        )


        rows.append({

            "date":
                dt.date(),

            "close":
                close
        })


    rows.sort(
        key=lambda item:
            item["date"]
    )


    if len(rows) < 100:

        raise RuntimeError(

            f"Insufficient Yahoo "
            f"history for {symbol}: "
            f"{len(rows)} rows"
        )


    return rows


# =========================================================
# TRY YAHOO SYMBOLS
# =========================================================

def fetch_direct_asset_history(
    asset_key,
    config
):

    errors = []


    for symbol in config[
        "symbols"
    ]:

        try:

            print(
                f"Trying Yahoo "
                f"{asset_key}: "
                f"{symbol}"
            )


            rows = (
                fetch_symbol_history(
                    symbol
                )
            )


            print(
                f"Loaded {asset_key}: "
                f"{symbol} "
                f"({len(rows)} rows)"
            )


            return (
                rows,
                symbol,
                None
            )


        except Exception as exc:

            error = (
                f"{symbol}: {exc}"
            )


            errors.append(
                error
            )


            print(
                f"Failed {asset_key}: "
                f"{error}"
            )


            time.sleep(
                1
            )


    return (
        None,
        None,
        " | ".join(
            errors
        )
    )


# =========================================================
# WEEKLY / MONTHLY RESAMPLE
# =========================================================

def resample_last_close(
    rows,
    mode
):

    buckets = {}


    for row in rows:

        date = (
            row["date"]
        )


        if mode == "weekly":

            iso = (
                date.isocalendar()
            )


            key = (
                iso.year,
                iso.week
            )


        elif mode == "monthly":

            key = (
                date.year,
                date.month
            )


        else:

            raise ValueError(
                f"Unknown mode: {mode}"
            )


        buckets[
            key
        ] = row


    result = list(
        buckets.values()
    )


    result.sort(
        key=lambda item:
            item["date"]
    )


    return result


# =========================================================
# DIRECT INDEX SCORE
# =========================================================

def score_series(
    values,
    fast_period,
    slow_period,
    momentum_period,
    high_period
):

    clean = []

    for value in values:

        number = safe_number(
            value
        )

        if number is not None:

            clean.append(
                number
            )


    minimum_required = max(

        slow_period,

        momentum_period + 1,

        high_period,

        15
    )


    if (
        len(clean)
        <
        minimum_required
    ):

        return (
            None,
            {
                "error":
                    "Insufficient history",

                "rows":
                    len(clean),

                "required":
                    minimum_required
            }
        )


    latest = (
        clean[-1]
    )


    fast_ma = average(
        clean[
            -fast_period:
        ]
    )


    slow_ma = average(
        clean[
            -slow_period:
        ]
    )


    momentum_reference = (

        clean[
            -(
                momentum_period
                +
                1
            )
        ]
    )


    momentum = pct_change(
        latest,
        momentum_reference
    )


    rsi = calculate_rsi(
        clean,
        14
    )


    recent_high = max(
        clean[
            -high_period:
        ]
    )


    distance_from_high = (
        pct_change(
            latest,
            recent_high
        )
    )


    # =====================================================
    # 1 PRICE VS FAST MA = 25
    # =====================================================

    price_fast_score = 0


    if (
        fast_ma is not None
        and
        latest >= fast_ma
    ):

        price_fast_score = 25


    # =====================================================
    # 2 FAST MA VS SLOW MA = 25
    # =====================================================

    trend_score = 0


    if (
        fast_ma is not None
        and
        slow_ma is not None
        and
        fast_ma >= slow_ma
    ):

        trend_score = 25


    # =====================================================
    # 3 MOMENTUM = 25
    # =====================================================

    momentum_score = 0


    if momentum is not None:

        if momentum >= 5:

            momentum_score = 25

        elif momentum >= 2:

            momentum_score = 20

        elif momentum >= 0:

            momentum_score = 15

        elif momentum >= -3:

            momentum_score = 8

        else:

            momentum_score = 0


    # =====================================================
    # 4 RSI + HIGH = 25
    # =====================================================

    strength_score = 0


    if rsi is not None:

        if rsi >= 60:

            strength_score += 15

        elif rsi >= 50:

            strength_score += 10

        elif rsi >= 40:

            strength_score += 5


    if (
        distance_from_high
        is not None
    ):

        if distance_from_high >= -3:

            strength_score += 10

        elif distance_from_high >= -7:

            strength_score += 7

        elif distance_from_high >= -12:

            strength_score += 4


    total_score = (

        price_fast_score
        +
        trend_score
        +
        momentum_score
        +
        strength_score
    )


    total_score = round(
        clamp(
            total_score
        )
    )


    details = {

        "latest":
            round(
                latest,
                2
            ),

        "fastMA":
            (
                round(
                    fast_ma,
                    2
                )
                if fast_ma is not None
                else None
            ),

        "slowMA":
            (
                round(
                    slow_ma,
                    2
                )
                if slow_ma is not None
                else None
            ),

        "momentumPct":
            (
                round(
                    momentum,
                    2
                )
                if momentum is not None
                else None
            ),

        "rsi14":
            (
                round(
                    rsi,
                    2
                )
                if rsi is not None
                else None
            ),

        "distanceFromHighPct":
            (
                round(
                    distance_from_high,
                    2
                )
                if distance_from_high
                is not None
                else None
            )
    }


    return (
        total_score,
        details
    )


# =========================================================
# BUILD DIRECT ASSET
# =========================================================

def build_direct_asset(
    asset_key,
    config
):

    (
        rows,
        source_symbol,
        fetch_error
    ) = fetch_direct_asset_history(
        asset_key,
        config
    )


    if not rows:

        return {

            "name":
                config["name"],

            "type":
                config["type"],

            "available":
                False,

            "source":
                "Yahoo Finance",

            "sourceSymbol":
                None,

            "date":
                None,

            "daily":
                None,

            "weekly":
                None,

            "monthly":
                None,

            "overall":
                None,

            "dailySignal":
                regime_label(
                    None,
                    config["type"]
                ),

            "weeklySignal":
                regime_label(
                    None,
                    config["type"]
                ),

            "monthlySignal":
                regime_label(
                    None,
                    config["type"]
                ),

            "overallSignal":
                regime_label(
                    None,
                    config["type"]
                ),

            "error":
                fetch_error
        }


    daily_values = [

        row["close"]

        for row in rows
    ]


    weekly_rows = (
        resample_last_close(
            rows,
            "weekly"
        )
    )


    weekly_values = [

        row["close"]

        for row in weekly_rows
    ]


    monthly_rows = (
        resample_last_close(
            rows,
            "monthly"
        )
    )


    monthly_values = [

        row["close"]

        for row in monthly_rows
    ]


    (
        daily_score,
        daily_details
    ) = score_series(

        daily_values,

        fast_period=20,

        slow_period=50,

        momentum_period=5,

        high_period=20
    )


    (
        weekly_score,
        weekly_details
    ) = score_series(

        weekly_values,

        fast_period=10,

        slow_period=30,

        momentum_period=4,

        high_period=13
    )


    (
        monthly_score,
        monthly_details
    ) = score_series(

        monthly_values,

        fast_period=6,

        slow_period=10,

        momentum_period=3,

        high_period=12
    )


    overall_score = (
        weighted_overall(
            daily_score,
            weekly_score,
            monthly_score
        )
    )


    return {

        "name":
            config["name"],

        "type":
            config["type"],

        "available":
            True,

        "source":
            "Yahoo Finance",

        "sourceSymbol":
            source_symbol,

        "date":
            str(
                rows[-1][
                    "date"
                ]
            ),

        "historyRows":
            len(rows),

        "daily":
            daily_score,

        "weekly":
            weekly_score,

        "monthly":
            monthly_score,

        "overall":
            overall_score,

        "dailySignal":
            regime_label(
                daily_score,
                config["type"]
            ),

        "weeklySignal":
            regime_label(
                weekly_score,
                config["type"]
            ),

        "monthlySignal":
            regime_label(
                monthly_score,
                config["type"]
            ),

        "overallSignal":
            regime_label(
                overall_score,
                config["type"]
            ),

        "details": {

            "daily":
                daily_details,

            "weekly":
                weekly_details,

            "monthly":
                monthly_details
        },

        "error":
            None
    }


# =========================================================
# PROXY SCORE HELPERS
#
# Used only for Smallcap and SME.
#
# Score = breadth + return strength
#
# 60% Breadth
# 40% Median return strength
# =========================================================

def return_strength_score(
    return_pct,
    timeframe
):

    value = safe_number(
        return_pct
    )


    if value is None:
        return None


    if timeframe == "daily":

        # -3% = 0
        #  0% = 50
        # +3% = 100

        return clamp(
            50
            +
            (
                value
                /
                3
            ) * 50
        )


    if timeframe == "weekly":

        # Using 1M stock-growth breadth
        # as medium-term proxy.
        #
        # -10% = 0
        #   0% = 50
        # +10% = 100

        return clamp(
            50
            +
            (
                value
                /
                10
            ) * 50
        )


    # Monthly / longer-term proxy
    #
    # -20% = 0
    #   0% = 50
    # +20% = 100

    return clamp(
        50
        +
        (
            value
            /
            20
        ) * 50
    )


def breadth_score(
    values
):

    clean = [

        safe_number(
            value
        )

        for value in values
    ]


    clean = [

        value

        for value in clean

        if value is not None
    ]


    if not clean:
        return None


    positive = sum(

        1

        for value in clean

        if value > 0
    )


    neutral = sum(

        1

        for value in clean

        if value == 0
    )


    ratio = (

        (
            positive
            +
            neutral * 0.5
        )

        /
        len(clean)
    )


    return (
        ratio * 100
    )


def proxy_timeframe_score(
    values,
    timeframe
):

    clean = [

        safe_number(
            value
        )

        for value in values
    ]


    clean = [

        value

        for value in clean

        if value is not None
    ]


    if len(clean) < 10:

        return (
            None,
            {
                "error":
                    "Insufficient proxy breadth",

                "availableStocks":
                    len(clean)
            }
        )


    breadth = (
        breadth_score(
            clean
        )
    )


    median_return = (
        median(
            clean
        )
    )


    return_strength = (
        return_strength_score(
            median_return,
            timeframe
        )
    )


    score = round(
        clamp(
            (
                breadth * 0.60
            )
            +
            (
                return_strength
                * 0.40
            )
        )
    )


    details = {

        "method":
            "Dashboard universe breadth proxy",

        "availableStocks":
            len(clean),

        "positiveBreadthPct":
            round(
                breadth,
                2
            ),

        "medianReturnPct":
            round(
                median_return,
                2
            ),

        "returnStrengthScore":
            round(
                return_strength,
                2
            )
    }


    return (
        score,
        details
    )


# =========================================================
# OVERALL SCORE
# =========================================================

def weighted_overall(
    daily,
    weekly,
    monthly
):

    weighted = [

        (
            daily,
            0.20
        ),

        (
            weekly,
            0.30
        ),

        (
            monthly,
            0.50
        )
    ]


    total = 0
    total_weight = 0


    for (
        score,
        weight
    ) in weighted:

        score = safe_number(
            score
        )


        if score is None:
            continue


        total += (
            score
            *
            weight
        )


        total_weight += (
            weight
        )


    if total_weight == 0:

        return None


    return round(
        total
        /
        total_weight
    )


# =========================================================
# SMALLCAP PROXY UNIVERSE
# =========================================================

def smallcap_proxy_stocks(
    stocks
):

    candidates = []


    for row in stocks:

        category = str(
            row.get(
                "marketCapCategory"
            )
            or ""
        ).strip().lower()


        if category != "small cap":
            continue


        market_cap = safe_number(
            row.get(
                "marketCapCr"
            )
        )


        if market_cap is None:
            continue


        candidates.append(
            row
        )


    # Largest 100 Small Cap category stocks.
    #
    # This is a proxy for NIFTY Smallcap 100,
    # not official constituent membership.

    candidates.sort(

        key=lambda row:
            safe_number(
                row.get(
                    "marketCapCr"
                )
            )
            or 0,

        reverse=True
    )


    return candidates[:100]


# =========================================================
# SME PROXY UNIVERSE
# =========================================================

def sme_proxy_stocks(
    stocks
):

    return [

        row

        for row in stocks

        if str(
            row.get(
                "board"
            )
            or ""
        ).strip().upper()
        == "SME"
    ]


# =========================================================
# BUILD PROXY ASSET
# =========================================================

def build_proxy_asset(
    name,
    stocks,
    market_date,
    source_description
):

    daily_values = [

        row.get(
            "changePct"
        )

        for row in stocks
    ]


    # Existing previous/current research values retained
    # inside stocks.json.
    #
    # 1M is used as weekly / medium-term breadth proxy.

    weekly_values = [

        row.get(
            "stockGrowth1M"
        )

        for row in stocks
    ]


    # 3M + 6M together make longer-term monthly proxy.

    monthly_values = []


    for row in stocks:

        growth_3m = safe_number(
            row.get(
                "stockGrowth3M"
            )
        )

        growth_6m = safe_number(
            row.get(
                "stockGrowth6M"
            )
        )


        values = [

            value

            for value in [
                growth_3m,
                growth_6m
            ]

            if value is not None
        ]


        if values:

            monthly_values.append(
                average(
                    values
                )
            )


    (
        daily_score,
        daily_details
    ) = proxy_timeframe_score(
        daily_values,
        "daily"
    )


    (
        weekly_score,
        weekly_details
    ) = proxy_timeframe_score(
        weekly_values,
        "weekly"
    )


    (
        monthly_score,
        monthly_details
    ) = proxy_timeframe_score(
        monthly_values,
        "monthly"
    )


    overall_score = (
        weighted_overall(
            daily_score,
            weekly_score,
            monthly_score
        )
    )


    available = (
        daily_score is not None
        or
        weekly_score is not None
        or
        monthly_score is not None
    )


    return {

        "name":
            name,

        "type":
            "equity",

        "available":
            available,

        "source":
            source_description,

        "sourceSymbol":
            None,

        "date":
            market_date,

        "universeSize":
            len(stocks),

        "daily":
            daily_score,

        "weekly":
            weekly_score,

        "monthly":
            monthly_score,

        "overall":
            overall_score,

        "dailySignal":
            regime_label(
                daily_score,
                "equity"
            ),

        "weeklySignal":
            regime_label(
                weekly_score,
                "equity"
            ),

        "monthlySignal":
            regime_label(
                monthly_score,
                "equity"
            ),

        "overallSignal":
            regime_label(
                overall_score,
                "equity"
            ),

        "details": {

            "daily":
                daily_details,

            "weekly":
                weekly_details,

            "monthly":
                monthly_details
        },

        "proxy":
            True,

        "proxyNote":
            (
                "Breadth/momentum proxy from "
                "dashboard NSE stock universe; "
                "not official index historical score."
            ),

        "error":
            (
                None
                if available
                else
                "Insufficient proxy data"
            )
    }


# =========================================================
# BUILD ALL REGIMES
# =========================================================

def build_all_regimes(
    stocks,
    market_date
):

    result = {}


    # =====================================================
    # DIRECT ASSETS
    # =====================================================

    for (
        asset_key,
        config
    ) in DIRECT_ASSETS.items():

        print()
        print(
            "=" * 60
        )

        print(
            f"BUILDING REGIME: "
            f"{config['name']}"
        )

        print(
            "=" * 60
        )


        try:

            result[
                asset_key
            ] = build_direct_asset(
                asset_key,
                config
            )


        except Exception as exc:

            result[
                asset_key
            ] = {

                "name":
                    config["name"],

                "type":
                    config["type"],

                "available":
                    False,

                "daily":
                    None,

                "weekly":
                    None,

                "monthly":
                    None,

                "overall":
                    None,

                "dailySignal":
                    regime_label(
                        None,
                        config["type"]
                    ),

                "weeklySignal":
                    regime_label(
                        None,
                        config["type"]
                    ),

                "monthlySignal":
                    regime_label(
                        None,
                        config["type"]
                    ),

                "overallSignal":
                    regime_label(
                        None,
                        config["type"]
                    ),

                "error":
                    str(exc)
            }


    # =====================================================
    # SMALLCAP PROXY
    # =====================================================

    print()
    print(
        "=" * 60
    )

    print(
        "BUILDING REGIME: "
        "NIFTY Smallcap 100 Proxy"
    )

    print(
        "=" * 60
    )


    smallcaps = (
        smallcap_proxy_stocks(
            stocks
        )
    )


    print(
        "Smallcap proxy universe:",
        len(smallcaps)
    )


    result[
        "smallcap100"
    ] = build_proxy_asset(

        name=
            "NIFTY Smallcap 100",

        stocks=
            smallcaps,

        market_date=
            market_date,

        source_description=
            (
                "NSE dashboard Small Cap "
                "top-100 market-cap breadth proxy"
            )
    )


    # =====================================================
    # SME PROXY
    # =====================================================

    print()
    print(
        "=" * 60
    )

    print(
        "BUILDING REGIME: "
        "NIFTY SME Emerge Proxy"
    )

    print(
        "=" * 60
    )


    sme_stocks = (
        sme_proxy_stocks(
            stocks
        )
    )


    print(
        "SME proxy universe:",
        len(sme_stocks)
    )


    result[
        "sme"
    ] = build_proxy_asset(

        name=
            "NIFTY SME Emerge",

        stocks=
            sme_stocks,

        market_date=
            market_date,

        source_description=
            (
                "Official NSE SME board "
                "dashboard breadth proxy"
            )
    )


    return result


# =========================================================
# HEADER SCORE
# =========================================================

def get_header_scores(
    regimes
):

    nifty = (
        regimes.get(
            "nifty50"
        )
        or {}
    )


    return {

        "daily":
            safe_number(
                nifty.get(
                    "daily"
                )
            ),

        "weekly":
            safe_number(
                nifty.get(
                    "weekly"
                )
            ),

        "monthly":
            safe_number(
                nifty.get(
                    "monthly"
                )
            )
    }


# =========================================================
# MAIN
# =========================================================

def main():

    meta = load_json(
        META_FILE,
        {}
    )


    stocks_data = load_json(
        STOCKS_FILE,
        []
    )


    if isinstance(
        stocks_data,
        dict
    ):

        stocks = (
            stocks_data.get(
                "stocks"
            )
            or []
        )

    else:

        stocks = (
            stocks_data
            if isinstance(
                stocks_data,
                list
            )
            else []
        )


    market_date = (

        meta.get(
            "marketDate"
        )

        or

        meta.get(
            "deliveryDate"
        )

        or

        datetime.now(
            timezone.utc
        )
        .date()
        .isoformat()
    )


    print()

    print(
        "Building multi-asset "
        "market regime..."
    )


    print(
        "Stocks loaded:",
        len(stocks)
    )


    regimes = (
        build_all_regimes(
            stocks,
            market_date
        )
    )


    # =====================================================
    # MULTI TIMEFRAME VIEW
    # =====================================================

    meta[
        "multiTimeframeMarketView"
    ] = regimes


    # =====================================================
    # HEADER COMPATIBILITY
    # =====================================================

    header_scores = (
        get_header_scores(
            regimes
        )
    )


    meta[
        "dailyRegimeScore"
    ] = (
        header_scores[
            "daily"
        ]
    )


    meta[
        "weeklyRegimeScore"
    ] = (
        header_scores[
            "weekly"
        ]
    )


    meta[
        "monthlyRegimeScore"
    ] = (
        header_scores[
            "monthly"
        ]
    )


    meta[
        "marketRegime"
    ] = {

        "daily":
            header_scores[
                "daily"
            ],

        "weekly":
            header_scores[
                "weekly"
            ],

        "monthly":
            header_scores[
                "monthly"
            ]
    }


    meta[
        "marketRegimeDate"
    ] = (
        market_date
    )


    # =====================================================
    # METHOD / SOURCES
    # =====================================================

    meta[
        "marketRegimeMethod"
    ] = {

        "scoreRange":
            "0-100",

        "directAssets":
            (
                "NIFTY 50, NIFTY Midcap 100 "
                "and Gold use historical price series"
            ),

        "smallcap100":
            (
                "Top 100 dashboard Small Cap stocks "
                "by current market cap; breadth/momentum proxy"
            ),

        "sme":
            (
                "Official NSE SME-board stocks from "
                "dashboard universe; breadth/momentum proxy"
            ),

        "proxyWeights": {

            "breadth":
                60,

            "medianReturnStrength":
                40
        },

        "overallWeights": {

            "daily":
                20,

            "weekly":
                30,

            "monthly":
                50
        },

        "bands": {

            "75-100":
                "Aggressive / Very Strong",

            "65-74":
                "Overweight / Strong",

            "55-64":
                "Selective / Positive",

            "45-54":
                "Warning / Neutral",

            "35-44":
                "Reduce / Weak",

            "0-34":
                "Defensive"
        }
    }


    meta[
        "marketRegimeGeneratedAt"
    ] = (

        datetime.now(
            timezone.utc
        )
        .isoformat()
    )


    # =====================================================
    # WRITE META
    # =====================================================

    META_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    with open(
        META_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(

            meta,

            file,

            indent=2,

            ensure_ascii=False
        )


    # =====================================================
    # LOG
    # =====================================================

    print()

    print(
        "=" * 60
    )

    print(
        "MULTI-TIMEFRAME MARKET VIEW"
    )

    print(
        "=" * 60
    )


    display_order = [

        "nifty50",
        "midcap100",
        "smallcap100",
        "sme",
        "gold"
    ]


    for key in display_order:

        asset = (
            regimes.get(
                key
            )
            or {}
        )


        print()

        print(
            asset.get(
                "name",
                key
            )
        )


        print(
            "  Source :",
            asset.get(
                "source"
            )
        )


        print(
            "  Symbol :",
            asset.get(
                "sourceSymbol"
            )
        )


        print(
            "  Universe:",
            asset.get(
                "universeSize"
            )
        )


        print(
            "  Date   :",
            asset.get(
                "date"
            )
        )


        print(
            "  Daily  :",
            asset.get(
                "daily"
            )
        )


        print(
            "  Weekly :",
            asset.get(
                "weekly"
            )
        )


        print(
            "  Monthly:",
            asset.get(
                "monthly"
            )
        )


        print(
            "  Overall:",
            asset.get(
                "overall"
            )
        )


        if asset.get(
            "proxy"
        ):

            print(
                "  Proxy  : YES"
            )


        if asset.get(
            "error"
        ):

            print(
                "  Error  :",
                asset.get(
                    "error"
                )
            )


    print()

    print(
        "Header regime:"
    )

    print(
        header_scores
    )


    print()

    print(
        "Market regime saved to:",
        META_FILE
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
