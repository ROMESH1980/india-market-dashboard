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


# =========================================================
# TAILWIND
# =========================================================

def tailwind_score(sector, industry):
    text = f"{sector or ''} {industry or ''}".lower()

    rules = [
        (
            ["renewable", "solar"],
            95,
            "Structural tailwind from renewable-energy capacity additions, energy transition and related investment."
        ),
        (
            ["power", "electric utility", "electrical equipment"],
            90,
            "Power demand, grid expansion, transmission investment and electrification provide structural support."
        ),
        (
            ["defence", "aerospace"],
            92,
            "Defence indigenisation, localisation and domestic procurement create a strong structural tailwind."
        ),
        (
            ["capital goods", "industrial machinery", "construction equipment"],
            88,
            "Domestic manufacturing and investment-cycle expansion support capital-goods demand."
        ),
        (
            ["infrastructure", "construction"],
            87,
            "Infrastructure investment and public/private capex provide a favourable demand environment."
        ),
        (
            ["electronics", "semiconductor", "electronic components"],
            92,
            "Electronics localisation, import substitution and domestic manufacturing expansion support growth."
        ),
        (
            ["railway", "rail"],
            90,
            "Railway modernisation and infrastructure spending provide a structural demand tailwind."
        ),
        (
            ["pharma", "pharmaceutical", "healthcare", "hospital"],
            82,
            "Healthcare demand, exports and rising healthcare penetration provide long-duration support."
        ),
        (
            ["auto component", "automobile", "automotive"],
            80,
            "Vehicle premiumisation, localisation and technology transition provide sector support."
        ),
        (
            ["bank", "financial services", "nbfc", "insurance", "asset management"],
            78,
            "Financialisation, credit penetration and formalisation support long-term sector growth."
        ),
        (
            ["telecom", "communication"],
            80,
            "Data consumption, network investment and digital adoption provide structural demand support."
        ),
        (
            ["data center", "cloud"],
            95,
            "Cloud adoption, AI infrastructure and data-centre capacity expansion create a strong demand tailwind."
        ),
        (
            ["logistics", "warehousing"],
            80,
            "Formalisation, organised logistics and e-commerce penetration support structural growth."
        ),
        (
            ["real estate", "realty"],
            72,
            "Urbanisation and housing/commercial demand provide a positive but cyclical tailwind."
        ),
        (
            ["consumer", "fmcg"],
            70,
            "Income growth, premiumisation and consumption expansion provide long-term support."
        ),
        (
            ["information technology", "software", "it services"],
            75,
            "Digital transformation, cloud and AI spending provide structural technology demand."
        ),
        (
            ["chemical", "specialty chemical"],
            76,
            "Import substitution, supply-chain diversification and specialty-product demand can support growth."
        ),
        (
            ["metal", "mining"],
            62,
            "Infrastructure and manufacturing demand provide support, but the sector remains commodity-cycle sensitive."
        ),
        (
            ["oil", "gas"],
            58,
            "Energy demand remains supportive, although commodity cycles and energy transition limit the structural score."
        ),
        (
            ["media", "entertainment"],
            55,
            "Digital consumption offers support, but industry economics remain mixed."
        ),
    ]

    for keywords, score, reason in rules:
        if any(word in text for word in keywords):
            return score, reason

    return None, (
        "No sufficiently reliable automated structural-tailwind rule "
        "is currently mapped to this sector/industry."
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
        50 + pct * 1.5
    )


def future_growth_score(info):
    parts = []
    details = []

    revenue_growth = safe_float(
        info.get("revenueGrowth")
    )

    if revenue_growth is not None:
        score = growth_component(
            revenue_growth
        )

        parts.append(score)

        details.append(
            f"Revenue growth {revenue_growth * 100:.1f}%"
        )

    earnings_growth = safe_float(
        info.get("earningsGrowth")
    )

    if earnings_growth is not None:
        score = growth_component(
            earnings_growth
        )

        parts.append(score)

        details.append(
            f"Earnings growth {earnings_growth * 100:.1f}%"
        )

    quarterly_growth = safe_float(
        info.get("earningsQuarterlyGrowth")
    )

    if quarterly_growth is not None:
        score = growth_component(
            quarterly_growth
        )

        parts.append(score)

        details.append(
            f"Quarterly earnings growth {quarterly_growth * 100:.1f}%"
        )

    forward_pe = safe_float(
        info.get("forwardPE")
    )

    trailing_pe = safe_float(
        info.get("trailingPE")
    )

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
        return None, (
            "Insufficient automated growth data available."
        )

    score = round(
        sum(parts) / len(parts),
        2
    )

    reason = (
        "Automated growth proxy based on "
        + ", ".join(details)
        if details
        else "Automated growth proxy based on available forward and historical financial data."
    )

    return score, reason


