import json
from pathlib import Path
from datetime import datetime, timezone
from statistics import median

import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
NIFTY500 = "^CRSLDX"
RUN_DATE = datetime.now(timezone.utc).date().isoformat()

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


def percentile_1_99(value, values):
    """
    Cross-sectional rating:
    lowest available observation = 1
    highest available observation = 99
    """

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

    if len(clean) == 1:
        return 99

    count = sum(
        1
        for v in clean
        if v <= value
    )

    rank_index = max(
        0,
        count - 1
    )

    score = (
        1
        +
        98
        * rank_index
        / (len(clean) - 1)
    )

    return round(
        clamp(score, 1, 99),
        2
    )


def fallback_value(
    new_value,
    previous,
    field
):
    """
    Current calculation unavailable ho to
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


def normalize_sector_name(value):
    return str(
        value or ""
    ).strip()


def normalize_industry_name(value):
    return str(
        value or ""
    ).strip()


def median_map(grouped):
    result = {}

    for key, values in grouped.items():

        clean = [
            safe_float(value)
            for value in values
            if safe_float(value) is not None
        ]

        if not clean:
            continue

        result[key] = round(
            median(clean),
            4
        )

    return result


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
            [
                "bank",
                "banking"
            ],
            "^NSEBANK"
        ),

        (
            [
                "financial services",
                "finance",
                "nbfc",
                "asset management",
                "insurance"
            ],
            "^CNXFINANCE"
        ),

        (
            [
                "automobile",
                "auto component",
                "auto components",
                "automotive",
                "auto"
            ],
            "^CNXAUTO"
        ),

        (
            [
                "information technology",
                "software",
                "it services",
                "technology"
            ],
            "^CNXIT"
        ),

        (
            [
                "fmcg",
                "consumer staples"
            ],
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
                "metals",
                "mining",
                "steel"
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
                "entertainment",
                "broadcasting"
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
                "capital goods",
                "industrials",
                "industrial"
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
            [
                "renewable",
                "solar",
                "power"
            ],
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
            [
                "industrial manufacturing"
            ],
            80,
            (
                "Automated Macro screening proxy: "
                "domestic manufacturing and investment-cycle "
                "conditions are supportive."
            )
        ),

        (
            [
                "defence",
                "aerospace"
            ],
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
            [
                "telecom"
            ],
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
            [
                "realty"
            ],
            65,
            (
                "Automated Macro screening proxy: "
                "urbanisation, housing demand and commercial activity "
                "provide moderate support."
            )
        ),

        (
            [
                "consumer"
            ],
            60,
            (
                "Automated Macro screening proxy: "
                "consumption growth, income growth and "
                "premiumisation provide moderate support."
            )
        ),

        (
            [
                "information technology"
            ],
            60,
            (
                "Automated Macro screening proxy: "
                "digital transformation, cloud adoption and "
                "technology spending provide support."
            )
        ),

        (
            [
                "oil",
                "gas"
            ],
            55,
            (
                "Automated Macro screening proxy: "
                "energy demand remains supportive, although "
                "commodity cycles reduce visibility."
            )
        ),

        (
            [
                "media"
            ],
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
            return (
                score,
                reason
            )

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

                close = data[
                    "Close"
                ]

                if isinstance(
                    close,
                    pd.Series
                ):

                    series = close

                elif ticker in close.columns:

                    series = close[
                        ticker
                    ]

                elif (
                    len(chunk) == 1
                    and len(close.columns) == 1
                ):

                    series = close.iloc[
                        :,
                        0
                    ]

                else:

                    return None

            elif (
                ticker
                in data.columns
                .get_level_values(0)
            ):

                block = data[
                    ticker
                ]

                if (
                    "Close"
                    not in block.columns
                ):
                    return None

                series = block[
                    "Close"
                ]

            else:

                return None

        else:

            if (
                "Close"
                not in data.columns
            ):
                return None

            series = data[
                "Close"
            ]

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


def download_history(
    tickers
):
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

                result[
                    ticker
                ] = series

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

    if (
        len(series)
        <= trading_days
    ):
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
                (
                    latest /
                    old
                ) - 1
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
        DATA /
        "stocks.json",
        []
    )

    company_data = load_json(
        DATA /
        "company_research.json",
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
        DATA /
        "company_evidence.json",
        {}
    )

    evidence_stocks = (
        evidence_data.get(
            "stocks",
            {}
        )
        or {}
    )

    previous_data = load_json(
        DATA /
        "research_scores.json",
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
    # HISTORY TICKERS
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
            index_tickers.add(
                idx
            )


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

        index_returns[
            ticker
        ] = {

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
    # STOCK ACTUAL RETURNS
    # =====================================================

    stock_growth_1m = {}
    stock_growth_3m = {}
    stock_growth_6m = {}


    for row in classified:

        symbol = row[
            "symbol"
        ]

        stock_series = history.get(
            f"{symbol}.NS"
        )

        if stock_series is None:
            continue


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


    # =====================================================
    # INDUSTRY MOMENTUM
    # =====================================================
    #
    # Same Industry ke sab available stocks ka
    # median return use hoga.
    #
    # Industry Rating:
    # 50% x 1M percentile
    # 30% x 3M percentile
    # 20% x 6M percentile
    # =====================================================

    industry_returns_1m = {}
    industry_returns_3m = {}
    industry_returns_6m = {}


    for row in classified:

        symbol = row.get(
            "symbol"
        )

        industry = normalize_industry_name(
            row.get(
                "industry"
            )
        )


        if (
            not symbol
            or not industry
            or industry == "Unclassified"
        ):
            continue


        value_1m = stock_growth_1m.get(
            symbol
        )

        value_3m = stock_growth_3m.get(
            symbol
        )

        value_6m = stock_growth_6m.get(
            symbol
        )


        if value_1m is not None:

            industry_returns_1m.setdefault(
                industry,
                []
            ).append(
                value_1m
            )


        if value_3m is not None:

            industry_returns_3m.setdefault(
                industry,
                []
            ).append(
                value_3m
            )


        if value_6m is not None:

            industry_returns_6m.setdefault(
                industry,
                []
            ).append(
                value_6m
            )


    industry_growth_1m = median_map(
        industry_returns_1m
    )

    industry_growth_3m = median_map(
        industry_returns_3m
    )

    industry_growth_6m = median_map(
        industry_returns_6m
    )


    industry_values_1m = list(
        industry_growth_1m.values()
    )

    industry_values_3m = list(
        industry_growth_3m.values()
    )

    industry_values_6m = list(
        industry_growth_6m.values()
    )


    industry_percentile_1m = {

        industry:
            percentile_1_99(
                value,
                industry_values_1m
            )

        for (
            industry,
            value
        ) in industry_growth_1m.items()
    }


    industry_percentile_3m = {

        industry:
            percentile_1_99(
                value,
                industry_values_3m
            )

        for (
            industry,
            value
        ) in industry_growth_3m.items()
    }


    industry_percentile_6m = {

        industry:
            percentile_1_99(
                value,
                industry_values_6m
            )

        for (
            industry,
            value
        ) in industry_growth_6m.items()
    }


    industry_rating = {}


    all_industries = (
        set(industry_growth_1m)
        |
        set(industry_growth_3m)
        |
        set(industry_growth_6m)
    )


    for industry in all_industries:

        p1 = industry_percentile_1m.get(
            industry
        )

        p3 = industry_percentile_3m.get(
            industry
        )

        p6 = industry_percentile_6m.get(
            industry
        )


        if (
            p1 is None
            or p3 is None
            or p6 is None
        ):
            continue


        rating = (
            p1 * 0.50
            +
            p3 * 0.30
            +
            p6 * 0.20
        )


        industry_rating[
            industry
        ] = int(
            round(
                clamp(
                    rating,
                    1,
                    99
                )
            )
        )


    # =====================================================
    # STOCK MOMENTUM RATING
    # =====================================================
    #
    # Relative 1M =
    # Stock 1M - Industry 1M
    #
    # Relative 3M =
    # Stock 3M - Industry 3M
    #
    # Relative 6M =
    # Stock 6M - Industry 6M
    #
    # Rating:
    # 50% x Relative 1M percentile
    # 30% x Relative 3M percentile
    # 20% x Relative 6M percentile
    # =====================================================

    stock_relative_1m = {}
    stock_relative_3m = {}
    stock_relative_6m = {}


    for row in classified:

        symbol = row.get(
            "symbol"
        )

        industry = normalize_industry_name(
            row.get(
                "industry"
            )
        )


        if (
            not symbol
            or not industry
            or industry == "Unclassified"
        ):
            continue


        stock_1m = stock_growth_1m.get(
            symbol
        )

        stock_3m = stock_growth_3m.get(
            symbol
        )

        stock_6m = stock_growth_6m.get(
            symbol
        )


        industry_1m = industry_growth_1m.get(
            industry
        )

        industry_3m = industry_growth_3m.get(
            industry
        )

        industry_6m = industry_growth_6m.get(
            industry
        )


        if (
            stock_1m is not None
            and industry_1m is not None
        ):

            stock_relative_1m[
                symbol
            ] = (
                stock_1m
                -
                industry_1m
            )


        if (
            stock_3m is not None
            and industry_3m is not None
        ):

            stock_relative_3m[
                symbol
            ] = (
                stock_3m
                -
                industry_3m
            )


        if (
            stock_6m is not None
            and industry_6m is not None
        ):

            stock_relative_6m[
                symbol
            ] = (
                stock_6m
                -
                industry_6m
            )


    relative_values_1m = list(
        stock_relative_1m.values()
    )

    relative_values_3m = list(
        stock_relative_3m.values()
    )

    relative_values_6m = list(
        stock_relative_6m.values()
    )


    stock_relative_percentile_1m = {

        symbol:
            percentile_1_99(
                value,
                relative_values_1m
            )

        for (
            symbol,
            value
        ) in stock_relative_1m.items()
    }


    stock_relative_percentile_3m = {

        symbol:
            percentile_1_99(
                value,
                relative_values_3m
            )

        for (
            symbol,
            value
        ) in stock_relative_3m.items()
    }


    stock_relative_percentile_6m = {

        symbol:
            percentile_1_99(
                value,
                relative_values_6m
            )

        for (
            symbol,
            value
        ) in stock_relative_6m.items()
    }


    stock_momentum_rating = {}


    all_momentum_symbols = (
        set(stock_relative_1m)
        |
        set(stock_relative_3m)
        |
        set(stock_relative_6m)
    )


    for symbol in all_momentum_symbols:

        p1 = stock_relative_percentile_1m.get(
            symbol
        )

        p3 = stock_relative_percentile_3m.get(
            symbol
        )

        p6 = stock_relative_percentile_6m.get(
            symbol
        )


        if (
            p1 is None
            or p3 is None
            or p6 is None
        ):
            continue


        rating = (
            p1 * 0.50
            +
            p3 * 0.30
            +
            p6 * 0.20
        )


        stock_momentum_rating[
            symbol
        ] = int(
            round(
                clamp(
                    rating,
                    1,
                    99
                )
            )
        )


    # =====================================================
    # EXISTING SECTOR STOCK-MEDIAN FALLBACK
    # =====================================================

    sector_stock_returns = {}


    for row in classified:

        symbol = row.get(
            "symbol"
        )

        sector = normalize_sector_name(
            row.get(
                "sector"
            )
        )


        if (
            not symbol
            or not sector
            or sector == "Unclassified"
        ):
            continue


        value = stock_growth_1m.get(
            symbol
        )


        if value is None:
            continue


        sector_stock_returns.setdefault(
            sector,
            []
        ).append(
            value
        )


    sector_median_1m = median_map(
        sector_stock_returns
    )


    # =====================================================
    # EXISTING FINAL SECTOR GROWTH MAP
    # =====================================================

    sector_growth_by_sector = {}

    sector_growth_source = {}

    unique_sector_rows = {}


    for row in classified:

        sector = normalize_sector_name(
            row.get(
                "sector"
            )
        )

        if (
            not sector
            or sector == "Unclassified"
        ):
            continue

        if (
            sector
            not in unique_sector_rows
        ):

            unique_sector_rows[
                sector
            ] = row


    for (
        sector,
        sample_row
    ) in unique_sector_rows.items():

        idx = sector_index(
            sample_row.get(
                "sector"
            ),
            sample_row.get(
                "industry"
            )
        )


        index_value = None


        if idx:

            index_value = (
                index_returns
                .get(
                    idx,
                    {}
                )
                .get(
                    "1M"
                )
            )


        if index_value is not None:

            sector_growth_by_sector[
                sector
            ] = index_value

            sector_growth_source[
                sector
            ] = (
                f"INDEX:{idx}"
            )

            continue


        median_value = (
            sector_median_1m
            .get(
                sector
            )
        )


        if median_value is not None:

            sector_growth_by_sector[
                sector
            ] = median_value

            sector_growth_source[
                sector
            ] = (
                "SECTOR_STOCK_MEDIAN"
            )


    # =====================================================
    # EXISTING SECTOR STRENGTH
    # =====================================================

    sector_growth_values = list(
        sector_growth_by_sector.values()
    )


    sector_strength_by_sector = {}


    for (
        sector,
        value
    ) in sector_growth_by_sector.items():

        sector_strength_by_sector[
            sector
        ] = percentile(
            value,
            sector_growth_values
        )


    # =====================================================
    # EXISTING STOCK STRENGTH RAW
    # =====================================================

    raw_1m = {}
    raw_3m = {}
    raw_6m = {}


    for row in classified:

        symbol = row[
            "symbol"
        ]

        stock_1m = (
            stock_growth_1m
            .get(symbol)
        )

        stock_3m = (
            stock_growth_3m
            .get(symbol)
        )

        stock_6m = (
            stock_growth_6m
            .get(symbol)
        )


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
            for value
            in benchmark_returns.values()
        ):

            benchmark_returns = (
                index_returns.get(
                    NIFTY500,
                    {}
                )
            )


        bench_1m = (
            benchmark_returns.get(
                "1M"
            )
        )

        bench_3m = (
            benchmark_returns.get(
                "3M"
            )
        )

        bench_6m = (
            benchmark_returns.get(
                "6M"
            )
        )


        if (
            stock_1m is not None
            and bench_1m is not None
        ):

            raw_1m[
                symbol
            ] = (
                stock_1m -
                bench_1m
            )


        if (
            stock_3m is not None
            and bench_3m is not None
        ):

            raw_3m[
                symbol
            ] = (
                stock_3m -
                bench_3m
            )


        if (
            stock_6m is not None
            and bench_6m is not None
        ):

            raw_6m[
                symbol
            ] = (
                stock_6m -
                bench_6m
            )


    # =====================================================
    # EXISTING STOCK STRENGTH PERCENTILES
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

        for (
            symbol,
            value
        ) in raw_1m.items()
    }


    stock_strength_3m = {

        symbol:
            percentile(
                value,
                values_3m
            )

        for (
            symbol,
            value
        ) in raw_3m.items()
    }


    stock_strength_6m = {

        symbol:
            percentile(
                value,
                values_6m
            )

        for (
            symbol,
            value
        ) in raw_6m.items()
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

    industry_growth_1m_fallback_count = 0
    industry_growth_3m_fallback_count = 0
    industry_growth_6m_fallback_count = 0

    industry_rating_fallback_count = 0
    stock_momentum_rating_fallback_count = 0

    verified_macro_count = 0
    automated_macro_count = 0

    verified_vm_count = 0
    automated_vm_count = 0


    sector_growth_index_count = 0
    sector_growth_median_count = 0


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


        sector = normalize_sector_name(
            row.get(
                "sector"
            )
        )

        industry = normalize_industry_name(
            row.get(
                "industry"
            )
        )


        idx = sector_index(
            sector,
            industry
        )


        # -------------------------------------------------
        # INDUSTRY MOMENTUM
        # -------------------------------------------------

        new_industry_growth_1m = None
        new_industry_growth_3m = None
        new_industry_growth_6m = None
        new_industry_rating = None


        if (
            industry
            and industry != "Unclassified"
        ):

            new_industry_growth_1m = (
                industry_growth_1m.get(
                    industry
                )
            )

            new_industry_growth_3m = (
                industry_growth_3m.get(
                    industry
                )
            )

            new_industry_growth_6m = (
                industry_growth_6m.get(
                    industry
                )
            )

            new_industry_rating = (
                industry_rating.get(
                    industry
                )
            )


        industry_growth_value_1m = (
            fallback_value(
                new_industry_growth_1m,
                previous,
                "industryGrowth1M"
            )
        )


        industry_growth_value_3m = (
            fallback_value(
                new_industry_growth_3m,
                previous,
                "industryGrowth3M"
            )
        )


        industry_growth_value_6m = (
            fallback_value(
                new_industry_growth_6m,
                previous,
                "industryGrowth6M"
            )
        )


        industry_rating_value = (
            fallback_value(
                new_industry_rating,
                previous,
                "industryRating"
            )
        )


        if (
            new_industry_growth_1m
            is None
            and industry_growth_value_1m
            is not None
        ):

            industry_growth_1m_fallback_count += 1


        if (
            new_industry_growth_3m
            is None
            and industry_growth_value_3m
            is not None
        ):

            industry_growth_3m_fallback_count += 1


        if (
            new_industry_growth_6m
            is None
            and industry_growth_value_6m
            is not None
        ):

            industry_growth_6m_fallback_count += 1


        if (
            new_industry_rating
            is None
            and industry_rating_value
            is not None
        ):

            industry_rating_fallback_count += 1


        # -------------------------------------------------
        # STOCK MOMENTUM RATING
        # -------------------------------------------------

        new_stock_momentum_rating = (
            stock_momentum_rating.get(
                symbol
            )
        )


        stock_momentum_rating_value = (
            fallback_value(
                new_stock_momentum_rating,
                previous,
                "stockMomentumRating"
            )
        )


        if (
            new_stock_momentum_rating
            is None
            and stock_momentum_rating_value
            is not None
        ):

            stock_momentum_rating_fallback_count += 1


        # -------------------------------------------------
        # ACTUAL SECTOR GROWTH 1M
        # -------------------------------------------------

        new_sector_growth_1m = None


        if (
            sector
            and sector != "Unclassified"
        ):

            new_sector_growth_1m = (
                sector_growth_by_sector
                .get(
                    sector
                )
            )


        sector_growth_1m = (
            fallback_value(
                new_sector_growth_1m,
                previous,
                "sectorGrowth1M"
            )
        )


        if (
            new_sector_growth_1m
            is None
            and sector_growth_1m
            is not None
        ):

            sector_growth_fallback_count += 1


        if (
            new_sector_growth_1m
            is not None
        ):

            source = (
                sector_growth_source
                .get(
                    sector,
                    ""
                )
            )


            if source.startswith(
                "INDEX:"
            ):

                sector_growth_index_count += 1


            elif (
                source ==
                "SECTOR_STOCK_MEDIAN"
            ):

                sector_growth_median_count += 1


        # -------------------------------------------------
        # SECTOR STRENGTH
        # -------------------------------------------------

        new_sector_strength = None


        if (
            sector
            and sector != "Unclassified"
        ):

            new_sector_strength = (
                sector_strength_by_sector
                .get(
                    sector
                )
            )


        sector_strength = (
            fallback_value(
                new_sector_strength,
                previous,
                "sectorStrength"
            )
        )


        if (
            new_sector_strength
            is None
            and sector_strength
            is not None
        ):

            sector_fallback_count += 1


        # -------------------------------------------------
        # STOCK GROWTH
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
            new_stock_growth_1m
            is None
            and stock_growth_value_1m
            is not None
        ):

            stock_growth_1m_fallback_count += 1


        if (
            new_stock_growth_3m
            is None
            and stock_growth_value_3m
            is not None
        ):

            stock_growth_3m_fallback_count += 1


        if (
            new_stock_growth_6m
            is None
            and stock_growth_value_6m
            is not None
        ):

            stock_growth_6m_fallback_count += 1


        # -------------------------------------------------
        # STOCK STRENGTH
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
                macro_verified[
                    "score"
                ]
            )


            macro_detail = {

                "reason":
                    macro_verified[
                        "reason"
                    ],

                "source":
                    macro_verified[
                        "source"
                    ],

                "sourceDate":
                    macro_verified[
                        "sourceDate"
                    ],

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


            macro_support = (
                fallback_value(
                    macro_support,
                    previous,
                    "macroSupport"
                )
            )


            macro_detail = {

                "reason":
                    macro_reason,

                "source":
                    METHODOLOGY[
                        "macro"
                    ],

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


            if (
                macro_support
                is not None
            ):

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
                vm_verified[
                    "score"
                ]
            )


            vm_detail = {

                "reason":
                    vm_verified[
                        "reason"
                    ],

                "source":
                    vm_verified[
                        "source"
                    ],

                "sourceDate":
                    vm_verified[
                        "sourceDate"
                    ],

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
                        float(change) *
                        7
                    )


                    turnover_score = percentile(
                        float(turnover),
                        all_turnover
                    )


                    if (
                        turnover_score
                        is not None
                    ):

                        value_migration = round(
                            momentum *
                            0.60
                            +
                            turnover_score *
                            0.40,
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


            if (
                value_migration
                is None
            ):

                old_vm = previous.get(
                    "valueMigration"
                )


                if old_vm is not None:

                    value_migration = (
                        old_vm
                    )


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

        scores[
            symbol
        ] = {

            # NEW INDUSTRY MOMENTUM

            "industryGrowth1M":
                industry_growth_value_1m,

            "industryGrowth3M":
                industry_growth_value_3m,

            "industryGrowth6M":
                industry_growth_value_6m,

            "industryRating":
                industry_rating_value,

            "stockMomentumRating":
                stock_momentum_rating_value,


            # EXISTING ACTUAL GROWTH %

            "sectorGrowth1M":
                sector_growth_1m,

            "sectorGrowthSource":
                (
                    sector_growth_source
                    .get(
                        sector
                    )
                    if (
                        sector_growth_1m
                        is not None
                    )
                    else None
                ),

            "stockGrowth1M":
                stock_growth_value_1m,

            "stockGrowth3M":
                stock_growth_value_3m,

            "stockGrowth6M":
                stock_growth_value_6m,


            # EXISTING STRENGTH

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


            # EXISTING RESEARCH

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
                    "Industry Growth uses the median actual return of "
                    "available stocks in the same Industry for 1M, "
                    "3M and 6M. Industry Rating and Stock Momentum "
                    "Rating use 1-99 percentile inputs with 50/30/20 "
                    "weights. Sector Growth retains the existing "
                    "sector-index / sector-stock median fallback. "
                    "Previous valid values are preserved when current "
                    "calculations are unavailable."
                ),

            "method": {

                "industryGrowth1M":
                    (
                        "Median actual 1-month return of available "
                        "stocks in the same Industry."
                    ),

                "industryGrowth3M":
                    (
                        "Median actual 3-month return of available "
                        "stocks in the same Industry."
                    ),

                "industryGrowth6M":
                    (
                        "Median actual 6-month return of available "
                        "stocks in the same Industry."
                    ),

                "industryRating":
                    (
                        "1-99 rating = 50% Industry 1M percentile + "
                        "30% Industry 3M percentile + "
                        "20% Industry 6M percentile."
                    ),

                "stockMomentumRating":
                    (
                        "1-99 rating based on Stock return minus "
                        "its own Industry median return for "
                        "1M/3M/6M, cross-sectionally ranked and "
                        "combined with 50%/30%/20% weights."
                    ),

                "sectorGrowth1M":
                    (
                        "Actual 1-month relevant Nifty sector-index "
                        "return; fallback is median 1-month return "
                        "of available stocks in the same sector."
                    ),

                "stockGrowth1M":
                    "Actual 1-month stock price return",

                "stockGrowth3M":
                    "Actual 3-month stock price return",

                "stockGrowth6M":
                    "Actual 6-month stock price return",

                "sectorStrength":
                    (
                        "Percentile rank of final sector 1-month "
                        "growth across available classified sectors."
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
                    "Industry Growth and Stock Growth are actual "
                    "price-return percentages. Industry Rating and "
                    "Stock Momentum Rating are 1-99 momentum ratings "
                    "using 50/30/20 weights. Sector Strength and "
                    "legacy Stock Strength remain 0-100 percentile "
                    "screening metrics. Automated Value Migration "
                    "is a screening proxy and not verified business "
                    "migration."
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

        "classifiedStocks":
            len(classified),

        "classifiedSectors":
            len(
                unique_sector_rows
            ),

        "industries1MAvailable":
            len(
                industry_growth_1m
            ),

        "industries3MAvailable":
            len(
                industry_growth_3m
            ),

        "industries6MAvailable":
            len(
                industry_growth_6m
            ),

        "industryRatingsAvailable":
            len(
                industry_rating
            ),

        "stockMomentumRatingsCalculated":
            len(
                stock_momentum_rating
            ),

        "sectorGrowthSectorsAvailable":
            len(
                sector_growth_by_sector
            ),

        "sectorGrowthIndexAssignments":
            sector_growth_index_count,

        "sectorGrowthMedianAssignments":
            sector_growth_median_count,

        "industryGrowth1MAvailable":
            sum(
                1
                for value
                in scores.values()
                if value.get(
                    "industryGrowth1M"
                )
                is not None
            ),

        "industryGrowth3MAvailable":
            sum(
                1
                for value
                in scores.values()
                if value.get(
                    "industryGrowth3M"
                )
                is not None
            ),

        "industryGrowth6MAvailable":
            sum(
                1
                for value
                in scores.values()
                if value.get(
                    "industryGrowth6M"
                )
                is not None
            ),

        "industryRatingAvailable":
            sum(
                1
                for value
                in scores.values()
                if value.get(
                    "industryRating"
                )
                is not None
            ),

        "stockMomentumRatingAvailable":
            sum(
                1
                for value
                in scores.values()
                if value.get(
                    "stockMomentumRating"
                )
                is not None
            ),

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

        "industryGrowth1MFallbackUsed":
            industry_growth_1m_fallback_count,

        "industryGrowth3MFallbackUsed":
            industry_growth_3m_fallback_count,

        "industryGrowth6MFallbackUsed":
            industry_growth_6m_fallback_count,

        "industryRatingFallbackUsed":
            industry_rating_fallback_count,

        "stockMomentumRatingFallbackUsed":
            stock_momentum_rating_fallback_count,

        "sectorGrowthFallbackUsed":
            sector_growth_fallback_count,

        "stockGrowth1MFallbackUsed":
            stock_growth_1m_fallback_count,

        "stockGrowth3MFallbackUsed":
            stock_growth_3m_fallback_count,

        "stockGrowth6MFallbackUsed":
            stock_growth_6m_fallback_count,

        "sectorStrengthFallbackUsed":
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
