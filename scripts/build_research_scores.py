import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

NIFTY500 = "^CRSLDX"

RUN_DATE = (
    datetime.now(timezone.utc)
    .date()
    .isoformat()
)

METHODOLOGY = {
    "macro": "methodology.html#macro",
    "valueMigration": "methodology.html#value-migration",
}


# =========================================================
# BASIC HELPERS
# =========================================================

def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def safe_float(value):
    try:
        if value is None:
            return None

        value = float(value)

        if pd.isna(value):
            return None

        return value

    except Exception:
        return None


def percentile(value, values):
    value = safe_float(value)

    if value is None:
        return None

    clean = sorted(
        float(v)
        for v in values
        if safe_float(v) is not None
    )

    if not clean:
        return None

    count = sum(
        1
        for v in clean
        if v <= value
    )

    return round(
        count / len(clean) * 100,
        2
    )


def fallback_value(
    new_value,
    previous,
    field
):
    """
    New calculation unavailable ho to
    previous valid value preserve karo.
    """

    if new_value is not None:
        return new_value

    old_value = (
        previous.get(field)
        if isinstance(previous, dict)
        else None
    )

    if old_value is None:
        return None

    return old_value


# =========================================================
# VERIFIED EVIDENCE
# =========================================================

def verified_evidence(
    evidence_stocks,
    symbol,
    field
):
    stock = (
        evidence_stocks.get(
            symbol,
            {}
        )
        or {}
    )

    block = (
        stock.get(
            field,
            {}
        )
        or {}
    )

    if not isinstance(
        block,
        dict
    ):
        return None

    score = safe_float(
        block.get("score")
    )

    reason = str(
        block.get("reason")
        or ""
    ).strip()

    source = str(
        block.get("source")
        or ""
    ).strip()

    source_date = str(
        block.get("sourceDate")
        or ""
    ).strip()

    if (
        score is None
        or not reason
        or not source
    ):
        return None

    return {
        "score": round(
            clamp(score),
            2
        ),
        "reason": reason,
        "source": source,
        "sourceDate": source_date,
        "mode": "VERIFIED",
    }


# =========================================================
# SECTOR INDEX MAPPING
# =========================================================

def sector_index(
    sector,
    industry
):
    text = (
        f"{sector or ''} "
        f"{industry or ''}"
    ).lower()

    rules = [
        (
            ["psu bank"],
            "^CNXPSUBANK"
        ),
        (
            ["bank"],
            "^NSEBANK"
        ),
        (
            [
                "financial services",
                "finance",
                "nbfc"
            ],
            "^CNXFINANCE"
        ),
        (
            [
                "automobile",
                "auto component",
                "auto"
            ],
            "^CNXAUTO"
        ),
        (
            [
                "information technology",
                "software",
                "it services"
            ],
            "^CNXIT"
        ),
        (
            ["fmcg"],
            "^CNXFMCG"
        ),
        (
            [
                "pharma",
                "pharmaceutical",
                "healthcare"
            ],
            "^CNXPHARMA"
        ),
        (
            [
                "metal",
                "mining"
            ],
            "^CNXMETAL"
        ),
        (
            [
                "realty",
                "real estate"
            ],
            "^CNXREALTY"
        ),
        (
            [
                "media",
                "entertainment"
            ],
            "^CNXMEDIA"
        ),
        (
            [
                "energy",
                "oil",
                "gas",
                "power",
                "renewable",
                "solar"
            ],
            "^CNXENERGY"
        ),
        (
            [
                "infrastructure",
                "construction",
                "capital goods"
            ],
            "^CNXINFRA"
        ),
    ]

    for words, ticker in rules:
        if any(
            word in text
            for word in words
        ):
            return ticker

    return None


# =========================================================
# MACRO SUPPORT
# =========================================================