# =========================================================
# FUNDAMENTAL QUALITY
# =========================================================

def fundamental_score(info):
    parts = []
    details = []

    roe = safe_float(
        info.get("returnOnEquity")
    )

    if roe is not None:
        parts.append(
            clamp(
                50 + roe * 100 * 1.5
            )
        )

        details.append(
            f"ROE {roe * 100:.1f}%"
        )

    profit_margin = safe_float(
        info.get("profitMargins")
    )

    if profit_margin is not None:
        parts.append(
            clamp(
                45 + profit_margin * 100 * 2
            )
        )

        details.append(
            f"Profit margin {profit_margin * 100:.1f}%"
        )

    operating_margin = safe_float(
        info.get("operatingMargins")
    )

    if operating_margin is not None:
        parts.append(
            clamp(
                45 +
                operating_margin * 100 * 1.8
            )
        )

        details.append(
            f"Operating margin {operating_margin * 100:.1f}%"
        )

    debt_equity = safe_float(
        info.get("debtToEquity")
    )

    if debt_equity is not None:
        parts.append(
            clamp(
                100 -
                debt_equity * 0.55
            )
        )

        details.append(
            f"Debt/equity {debt_equity:.1f}"
        )

    current_ratio = safe_float(
        info.get("currentRatio")
    )

    if current_ratio is not None:
        parts.append(
            clamp(
                current_ratio * 45
            )
        )

        details.append(
            f"Current ratio {current_ratio:.2f}"
        )

    free_cashflow = safe_float(
        info.get("freeCashflow")
    )

    if free_cashflow is not None:
        parts.append(
            75 if free_cashflow > 0 else 25
        )

        details.append(
            "Positive free cash flow"
            if free_cashflow > 0
            else "Negative free cash flow"
        )

    operating_cf = safe_float(
        info.get("operatingCashflow")
    )

    if operating_cf is not None:
        parts.append(
            75 if operating_cf > 0 else 25
        )

        details.append(
            "Positive operating cash flow"
            if operating_cf > 0
            else "Negative operating cash flow"
        )

    if len(parts) < 2:
        return None, (
            "Insufficient automated fundamental data available."
        )

    score = round(
        sum(parts) / len(parts),
        2
    )

    reason = (
        "Automated fundamental-quality proxy: "
        + ", ".join(details)
    )

    return score, reason


# =========================================================
# CAPEX
# =========================================================

def capex_score(ticker):
    try:
        cf = ticker.cashflow

        if cf is None or cf.empty:
            return None, (
                "Cash-flow statement unavailable for automated CAPEX analysis."
            )

        capex = None
        operating_cf = None

        possible_capex = [
            "Capital Expenditure",
            "Capital Expenditures",
        ]

        possible_ocf = [
            "Operating Cash Flow",
            "Total Cash From Operating Activities",
        ]

        for name in possible_capex:
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

        for name in possible_ocf:
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
            return None, (
                "Capital expenditure data unavailable."
            )

        capex_abs = abs(capex)

        if (
            operating_cf is None
            or operating_cf <= 0
        ):
            score = (
                50
                if capex_abs > 0
                else None
            )

            return score, (
                "CAPEX detected, but positive operating cash flow was not available for comparison."
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
            f"Automated CAPEX proxy: capital expenditure is "
            f"{ratio:.2f}× operating cash flow."
        )

        return score, reason

    except Exception as e:
        return None, (
            f"CAPEX calculation unavailable: {e}"
        )


# =========================================================
# STOCK ANALYSIS
# =========================================================

