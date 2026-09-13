import json
import math
from datetime import datetime, timezone
from pathlib import Path


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "data"

STOCKS_PATH = DATA / "stocks.json"

OUTPUT_PATH = DATA / "big_move_scanner.json"


# =========================================================
# SETTINGS
# =========================================================

MIN_MARKET_CAP_CR = 100


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

    DATA.mkdir(
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


# =========================================================
# NUMBER HELPERS
# =========================================================

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
                .replace("Cr", "")
                .replace("x", "")
                .strip()
            )

            if not value:
                return None

        value = float(value)

        if not math.isfinite(value):
            return None

        return value

    except Exception:

        return None


def positive_float(value):

    value = safe_float(
        value
    )

    if (
        value is None
        or
        value <= 0
    ):

        return None

    return value


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


def clamp(
    value,
    minimum=0,
    maximum=100,
):

    value = safe_float(
        value
    )

    if value is None:
        return None

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


# =========================================================
# BOOLEAN HELPERS
# =========================================================

def truthy(value):

    if value is True:
        return True

    if isinstance(
        value,
        str,
    ):

        return (
            value.strip().lower()
            in {
                "yes",
                "true",
                "1",
                "ready",
                "confirmed",
            }
        )

    return False


# =========================================================
# STOCK FIELD HELPERS
# =========================================================

def company_name(row):

    return (
        row.get("name")
        or
        row.get("companyName")
        or
        row.get("symbol")
        or
        ""
    )


def symbol(row):

    return str(
        row.get("symbol")
        or ""
    ).strip().upper()


def market_cap(row):

    return positive_float(
        row.get(
            "marketCapCr"
        )
    )


def price(row):

    return positive_float(
        row.get(
            "price"
        )
    )


# =========================================================
# RETURN HELPERS
# =========================================================

def return_1m(row):

    return round_or_none(
        row.get(
            "stockGrowth1M"
        )
    )


def return_3m(row):

    value = row.get(
        "stockGrowth3M"
    )

    if value is None:

        value = row.get(
            "rsReturn3M"
        )

    return round_or_none(
        value
    )


def return_6m(row):

    value = row.get(
        "stockGrowth6M"
    )

    if value is None:

        value = row.get(
            "rsReturn6M"
        )

    return round_or_none(
        value
    )


def return_1y(row):

    value = row.get(
        "rsReturn12M"
    )

    return round_or_none(
        value
    )


# =========================================================
# RATING HELPERS
# =========================================================

def rs_rating(row):

    value = safe_float(
        row.get(
            "rsRating"
        )
    )

    if value is None:
        return None

    return int(
        max(
            1,
            min(
                99,
                round(value),
            ),
        )
    )


def stock_momentum_rating(row):

    value = safe_float(
        row.get(
            "stockMomentumRating"
        )
    )

    if value is None:
        return None

    return int(
        max(
            1,
            min(
                99,
                round(value),
            ),
        )
    )


def industry_rating(row):

    value = safe_float(
        row.get(
            "industryRating"
        )
    )

    if value is None:
        return None

    return int(
        max(
            1,
            min(
                99,
                round(value),
            ),
        )
    )


# =========================================================
# RESEARCH SCORE HELPERS
# =========================================================

def score_value(
    row,
    field,
):

    return clamp(
        row.get(
            field
        )
    )


def research_reasons(row):

    reasons = row.get(
        "researchReasons"
    )

    if isinstance(
        reasons,
        dict,
    ):

        return reasons

    return {}


def reason_to_text(value):

    if value is None:
        return ""

    if isinstance(
        value,
        str,
    ):

        return value

    if isinstance(
        value,
        dict,
    ):

        parts = []

        for key in [
            "reason",
            "description",
            "note",
            "source",
        ]:

            text = value.get(
                key
            )

            if text:
                parts.append(
                    str(text)
                )

        return " ".join(
            parts
        )

    if isinstance(
        value,
        list,
    ):

        return " ".join(
            reason_to_text(x)
            for x in value
        )

    return str(
        value
    )