def macro_score(
    sector,
    industry
):
    text = (
        f"{sector or ''} "
        f"{industry or ''}"
    ).lower()

    rules = [
        (
            ["renewable", "solar", "power"],
            90,
            (
                "Automated Macro screening proxy: "
                "power demand, energy transition, grid investment "
                "and related capital expenditure provide strong support."
            )
        ),

        (
            [
                "capital goods",
                "construction",
                "infrastructure"
            ],
            85,
            (
                "Automated Macro screening proxy: "
                "infrastructure spending, domestic manufacturing "
                "and the investment cycle provide sector support."
            )
        ),

        (
            [
                "electrical equipment",
                "electronics",
                "semiconductor"
            ],
            85,
            (
                "Automated Macro screening proxy: "
                "electrification, localisation, import substitution "
                "and domestic manufacturing provide support."
            )
        ),

        (
            ["industrial manufacturing"],
            80,
            (
                "Automated Macro screening proxy: "
                "domestic manufacturing and investment-cycle "
                "conditions are supportive."
            )
        ),

        (
            ["defence", "aerospace"],
            80,
            (
                "Automated Macro screening proxy: "
                "domestic procurement, localisation and "
                "indigenisation provide policy support."
            )
        ),

        (
            [
                "financial services",
                "bank"
            ],
            70,
            (
                "Automated Macro screening proxy: "
                "financialisation, formalisation and "
                "credit penetration support sector growth."
            )
        ),

        (
            [
                "automobile",
                "auto components"
            ],
            70,
            (
                "Automated Macro screening proxy: "
                "vehicle demand, premiumisation, localisation "
                "and technology transition provide support."
            )
        ),

        (
            [
                "healthcare",
                "pharma"
            ],
            70,
            (
                "Automated Macro screening proxy: "
                "healthcare demand, exports and rising "
                "healthcare penetration provide support."
            )
        ),

        (
            ["telecom"],
            70,
            (
                "Automated Macro screening proxy: "
                "data consumption, digital adoption and "
                "network investment support telecom demand."
            )
        ),

        (
            [
                "metals",
                "mining"
            ],
            65,
            (
                "Automated Macro screening proxy: "
                "infrastructure and manufacturing demand provide support, "
                "although commodity cyclicality remains important."
            )
        ),

        (
            ["realty"],
            65,
            (
                "Automated Macro screening proxy: "
                "urbanisation, housing demand and commercial activity "
                "provide moderate support."
            )
        ),

        (
            ["consumer"],
            60,
            (
                "Automated Macro screening proxy: "
                "consumption growth, income growth and "
                "premiumisation provide moderate support."
            )
        ),

        (
            ["information technology"],
            60,
            (
                "Automated Macro screening proxy: "
                "digital transformation, cloud adoption and "
                "technology spending provide support."
            )
        ),

        (
            ["oil", "gas"],
            55,
            (
                "Automated Macro screening proxy: "
                "energy demand remains supportive, although "
                "commodity cycles reduce visibility."
            )
        ),

        (
            ["media"],
            50,
            (
                "Automated Macro screening proxy: "
                "digital consumption provides some support, "
                "while industry economics remain mixed."
            )
        ),
    ]

    for keywords, score, reason in rules:
        if any(
            keyword in text
            for keyword in keywords
        ):
            return score, reason

    return (
        None,
        (
            "Automated Macro screening proxy unavailable: "
            "no mapped Macro-support rule for this sector/industry."
        )
    )


# =========================================================
# YFINANCE HISTORY
# =========================================================

def extract_close_series(
    data,
    ticker,
    chunk
):
    if (
        data is None
        or len(data) == 0
    ):
        return None

    try:

        if isinstance(
            data.columns,
            pd.MultiIndex
        ):

            if (
                "Close"
                in data.columns
                .get_level_values(0)
            ):

                close = data["Close"]

                if isinstance(
                    close,
                    pd.Series
                ):
                    series = close

                elif ticker in close.columns:
                    series = close[ticker]

                elif (
                    len(chunk) == 1
                    and len(close.columns) == 1
                ):
                    series = close.iloc[:, 0]

                else:
                    return None

            elif (
                ticker
                in data.columns
                .get_level_values(0)
            ):

                block = data[ticker]

                if "Close" not in block.columns:
                    return None

                series = block["Close"]

            else:
                return None

        else:

            if "Close" not in data.columns:
                return None

            series = data["Close"]

        series = (
            pd.Series(series)
            .dropna()
            .astype(float)
        )

        if len(series) == 0:
            return None

        return series

    except Exception:
        return None


