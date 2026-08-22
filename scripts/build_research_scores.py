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
        1 for v in clean
        if v <= float(value)
    )

    return round(
        count / len(clean) * 100,
        2
    )


def sector_index(sector, industry):
    text = f"{sector or ''} {industry or ''}".lower()

    rules = [
        (["psu bank"], "^CNXPSUBANK"),
        (["bank"], "^NSEBANK"),
        (["financial services", "finance", "nbfc"], "^CNXFINANCE"),
        (["automobile", "auto component", "auto"], "^CNXAUTO"),
        (["information technology", "software", "it services"], "^CNXIT"),
        (["fmcg"], "^CNXFMCG"),
        (["pharma", "pharmaceutical", "healthcare"], "^CNXPHARMA"),
        (["metal", "mining"], "^CNXMETAL"),
        (["realty", "real estate"], "^CNXREALTY"),
        (["media", "entertainment"], "^CNXMEDIA"),
        (["energy", "oil", "gas", "power", "renewable", "solar"], "^CNXENERGY"),
        (["infrastructure", "construction", "capital goods"], "^CNXINFRA"),
    ]

    for words, ticker in rules:
        if any(word in text for word in words):
            return ticker

    return None


def macro_score(sector, industry):
    text = f"{sector or ''} {industry or ''}".lower()

    rules = [
        (["renewable", "solar", "power"], 90),
        (["capital goods", "construction", "infrastructure"], 85),
        (["electrical equipment", "electronics", "semiconductor"], 85),
        (["industrial manufacturing"], 80),
        (["defence", "aerospace"], 80),
        (["financial services", "bank"], 70),
        (["automobile", "auto components"], 70),
        (["healthcare", "pharma"], 70),
        (["telecom"], 70),
        (["metals", "mining"], 65),
        (["realty"], 65),
        (["consumer"], 60),
        (["information technology"], 60),
        (["oil", "gas"], 55),
        (["media"], 50),
    ]

    for keywords, score in rules:
        if any(k in text for k in keywords):
            return score

    return None


def extract_close_series(data, ticker, chunk):
    if data is None or len(data) == 0:
        return None

    try:
        if isinstance(data.columns, pd.MultiIndex):

            # Format 1:
            # level 0 = Price field
            # level 1 = ticker
            if "Close" in data.columns.get_level_values(0):
                close = data["Close"]

                if isinstance(close, pd.Series):
                    series = close
                elif ticker in close.columns:
                    series = close[ticker]
                elif len(chunk) == 1 and len(close.columns) == 1:
                    series = close.iloc[:, 0]
                else:
                    return None

            # Format 2:
            # level 0 = ticker
            # level 1 = Price field
            elif ticker in data.columns.get_level_values(0):
                block = data[ticker]

                if "Close" not in block.columns:
                    return None

                series = block["Close"]

            else:
                return None

        else:
            # Single ticker response
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

    except Exception as e:
        print(
            f"Close extraction failed for {ticker}: {e}"
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
        chunk = tickers[
            start:start + chunk_size
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
            len(result)
    })

    return result


def period_return(series, trading_days):
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
            ((latest / old) - 1) * 100,
            4
        )

    except Exception:
        return None


