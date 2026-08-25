import json
import math
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

RUN_DATE = (
    datetime.now(timezone.utc)
    .date()
    .isoformat()
)

METHODOLOGY = {
    "tailwind":
        "methodology.html#tailwind",

    "futureGrowth":
        "methodology.html#future-growth",

    "fundamentalQuality":
        "methodology.html#fundamental",

    "capex":
        "methodology.html#capex",
}


# =========================================================
# BASIC HELPERS
# =========================================================

def load_json(path, default):
    try:
        return json.loads(
            path.read_text()
        )
    except Exception:
        return default


def clamp(x, lo=0, hi=100):
    return max(
        lo,
        min(hi, x)
    )


def safe_float(x):
    try:
        if x is None:
            return None

        value = float(x)

        if (
            math.isnan(value)
            or math.isinf(value)
        ):
            return None

        return value

    except Exception:
        return None


def clean_text(value):
    if value is None:
        return ""

    return str(
        value
    ).strip()


def valid_score(value):
    value = safe_float(
        value
    )

    if value is None:
        return None

    return round(
        clamp(value),
        2
    )


# =========================================================
# VERIFIED EVIDENCE
# =========================================================

def evidence_block(
    evidence_stock,
    key
):
    if not isinstance(
        evidence_stock,
        dict
    ):
        return {}

    block = evidence_stock.get(
        key,
        {}
    )

    if not isinstance(
        block,
        dict
    ):
        return {}

    return block


def verified_override(
    evidence_stock,
    key
):
    block = evidence_block(
        evidence_stock,
        key
    )

    score = valid_score(
        block.get("score")
    )

    reason = clean_text(
        block.get("reason")
    )

    source = clean_text(
        block.get("source")
    )

    source_date = clean_text(
        block.get("sourceDate")
    )

    if (
        score is None
        or not reason
        or not source
    ):
        return None

    return {
        "score":
            score,

        "reason":
            reason,

        "source":
            source,

        "sourceDate":
            source_date,

        "mode":
            "VERIFIED",
    }


# =========================================================
# TAILWIND AUTOMATED BASE
# =========================================================

