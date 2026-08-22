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


def main():

    stocks = load_json(
        DATA / "stocks.json",
        []
    )

    old_data = load_json(
        DATA / "research_scores.json",
        {}
    )

    old_scores = old_data.get(
        "stocks",
        {}
    )

    # ----------------------------
    # SECTOR STRENGTH
    # ----------------------------

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

    # ----------------------------
    # VALUE MIGRATION INPUTS
    # ----------------------------

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
    vm_available = 0

    for row in stocks:

        symbol = row.get("symbol")

        if not symbol:
            continue

        sector = row.get("sector")

        # ========================
        # Sector Strength
        # ========================

        sector_strength = None

        if sector in sector_avg:

            sector_strength = percentile(
                sector_avg[sector],
                all_sector_avg
            )

            if sector_strength is not None:
                sector_available += 1

        # ========================
        # Value Migration
        # ========================

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

        previous = old_scores.get(
            symbol,
            {}
        )

        scores[symbol] = {

            # Always refresh these two
            "sectorStrength":
                sector_strength,

            "valueMigration":
                value_migration,

            # Preserve manual/future data
            "macroSupport":
                previous.get(
                    "macroSupport"
                ),

            "futureGrowth":
                previous.get(
                    "futureGrowth"
                ),

            "fundamentalQuality":
                previous.get(
                    "fundamentalQuality"
                ),

            "capexScore":
                previous.get(
                    "capexScore"
                )
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

                "valueMigration":
                    "60% price momentum + 40% turnover percentile",

                "macroSupport":
                    "Pending macro scoring source",

                "futureGrowth":
                    "Pending growth scoring source",

                "fundamentalQuality":
                    "Pending fundamental source",

                "capexScore":
                    "Pending CAPEX/filing source"
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

        "stocks": scores
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

        "valueMigrationAvailable":
            vm_available,

        "classifiedSectors":
            len(sector_avg)
    })


if __name__ == "__main__":
    main()