def download_history(tickers):
    result = {}

    tickers = list(
        dict.fromkeys(
            ticker
            for ticker in tickers
            if ticker
        )
    )

    chunk_size = 100

    for start in range(
        0,
        len(tickers),
        chunk_size
    ):

        chunk = tickers[
            start:
            start + chunk_size
        ]

        print(
            f"Historical prices: "
            f"{start + 1}-"
            f"{min(start + chunk_size, len(tickers))}/"
            f"{len(tickers)}"
        )

        try:

            data = yf.download(
                tickers=chunk,
                period="8mo",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,
                group_by="column",
            )

        except Exception as e:

            print(
                f"Historical chunk failed: {e}"
            )

            continue

        for ticker in chunk:

            series = extract_close_series(
                data,
                ticker,
                chunk
            )

            if series is not None:
                result[ticker] = series

    print({
        "historyTickersRequested":
            len(tickers),

        "historyTickersLoaded":
            len(result),
    })

    return result


def period_return(
    series,
    trading_days
):
    if series is None:
        return None

    if len(series) <= trading_days:
        return None

    try:

        latest = float(
            series.iloc[-1]
        )

        old = float(
            series.iloc[
                -(trading_days + 1)
            ]
        )

        if old == 0:
            return None

        return round(
            (
                (latest / old) - 1
            ) * 100,
            4
        )

    except Exception:
        return None


# =========================================================
# MAIN
# =========================================================