def tailwind_score(
    sector,
    industry
):
    text = (
        f"{sector or ''} "
        f"{industry or ''}"
    ).lower()

    rules = [

        (
            ["renewable", "solar"],
            95,
            (
                "Automated screening proxy: "
                "renewable-energy capacity additions, "
                "energy transition and related investment "
                "provide a strong structural tailwind."
            )
        ),

        (
            [
                "power",
                "electric utility",
                "electrical equipment"
            ],
            90,
            (
                "Automated screening proxy: "
                "power demand, grid expansion, "
                "transmission investment and electrification "
                "support the industry."
            )
        ),

        (
            ["defence", "aerospace"],
            92,
            (
                "Automated screening proxy: "
                "defence localisation, indigenisation and "
                "domestic procurement support growth."
            )
        ),

        (
            [
                "capital goods",
                "industrial machinery",
                "construction equipment"
            ],
            88,
            (
                "Automated screening proxy: "
                "domestic manufacturing and the investment "
                "cycle support capital-goods demand."
            )
        ),

        (
            [
                "infrastructure",
                "construction"
            ],
            87,
            (
                "Automated screening proxy: "
                "infrastructure investment and public/private "
                "CAPEX provide a favourable demand environment."
            )
        ),

        (
            [
                "electronics",
                "semiconductor",
                "electronic components"
            ],
            92,
            (
                "Automated screening proxy: "
                "electronics localisation, import substitution "
                "and domestic manufacturing expansion "
                "support structural growth."
            )
        ),

        (
            ["railway", "rail"],
            90,
            (
                "Automated screening proxy: "
                "railway modernisation and infrastructure "
                "spending provide structural demand support."
            )
        ),

        (
            [
                "pharma",
                "pharmaceutical",
                "healthcare",
                "hospital"
            ],
            82,
            (
                "Automated screening proxy: "
                "healthcare demand, exports and rising "
                "healthcare penetration provide long-duration support."
            )
        ),

        (
            [
                "auto component",
                "automobile",
                "automotive"
            ],
            80,
            (
                "Automated screening proxy: "
                "vehicle premiumisation, localisation and "
                "technology transition provide sector support."
            )
        ),

        (
            [
                "bank",
                "financial services",
                "nbfc",
                "insurance",
                "asset management"
            ],
            78,
            (
                "Automated screening proxy: "
                "financialisation, credit penetration and "
                "formalisation support long-term sector growth."
            )
        ),

        (
            [
                "telecom",
                "communication"
            ],
            80,
            (
                "Automated screening proxy: "
                "data consumption, network investment and "
                "digital adoption provide structural demand."
            )
        ),

        (
            [
                "data center",
                "data centre",
                "cloud"
            ],
            95,
            (
                "Automated screening proxy: "
                "cloud adoption, AI infrastructure and "
                "data-centre capacity expansion provide "
                "a strong structural tailwind."
            )
        ),

        (
            [
                "logistics",
                "warehousing"
            ],
            80,
            (
                "Automated screening proxy: "
                "formalisation, organised logistics and "
                "e-commerce penetration support structural growth."
            )
        ),

        (
            [
                "real estate",
                "realty"
            ],
            72,
            (
                "Automated screening proxy: "
                "urbanisation and housing/commercial demand "
                "provide positive but cyclical support."
            )
        ),

        (
            [
                "consumer",
                "fmcg"
            ],
            70,
            (
                "Automated screening proxy: "
                "income growth, premiumisation and "
                "consumption expansion provide long-term support."
            )
        ),

        (
            [
                "information technology",
                "software",
                "it services"
            ],
            75,
            (
                "Automated screening proxy: "
                "digital transformation, cloud and AI spending "
                "provide structural technology demand."
            )
        ),

        (
            [
                "chemical",
                "specialty chemical"
            ],
            76,
            (
                "Automated screening proxy: "
                "import substitution, supply-chain diversification "
                "and specialty-product demand can support growth."
            )
        ),

        (
            [
                "metal",
                "mining"
            ],
            62,
            (
                "Automated screening proxy: "
                "infrastructure and manufacturing demand "
                "provide support, while commodity-cycle "
                "sensitivity remains important."
            )
        ),

        (
            [
                "oil",
                "gas"
            ],
            58,
            (
                "Automated screening proxy: "
                "energy demand remains supportive, although "
                "commodity cycles and energy transition "
                "limit structural visibility."
            )
        ),

        (
            [
                "media",
                "entertainment"
            ],
            55,
            (
                "Automated screening proxy: "
                "digital consumption provides support, "
                "but industry economics remain mixed."
            )
        ),
    ]

    for (
        keywords,
        score,
        reason
    ) in rules:

        if any(
            word in text
            for word in keywords
        ):
            return (
                score,
                reason
            )

    return (
        None,
        (
            "Automated screening proxy unavailable: "
            "no mapped structural-tailwind rule "
            "for this sector/industry."
        )
    )


# =========================================================
# FUTURE GROWTH
# =========================================================

def growth_component(x):
    x = safe_float(x)

    if x is None:
        return None

    pct = x * 100

    return clamp(
        50 +
        pct * 1.5
    )


