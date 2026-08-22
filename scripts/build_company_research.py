import json
import math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def safe_float(x):
    try:
        if x is None:
            return None

        x = float(x)

        if math.isnan(x) or math.isinf(x):
            return None

        return x
    except Exception:
        return None


def growth_component(x):
    x = safe_float(x)

    if x is None:
        return None

    # Yahoo usually returns growth as decimal:
    # 0.20 = 20%
    pct = x * 100

    return clamp(
        50 + pct * 1.5
    )


def fundamental_score(info):
    parts = []

    roe = safe_float(
        info.get("returnOnEquity")
    )

    if roe is not None:
        parts.append(
            clamp(50 + roe * 100 * 1.5)
        )

    margin = safe_float(
        info.get("profitMargins")
    )

    if margin is not None:
        parts.append(
            clamp(45 + margin * 100 * 2)
        )

    operating_margin = safe_float(
        info.get("operatingMargins")
    )

    if operating_margin is not None:
        parts.append(
            clamp(45 + operating_margin * 100 * 1.8)
        )

    debt_equity = safe_float(
        info.get("debtToEquity")
    )

    if debt_equity is not None:
        # Yahoo debt/equity often reported as percentage
        parts.append(
            clamp(100 - debt_equity * 0.55)
        )

    current_ratio = safe_float(
        info.get("currentRatio")
    )

    if current_ratio is not None:
        parts.append(
            clamp(current_ratio * 45)
        )

    fcf = safe_float(
        info.get("freeCashflow")
    )

    operating_cf = safe_float(
        info.get("operatingCashflow")
    )

    if fcf is not None:
        parts.append(
            75 if fcf > 0 else 25
        )

    if operating_cf is not None:
        parts.append(
            75 if operating_cf > 0 else 25
        )

    if len(parts) < 2:
        return None

    return round(
        sum(parts) / len(parts),
        2
    )


def future_growth_score(info):
    parts = []

    for key in [
        "revenueGrowth",
        "earningsGrowth",
        "earningsQuarterlyGrowth"
    ]:
        value = growth_component(
            info.get(key)
        )

        if value is not None:
            parts.append(value)

    forward_pe = safe_float(
        info.get("forwardPE")
    )

    trailing_pe = safe_float(
        info.get("trailingPE")
    )

    # Forward valuation improving can modestly support
    # growth outlook, but it receives low influence.
    if (
        forward_pe is not None
        and trailing_pe is not None
        and trailing_pe > 0
    ):
        improvement = (
            trailing_pe - forward_pe
        ) / trailing_pe

        parts.append(
            clamp(
                50 + improvement * 40
            )
        )

    if not parts:
        return None

    return round(
        sum(parts) / len(parts),
        2
    )


def capex_score(ticker):
    try:
        cf = ticker.cashflow

        if cf is None or cf.empty:
            return None

        capex = None
        operating_cf = None

        possible_capex = [
            "Capital Expenditure",
            "Capital Expenditures"
        ]

        possible_ocf = [
            "Operating Cash Flow",
            "Total Cash From Operating Activities"
        ]

        for name in possible_capex:
            if name in cf.index:
                values = cf.loc[name].dropna()

                if len(values):
                    capex = safe_float(
                        values.iloc[0]
                    )
                    break

        for name in possible_ocf:
            if name in cf.index:
                values = cf.loc[name].dropna()

                if len(values):
                    operating_cf = safe_float(
                        values.iloc[0]
                    )
                    break

        if capex is None:
            return None

        # Cash-flow statements usually show
        # capex as negative cash outflow.
        capex_abs = abs(capex)

        if operating_cf is None or operating_cf <= 0:
            return 50 if capex_abs > 0 else None

        ratio = (
            capex_abs /
            operating_cf
        )

        # Expansion proxy:
        # meaningful investment supported by positive CFO.
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

        return score

    except Exception:
        return None


def analyze_stock(symbol):
    yahoo_symbol = (
        f"{symbol}.NS"
    )

    try:
        ticker = yf.Ticker(
            yahoo_symbol
        )

        info = ticker.info or {}

        future_growth = (
            future_growth_score(info)
        )

        fundamental = (
            fundamental_score(info)
        )

        capex = (
            capex_score(ticker)
        )

        return symbol, {
            "futureGrowth":
                future_growth,

            "fundamentalQuality":
                fundamental,

            "capexScore":
                capex,

            "source":
                "Yahoo Finance financial-data proxy"
        }

    except Exception as e:
        print(
            f"{symbol}: unavailable: {e}"
        )

        return symbol, None


def main():

    stocks = load_json(
        DATA / "stocks.json",
        []
    )

    existing = load_json(
        DATA / "company_research.json",
        {}
    )

    existing_stocks = existing.get(
        "stocks",
        {}
    )

    # Focus on classified/Nifty-500 universe first.
    symbols = []

    for row in stocks:
        symbol = row.get("symbol")
        sector = row.get("sector")

        if (
            symbol
            and sector
            and sector != "Unclassified"
        ):
            symbols.append(symbol)

    symbols = list(
        dict.fromkeys(symbols)
    )

    result = dict(
        existing_stocks
    )

    completed = 0
    full_data = 0

    # Parallel fetching keeps workflow reasonably fast.
    with ThreadPoolExecutor(
        max_workers=6
    ) as executor:

        futures = {
            executor.submit(
                analyze_stock,
                symbol
            ): symbol
            for symbol in symbols
        }

        for future in as_completed(
            futures
        ):
            symbol, data = (
                future.result()
            )

            completed += 1

            if data is None:
                continue

            previous = result.get(
                symbol,
                {}
            )

            result[symbol] = {
                "futureGrowth":
                    data.get("futureGrowth")
                    if data.get("futureGrowth") is not None
                    else previous.get("futureGrowth"),

                "fundamentalQuality":
                    data.get("fundamentalQuality")
                    if data.get("fundamentalQuality") is not None
                    else previous.get("fundamentalQuality"),

                "capexScore":
                    data.get("capexScore")
                    if data.get("capexScore") is not None
                    else previous.get("capexScore"),

                "source":
                    data.get("source")
            }

            r = result[symbol]

            if (
                r.get("futureGrowth") is not None
                and r.get("fundamentalQuality") is not None
                and r.get("capexScore") is not None
            ):
                full_data += 1

            if completed % 25 == 0:
                print(
                    f"Processed {completed}/{len(symbols)}"
                )

    output = {
        "_meta": {
            "description":
                "Company research inputs for NSE dashboard",

            "scale":
                "0-100",

            "method": {
                "futureGrowth":
                    "Revenue and earnings growth proxy",

                "fundamentalQuality":
                    "ROE, margins, debt, liquidity and cash-flow proxy",

                "capexScore":
                    "Capital expenditure relative to operating cash flow proxy"
            },

            "warning":
                "These are automated financial-data proxies, not substitutes for company filings."
        },

        "stocks":
            result
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
            len(symbols),

        "processed":
            completed,

        "completeCompanyScores":
            full_data
    })


if __name__ == "__main__":
    main()