def main():

    stocks = load_json(
        DATA / "stocks.json",
        []
    )

    company_data = load_json(
        DATA / "company_research.json",
        {}
    )

    company_scores = (
        company_data.get(
            "stocks",
            {}
        )
        or {}
    )

    evidence_data = load_json(
        DATA / "company_evidence.json",
        {}
    )

    evidence_stocks = (
        evidence_data.get(
            "stocks",
            {}
        )
        or {}
    )

    # -----------------------------------------------------
    # Previous research scores
    # -----------------------------------------------------

    previous_data = load_json(
        DATA / "research_scores.json",
        {}
    )

    previous_scores = (
        previous_data.get(
            "stocks",
            {}
        )
        or {}
    )

    # =====================================================
    # CLASSIFIED STOCKS
    # =====================================================

    classified = [
        row
        for row in stocks
        if (
            row.get("symbol")
            and row.get("sector")
            and row.get("sector")
            != "Unclassified"
        )
    ]

    # =====================================================
    # HISTORY
    # =====================================================

    stock_tickers = [
        f"{row['symbol']}.NS"
        for row in classified
    ]

    index_tickers = {
        NIFTY500
    }

    for row in classified:

        idx = sector_index(
            row.get("sector"),
            row.get("industry")
        )

        if idx:
            index_tickers.add(idx)

    history = download_history(
        stock_tickers
        +
        list(index_tickers)
    )

    # =====================================================
    # INDEX RETURNS
    # =====================================================

    index_returns = {}

    for ticker in index_tickers:

        series = history.get(
            ticker
        )

        index_returns[ticker] = {

            "1M":
                period_return(
                    series,
                    21
                ),

            "3M":
                period_return(
                    series,
                    63
                ),

            "6M":
                period_return(
                    series,
                    126
                ),
        }

    # =====================================================
    # SECTOR STRENGTH + ACTUAL SECTOR GROWTH
    # =====================================================

    sector_index_1m = {}

    for row in classified:

        idx = sector_index(
            row.get("sector"),
            row.get("industry")
        )

        if not idx:
            continue

        value = (
            index_returns
            .get(idx, {})
            .get("1M")
        )

        if value is not None:
            sector_index_1m[idx] = value

    sector_return_values = list(
        sector_index_1m.values()
    )

    sector_strength_by_index = {}

    for idx, value in (
        sector_index_1m.items()
    ):

        sector_strength_by_index[
            idx
        ] = percentile(
            value,
            sector_return_values
        )

    # =====================================================
    # STOCK GROWTH + STOCK STRENGTH RAW
    # =====================================================

    stock_growth_1m = {}
    stock_growth_3m = {}
    stock_growth_6m = {}

    raw_1m = {}
    raw_3m = {}
    raw_6m = {}

    for row in classified:

        symbol = row["symbol"]

        stock_series = history.get(
            f"{symbol}.NS"
        )

        if stock_series is None:
            continue

        idx = sector_index(
            row.get("sector"),
            row.get("industry")
        )

        benchmark = (
            idx
            or NIFTY500
        )

        benchmark_returns = (
            index_returns.get(
                benchmark,
                {}
            )
        )

        if not any(
            value is not None
            for value in
            benchmark_returns.values()
        ):

            benchmark_returns = (
                index_returns.get(
                    NIFTY500,
                    {}
                )
            )

        stock_1m = period_return(
            stock_series,
            21
        )

        stock_3m = period_return(
            stock_series,
            63
        )

        stock_6m = period_return(
            stock_series,
            126
        )

        # -------------------------------------------------
        # ACTUAL STOCK GROWTH %
        # -------------------------------------------------

        if stock_1m is not None:
            stock_growth_1m[
                symbol
            ] = stock_1m

        if stock_3m is not None:
            stock_growth_3m[
                symbol
            ] = stock_3m

        if stock_6m is not None:
            stock_growth_6m[
                symbol
            ] = stock_6m

        # -------------------------------------------------
        # BENCHMARK RETURNS
        # -------------------------------------------------

        bench_1m = (
            benchmark_returns.get("1M")
        )

        bench_3m = (
            benchmark_returns.get("3M")
        )

        bench_6m = (
            benchmark_returns.get("6M")
        )

        # -------------------------------------------------
        # EXCESS RETURNS FOR STRENGTH
        # -------------------------------------------------

        if (
            stock_1m is not None
            and bench_1m is not None
        ):
            raw_1m[symbol] = (
                stock_1m -
                bench_1m
            )

        if (
            stock_3m is not None
            and bench_3m is not None
        ):
            raw_3m[symbol] = (
                stock_3m -
                bench_3m
            )

        if (
            stock_6m is not None
            and bench_6m is not None
        ):
            raw_6m[symbol] = (
                stock_6m -
                bench_6m
            )

    # =====================================================
    # STOCK STRENGTH PERCENTILES
    # =====================================================

    values_1m = list(
        raw_1m.values()
    )

    values_3m = list(
        raw_3m.values()
    )

    values_6m = list(
        raw_6m.values()
    )

    stock_strength_1m = {
        symbol:
            percentile(
                value,
                values_1m
            )
        for symbol, value
        in raw_1m.items()
    }

    stock_strength_3m = {
        symbol:
            percentile(
                value,
                values_3m
            )
        for symbol, value
        in raw_3m.items()
    }

    stock_strength_6m = {
        symbol:
            percentile(
                value,
                values_6m
            )
        for symbol, value
        in raw_6m.items()
    }

    # =====================================================
    # TURNOVER
    # =====================================================

    all_turnover = []

    for row in stocks:

        turnover = row.get(
            "turnoverCr"
        )

        if turnover is not None:

            try:
                all_turnover.append(
                    float(turnover)
                )

            except Exception:
                pass

    # =====================================================
    # FINAL SCORES
    # =====================================================

    scores = {}

    sector_fallback_count = 0
    strength_1m_fallback_count = 0
    strength_3m_fallback_count = 0
    strength_6m_fallback_count = 0

    sector_growth_fallback_count = 0
    stock_growth_1m_fallback_count = 0
    stock_growth_3m_fallback_count = 0
    stock_growth_6m_fallback_count = 0

    verified_macro_count = 0
    automated_macro_count = 0

    verified_vm_count = 0
    automated_vm_count = 0

    for row in stocks:

        symbol = row.get(
            "symbol"
        )

        if not symbol:
            continue

        previous = (
            previous_scores.get(
                symbol,
                {}
            )
            or {}
        )

        sector = row.get(
            "sector"
        )

        industry = row.get(
            "industry"
        )

        idx = sector_index(
            sector,
            industry
        )

        # -------------------------------------------------
        # ACTUAL SECTOR GROWTH %
        # -------------------------------------------------

        new_sector_growth_1m = None

        if idx:

            new_sector_growth_1m = (
                index_returns
                .get(idx, {})
                .get("1M")
            )

        sector_growth_1m = (
            fallback_value(
                new_sector_growth_1m,
                previous,
                "sectorGrowth1M"
            )
        )

        if (
            new_sector_growth_1m is None
            and sector_growth_1m is not None
        ):
            sector_growth_fallback_count += 1

        # -------------------------------------------------
        # SECTOR STRENGTH WITH FALLBACK
        # -------------------------------------------------

        new_sector_strength = None

        if idx:

            new_sector_strength = (
                sector_strength_by_index
                .get(idx)
            )

        sector_strength = (
            fallback_value(
                new_sector_strength,
                previous,
                "sectorStrength"
            )
        )

        if (
            new_sector_strength is None
            and sector_strength is not None
        ):
            sector_fallback_count += 1

        # -------------------------------------------------
        # ACTUAL STOCK GROWTH % WITH FALLBACK
        # -------------------------------------------------

        new_stock_growth_1m = (
            stock_growth_1m.get(
                symbol
            )
        )

        new_stock_growth_3m = (
            stock_growth_3m.get(
                symbol
            )
        )

        new_stock_growth_6m = (
            stock_growth_6m.get(
                symbol
            )
        )

        stock_growth_value_1m = (
            fallback_value(
                new_stock_growth_1m,
                previous,
                "stockGrowth1M"
            )
        )

        stock_growth_value_3m = (
            fallback_value(
                new_stock_growth_3m,
                previous,
                "stockGrowth3M"
            )
        )

        stock_growth_value_6m = (
            fallback_value(
                new_stock_growth_6m,
                previous,
                "stockGrowth6M"
            )
        )

        if (
            new_stock_growth_1m is None
            and stock_growth_value_1m is not None
        ):
            stock_growth_1m_fallback_count += 1

        if (
            new_stock_growth_3m is None
            and stock_growth_value_3m is not None
        ):
            stock_growth_3m_fallback_count += 1

        if (
            new_stock_growth_6m is None
            and stock_growth_value_6m is not None
        ):
            stock_growth_6m_fallback_count += 1

        # -------------------------------------------------
        # STOCK STRENGTH WITH FALLBACK
        # -------------------------------------------------

        new_1m = (
            stock_strength_1m
            .get(symbol)
        )

        new_3m = (
            stock_strength_3m
            .get(symbol)
        )

        new_6m = (
            stock_strength_6m
            .get(symbol)
        )

        strength_1m = fallback_value(
            new_1m,
            previous,
            "stockStrength1M"
        )

        strength_3m = fallback_value(
            new_3m,
            previous,
            "stockStrength3M"
        )

        strength_6m = fallback_value(
            new_6m,
            previous,
            "stockStrength6M"
        )

        if (
            new_1m is None
            and strength_1m is not None
        ):
            strength_1m_fallback_count += 1

        if (
            new_3m is None
            and strength_3m is not None
        ):
            strength_3m_fallback_count += 1

        if (
            new_6m is None
            and strength_6m is not None
        ):
            strength_6m_fallback_count += 1

        # -------------------------------------------------
        # COMPANY RESEARCH
        # -------------------------------------------------

        company = (
            company_scores.get(
                symbol,
                {}
            )
            or {}
        )

        company_reasons = (
            company.get(
                "researchReasons",
                {}
            )
            or {}
        )

        # -------------------------------------------------
        # MACRO
        # -------------------------------------------------

        macro_verified = (
            verified_evidence(
                evidence_stocks,
                symbol,
                "macro"
            )
        )

        if macro_verified:

            macro_support = (
                macro_verified["score"]
            )

            macro_detail = {
                "reason":
                    macro_verified["reason"],

                "source":
                    macro_verified["source"],

                "sourceDate":
                    macro_verified["sourceDate"],

                "mode":
                    "VERIFIED",
            }

            verified_macro_count += 1

        else:

            (
                macro_support,
                macro_reason
            ) = macro_score(
                sector,
                industry
            )

            macro_support = fallback_value(
                macro_support,
                previous,
                "macroSupport"
            )

            macro_detail = {
                "reason":
                    macro_reason,

                "source":
                    METHODOLOGY["macro"],

                "sourceDate":
                    RUN_DATE,

                "mode":
                    (
                        "AUTOMATED"
                        if macro_support
                        is not None
                        else "PENDING"
                    ),
            }

            if macro_support is not None:
                automated_macro_count += 1

        # -------------------------------------------------
        # VALUE MIGRATION
        # -------------------------------------------------

        vm_verified = (
            verified_evidence(
                evidence_stocks,
                symbol,
                "valueMigration"
            )
        )

        value_migration = None

        if vm_verified:

            value_migration = (
                vm_verified["score"]
            )

            vm_detail = {
                "reason":
                    vm_verified["reason"],

                "source":
                    vm_verified["source"],

                "sourceDate":
                    vm_verified["sourceDate"],

                "mode":
                    "VERIFIED",
            }

            verified_vm_count += 1

        else:

            change = row.get(
                "changePct"
            )

            turnover = row.get(
                "turnoverCr"
            )

            vm_detail = {
                "reason":
                    (
                        "Automated Value Migration screening proxy "
                        "is currently unavailable because required "
                        "price or turnover data is missing. "
                        "This is not a verified business Value Migration rating."
                    ),

                "source":
                    METHODOLOGY[
                        "valueMigration"
                    ],

                "sourceDate":
                    RUN_DATE,

                "mode":
                    "PENDING",
            }

            if (
                change is not None
                and turnover is not None
                and all_turnover
            ):

                try:

                    momentum = clamp(
                        50 +
                        float(change) * 7
                    )

                    turnover_score = percentile(
                        float(turnover),
                        all_turnover
                    )

                    if turnover_score is not None:

                        value_migration = round(
                            momentum * 0.60
                            +
                            turnover_score * 0.40,
                            2
                        )

                        vm_detail = {
                            "reason":
                                (
                                    "AUTOMATED screening proxy only — "
                                    "NOT verified business Value Migration. "
                                    "Current score uses 60% short-term "
                                    f"price-momentum component ({momentum:.1f}) "
                                    "and 40% turnover-percentile component "
                                    f"({turnover_score:.1f}). "
                                    "Verified Value Migration requires "
                                    "company/business evidence showing a "
                                    "structural shift such as market-share migration, "
                                    "import substitution, organised-market gains, "
                                    "technology transition or movement toward "
                                    "higher-value products."
                                ),

                            "source":
                                METHODOLOGY[
                                    "valueMigration"
                                ],

                            "sourceDate":
                                RUN_DATE,

                            "mode":
                                "AUTOMATED_PROXY",
                        }

                        automated_vm_count += 1

                except Exception:
                    pass

            # Previous VM fallback

            if value_migration is None:

                old_vm = previous.get(
                    "valueMigration"
                )

                if old_vm is not None:

                    value_migration = old_vm

                    old_reasons = (
                        previous.get(
                            "researchReasons",
                            {}
                        )
                        or {}
                    )

                    old_vm_detail = (
                        old_reasons.get(
                            "valueMigration",
                            {}
                        )
                        or {}
                    )

                    if old_vm_detail:
                        vm_detail = (
                            old_vm_detail
                        )

        # -------------------------------------------------
        # COMPANY SCORE FALLBACKS
        # -------------------------------------------------

        tailwind_score = fallback_value(
            company.get(
                "tailwindScore"
            ),
            previous,
            "tailwindScore"
        )

        future_growth = fallback_value(
            company.get(
                "futureGrowth"
            ),
            previous,
            "futureGrowth"
        )

        fundamental_quality = fallback_value(
            company.get(
                "fundamentalQuality"
            ),
            previous,
            "fundamentalQuality"
        )

        capex_score_value = fallback_value(
            company.get(
                "capexScore"
            ),
            previous,
            "capexScore"
        )

        # -------------------------------------------------
        # RESEARCH REASONS
        # -------------------------------------------------

        previous_reasons = (
            previous.get(
                "researchReasons",
                {}
            )
            or {}
        )

        research_reasons = {

            "tailwind":
                (
                    company_reasons.get(
                        "tailwind"
                    )
                    or
                    previous_reasons.get(
                        "tailwind",
                        {}
                    )
                ),

            "macro":
                macro_detail,

            "valueMigration":
                vm_detail,

            "futureGrowth":
                (
                    company_reasons.get(
                        "futureGrowth"
                    )
                    or
                    previous_reasons.get(
                        "futureGrowth",
                        {}
                    )
                ),

            "fundamentalQuality":
                (
                    company_reasons.get(
                        "fundamentalQuality"
                    )
                    or
                    previous_reasons.get(
                        "fundamentalQuality",
                        {}
                    )
                ),

            "capex":
                (
                    company_reasons.get(
                        "capex"
                    )
                    or
                    previous_reasons.get(
                        "capex",
                        {}
                    )
                ),
        }

        # -------------------------------------------------
        # FINAL RECORD
        # -------------------------------------------------

        scores[symbol] = {

            # =============================================
            # ACTUAL GROWTH %
            # =============================================

            "sectorGrowth1M":
                sector_growth_1m,

            "stockGrowth1M":
                stock_growth_value_1m,

            "stockGrowth3M":
                stock_growth_value_3m,

            "stockGrowth6M":
                stock_growth_value_6m,

            # =============================================
            # EXISTING STRENGTH SCORES
            # =============================================

            "sectorStrength":
                sector_strength,

            "stockStrength1M":
                strength_1m,

            "stockStrength3M":
                strength_3m,

            "stockStrength6M":
                strength_6m,

            "strengthBenchmark":
                (
                    idx
                    or
                    previous.get(
                        "strengthBenchmark"
                    )
                    or
                    NIFTY500
                ),

            # =============================================
            # RESEARCH SCORES
            # =============================================

            "tailwindScore":
                tailwind_score,

            "macroSupport":
                macro_support,

            "valueMigration":
                value_migration,

            "futureGrowth":
                future_growth,

            "fundamentalQuality":
                fundamental_quality,

            "capexScore":
                capex_score_value,

            "researchReasons":
                research_reasons,
        }

    # =====================================================
    # OUTPUT
    # =====================================================

    output = {

        "_meta": {

            "description":
                (
                    "MY MARKET RESEARCH "
                    "research scoring inputs"
                ),

            "scale":
                "0-100",

            "updated":
                RUN_DATE,

            "methodologyPage":
                "methodology.html",

            "historyFallback":
                (
                    "Previous valid Sector Growth, Stock Growth, "
                    "Sector Strength and Stock Strength values "
                    "are preserved when current historical-price "
                    "data is unavailable."
                ),

            "method": {

                "sectorGrowth1M":
                    (
                        "Actual 1-month return of relevant "
                        "Nifty sector index"
                    ),

                "stockGrowth1M":
                    "Actual 1-month stock price return",

                "stockGrowth3M":
                    "Actual 3-month stock price return",

                "stockGrowth6M":
                    "Actual 6-month stock price return",

                "sectorStrength":
                    (
                        "1-month relevant Nifty "
                        "sector-index return percentile"
                    ),

                "stockStrength1M":
                    (
                        "1-month stock excess return "
                        "versus relevant benchmark percentile"
                    ),

                "stockStrength3M":
                    (
                        "3-month stock excess return "
                        "versus relevant benchmark percentile"
                    ),

                "stockStrength6M":
                    (
                        "6-month stock excess return "
                        "versus relevant benchmark percentile"
                    ),

                "tailwindScore":
                    (
                        "Company research / sector "
                        "structural-tailwind score"
                    ),

                "macroSupport":
                    (
                        "Verified evidence override when available; "
                        "otherwise sector-level Macro screening heuristic"
                    ),

                "valueMigration":
                    (
                        "Verified company/business evidence overrides "
                        "the automated price/turnover screening proxy"
                    ),

                "futureGrowth":
                    "Company research score",

                "fundamentalQuality":
                    "Company financial-quality score",

                "capexScore":
                    "Company CAPEX score",
            },

            "weights": {

                "sectorStrength":
                    10,

                "macroSupport":
                    20,

                "valueMigration":
                    20,

                "futureGrowth":
                    20,

                "fundamentalQuality":
                    20,

                "capexScore":
                    10,
            },

            "note":
                (
                    "Sector Growth and Stock Growth are actual "
                    "price-return percentages. Sector Strength and "
                    "Stock Strength remain 0-100 percentile screening "
                    "metrics. Automated Value Migration is a screening "
                    "proxy and not verified business migration."
                ),
        },

        "stocks":
            scores,
    }

    (
        DATA /
        "research_scores.json"
    ).write_text(

        json.dumps(
            output,
            indent=2,
            ensure_ascii=False
        )
    )

    # =====================================================
    # LOG
    # =====================================================

    print({

        "stocksProcessed":
            len(scores),

        "sectorGrowth1MAvailable":
            sum(
                1
                for value
                in scores.values()
                if value.get(
                    "sectorGrowth1M"
                )
                is not None
            ),

        "stockGrowth1MAvailable":
            sum(
                1
                for value
                in scores.values()
                if value.get(
                    "stockGrowth1M"
                )
                is not None
            ),

        "stockGrowth3MAvailable":
            sum(
                1
                for value
                in scores.values()
                if value.get(
                    "stockGrowth3M"
                )
                is not None
            ),

        "stockGrowth6MAvailable":
            sum(
                1
                for value
                in scores.values()
                if value.get(
                    "stockGrowth6M"
                )
                is not None
            ),

        "sectorStrengthAvailable":
            sum(
                1
                for value
                in scores.values()
                if value.get(
                    "sectorStrength"
                )
                is not None
            ),

        "stockStrength1MAvailable":
            sum(
                1
                for value
                in scores.values()
                if value.get(
                    "stockStrength1M"
                )
                is not None
            ),

        "stockStrength3MAvailable":
            sum(
                1
                for value
                in scores.values()
                if value.get(
                    "stockStrength3M"
                )
                is not None
            ),

        "stockStrength6MAvailable":
            sum(
                1
                for value
                in scores.values()
                if value.get(
                    "stockStrength6M"
                )
                is not None
            ),

        "sectorGrowthFallbackUsed":
            sector_growth_fallback_count,

        "stockGrowth1MFallbackUsed":
            stock_growth_1m_fallback_count,

        "stockGrowth3MFallbackUsed":
            stock_growth_3m_fallback_count,

        "stockGrowth6MFallbackUsed":
            stock_growth_6m_fallback_count,

        "sectorFallbackUsed":
            sector_fallback_count,

        "stockStrength1MFallbackUsed":
            strength_1m_fallback_count,

        "stockStrength3MFallbackUsed":
            strength_3m_fallback_count,

        "stockStrength6MFallbackUsed":
            strength_6m_fallback_count,

        "verifiedMacro":
            verified_macro_count,

        "automatedMacro":
            automated_macro_count,

        "verifiedValueMigration":
            verified_vm_count,

        "automatedValueMigrationProxy":
            automated_vm_count,
    })


if __name__ == "__main__":
    main()
