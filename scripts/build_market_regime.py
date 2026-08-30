import json
import math
from pathlib import Path
from datetime import datetime, timezone

import requests


ROOT = Path(__file__).resolve().parents[1]
META_FILE = ROOT / "data" / "meta.json"

YAHOO_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/"
    "%5ENSEI?range=5y&interval=1d&events=history"
)


# =========================================================
# HELPERS
# =========================================================

def safe_number(value):
    try:
        n = float(value)

        if math.isfinite(n):
            return n

    except Exception:
        pass

    return None


def average(values):
    values = [
        safe_number(v)
        for v in values
    ]

    values = [
        v for v in values
        if v is not None
    ]

    if not values:
        return None

    return sum(values) / len(values)


def pct_change(current, previous):
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


def clamp(value, low=0, high=100):
    return max(
        low,
        min(high, value)
    )


# =========================================================
# RSI
# =========================================================

def calculate_rsi(values, period=14):
    values = [
        safe_number(v)
        for v in values
    ]

    values = [
        v for v in values
        if v is not None
    ]

    if len(values) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(
        len(values) - period,
        len(values)
    ):
        change = (
            values[i]
            - values[i - 1]
        )

        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = average(gains)
    avg_loss = average(losses)

    if avg_gain is None:
        return None

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (
        100 / (1 + rs)
    )


# =========================================================
# YAHOO NIFTY DATA
# =========================================================