def combined_research_text(row):

    blocks = []

    reasons = research_reasons(
        row
    )

    for value in reasons.values():

        text = reason_to_text(
            value
        )

        if text:
            blocks.append(
                text
            )

    for field in [
        "tmvDetails",
        "gfcDetails",
        "fundamentalReason",
        "growthReason",
        "capexReason",
        "tailwindReason",
    ]:

        value = row.get(
            field
        )

        text = reason_to_text(
            value
        )

        if text:
            blocks.append(
                text
            )

    return (
        " ".join(blocks)
        .lower()
    )


# =========================================================
# FUNDAMENTAL / BUSINESS TRIGGER ENGINE
# =========================================================

TRIGGER_KEYWORDS = {

    "Earnings Acceleration": [
        "earnings growth",
        "earnings acceleration",
        "profit growth",
        "pat growth",
        "revenue growth",
        "sales growth",
        "strong result",
        "strong results",
    ],

    "Margin Expansion": [
        "margin expansion",
        "margin improved",
        "margin improvement",
        "ebitda margin",
        "operating margin",
    ],

    "Order Win": [
        "order win",
        "order wins",
        "new order",
        "order received",
        "order book",
        "orderbook",
        "contract awarded",
        "contract win",
    ],

    "CAPEX": [
        "capex",
        "capital expenditure",
        "investment programme",
        "investment program",
    ],

    "Capacity Expansion": [
        "capacity expansion",
        "capacity addition",
        "capacity increase",
        "expansion project",
        "new facility",
        "new plant",
        "new unit",
        "commissioning",
    ],

    "New Product": [
        "new product",
        "product launch",
        "new launch",
        "new segment",
        "product portfolio",
    ],

    "Fund Raising": [
        "fund raising",
        "fundraising",
        "preferential issue",
        "preferential allotment",
        "warrant",
        "warrants",
        "qip",
        "qualified institutional placement",
        "rights issue",
    ],

    "Corporate Action": [
        "bonus",
        "stock split",
        "split",
        "merger",
        "demerger",
        "acquisition",
        "buyback",
        "promoter purchase",
    ],

    "Industry Tailwind": [
        "tailwind",
        "industry growth",
        "sector growth",
        "strong demand",
        "demand growth",
        "market expansion",
        "import substitution",
        "value migration",
    ],

}


def detect_text_triggers(row):

    text = combined_research_text(
        row
    )

    detected = []

    if not text:
        return detected

    for (
        label,
        keywords,
    ) in TRIGGER_KEYWORDS.items():

        for keyword in keywords:

            if keyword in text:

                detected.append(
                    label
                )

                break

    return detected


# =========================================================
# SCORE-BASED TRIGGER ENGINE
# =========================================================

def detect_score_triggers(row):

    detected = []

    future_growth = score_value(
        row,
        "futureGrowth",
    )

    fundamental = score_value(
        row,
        "fundamentalQuality",
    )

    capex = score_value(
        row,
        "capexScore",
    )

    tailwind = score_value(
        row,
        "tailwindScore",
    )

    macro = score_value(
        row,
        "macroSupport",
    )

    value_migration = score_value(
        row,
        "valueMigration",
    )


    if (
        future_growth is not None
        and
        future_growth >= 70
    ):

        detected.append(
            "Growth"
        )


    if (
        fundamental is not None
        and
        fundamental >= 70
    ):

        detected.append(
            "Fundamental Quality"
        )


    if (
        capex is not None
        and
        capex >= 70
    ):

        detected.append(
            "CAPEX"
        )


    if (
        tailwind is not None
        and
        tailwind >= 70
    ):

        detected.append(
            "Industry Tailwind"
        )


    if (
        macro is not None
        and
        macro >= 70
    ):

        detected.append(
            "Macro Support"
        )


    if (
        value_migration is not None
        and
        value_migration >= 70
    ):

        detected.append(
            "Value Migration"
        )


    return detected


def get_triggers(row):

    triggers = []

    for trigger in (
        detect_text_triggers(row)
        +
        detect_score_triggers(row)
    ):

        if trigger not in triggers:

            triggers.append(
                trigger
            )

    return triggers


# =========================================================
# KEY TRIGGER
# =========================================================

TRIGGER_PRIORITY = [

    "Earnings Acceleration",

    "Margin Expansion",

    "Order Win",

    "Capacity Expansion",

    "CAPEX",

    "New Product",

    "Fund Raising",

    "Corporate Action",

    "Fundamental Quality",

    "Growth",

    "Industry Tailwind",

    "Value Migration",

    "Macro Support",

]