def analyze_stock(row):
    symbol = row.get("symbol")

    if not symbol:
        return None, None

    yahoo_symbol = (
        f"{symbol}.NS"
    )

    sector = row.get("sector")
    industry = row.get("industry")

    tailwind, tailwind_reason = (
        tailwind_score(
            sector,
            industry
        )
    )

    yahoo_url = (
        f"https://finance.yahoo.com/quote/{yahoo_symbol}/"
    )

    try:
        ticker = yf.Ticker(
            yahoo_symbol
        )

        info = ticker.info or {}

        future_growth, growth_reason = (
            future_growth_score(
                info
            )
        )

        fundamental, fundamental_reason = (
            fundamental_score(
                info
            )
        )

        capex, capex_reason = (
            capex_score(
                ticker
            )
        )

        return symbol, {

            "tailwindScore":
                tailwind,

            "futureGrowth":
                future_growth,

            "fundamentalQuality":
                fundamental,

            "capexScore":
                capex,

            "researchReasons": {

                "tailwind": {
                    "reason":
                        tailwind_reason,

                    "source":
                        "",

                    "sourceDate":
                        "",
                },

                "futureGrowth": {
                    "reason":
                        growth_reason,

                    "source":
                        yahoo_url,

                    "sourceDate":
                        "",
                },

                "fundamentalQuality": {
                    "reason":
                        fundamental_reason,

                    "source":
                        yahoo_url,

                    "sourceDate":
                        "",
                },

                "capex": {
                    "reason":
                        capex_reason,

                    "source":
                        yahoo_url,

                    "sourceDate":
                        "",
                },

            },

            "source":
                "Yahoo Finance automated financial-data proxy",
        }

    except Exception as e:

        return symbol, {

            "tailwindScore":
                tailwind,

            "futureGrowth":
                None,

            "fundamentalQuality":
                None,

            "capexScore":
                None,

            "researchReasons": {

                "tailwind": {
                    "reason":
                        tailwind_reason,

                    "source":
                        "",

                    "sourceDate":
                        "",
                },

                "futureGrowth": {
                    "reason":
                        f"Automated financial data unavailable: {e}",

                    "source":
                        yahoo_url,

                    "sourceDate":
                        "",
                },

                "fundamentalQuality": {
                    "reason":
                        f"Automated financial data unavailable: {e}",

                    "source":
                        yahoo_url,

                    "sourceDate":
                        "",
                },

                "capex": {
                    "reason":
                        f"Automated financial data unavailable: {e}",

                    "source":
                        yahoo_url,

                    "sourceDate":
                        "",
                },

            },

            "source":
                "Yahoo Finance automated financial-data proxy",
        }


# =========================================================
# MAIN
# =========================================================

def main():

    stocks = load_json(
        DATA / "stocks.json",
        []
    )

    existing = load_json(
        DATA / "company_research.json",
        {}
    )

    existing_stocks = (
        existing.get(
            "stocks",
            {}
        )
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

    with ThreadPoolExecutor(
        max_workers=6
    ) as executor:

        futures = {
            executor.submit(
                analyze_stock,
                row
            ): row.get("symbol")

            for row in rows
        }

        for future in as_completed(
            futures
        ):

            symbol, data = (
                future.result()
            )

            processed += 1

            if (
                not symbol
                or data is None
            ):
                continue

            previous = (
                result.get(
                    symbol,
                    {}
                )
            )

            tailwind = (
                data.get(
                    "tailwindScore"
                )
            )

            future_growth = (
                data.get(
                    "futureGrowth"
                )
            )

            fundamental = (
                data.get(
                    "fundamentalQuality"
                )
            )

            capex = (
                data.get(
                    "capexScore"
                )
            )

            result[symbol] = {

                "tailwindScore":
                    (
                        tailwind
                        if tailwind is not None
                        else previous.get(
                            "tailwindScore"
                        )
                    ),

                "futureGrowth":
                    (
                        future_growth
                        if future_growth is not None
                        else previous.get(
                            "futureGrowth"
                        )
                    ),

                "fundamentalQuality":
                    (
                        fundamental
                        if fundamental is not None
                        else previous.get(
                            "fundamentalQuality"
                        )
                    ),

                "capexScore":
                    (
                        capex
                        if capex is not None
                        else previous.get(
                            "capexScore"
                        )
                    ),

                "researchReasons":
                    data.get(
                        "researchReasons"
                    )
                    or previous.get(
                        "researchReasons",
                        {}
                    ),

                "source":
                    data.get(
                        "source"
                    ),
            }

            final = result[symbol]

            if final.get(
                "tailwindScore"
            ) is not None:
                tailwind_available += 1

            if final.get(
                "futureGrowth"
            ) is not None:
                future_available += 1

            if final.get(
                "fundamentalQuality"
            ) is not None:
                fundamental_available += 1

            if final.get(
                "capexScore"
            ) is not None:
                capex_available += 1

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
                "Company research inputs for NSE dashboard",

            "scale":
                "0-100",

            "method": {

                "tailwindScore":
                    "Sector/industry structural-tailwind heuristic",

                "futureGrowth":
                    "Revenue and earnings growth proxy",

                "fundamentalQuality":
                    "ROE, margins, debt, liquidity and cash-flow proxy",

                "capexScore":
                    "Capital expenditure relative to operating cash-flow proxy",
            },

            "warning":
                (
                    "Automated research proxies are screening tools, "
                    "not substitutes for exchange filings or management commentary."
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
    })


if __name__ == "__main__":
    main()