def future_growth_score(info):
    parts = []
    details = []

    revenue_growth = safe_float(
        info.get(
            "revenueGrowth"
        )
    )

    if revenue_growth is not None:

        parts.append(
            growth_component(
                revenue_growth
            )
        )

        details.append(
            (
                "revenue growth "
                f"{revenue_growth * 100:.1f}%"
            )
        )


    earnings_growth = safe_float(
        info.get(
            "earningsGrowth"
        )
    )

    if earnings_growth is not None:

        parts.append(
            growth_component(
                earnings_growth
            )
        )

        details.append(
            (
                "earnings growth "
                f"{earnings_growth * 100:.1f}%"
            )
        )


    quarterly_growth = safe_float(
        info.get(
            "earningsQuarterlyGrowth"
        )
    )

    if quarterly_growth is not None:

        parts.append(
            growth_component(
                quarterly_growth
            )
        )

        details.append(
            (
                "quarterly earnings growth "
                f"{quarterly_growth * 100:.1f}%"
            )
        )


    forward_pe = safe_float(
        info.get(
            "forwardPE"
        )
    )

    trailing_pe = safe_float(
        info.get(
            "trailingPE"
        )
    )

    if (
        forward_pe is not None
        and trailing_pe is not None
        and trailing_pe > 0
    ):

        improvement = (
            trailing_pe -
            forward_pe
        ) / trailing_pe

        parts.append(
            clamp(
                50 +
                improvement * 40
            )
        )


    if not parts:
        return (
            None,
            (
                "Automated screening proxy unavailable: "
                "insufficient growth data."
            )
        )


    score = round(
        sum(parts) /
        len(parts),
        2
    )


    if details:

        reason = (
            "Automated screening proxy based on "
            + ", ".join(details)
            + "."
        )

    else:

        reason = (
            "Automated screening proxy based on "
            "available historical and forward "
            "financial data."
        )


    return (
        score,
        reason
    )


# =========================================================
# FUNDAMENTAL QUALITY
# =========================================================

def fundamental_score(info):
    parts = []
    details = []

    roe = safe_float(
        info.get(
            "returnOnEquity"
        )
    )

    if roe is not None:

        parts.append(
            clamp(
                50 +
                roe * 100 * 1.5
            )
        )

        details.append(
            f"ROE {roe * 100:.1f}%"
        )


    profit_margin = safe_float(
        info.get(
            "profitMargins"
        )
    )

    if profit_margin is not None:

        parts.append(
            clamp(
                45 +
                profit_margin *
                100 * 2
            )
        )

        details.append(
            (
                "profit margin "
                f"{profit_margin * 100:.1f}%"
            )
        )


    operating_margin = safe_float(
        info.get(
            "operatingMargins"
        )
    )

    if operating_margin is not None:

        parts.append(
            clamp(
                45 +
                operating_margin *
                100 * 1.8
            )
        )

        details.append(
            (
                "operating margin "
                f"{operating_margin * 100:.1f}%"
            )
        )


    debt_equity = safe_float(
        info.get(
            "debtToEquity"
        )
    )

    if debt_equity is not None:

        parts.append(
            clamp(
                100 -
                debt_equity *
                0.55
            )
        )

        details.append(
            (
                "debt/equity "
                f"{debt_equity:.1f}"
            )
        )


    current_ratio = safe_float(
        info.get(
            "currentRatio"
        )
    )

    if current_ratio is not None:

        parts.append(
            clamp(
                current_ratio *
                45
            )
        )

        details.append(
            (
                "current ratio "
                f"{current_ratio:.2f}"
            )
        )


    free_cashflow = safe_float(
        info.get(
            "freeCashflow"
        )
    )

    if free_cashflow is not None:

        parts.append(
            75
            if free_cashflow > 0
            else 25
        )

        details.append(
            (
                "positive free cash flow"
                if free_cashflow > 0
                else "negative free cash flow"
            )
        )


    operating_cf = safe_float(
        info.get(
            "operatingCashflow"
        )
    )

    if operating_cf is not None:

        parts.append(
            75
            if operating_cf > 0
            else 25
        )

        details.append(
            (
                "positive operating cash flow"
                if operating_cf > 0
                else "negative operating cash flow"
            )
        )


    if len(parts) < 2:

        return (
            None,
            (
                "Automated screening proxy unavailable: "
                "insufficient fundamental data."
            )
        )


    score = round(
        sum(parts) /
        len(parts),
        2
    )


    reason = (
        "Automated screening proxy based on "
        + ", ".join(details)
        + "."
    )


    return (
        score,
        reason
    )