def key_trigger(
    triggers,
):

    for item in TRIGGER_PRIORITY:

        if item in triggers:

            return item

    if triggers:

        return triggers[0]

    return None


# =========================================================
# PRELIMINARY MOMENTUM SCORE
# =========================================================
#
# Maximum = 35 points
#
# RS Rating              = 15
# Stock Momentum Rating  = 10
# Industry Rating        = 10
#
# These are already available from the existing
# MY MARKET RESEARCH engine.
#
# =========================================================

def momentum_score(row):

    score = 0.0

    available = 0.0


    rs = rs_rating(
        row
    )

    if rs is not None:

        available += 15

        score += (
            rs
            /
            99
            *
            15
        )


    momentum = stock_momentum_rating(
        row
    )

    if momentum is not None:

        available += 10

        score += (
            momentum
            /
            99
            *
            10
        )


    industry = industry_rating(
        row
    )

    if industry is not None:

        available += 10

        score += (
            industry
            /
            99
            *
            10
        )


    return (
        score,
        available,
    )


# =========================================================
# RETURN QUALITY SCORE
# =========================================================
#
# Maximum = 15 points
#
# This is NOT a substitute for chart structure.
#
# It only measures whether price momentum is already
# strong across multiple periods.
#
# =========================================================

def score_return(
    value,
    full_threshold,
):

    value = safe_float(
        value
    )

    if value is None:

        return None

    if value <= 0:

        return 0

    ratio = (
        value
        /
        full_threshold
    )

    return min(
        1,
        ratio,
    )


def return_quality_score(row):

    periods = [

        (
            return_1m(row),
            15,
            4,
        ),

        (
            return_3m(row),
            30,
            4,
        ),

        (
            return_6m(row),
            50,
            4,
        ),

        (
            return_1y(row),
            80,
            3,
        ),

    ]


    score = 0.0

    available = 0.0


    for (
        value,
        full_threshold,
        max_points,
    ) in periods:

        result = score_return(
            value,
            full_threshold,
        )

        if result is None:
            continue

        available += max_points

        score += (
            result
            *
            max_points
        )


    return (
        score,
        available,
    )


# =========================================================
# FUNDAMENTAL SCORE
# =========================================================
#
# Maximum = 30 points
#
# Future Growth           8
# Fundamental Quality     8
# CAPEX                    5
# Tailwind                 4
# Value Migration          3
# Macro                    2
#
# =========================================================

def fundamental_score(row):

    fields = [

        (
            "futureGrowth",
            8,
        ),

        (
            "fundamentalQuality",
            8,
        ),

        (
            "capexScore",
            5,
        ),

        (
            "tailwindScore",
            4,
        ),

        (
            "valueMigration",
            3,
        ),

        (
            "macroSupport",
            2,
        ),

    ]


    score = 0.0

    available = 0.0


    for (
        field,
        max_points,
    ) in fields:

        value = score_value(
            row,
            field,
        )

        if value is None:
            continue

        available += max_points

        score += (
            value
            /
            100
            *
            max_points
        )


    return (
        score,
        available,
    )


# =========================================================
# BUSINESS TRIGGER BONUS
# =========================================================
#
# Maximum = 20 points
#
# Trigger quality is deliberately capped.
#
# =========================================================

TRIGGER_POINTS = {

    "Earnings Acceleration": 5,

    "Margin Expansion": 4,

    "Order Win": 5,

    "CAPEX": 4,

    "Capacity Expansion": 5,

    "New Product": 3,

    "Fund Raising": 2,

    "Corporate Action": 2,

    "Industry Tailwind": 3,

    "Fundamental Quality": 2,

    "Growth": 2,

    "Value Migration": 2,

    "Macro Support": 1,

}


def trigger_score(
    triggers,
):

    total = 0

    for trigger in triggers:

        total += TRIGGER_POINTS.get(
            trigger,
            0,
        )

    return min(
        20,
        total,
    )


