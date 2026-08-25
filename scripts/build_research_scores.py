import json
from pathlib import Path

import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

NIFTY500 = "^CRSLDX"


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def percentile(value, values):
    clean = sorted(
        float(v)
        for v in values
        if v is not None
    )

    if not clean:
        return None

    count = sum(
        1
        for v in clean
        if v <= float(value)
    )

    return round(
        count / len(clean) * 100,
        2
    )


# =========================================================
# SECTOR / INDEX MAPPING
# =========================================================

def sector_index(sector, industry):
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

def macro_score(sector, industry):
    text = (
        f"{sector or ''} "
        f"{industry or ''}"
    ).lower()

    rules = [
        (
            ["renewable", "solar", "power"],
            90,
            (
                "Strong macro support from power demand, "
                "energy transition and related investment."
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
                "Support from infrastructure spending, "
                "manufacturing and the domestic capex cycle."
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
                "Support from electrification, localisation "
                "and domestic manufacturing."
            )
        ),
        (
            ["industrial manufacturing"],
            80,
            (
                "Domestic manufacturing and investment-cycle "
                "support remain favourable."
            )
        ),
        (
            ["defence", "aerospace"],
            80,
            (
                "Defence localisation and domestic procurement "
                "provide macro support."
            )
        ),
        (
            ["financial services", "bank"],
            70,
            (
                "Financialisation and credit penetration "
                "provide structural support."
            )
        ),
        (
            ["automobile", "auto components"],
            70,
            (
                "Auto demand, premiumisation and localisation "
                "support the sector."
            )
        ),
        (
            ["healthcare", "pharma"],
            70,
            (
                "Healthcare demand and export opportunities "
                "provide positive support."
            )
        ),
        (
            ["telecom"],
            70,
            (
                "Data consumption and digital adoption "
                "support telecom demand."
            )
        ),
        (
            ["metals", "mining"],
            65,
            (
                "Infrastructure demand supports the sector, "
                "but commodity cyclicality remains important."
            )
        ),
        (
            ["realty"],
            65,
            (
                "Urbanisation and property demand provide "
                "moderate macro support."
            )
        ),
        (
            ["consumer"],
            60,
            (
                "Consumption growth and premiumisation "
                "provide moderate support."
            )
        ),
        (
            ["information technology"],
            60,
            (
                "Digital transformation and technology spending "
                "provide moderate support."
            )
        ),
        (
            ["oil", "gas"],
            55,
            (
                "Energy demand remains supportive, "
                "but commodity cycles reduce visibility."
            )
        ),
        (
            ["media"],
            50,
            (
                "Digital consumption provides support, "
                "but industry economics are mixed."
            )
        ),
    ]

    for keywords, score, reason in rules:
        if any(
            keyword in text
            for keyword in keywords
        ):
            return score, reason

    return None, (
        "No reliable automated macro-support rule "
        "is mapped to this sector/industry."
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

                if (
                    "Close"
                    not in block.columns
                ):
                    return None

                series = block["Close"]

            else:
                return None

        else:

            if (
                "Close"
                not in data.columns
            ):
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

    except Exception as e:

        print(
            f"Close extraction failed "
            f"for {ticker}: {e}"
        )

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

        chunk = (
            tickers[
                start:
                start + chunk_size
            ]
        )

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
                f"Historical chunk failed: "
                f"{e}"
            )

            continue

        for ticker in chunk:

            series = (
                extract_close_series(
                    data,
                    ticker,
                    chunk
                )
            )

            if series is not None:
                result[ticker] = series

    print({
        "historyTickersRequested":
            len(tickers),

        "historyTickersLoaded":
            len(result)
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
                (latest / old)
                - 1
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
    )

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

    print({
        "stocksInUniverse":
            len(stocks),

        "classifiedStocks":
            len(classified)
    })


    # =====================================================
    # HISTORICAL STOCK + INDEX DATA
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
        + list(index_tickers)
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
    # MONTHLY SECTOR STRENGTH
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
            .get(
                idx,
                {}
            )
            .get("1M")
        )

        if value is not None:
            sector_index_1m[
                idx
            ] = value

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
    # STOCK STRENGTH
    # =====================================================

    raw_1m = {}
    raw_3m = {}
    raw_6m = {}

    for row in classified:

        symbol = row["symbol"]

        stock_ticker = (
            f"{symbol}.NS"
        )

        stock_series = history.get(
            stock_ticker
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

            raw_1m[symbol] = (
                stock_1m
                - bench_1m
            )

        if (
            stock_3m is not None
            and bench_3m is not None
        ):

            raw_3m[symbol] = (
                stock_3m
                - bench_3m
            )

        if (
            stock_6m is not None
            and bench_6m is not None
        ):

            raw_6m[symbol] = (
                stock_6m
                - bench_6m
            )

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
    # TURNOVER FOR VALUE MIGRATION
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
    # BUILD FINAL SCORE INPUTS
    # =====================================================

    scores = {}

    tailwind_available = 0
    macro_available = 0
    vm_available = 0

    for row in stocks:

        symbol = row.get(
            "symbol"
        )

        if not symbol:
            continue

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
        # SECTOR STRENGTH
        # -------------------------------------------------

        sector_strength = None

        if idx:

            sector_strength = (
                sector_strength_by_index
                .get(idx)
            )


        # -------------------------------------------------
        # MACRO
        # -------------------------------------------------

        macro_support, macro_reason = (
            macro_score(
                sector,
                industry
            )
        )

        if macro_support is not None:
            macro_available += 1


        # -------------------------------------------------
        # VALUE MIGRATION
        # -------------------------------------------------

        value_migration = None

        vm_reason = (
            "Value Migration score is unavailable "
            "because required price/turnover data is missing."
        )

        change = row.get(
            "changePct"
        )

        turnover = row.get(
            "turnoverCr"
        )

        if (
            change is not None
            and turnover is not None
            and all_turnover
        ):

            try:

                momentum = clamp(
                    50
                    + float(change) * 7
                )

                turnover_score = percentile(
                    float(turnover),
                    all_turnover
                )

                if turnover_score is not None:

                    value_migration = round(
                        momentum * 0.60
                        + turnover_score * 0.40,
                        2
                    )

                    vm_available += 1

                    vm_reason = (
                        "Automated Value Migration score: "
                        f"60% daily price momentum "
                        f"(component {momentum:.1f}) + "
                        f"40% turnover percentile "
                        f"(component {turnover_score:.1f})."
                    )

            except Exception:
                pass


        # -------------------------------------------------
        # COMPANY RESEARCH
        # -------------------------------------------------

        company = (
            company_scores
            .get(
                symbol,
                {}
            )
        )

        tailwind = company.get(
            "tailwindScore"
        )

        if tailwind is not None:
            tailwind_available += 1

        company_reasons = (
            company.get(
                "researchReasons",
                {}
            )
            or {}
        )


        # -------------------------------------------------
        # COMBINED REASON STRUCTURE
        # -------------------------------------------------

        research_reasons = {

            "tailwind":
                company_reasons.get(
                    "tailwind",
                    {}
                ),

            "macro": {
                "reason":
                    macro_reason,

                "source":
                    "",

                "sourceDate":
                    "",
            },

            "valueMigration": {
                "reason":
                    vm_reason,

                "source":
                    "",

                "sourceDate":
                    "",
            },

            "futureGrowth":
                company_reasons.get(
                    "futureGrowth",
                    {}
                ),

            "fundamentalQuality":
                company_reasons.get(
                    "fundamentalQuality",
                    {}
                ),

            "capex":
                company_reasons.get(
                    "capex",
                    {}
                ),
        }


        scores[symbol] = {

            "sectorStrength":
                sector_strength,

            "stockStrength1M":
                stock_strength_1m
                .get(symbol),

            "stockStrength3M":
                stock_strength_3m
                .get(symbol),

            "stockStrength6M":
                stock_strength_6m
                .get(symbol),

            "strengthBenchmark":
                idx or NIFTY500,

            "tailwindScore":
                tailwind,

            "macroSupport":
                macro_support,

            "valueMigration":
                value_migration,

            "futureGrowth":
                company.get(
                    "futureGrowth"
                ),

            "fundamentalQuality":
                company.get(
                    "fundamentalQuality"
                ),

            "capexScore":
                company.get(
                    "capexScore"
                ),

            "researchReasons":
                research_reasons,
        }


    # =====================================================
    # OUTPUT
    # =====================================================

    output = {

        "_meta": {

            "description":
                "NSE research scoring inputs",

            "scale":
                "0-100",

            "method": {

                "sectorStrength":
                    (
                        "1-month relevant Nifty "
                        "sector-index return percentile"
                    ),

                "stockStrength1M":
                    (
                        "1-month stock excess return "
                        "vs relevant index percentile"
                    ),

                "stockStrength3M":
                    (
                        "3-month stock excess return "
                        "vs relevant index percentile"
                    ),

                "stockStrength6M":
                    (
                        "6-month stock excess return "
                        "vs relevant index percentile"
                    ),

                "tailwindScore":
                    (
                        "Sector/industry structural "
                        "tailwind heuristic"
                    ),

                "macroSupport":
                    (
                        "Sector-level macro-support "
                        "heuristic"
                    ),

                "valueMigration":
                    (
                        "60% daily momentum + "
                        "40% turnover percentile"
                    ),

                "futureGrowth":
                    "Company research input",

                "fundamentalQuality":
                    "Company financial-quality input",

                "capexScore":
                    "Company CAPEX input",
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
                    "Tailwind and Stock Strength "
                    "remain separate screening metrics "
                    "and are not included in Overall Score."
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


    print({

        "stocksProcessed":
            len(scores),

        "monthlySectorStrength":
            sum(
                1
                for x in scores.values()
                if x.get(
                    "sectorStrength"
                ) is not None
            ),

        "stockStrength1M":
            len(
                stock_strength_1m
            ),

        "stockStrength3M":
            len(
                stock_strength_3m
            ),

        "stockStrength6M":
            len(
                stock_strength_6m
            ),

        "tailwindAvailable":
            tailwind_available,

        "macroAvailable":
            macro_available,

        "valueMigrationAvailable":
            vm_available,
    })


if __name__ == "__main__":
    main()
