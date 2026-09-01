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
META_FILE = ROOT / "data" / "meta.json"


# =========================================================
# ASSETS
# =========================================================
#
# IMPORTANT:
# Every asset is calculated independently.
#
# If one asset fails:
# - entire workflow will NOT fail
# - that asset will show Pending
#
# Gold is kept separate from equity.
# =========================================================

ASSETS = {

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

    "smallcap100": {
        "name": "NIFTY Smallcap 100",
        "type": "equity",
        "symbols": [
            "NIFTY_SMLCAP_100.NS",
            "^CNXSC"
        ]
    },

    "sme": {
        "name": "NIFTY SME Emerge",
        "type": "equity",
        "symbols": [
            "NIFTY_SME_EMERGE.NS",
            "^NIFTYSME"
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

        n = float(value)

        if math.isfinite(n):
            return n

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
        min(high, value)
    )


def average(values):

    clean = []

    for value in values:

        n = safe_number(value)

        if n is not None:
            clean.append(n)

    if not clean:
        return None

    return sum(clean) / len(clean)


def pct_change(
    current,
    previous
):

    current = safe_number(current)
    previous = safe_number(previous)

    if (
        current is None
        or previous is None
        or previous == 0
    ):
        return None

    return (
        (current / previous) - 1
    ) * 100


# =========================================================
# RSI
# =========================================================

def calculate_rsi(
    values,
    period=14
):

    clean = []

    for value in values:

        n = safe_number(value)

        if n is not None:
            clean.append(n)

    if len(clean) < period + 1:
        return None


    gains = []
    losses = []


    start_index = (
        len(clean)
        - period
    )


    for i in range(
        start_index,
        len(clean)
    ):

        change = (
            clean[i]
            - clean[i - 1]
        )


        if change > 0:

            gains.append(change)
            losses.append(0)

        else:

            gains.append(0)
            losses.append(
                abs(change)
            )


    avg_gain = average(gains)
    avg_loss = average(losses)


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
            (1 + rs)
        )
    )


# =========================================================
# REGIME LABEL
# =========================================================

def regime_label(
    score,
    asset_type="equity"
):

    score = safe_number(score)


    if score is None:

        return {
            "label": "Pending",
            "signal": "pending",
            "emoji": "⚪"
        }


    # =====================================================
    # GOLD WORDING
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
    # EQUITY WORDING
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
# YAHOO DOWNLOAD
# =========================================================

def yahoo_chart_url(symbol):

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


def fetch_symbol_history(symbol):

    url = yahoo_chart_url(
        symbol
    )


    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )


    response.raise_for_status()


    payload = response.json()


    chart = (
        payload.get("chart")
        or {}
    )


    error = chart.get("error")


    if error:

        raise RuntimeError(
            str(error)
        )


    results = (
        chart.get("result")
        or []
    )


    if not results:

        raise RuntimeError(
            f"No Yahoo result for {symbol}"
        )


    result = results[0]


    timestamps = (
        result.get("timestamp")
        or []
    )


    indicators = (
        result.get("indicators")
        or {}
    )


    quote_data = (
        indicators.get("quote")
        or [{}]
    )[0]


    closes = (
        quote_data.get("close")
        or []
    )


    rows = []


    for ts, close in zip(
        timestamps,
        closes
    ):

        close = safe_number(close)

        if close is None:
            continue


        dt = datetime.fromtimestamp(
            ts,
            tz=timezone.utc
        )


        rows.append({
            "date": dt.date(),
            "close": close
        })


    rows.sort(
        key=lambda x: x["date"]
    )


    if len(rows) < 100:

        raise RuntimeError(
            f"Insufficient history for {symbol}: "
            f"{len(rows)} rows"
        )


    return rows


# =========================================================
# TRY SYMBOLS
# =========================================================