# =========================================================
# PRELIMINARY SCORE
# =========================================================
#
# CURRENT PHASE
#
# Momentum                 35
# Return Quality           15
# Fundamental Quality      30
# Business Triggers        20
#
# TOTAL                   100
#
#
# IMPORTANT:
#
# Technical chart engine is intentionally NOT guessed.
#
# In Phase-2:
#
# - Prior Move
# - Retracement
# - Consolidation Days
# - Volume Contraction
# - Volatility Contraction
# - Breakout Distance
# - Turnover Expansion
# - Free Float Shares
#
# will be integrated.
#
# When Phase-2 is added, final score weights will be
# redesigned around technical + fundamental + supply.
#
# =========================================================

def calculate_preliminary_score(
    row,
    triggers,
):

    momentum, momentum_available = (
        momentum_score(
            row
        )
    )

    returns, returns_available = (
        return_quality_score(
            row
        )
    )

    fundamental, fundamental_available = (
        fundamental_score(
            row
        )
    )

    trigger_points = trigger_score(
        triggers
    )


    raw_score = (
        momentum
        +
        returns
        +
        fundamental
        +
        trigger_points
    )


    score = int(
        round(
            max(
                0,
                min(
                    100,
                    raw_score,
                ),
            )
        )
    )


    coverage_available = (
        momentum_available
        +
        returns_available
        +
        fundamental_available
        +
        20
    )


    coverage_pct = (
        coverage_available
        /
        100
        *
        100
    )


    return {

        "score":
            score,

        "coveragePct":
            round(
                coverage_pct,
                1,
            ),

        "components": {

            "momentum":
                round(
                    momentum,
                    2,
                ),

            "returnQuality":
                round(
                    returns,
                    2,
                ),

            "fundamental":
                round(
                    fundamental,
                    2,
                ),

            "businessTriggers":
                trigger_points,

        },

    }


# =========================================================
# TECHNICAL DATA PLACEHOLDERS
# =========================================================
#
# DO NOT manufacture technical values from
# 1M / 3M / 6M returns.
#
# Proper daily OHLCV history will be used in Phase-2.
#
# =========================================================

def technical_fields(row):

    return {

        "priorMovePct":
            round_or_none(
                row.get(
                    "priorMovePct"
                )
            ),

        "movePeriod":
            row.get(
                "movePeriod"
            ),

        "retracementPct":
            round_or_none(
                row.get(
                    "retracementPct"
                )
            ),

        "consolidationDays":
            row.get(
                "consolidationDays"
            ),

        "volumeContraction":
            (
                row.get(
                    "volumeContraction"
                )
                if
                "volumeContraction"
                in row
                else
                None
            ),

        "volatilityContraction":
            (
                row.get(
                    "volatilityContraction"
                )
                if
                "volatilityContraction"
                in row
                else
                None
            ),

        "breakoutStatus":
            (
                row.get(
                    "breakoutStatus"
                )
                or
                "Pending"
            ),

        "turnoverExpansion":
            (
                row.get(
                    "turnoverExpansion"
                )
                if
                "turnoverExpansion"
                in row
                else
                None
            ),

    }


# =========================================================
# FREE FLOAT
# =========================================================

def free_float_shares(row):

    candidates = [

        row.get(
            "freeFloatShares"
        ),

        row.get(
            "free_float_shares"
        ),

        row.get(
            "freeFloatQuantity"
        ),

        row.get(
            "freeFloatQty"
        ),

    ]

    for value in candidates:

        result = positive_float(
            value
        )

        if result is not None:

            return int(
                round(
                    result
                )
            )

    return None


# =========================================================
# MISSING CONDITIONS
# =========================================================

def missing_conditions(
    row,
    technical,
    free_float,
    triggers,
):

    missing = []


    if rs_rating(row) is None:

        missing.append(
            "RS Rating"
        )


    if stock_momentum_rating(
        row
    ) is None:

        missing.append(
            "Stock Momentum"
        )


    if industry_rating(
        row
    ) is None:

        missing.append(
            "Industry Rating"
        )


    if free_float is None:

        missing.append(
            "Free Float Shares"
        )


    if technical.get(
        "priorMovePct"
    ) is None:

        missing.append(
            "Prior Move"
        )


    if technical.get(
        "retracementPct"
    ) is None:

        missing.append(
            "Retracement"
        )


    if technical.get(
        "consolidationDays"
    ) is None:

        missing.append(
            "Consolidation"
        )


    if technical.get(
        "volumeContraction"
    ) is None:

        missing.append(
            "Volume Contraction"
        )


    if technical.get(
        "volatilityContraction"
    ) is None:

        missing.append(
            "Volatility Contraction"
        )


    if (
        technical.get(
            "breakoutStatus"
        )
        in {
            None,
            "",
            "Pending",
        }
    ):

        missing.append(
            "Breakout Analysis"
        )


    if technical.get(
        "turnoverExpansion"
    ) is None:

        missing.append(
            "Turnover Expansion"
        )


    if not triggers:

        missing.append(
            "Confirmed Business Trigger"
        )


    return missing