def fetch_nifty_daily():

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; IndiaMarketDashboard/1.0)"
        )
    }

    response = requests.get(
        YAHOO_URL,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    payload = response.json()

    result = (
        payload
        .get("chart", {})
        .get("result", [])
    )

    if not result:
        raise RuntimeError(
            "Yahoo returned no NIFTY data"
        )

    data = result[0]

    timestamps = (
        data.get("timestamp")
        or []
    )

    quote = (
        data
        .get("indicators", {})
        .get("quote", [{}])[0]
    )

    closes = (
        quote.get("close")
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

    if len(rows) < 100:
        raise RuntimeError(
            "Not enough NIFTY history"
        )

    return rows


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

            iso = date.isocalendar()

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
                "Invalid resample mode"
            )

        buckets[key] = row

    result = list(
        buckets.values()
    )

    result.sort(
        key=lambda x: x["date"]
    )

    return result


# =========================================================
# SCORE COMPONENT
# =========================================================

def score_series(
    values,
    fast_period,
    slow_period,
    momentum_period,
    high_period
):

    values = [
        safe_number(v)
        for v in values
    ]

    values = [
        v for v in values
        if v is not None
    ]

    minimum_required = max(
        slow_period,
        momentum_period + 1,
        high_period,
        15
    )

    if len(values) < minimum_required:
        return None, {}


    latest = values[-1]


    fast_ma = average(
        values[-fast_period:]
    )

    slow_ma = average(
        values[-slow_period:]
    )


    momentum_reference = (
        values[-(
            momentum_period + 1
        )]
    )

    momentum = pct_change(
        latest,
        momentum_reference
    )


    rsi = calculate_rsi(
        values,
        14
    )


    recent_high = max(
        values[-high_period:]
    )

    distance_from_high = pct_change(
        latest,
        recent_high
    )


    # =====================================================
    # COMPONENT 1
    # PRICE VS FAST MA
    # 25 POINTS
    # =====================================================

    price_fast_score = 0

    if (
        fast_ma is not None
        and latest >= fast_ma
    ):
        price_fast_score = 25


    # =====================================================
    # COMPONENT 2
    # FAST MA VS SLOW MA
    # 25 POINTS
    # =====================================================

    trend_score = 0

    if (
        fast_ma is not None
        and slow_ma is not None
        and fast_ma >= slow_ma
    ):
        trend_score = 25


    # =====================================================
    # COMPONENT 3
    # MOMENTUM
    # 25 POINTS
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
    # COMPONENT 4
    # RSI + DISTANCE FROM HIGH
    # 25 POINTS
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


    score = (
        price_fast_score
        + trend_score
        + momentum_score
        + strength_score
    )


    score = round(
        clamp(score)
    )


    details = {
        "latest": round(
            latest,
            2
        ),
        "fastMA": (
            round(fast_ma, 2)
            if fast_ma is not None
            else None
        ),
        "slowMA": (
            round(slow_ma, 2)
            if slow_ma is not None
            else None
        ),
        "momentumPct": (
            round(momentum, 2)
            if momentum is not None
            else None
        ),
        "rsi14": (
            round(rsi, 2)
            if rsi is not None
            else None
        ),
        "distanceFromHighPct": (
            round(
                distance_from_high,
                2
            )
            if distance_from_high
            is not None
            else None
        )
    }

    return score, details


# =========================================================
# BUILD REGIME
# =========================================================

def build_regime():

    rows = fetch_nifty_daily()

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
    # Fast 20 DMA
    # Slow 50 DMA
    # Momentum 5 trading days
    # High 20 days
    # =====================================================

    daily_score, daily_details = (
        score_series(
            daily_values,
            fast_period=20,
            slow_period=50,
            momentum_period=5,
            high_period=20
        )
    )


    # =====================================================
    # WEEKLY
    #
    # Fast 10 week MA
    # Slow 30 week MA
    # Momentum 4 weeks
    # High 13 weeks
    # =====================================================

    weekly_score, weekly_details = (
        score_series(
            weekly_values,
            fast_period=10,
            slow_period=30,
            momentum_period=4,
            high_period=13
        )
    )


    # =====================================================
    # MONTHLY
    #
    # Fast 6 month MA
    # Slow 10 month MA
    # Momentum 3 months
    # High 12 months
    # =====================================================

    monthly_score, monthly_details = (
        score_series(
            monthly_values,
            fast_period=6,
            slow_period=10,
            momentum_period=3,
            high_period=12
        )
    )


    return {
        "daily": daily_score,
        "weekly": weekly_score,
        "monthly": monthly_score,

        "details": {
            "daily": daily_details,
            "weekly": weekly_details,
            "monthly": monthly_details
        },

        "source": "NIFTY 50 Yahoo Finance chart data",

        "asOfDate": str(
            rows[-1]["date"]
        )
    }


# =========================================================
# UPDATE META.JSON
# =========================================================

def main():

    if META_FILE.exists():

        with open(
            META_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            meta = json.load(f)

    else:
        meta = {}


    try:

        regime = build_regime()


        meta[
            "monthlyRegimeScore"
        ] = regime["monthly"]


        meta[
            "weeklyRegimeScore"
        ] = regime["weekly"]


        meta[
            "dailyRegimeScore"
        ] = regime["daily"]


        meta[
            "marketRegime"
        ] = {
            "monthly":
                regime["monthly"],

            "weekly":
                regime["weekly"],

            "daily":
                regime["daily"]
        }


        meta[
            "marketRegimeDetails"
        ] = regime["details"]


        meta[
            "marketRegimeSource"
        ] = regime["source"]


        meta[
            "marketRegimeDate"
        ] = regime["asOfDate"]


        print(
            "Market regime:",
            {
                "monthly":
                    regime["monthly"],

                "weekly":
                    regime["weekly"],

                "daily":
                    regime["daily"],

                "date":
                    regime["asOfDate"]
            }
        )


    except Exception as exc:

        print(
            "Market regime build failed:",
            exc
        )

        meta.setdefault(
            "monthlyRegimeScore",
            None
        )

        meta.setdefault(
            "weeklyRegimeScore",
            None
        )

        meta.setdefault(
            "dailyRegimeScore",
            None
        )


    META_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    with open(
        META_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            meta,
            f,
            indent=2,
            ensure_ascii=False
        )


if __name__ == "__main__":
    main()