# =========================================================
# CAPEX
# =========================================================

def capex_score(ticker):
    try:

        cf = ticker.cashflow

        if (
            cf is None
            or cf.empty
        ):

            return (
                None,
                (
                    "Automated screening proxy unavailable: "
                    "cash-flow statement not available."
                )
            )


        capex = None
        operating_cf = None


        capex_names = [
            "Capital Expenditure",
            "Capital Expenditures",
        ]


        ocf_names = [
            "Operating Cash Flow",
            "Total Cash From Operating Activities",
        ]


        for name in capex_names:

            if name in cf.index:

                values = (
                    cf.loc[name]
                    .dropna()
                )

                if len(values):

                    capex = safe_float(
                        values.iloc[0]
                    )

                    break


        for name in ocf_names:

            if name in cf.index:

                values = (
                    cf.loc[name]
                    .dropna()
                )

                if len(values):

                    operating_cf = safe_float(
                        values.iloc[0]
                    )

                    break


        if capex is None:

            return (
                None,
                (
                    "Automated screening proxy unavailable: "
                    "capital expenditure data not available."
                )
            )


        capex_abs = abs(
            capex
        )


        if (
            operating_cf is None
            or operating_cf <= 0
        ):

            if capex_abs > 0:

                return (
                    50,
                    (
                        "Automated screening proxy: "
                        "CAPEX detected, but positive operating "
                        "cash flow was unavailable for comparison."
                    )
                )

            return (
                None,
                "Automated screening proxy unavailable."
            )


        ratio = (
            capex_abs /
            operating_cf
        )


        if ratio >= 0.50:
            score = 90

        elif ratio >= 0.30:
            score = 80

        elif ratio >= 0.15:
            score = 70

        elif ratio >= 0.05:
            score = 60

        elif ratio > 0:
            score = 50

        else:
            score = 35


        reason = (
            "Automated screening proxy: "
            "capital expenditure is "
            f"{ratio:.2f}× operating cash flow."
        )


        return (
            score,
            reason
        )


    except Exception as e:

        return (
            None,
            (
                "Automated screening proxy unavailable: "
                f"{e}"
            )
        )


# =========================================================
# REASON HELPERS
# =========================================================

def automated_detail(
    reason,
    source
):
    return {
        "reason":
            reason,

        "source":
            source,

        "sourceDate":
            RUN_DATE,

        "mode":
            "AUTOMATED",
    }


def verified_detail(
    verified
):
    return {
        "reason":
            verified["reason"],

        "source":
            verified["source"],

        "sourceDate":
            verified["sourceDate"],

        "mode":
            "VERIFIED",
    }


def previous_detail(
    previous,
    key
):
    reasons = (
        previous.get(
            "researchReasons",
            {}
        )
        or {}
    )

    block = (
        reasons.get(
            key,
            {}
        )
        or {}
    )

    if not isinstance(
        block,
        dict
    ):
        return {}

    return block


def previous_valid_score(
    previous,
    score_key
):
    return valid_score(
        previous.get(
            score_key
        )
    )


# =========================================================
# ANALYZE ONE STOCK
# =========================================================