# =========================================================
# SETUP STATUS
# =========================================================

def technical_ready(
    technical,
):

    required = [

        technical.get(
            "priorMovePct"
        ),

        technical.get(
            "retracementPct"
        ),

        technical.get(
            "consolidationDays"
        ),

        technical.get(
            "volumeContraction"
        ),

        technical.get(
            "volatilityContraction"
        ),

        technical.get(
            "turnoverExpansion"
        ),

    ]

    if any(
        value is None
        for value in required
    ):

        return False


    breakout = technical.get(
        "breakoutStatus"
    )

    if (
        not breakout
        or
        breakout == "Pending"
    ):

        return False


    return True


def setup_status(
    score,
    technical,
):

    if not technical_ready(
        technical
    ):

        if score >= 80:

            return (
                "High Potential / "
                "Technical Pending"
            )

        if score >= 70:

            return (
                "Watchlist / "
                "Technical Pending"
            )

        return (
            "Data Building"
        )


    breakout = str(
        technical.get(
            "breakoutStatus"
        )
        or ""
    ).lower()


    if (
        "breakout"
        in breakout
        and
        "near"
        not in breakout
    ):

        if score >= 75:

            return "Breakout"


    if "near" in breakout:

        if score >= 70:

            return "Near Breakout"


    if score >= 80:

        return "Strong Setup"


    if score >= 65:

        return "Watchlist"


    return "Developing"


# =========================================================
# BUILD ONE STOCK
# =========================================================