def main():

    stocks = load_json(
        DATA / "stocks.json",
        []
    )

    company_data = load_json(
        DATA / "company_research.json",
        {}
    )

    company_scores = company_data.get(
        "stocks",
        {}
    )

    classified = [
        row
        for row in stocks
        if (
            row.get("symbol")
            and row.get("sector")
            and row.get("sector") != "Unclassified"
        )
    ]

    print({
        "stocksInUniverse":
            len(stocks),

        "classifiedStocks":
            len(classified)
    })

    # --------------------------------
    # Historical stock + index data
    # --------------------------------

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
        stock_tickers +
        list(index_tickers)
    )

    # --------------------------------
    # Index returns
    # --------------------------------

    index_returns = {}

    for ticker in index_tickers:

        series = history.get(
            ticker
        )

        index_returns[ticker] = {
            "1M": period_return(
                series,
                21
            ),
            "3M": period_return(
                series,
                63
            ),
            "6M": period_return(
                series,
                126
            ),
        }

    print(
        "Index returns:",
        index_returns
    )

    # --------------------------------
    # MONTHLY SECTOR STRENGTH
    # --------------------------------

    sector_index_1m = {}

    for row in classified:

        idx = sector_index(
            row.get("sector"),
            row.get("industry")
        )

        if not idx:
            continue

        r = (
            index_returns
            .get(idx, {})
            .get("1M")
        )

        if r is not None:
            sector_index_1m[idx] = r

    sector_return_values = list(
        sector_index_1m.values()
    )

    sector_strength_by_index = {}

    for idx, r in sector_index_1m.items():

        sector_strength_by_index[idx] = (
            percentile(
                r,
                sector_return_values
            )
        )

    # --------------------------------
    # STOCK STRENGTH
    # --------------------------------

    raw_1m = {}
    raw_3m = {}
    raw_6m = {}

    missing_stock_history = 0
    missing_benchmark_history = 0

    for row in classified:

        symbol = row["symbol"]
        stock_ticker = f"{symbol}.NS"

        stock_series = history.get(
            stock_ticker
        )

        if stock_series is None:
            missing_stock_history += 1
            continue

        idx = sector_index(
            row.get("sector"),
            row.get("industry")
        )

        benchmark = idx or NIFTY500

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

        if not any(
            value is not None
            for value in
            benchmark_returns.values()
        ):
            missing_benchmark_history += 1
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

        bench_1m = (
            benchmark_returns
            .get("1M")
        )

        bench_3m = (
            benchmark_returns
            .get("3M")
        )

        bench_6m = (
            benchmark_returns
            .get("6M")
        )

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

    print({
        "missingStockHistory":
            missing_stock_history,

        "missingBenchmarkHistory":
            missing_benchmark_history,

        "stockStrength1M":
            len(stock_strength_1m),

        "stockStrength3M":
            len(stock_strength_3m),

        "stockStrength6M":
            len(stock_strength_6m)
    })

    # --------------------------------
    # Value Migration
    # --------------------------------

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

    # --------------------------------
    # Final scores
    # --------------------------------

    scores = {}

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

        sector_strength = None

        if idx:
            sector_strength = (
                sector_strength_by_index
                .get(idx)
            )

        macro_support = (
            macro_score(
                sector,
                industry
            )
        )

        value_migration = None

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
                    50 +
                    float(change) * 7
                )

                turnover_score = (
                    percentile(
                        float(turnover),
                        all_turnover
                    )
                )

                if turnover_score is not None:

                    value_migration = round(
                        momentum * 0.60 +
                        turnover_score * 0.40,
                        2
                    )

            except Exception:
                pass

        company = (
            company_scores
            .get(
                symbol,
                {}
            )
        )

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

            "strengthBenchmark":
                idx or NIFTY500
        }

    output = {

        "_meta": {

            "description":
                "NSE research scoring inputs",

            "scale":
                "0-100",

            "method": {

                "sectorStrength":
                    "1-month relevant Nifty sector index return percentile",

                "stockStrength1M":
                    "1-month stock excess return vs relevant index percentile",

                "stockStrength3M":
                    "3-month stock excess return vs relevant index percentile",

                "stockStrength6M":
                    "6-month stock excess return vs relevant index percentile",

                "macroSupport":
                    "Sector-level macro heuristic",

                "valueMigration":
                    "60% daily momentum + 40% turnover percentile",

                "futureGrowth":
                    "Company research input",

                "fundamentalQuality":
                    "Company financial quality input",

                "capexScore":
                    "Company CAPEX input"
            },

            "weights": {
                "sectorStrength": 10,
                "macroSupport": 20,
                "valueMigration": 20,
                "futureGrowth": 20,
                "fundamentalQuality": 20,
                "capexScore": 10
            }
        },

        "stocks":
            scores
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
                for x in
                scores.values()
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
            )
    })


if __name__ == "__main__":
    main()