def analyze_stock(
    row,
    evidence_stocks,
    previous
):
    symbol = row.get(
        "symbol"
    )

    if not symbol:
        return None, None


    yahoo_symbol = (
        f"{symbol}.NS"
    )


    sector = row.get(
        "sector"
    )

    industry = row.get(
        "industry"
    )


    evidence_stock = (
        evidence_stocks.get(
            symbol,
            {}
        )
        or {}
    )


    # -----------------------------------------------------
    # VERIFIED EVIDENCE
    # -----------------------------------------------------

    verified_tailwind = (
        verified_override(
            evidence_stock,
            "tailwind"
        )
    )

    verified_growth = (
        verified_override(
            evidence_stock,
            "futureGrowth"
        )
    )

    verified_fundamental = (
        verified_override(
            evidence_stock,
            "fundamentalQuality"
        )
    )

    verified_capex = (
        verified_override(
            evidence_stock,
            "capex"
        )
    )


    # -----------------------------------------------------
    # TAILWIND
    # -----------------------------------------------------

    tailwind_auto, tailwind_reason = (
        tailwind_score(
            sector,
            industry
        )
    )


    if verified_tailwind:

        tailwind = (
            verified_tailwind[
                "score"
            ]
        )

        tailwind_detail = (
            verified_detail(
                verified_tailwind
            )
        )

    else:

        tailwind = (
            valid_score(
                tailwind_auto
            )
        )

        if tailwind is not None:

            tailwind_detail = (
                automated_detail(
                    tailwind_reason,
                    METHODOLOGY[
                        "tailwind"
                    ]
                )
            )

        else:

            old_score = (
                previous_valid_score(
                    previous,
                    "tailwindScore"
                )
            )

            old_detail = (
                previous_detail(
                    previous,
                    "tailwind"
                )
            )

            if (
                old_score is not None
                and old_detail
            ):

                tailwind = (
                    old_score
                )

                tailwind_detail = (
                    old_detail
                )

            else:

                tailwind = None

                tailwind_detail = (
                    automated_detail(
                        tailwind_reason,
                        METHODOLOGY[
                            "tailwind"
                        ]
                    )
                )


    # -----------------------------------------------------
    # YAHOO FINANCIAL DATA
    # -----------------------------------------------------

    data_ok = False

    growth_auto = None
    growth_reason = ""

    fundamental_auto = None
    fundamental_reason = ""

    capex_auto = None
    capex_reason = ""


    try:

        ticker = yf.Ticker(
            yahoo_symbol
        )


        info = (
            ticker.info
            or {}
        )


        growth_auto, growth_reason = (
            future_growth_score(
                info
            )
        )


        fundamental_auto, fundamental_reason = (
            fundamental_score(
                info
            )
        )


        capex_auto, capex_reason = (
            capex_score(
                ticker
            )
        )


        data_ok = (
            growth_auto is not None
            or fundamental_auto is not None
            or capex_auto is not None
        )


    except Exception as e:

        failure_reason = (
            "Automated financial-data refresh failed: "
            f"{e}"
        )

        growth_reason = (
            failure_reason
        )

        fundamental_reason = (
            failure_reason
        )

        capex_reason = (
            failure_reason
        )


    # -----------------------------------------------------
    # FUTURE GROWTH
    # -----------------------------------------------------

    if verified_growth:

        future_growth = (
            verified_growth[
                "score"
            ]
        )

        growth_detail = (
            verified_detail(
                verified_growth
            )
        )

    else:

        growth_score = (
            valid_score(
                growth_auto
            )
        )

        if growth_score is not None:

            future_growth = (
                growth_score
            )

            growth_detail = (
                automated_detail(
                    growth_reason,
                    METHODOLOGY[
                        "futureGrowth"
                    ]
                )
            )

        else:

            old_score = (
                previous_valid_score(
                    previous,
                    "futureGrowth"
                )
            )

            old_detail = (
                previous_detail(
                    previous,
                    "futureGrowth"
                )
            )

            if (
                old_score is not None
                and old_detail
            ):

                future_growth = (
                    old_score
                )

                growth_detail = (
                    old_detail
                )

            else:

                future_growth = None

                growth_detail = (
                    automated_detail(
                        growth_reason
                        or
                        (
                            "Automated screening proxy unavailable: "
                            "insufficient growth data."
                        ),
                        METHODOLOGY[
                            "futureGrowth"
                        ]
                    )
                )


    # -----------------------------------------------------
    # FUNDAMENTAL
    # -----------------------------------------------------

    if verified_fundamental:

        fundamental = (
            verified_fundamental[
                "score"
            ]
        )

        fundamental_detail = (
            verified_detail(
                verified_fundamental
            )
        )

    else:

        fundamental_score_value = (
            valid_score(
                fundamental_auto
            )
        )

        if (
            fundamental_score_value
            is not None
        ):

            fundamental = (
                fundamental_score_value
            )

            fundamental_detail = (
                automated_detail(
                    fundamental_reason,
                    METHODOLOGY[
                        "fundamentalQuality"
                    ]
                )
            )

        else:

            old_score = (
                previous_valid_score(
                    previous,
                    "fundamentalQuality"
                )
            )

            old_detail = (
                previous_detail(
                    previous,
                    "fundamentalQuality"
                )
            )

            if (
                old_score is not None
                and old_detail
            ):

                fundamental = (
                    old_score
                )

                fundamental_detail = (
                    old_detail
                )

            else:

                fundamental = None

                fundamental_detail = (
                    automated_detail(
                        fundamental_reason
                        or
                        (
                            "Automated screening proxy unavailable: "
                            "insufficient fundamental data."
                        ),
                        METHODOLOGY[
                            "fundamentalQuality"
                        ]
                    )
                )


    # -----------------------------------------------------
    # CAPEX
    # -----------------------------------------------------

    if verified_capex:

        capex = (
            verified_capex[
                "score"
            ]
        )

        capex_detail = (
            verified_detail(
                verified_capex
            )
        )

    else:

        capex_score_value = (
            valid_score(
                capex_auto
            )
        )

        if capex_score_value is not None:

            capex = (
                capex_score_value
            )

            capex_detail = (
                automated_detail(
                    capex_reason,
                    METHODOLOGY[
                        "capex"
                    ]
                )
            )

        else:

            old_score = (
                previous_valid_score(
                    previous,
                    "capexScore"
                )
            )

            old_detail = (
                previous_detail(
                    previous,
                    "capex"
                )
            )

            if (
                old_score is not None
                and old_detail
            ):

                capex = (
                    old_score
                )

                capex_detail = (
                    old_detail
                )

            else:

                capex = None

                capex_detail = (
                    automated_detail(
                        capex_reason
                        or
                        (
                            "Automated screening proxy unavailable: "
                            "CAPEX data not available."
                        ),
                        METHODOLOGY[
                            "capex"
                        ]
                    )
                )


    return (
        symbol,
        {

            "tailwindScore":
                tailwind,

            "futureGrowth":
                future_growth,

            "fundamentalQuality":
                fundamental,

            "capexScore":
                capex,

            "researchReasons": {

                "tailwind":
                    tailwind_detail,

                "futureGrowth":
                    growth_detail,

                "fundamentalQuality":
                    fundamental_detail,

                "capex":
                    capex_detail,
            },

            "researchMode": {

                "tailwind":
                    tailwind_detail.get(
                        "mode"
                    ),

                "futureGrowth":
                    growth_detail.get(
                        "mode"
                    ),

                "fundamentalQuality":
                    fundamental_detail.get(
                        "mode"
                    ),

                "capex":
                    capex_detail.get(
                        "mode"
                    ),
            },

            "financialDataRefresh":
                (
                    "OK"
                    if data_ok
                    else "PARTIAL_OR_UNAVAILABLE"
                ),
        }
    )