def build_scanner_row(row):

    stock_symbol = symbol(
        row
    )

    if not stock_symbol:

        return None


    mcap = market_cap(
        row
    )


    # Permanent dashboard universe rule:
    # Known market cap below ₹100 Cr excluded.
    #
    # Unknown market cap remains.
    if (
        mcap is not None
        and
        mcap < MIN_MARKET_CAP_CR
    ):

        return None


    current_price = price(
        row
    )

    if current_price is None:

        return None


    triggers = get_triggers(
        row
    )


    score_data = (
        calculate_preliminary_score(
            row,
            triggers,
        )
    )


    technical = technical_fields(
        row
    )


    free_float = free_float_shares(
        row
    )


    missing = missing_conditions(
        row,
        technical,
        free_float,
        triggers,
    )


    status = setup_status(
        score_data[
            "score"
        ],
        technical,
    )


    fundamental_trigger = (
        len(triggers) > 0
    )


    return {

        # =================================================
        # IDENTITY
        # =================================================

        "stock":
            company_name(
                row
            ),

        "symbol":
            stock_symbol,

        "series":
            row.get(
                "series"
            ),

        "board":
            row.get(
                "board"
            ),

        "sector":
            row.get(
                "sector"
            )
            or
            "Unclassified",

        "industry":
            row.get(
                "industry"
            )
            or
            "Unclassified",


        # =================================================
        # BASIC MARKET DATA
        # =================================================

        "price":
            round(
                current_price,
                2,
            ),

        "marketCapCr":
            round_or_none(
                mcap,
                2,
            ),

        "priceDate":
            row.get(
                "priceDate"
            ),


        # =================================================
        # RETURNS
        # =================================================

        "return1M":
            return_1m(
                row
            ),

        "return3M":
            return_3m(
                row
            ),

        "return6M":
            return_6m(
                row
            ),

        "return1Y":
            return_1y(
                row
            ),


        # =================================================
        # RELATIVE STRENGTH
        # =================================================

        "rsRating":
            rs_rating(
                row
            ),

        "rsLabel":
            row.get(
                "rsLabel"
            ),

        "stockMomentumRating":
            stock_momentum_rating(
                row
            ),

        "industryRating":
            industry_rating(
                row
            ),


        # =================================================
        # SUPPLY
        # =================================================

        "freeFloatShares":
            free_float,


        # =================================================
        # CHART STRUCTURE
        # =================================================

        "priorMovePct":
            technical[
                "priorMovePct"
            ],

        "movePeriod":
            technical[
                "movePeriod"
            ],

        "retracementPct":
            technical[
                "retracementPct"
            ],

        "consolidationDays":
            technical[
                "consolidationDays"
            ],

        "volumeContraction":
            technical[
                "volumeContraction"
            ],

        "volatilityContraction":
            technical[
                "volatilityContraction"
            ],

        "breakoutStatus":
            technical[
                "breakoutStatus"
            ],

        "turnoverExpansion":
            technical[
                "turnoverExpansion"
            ],


        # =================================================
        # FUNDAMENTAL / BUSINESS
        # =================================================

        "fundamentalTrigger":
            fundamental_trigger,

        "keyTrigger":
            key_trigger(
                triggers
            ),

        "triggers":
            triggers,


        # =================================================
        # EXISTING RESEARCH SCORES
        # =================================================

        "tailwindScore":
            score_value(
                row,
                "tailwindScore",
            ),

        "macroSupport":
            score_value(
                row,
                "macroSupport",
            ),

        "valueMigration":
            score_value(
                row,
                "valueMigration",
            ),

        "futureGrowth":
            score_value(
                row,
                "futureGrowth",
            ),

        "fundamentalQuality":
            score_value(
                row,
                "fundamentalQuality",
            ),

        "capexScore":
            score_value(
                row,
                "capexScore",
            ),

        "tmvScore":
            score_value(
                row,
                "tmvScore",
            ),

        "gfcScore":
            score_value(
                row,
                "gfcScore",
            ),

        "overallScore":
            score_value(
                row,
                "overallScore",
            ),


        # =================================================
        # BIG MOVE SCORE
        # =================================================

        "bigMoveScore":
            score_data[
                "score"
            ],

        "scoreCoveragePct":
            score_data[
                "coveragePct"
            ],

        "scoreComponents":
            score_data[
                "components"
            ],

        "scorePhase":
            "PHASE_1_PRELIMINARY",


        # =================================================
        # FINAL STATUS
        # =================================================

        "setupStatus":
            status,

        "missingConditions":
            (
                " | ".join(
                    missing
                )
                if missing
                else
                "None"
            ),

        "missingConditionsList":
            missing,

    }


# =========================================================
# SORTING
# =========================================================

def sort_rows(rows):

    def sort_key(row):

        return (

            row.get(
                "bigMoveScore"
            )
            or 0,

            row.get(
                "rsRating"
            )
            or 0,

            row.get(
                "stockMomentumRating"
            )
            or 0,

            row.get(
                "industryRating"
            )
            or 0,

        )

    return sorted(
        rows,
        key=sort_key,
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
                for row in rows
                if (
                    row.get(
                        "bigMoveScore"
                    )
                    or 0
                )
                >= 80
            ),

        "score70Plus":
            sum(
                1
                for row in rows
                if (
                    row.get(
                        "bigMoveScore"
                    )
                    or 0
                )
                >= 70
            ),

        "rs80Plus":
            sum(
                1
                for row in rows
                if (
                    row.get(
                        "rsRating"
                    )
                    or 0
                )
                >= 80
            ),

        "rs90Plus":
            sum(
                1
                for row in rows
                if (
                    row.get(
                        "rsRating"
                    )
                    or 0
                )
                >= 90
            ),

        "triggerPresent":
            sum(
                1
                for row in rows
                if row.get(
                    "fundamentalTrigger"
                )
            ),

        "technicalReady":
            sum(
                1
                for row in rows
                if row.get(
                    "setupStatus"
                )
                in {
                    "Strong Setup",
                    "Near Breakout",
                    "Breakout",
                    "Watchlist",
                    "Developing",
                }
            ),

        "freeFloatReady":
            sum(
                1
                for row in rows
                if row.get(
                    "freeFloatShares"
                )
                is not None
            ),

        "industryReady":
            sum(
                1
                for row in rows
                if row.get(
                    "industryRating"
                )
                is not None
            ),

        "stockMomentumReady":
            sum(
                1
                for row in rows
                if row.get(
                    "stockMomentumRating"
                )
                is not None
            ),

    }


