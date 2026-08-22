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


def percentile_rank(values):
    clean = sorted(v for v in values if v is not None)

    if not clean:
        return {}

    result = {}

    for value in clean:
        less_equal = sum(1 for x in clean if x <= value)
        result[value] = round((less_equal / len(clean)) * 100, 2)

    return result


def main():
    stocks = load_json(DATA / "stocks.json", [])
    old_scores = load_json(DATA / "research_scores.json", {})

    sector_rows = defaultdict(list)

    for row in stocks:
        sector = row.get("sector")

        if not sector or sector == "Unclassified":
            continue

        sector_rows[sector].append(row)

    sector_change = {}

    for sector, rows in sector_rows.items():
        changes = [
            float(r["changePct"])
            for r in rows
            if r.get("changePct") is not None
        ]

        if changes:
            sector_change[sector] = sum(changes) / len(changes)

    sector_rank = percentile_rank(
        list(sector_change.values())
    )

    turnovers = [
        float(r["turnoverCr"])
        for r in stocks
        if r.get("turnoverCr") is not None
    ]

    turnover_rank = percentile_rank(turnovers)

    scores = {}

    for row in stocks:
        symbol = row.get("symbol")
        sector = row.get("sector")

        if not symbol:
            continue

        sector_strength = None

        if sector in sector_change:
            sector_strength = sector_rank.get(
                sector_change[sector]
            )

        value_migration = None

        change_pct = row.get("changePct")
        turnover = row.get("turnoverCr")

        if change_pct is not None and turnover is not None:
            momentum_score = clamp(
                50 + float(change_pct) * 7
            )

            liquidity_score = turnover_rank.get(
                float(turnover),
                50
            )

            value_migration = round(
                momentum_score * 0.60 +
                liquidity_score * 0.40,
                2
            )

        existing = (
            old_scores
            .get("stocks", {})
            .get(symbol, {})
        )

        scores[symbol] = {
            "sectorStrength": (
                existing.get("sectorStrength")
                if existing.get("sectorStrength") is not None
                else sector_strength
            ),
            "macroSupport": existing.get("macroSupport"),
            "valueMigration": (
                existing.get("valueMigration")
                if existing.get("valueMigration") is not None
                else value_migration
            ),
            "futureGrowth": existing.get("futureGrowth"),
            "fundamentalQuality": existing.get("fundamentalQuality"),
            "capexScore": existing.get("capexScore")
        }

    output = {
        "_meta": {
            "description": "Research scoring inputs",
            "scale": "0-100",
            "method": {
                "sectorStrength": "Cross-sectional sector EOD performance percentile",
                "valueMigration": "60% daily momentum + 40% turnover percentile proxy",
                "macroSupport": "Pending source data",
                "futureGrowth": "Pending source data",
                "fundamentalQuality": "Pending financial data",
                "capexScore": "Pending filing/capex data"
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

    (DATA / "research_scores.json").write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False
        )
    )

    print({
        "stocksScored": len(scores),
        "sectors": len(sector_rows),
        "sectorStrengthAvailable": sum(
            1 for x in scores.values()
            if x["sectorStrength"] is not None
        ),
        "valueMigrationAvailable": sum(
            1 for x in scores.values()
            if x["valueMigration"] is not None
        )
    })


if __name__ == "__main__":
    main()