# =========================================================
# MAIN
# =========================================================

def main():

    stocks = load_json(
        DATA /
        "stocks.json",
        []
    )


    existing = load_json(
        DATA /
        "company_research.json",
        {}
    )


    evidence = load_json(
        DATA /
        "company_evidence.json",
        {}
    )


    existing_stocks = (
        existing.get(
            "stocks",
            {}
        )
        or {}
    )


    evidence_stocks = (
        evidence.get(
            "stocks",
            {}
        )
        or {}
    )


    rows = [
        row
        for row in stocks
        if (
            row.get("symbol")
            and row.get("sector")
            and row.get("sector")
            != "Unclassified"
        )
    ]


    result = dict(
        existing_stocks
    )


    processed = 0

    tailwind_available = 0
    future_available = 0
    fundamental_available = 0
    capex_available = 0

    verified_tailwind = 0
    verified_growth = 0
    verified_fundamental = 0
    verified_capex = 0


    with ThreadPoolExecutor(
        max_workers=6
    ) as executor:


        futures = {}


        for row in rows:

            symbol = (
                row.get(
                    "symbol"
                )
            )

            previous = (
                result.get(
                    symbol,
                    {}
                )
                or {}
            )


            future = (
                executor.submit(
                    analyze_stock,
                    row,
                    evidence_stocks,
                    previous
                )
            )


            futures[
                future
            ] = symbol


        for future in as_completed(
            futures
        ):

            processed += 1


            try:

                symbol, data = (
                    future.result()
                )


            except Exception as e:

                print(
                    "Stock analysis failed:",
                    e
                )

                continue


            if (
                not symbol
                or data is None
            ):
                continue


            result[
                symbol
            ] = data


            final = (
                result[
                    symbol
                ]
            )


            if (
                final.get(
                    "tailwindScore"
                )
                is not None
            ):
                tailwind_available += 1


            if (
                final.get(
                    "futureGrowth"
                )
                is not None
            ):
                future_available += 1


            if (
                final.get(
                    "fundamentalQuality"
                )
                is not None
            ):
                fundamental_available += 1


            if (
                final.get(
                    "capexScore"
                )
                is not None
            ):
                capex_available += 1


            modes = (
                final.get(
                    "researchMode",
                    {}
                )
                or {}
            )


            if (
                modes.get(
                    "tailwind"
                )
                == "VERIFIED"
            ):
                verified_tailwind += 1


            if (
                modes.get(
                    "futureGrowth"
                )
                == "VERIFIED"
            ):
                verified_growth += 1


            if (
                modes.get(
                    "fundamentalQuality"
                )
                == "VERIFIED"
            ):
                verified_fundamental += 1


            if (
                modes.get(
                    "capex"
                )
                == "VERIFIED"
            ):
                verified_capex += 1


            if (
                processed % 25
                == 0
            ):

                print(
                    f"Processed "
                    f"{processed}/"
                    f"{len(rows)}"
                )


    output = {

        "_meta": {

            "description":
                (
                    "Company research inputs "
                    "for MY MARKET RESEARCH"
                ),

            "scale":
                "0-100",

            "updated":
                RUN_DATE,

            "method": {

                "tailwindScore":
                    (
                        "Verified evidence override when available; "
                        "otherwise sector/industry structural-tailwind proxy."
                    ),

                "futureGrowth":
                    (
                        "Verified evidence override when available; "
                        "otherwise automated growth screening proxy."
                    ),

                "fundamentalQuality":
                    (
                        "Verified evidence override when available; "
                        "otherwise automated financial-quality proxy."
                    ),

                "capexScore":
                    (
                        "Verified evidence override when available; "
                        "otherwise automated CAPEX proxy."
                    ),
            },

            "methodologyPage":
                "methodology.html",

            "verifiedEvidenceFile":
                "data/company_evidence.json",

            "warning":
                (
                    "AUTOMATED scores are screening proxies. "
                    "VERIFIED scores require reason + source evidence."
                ),
        },

        "stocks":
            result,
    }


    (
        DATA /
        "company_research.json"
    ).write_text(

        json.dumps(
            output,
            indent=2,
            ensure_ascii=False
        )
    )


    print({

        "classifiedStocks":
            len(rows),

        "processed":
            processed,

        "tailwindAvailable":
            tailwind_available,

        "futureGrowthAvailable":
            future_available,

        "fundamentalAvailable":
            fundamental_available,

        "capexAvailable":
            capex_available,

        "verifiedTailwind":
            verified_tailwind,

        "verifiedFutureGrowth":
            verified_growth,

        "verifiedFundamental":
            verified_fundamental,

        "verifiedCapex":
            verified_capex,
    })


if __name__ == "__main__":
    main()