def fetch_asset_history(
    asset_key,
    config
):

    errors = []


    for symbol in config["symbols"]:

        try:

            print(
                f"Trying {asset_key}: {symbol}"
            )


            rows = fetch_symbol_history(
                symbol
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

            message = (
                f"{symbol}: {exc}"
            )

            errors.append(message)

            print(
                f"Failed {asset_key}: "
                f"{message}"
            )


            time.sleep(1)


    return (
        None,
        None,
        " | ".join(errors)
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

        date = row["date"]


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


        # because rows are sorted,
        # latest row overwrites earlier row
        buckets[key] = row


    result = list(
        buckets.values()
    )


    result.sort(
        key=lambda x: x["date"]
    )


    return result


# =========================================================
# CORE SCORE
# =========================================================
#
# Total = 100
#
# 1. Price vs Fast MA       25
# 2. Fast MA vs Slow MA     25
# 3. Momentum               25
# 4. RSI + distance high    25
#
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

        n = safe_number(value)

        if n is not None:
            clean.append(n)


    minimum_required = max(
        slow_period,
        momentum_period + 1,
        high_period,
        15
    )


    if (
        len(clean)
        < minimum_required
    ):

        return (
            None,
            {
                "error":
                    "Insufficient history"
            }
        )


    latest = clean[-1]


    fast_ma = average(
        clean[-fast_period:]
    )


    slow_ma = average(
        clean[-slow_period:]
    )


    momentum_reference = (
        clean[
            -(
                momentum_period
                + 1
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
        clean[-high_period:]
    )


    distance_from_high = pct_change(
        latest,
        recent_high
    )


    # =====================================================
    # 1. PRICE VS FAST MA
    # =====================================================

    price_fast_score = 0


    if (
        fast_ma is not None
        and latest >= fast_ma
    ):

        price_fast_score = 25


    # =====================================================
    # 2. FAST MA VS SLOW MA
    # =====================================================

    trend_score = 0


    if (
        fast_ma is not None
        and slow_ma is not None
        and fast_ma >= slow_ma
    ):

        trend_score = 25


    # =====================================================
    # 3. MOMENTUM
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
    # 4. RSI + DISTANCE FROM HIGH
    # =====================================================

    strength_score = 0


    if rsi is not None:

        if rsi >= 60:

            strength_score += 15


        elif rsi >= 50:

            strength_score += 10


        elif rsi >= 40:

            strength_score += 5


    if distance_from_high is not None:

        if distance_from_high >= -3:

            strength_score += 10


        elif distance_from_high >= -7:

            strength_score += 7


        elif distance_from_high >= -12:

            strength_score += 4


    total_score = (
        price_fast_score
        + trend_score
        + momentum_score
        + strength_score
    )


    total_score = round(
        clamp(total_score)
    )


    details = {

        "latest": round(
            latest,
            2
        ),

        "fastMA": (
            round(
                fast_ma,
                2
            )
            if fast_ma is not None
            else None
        ),

        "slowMA": (
            round(
                slow_ma,
                2
            )
            if slow_ma is not None
            else None
        ),

        "momentumPct": (
            round(
                momentum,
                2
            )
            if momentum is not None
            else None
        ),

        "rsi14": (
            round(
                rsi,
                2
            )
            if rsi is not None
            else None
        ),

        "distanceFromHighPct": (
            round(
                distance_from_high,
                2
            )
            if (
                distance_from_high
                is not None
            )
            else None
        ),

        "components": {

            "priceVsFastMA":
                price_fast_score,

            "trend":
                trend_score,

            "momentum":
                momentum_score,

            "strength":
                strength_score
        }
    }


    return (
        total_score,
        details
    )


# =========================================================
# BUILD ONE ASSET
# =========================================================

def build_asset_regime(
    asset_key,
    config
):

    (
        rows,
        source_symbol,
        fetch_error
    ) = fetch_asset_history(
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


    # =====================================================
    # DAILY
    #
    # 20 DMA
    # 50 DMA
    # 5-day momentum
    # 20-day high
    # =====================================================

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


    # =====================================================
    # WEEKLY
    #
    # 10-week MA
    # 30-week MA
    # 4-week momentum
    # 13-week high
    # =====================================================

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


    # =====================================================
    # MONTHLY
    #
    # 6-month MA
    # 10-month MA
    # 3-month momentum
    # 12-month high
    # =====================================================

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


    # =====================================================
    # OVERALL
    #
    # Daily   20%
    # Weekly  30%
    # Monthly 50%
    #
    # Longer timeframe receives higher weight.
    # =====================================================

    scores_for_overall = [

        (
            daily_score,
            0.20
        ),

        (
            weekly_score,
            0.30
        ),

        (
            monthly_score,
            0.50
        )
    ]


    weighted_total = 0
    weight_total = 0


    for (
        score,
        weight
    ) in scores_for_overall:

        if score is None:
            continue

        weighted_total += (
            score *
            weight
        )

        weight_total += weight


    overall_score = None


    if weight_total > 0:

        overall_score = round(
            weighted_total /
            weight_total
        )


    return {

        "name":
            config["name"],

        "type":
            config["type"],

        "available":
            True,

        "sourceSymbol":
            source_symbol,

        "date":
            str(
                rows[-1]["date"]
            ),

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
# BUILD ALL ASSETS
# =========================================================

def build_all_regimes():

    result = {}


    for (
        asset_key,
        config
    ) in ASSETS.items():

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
            ] = build_asset_regime(
                asset_key,
                config
            )


        except Exception as exc:

            print(
                f"Unexpected failure "
                f"for {asset_key}: "
                f"{exc}"
            )


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

                "error":
                    str(exc)
            }


    return result


# =========================================================
# HEADER SCORE
# =========================================================
#
# Existing header stays compatible.
#
# Header currently uses NIFTY 50 regime.
#
# Later, if desired, header can be changed to:
# Midcap + Smallcap composite.
#
# =========================================================

def get_header_scores(
    regimes
):

    nifty = (
        regimes.get("nifty50")
        or {}
    )


    return {

        "daily":
            safe_number(
                nifty.get("daily")
            ),

        "weekly":
            safe_number(
                nifty.get("weekly")
            ),

        "monthly":
            safe_number(
                nifty.get("monthly")
            )
    }


# =========================================================
# MAIN
# =========================================================

def main():

    # =====================================================
    # LOAD EXISTING META
    # =====================================================

    if META_FILE.exists():

        with open(
            META_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            meta = json.load(file)

    else:

        meta = {}


    print()
    print(
        "Building multi-asset "
        "market regime..."
    )


    regimes = build_all_regimes()


    # =====================================================
    # FULL MULTI-TIMEFRAME VIEW
    # =====================================================

    meta[
        "multiTimeframeMarketView"
    ] = regimes


    # =====================================================
    # HEADER BACKWARD COMPATIBILITY
    # =====================================================

    header_scores = (
        get_header_scores(
            regimes
        )
    )


    meta[
        "dailyRegimeScore"
    ] = (
        header_scores["daily"]
    )


    meta[
        "weeklyRegimeScore"
    ] = (
        header_scores["weekly"]
    )


    meta[
        "monthlyRegimeScore"
    ] = (
        header_scores["monthly"]
    )


    meta[
        "marketRegime"
    ] = {

        "daily":
            header_scores["daily"],

        "weekly":
            header_scores["weekly"],

        "monthly":
            header_scores["monthly"]
    }


    # =====================================================
    # SOURCE / METHOD
    # =====================================================

    meta[
        "marketRegimeMethod"
    ] = {

        "scoreRange":
            "0-100",

        "daily":
            (
                "20DMA / 50DMA / "
                "5-day momentum / "
                "RSI / 20-day high"
            ),

        "weekly":
            (
                "10-week MA / "
                "30-week MA / "
                "4-week momentum / "
                "RSI / 13-week high"
            ),

        "monthly":
            (
                "6-month MA / "
                "10-month MA / "
                "3-month momentum / "
                "RSI / 12-month high"
            ),

        "overallWeights": {
            "daily": 20,
            "weekly": 30,
            "monthly": 50
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


    for (
        key,
        asset
    ) in regimes.items():

        print()

        print(
            asset.get(
                "name",
                key
            )
        )

        print(
            "  Symbol :",
            asset.get(
                "sourceSymbol"
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


        if asset.get("error"):

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
