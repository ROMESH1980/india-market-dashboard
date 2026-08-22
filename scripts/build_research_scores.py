import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


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

    sector_changes = defaultdict(list)

    for row in stocks:

        sector = row.get("sector")
        change = row.get("changePct")

        if (
            sector
            and sector != "Unclassified"
            and change is not None
        ):
            try:
                sector_changes[sector].append(
                    float(change)
                )
            except Exception:
                pass

    sector_avg = {}

    for sector, values in sector_changes.items():

        if values:
            sector_avg[sector] = (
                sum(values) / len(values)
            )

    all_sector_avg = list(
        sector_avg.values()
    )

    all_turnover = []

    for row in stocks:

        turnover = row.get("turnoverCr")

        if turnover is not None:
            try:
                all_turnover.append(
                    float(turnover)
                )
            except Exception:
                pass

    scores = {}

    sector_available = 0
    macro_available = 0
    vm_available = 0
    future_available = 0
    fundamental_available = 0
    capex_available = 0

    for row in stocks:

        symbol = row.get("symbol")

        if not symbol:
            continue

        sector = row.get("sector")
        industry = row.get("industry")

        # -------------------------
        # Sector Strength
        # -------------------------

        sector_strength = None

        if sector in sector_avg:

            sector_strength = percentile(
                sector_avg[sector],
                all_sector_avg
            )

            if sector_strength is not None:
                sector_available += 1

        # -------------------------
        # Macro Support
        # -------------------------

        macro_support = macro_score(
            sector,
            industry
        )

        if macro_support is not None:
            macro_available += 1

        # -------------------------
        # Value Migration
        # -------------------------

        value_migration = None

        change = row.get("changePct")
        turnover = row.get("turnoverCr")

        if (
            change is not None
            and turnover is not None
        ):

            try:

                momentum = clamp(
                    50 + float(change) * 7
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

            except Exception:
                pass

        # -------------------------
        # Company research data
        # -------------------------

        company = company_scores.get(
            symbol,
            {}
        )

        future_growth = company.get(
            "futureGrowth"
        )

        fundamental_quality = company.get(
            "fundamentalQuality"
        )

        capex_score = company.get(
            "capexScore"
        )

        if future_growth is not None:
            future_available += 1

        if fundamental_quality is not None:
            fundamental_available += 1

        if capex_score is not None:
            capex_available += 1

        scores[symbol] = {

            "sectorStrength":
                sector_strength,

            "macroSupport":
                macro_support,

            "valueMigration":
                value_migration,

            "futureGrowth":
                future_growth,

            "fundamentalQuality":
                fundamental_quality,

            "capexScore":
                capex_score
        }

    output = {

        "_meta": {

            "description":
                "India Market Dashboard research scoring inputs",

            "scale":
                "0-100",

            "method": {

                "sectorStrength":
                    "Sector EOD performance percentile",

                "macroSupport":
                    "Sector-level macro policy/tailwind heuristic",

                "valueMigration":
                    "60% price momentum + 40% turnover percentile",

                "futureGrowth":
                    "Company-specific research input",

                "fundamentalQuality":
                    "Company-specific financial quality input",

                "capexScore":
                    "Company-specific CAPEX/expansion input"
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
        DATA / "research_scores.json"
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

        "sectorStrengthAvailable":
            sector_available,

        "macroSupportAvailable":
            macro_available,

        "valueMigrationAvailable":
            vm_available,

        "futureGrowthAvailable":
            future_available,

        "fundamentalQualityAvailable":
            fundamental_available,

        "capexAvailable":
            capex_available,

        "classifiedSectors":
            len(sector_avg)
    })


if __name__ == "__main__":
    main()