# =========================================================
# MARKET DATE
# =========================================================

def detect_market_date(stocks):

    dates = []

    for row in stocks:

        for field in [
            "priceDate",
            "rsDate",
        ]:

            value = row.get(
                field
            )

            if value:

                dates.append(
                    str(value)
                )

    if dates:

        return max(
            dates
        )

    return (
        datetime.now(
            timezone.utc
        )
        .date()
        .isoformat()
    )


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "=============================================="
    )

    print(
        "BUILD BIG MOVE SCANNER"
    )

    print(
        "=============================================="
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


    if not stocks:

        raise RuntimeError(
            "stocks.json is empty"
        )


    print(
        "Stocks loaded:",
        len(stocks),
    )


    rows = []


    skipped = {

        "noSymbol":
            0,

        "noPrice":
            0,

        "below100Cr":
            0,

    }


    for stock in stocks:

        stock_symbol = symbol(
            stock
        )


        if not stock_symbol:

            skipped[
                "noSymbol"
            ] += 1

            continue


        mcap = market_cap(
            stock
        )


        if (
            mcap is not None
            and
            mcap < MIN_MARKET_CAP_CR
        ):

            skipped[
                "below100Cr"
            ] += 1

            continue


        if price(
            stock
        ) is None:

            skipped[
                "noPrice"
            ] += 1

            continue


        scanner_row = (
            build_scanner_row(
                stock
            )
        )


        if scanner_row:

            rows.append(
                scanner_row
            )


    rows = sort_rows(
        rows
    )


    market_date = detect_market_date(
        stocks
    )


    generated_at = (
        datetime.now(
            timezone.utc
        )
        .replace(
            microsecond=0
        )
        .isoformat()
    )


    summary = build_summary(
        rows
    )


    output = {

        "marketDate":
            market_date,

        "updated":
            market_date,

        "generatedAt":
            generated_at,

        "scannerVersion":
            "1.0",

        "phase":
            "PHASE_1_PRELIMINARY",

        "methodology": {

            "description":
                (
                    "Phase-1 Big Move Scanner combines existing "
                    "NSE price momentum, RS Rating, Stock Momentum, "
                    "Industry Rating, company research scores and "
                    "detected business triggers. Technical chart "
                    "structure and free-float supply data are not "
                    "guessed when unavailable."
                ),

            "scoreWeights": {

                "momentum":
                    35,

                "returnQuality":
                    15,

                "fundamental":
                    30,

                "businessTriggers":
                    20,

            },

            "phase2WillAdd": [

                "Prior Move Detection",

                "Retracement",

                "Consolidation Days",

                "Volume Contraction",

                "Volatility Contraction",

                "Breakout Distance",

                "Turnover Expansion",

                "Free Float Shares",

            ],

        },

        "summary":
            summary,

        "skipped":
            skipped,

        "rows":
            rows,

    }


    save_json(
        OUTPUT_PATH,
        output,
    )


    print()

    print(
        "=============================================="
    )

    print(
        "BIG MOVE SCANNER SUMMARY"
    )

    print(
        "=============================================="
    )


    print({
        "marketDate":
            market_date,

        "inputStocks":
            len(stocks),

        "scannerStocks":
            len(rows),

        "score80Plus":
            summary[
                "score80Plus"
            ],

        "score70Plus":
            summary[
                "score70Plus"
            ],

        "rs90Plus":
            summary[
                "rs90Plus"
            ],

        "triggerPresent":
            summary[
                "triggerPresent"
            ],

        "industryReady":
            summary[
                "industryReady"
            ],

        "stockMomentumReady":
            summary[
                "stockMomentumReady"
            ],

        "technicalReady":
            summary[
                "technicalReady"
            ],

        "freeFloatReady":
            summary[
                "freeFloatReady"
            ],

        "skipped":
            skipped,

        "output":
            str(
                OUTPUT_PATH
            ),

    })


    print()

    print(
        "Big Move Scanner Phase-1 build complete."
    )


if __name__ == "__main__":

    main()
