import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def calc_overall(row):
    fields = {
        "macroSupport": 0.20,
        "valueMigration": 0.20,
        "futureGrowth": 0.20,
        "fundamentalQuality": 0.20,
        "capexScore": 0.10,
        "sectorStrength": 0.10,
    }

    # Overall tabhi calculate hoga
    # jab existing 6 core scores available hon.
    # Tailwind aur Stock Strength फिलहाल
    # Overall me include nahi hain.
    if any(
        row.get(field) is None
        for field in fields
    ):
        return None

    return round(
        sum(
            float(row[field]) * weight
            for field, weight
            in fields.items()
        ),
        2
    )


def main():
    stocks_path = DATA / "stocks.json"
    scores_path = DATA / "research_scores.json"

    stocks = load_json(
        stocks_path,
        []
    )

    score_data = load_json(
        scores_path,
        {}
    )

    scores = score_data.get(
        "stocks",
        {}
    )

    # Ye saare fields research_scores.json
    # se stocks.json me copy honge.
    fields = [
        "sectorStrength",

        "stockStrength1M",
        "stockStrength3M",
        "stockStrength6M",

        "strengthBenchmark",

        "tailwindScore",

        "macroSupport",
        "valueMigration",
        "futureGrowth",
        "fundamentalQuality",
        "capexScore",

        "researchReasons",
    ]

    updated = 0
    fully_scored = 0

    tailwind_available = 0
    stock_strength_1m_available = 0
    stock_strength_3m_available = 0
    stock_strength_6m_available = 0
    reasons_available = 0

    for row in stocks:
        symbol = row.get(
            "symbol",
            ""
        )

        if not symbol:
            continue

        score = scores.get(
            symbol,
            {}
        )

        if score:
            updated += 1

        for field in fields:
            if field in score:
                row[field] = score[field]

        row["overallScore"] = (
            calc_overall(row)
        )

        if (
            row["overallScore"]
            is not None
        ):
            fully_scored += 1

        if (
            row.get("tailwindScore")
            is not None
        ):
            tailwind_available += 1

        if (
            row.get("stockStrength1M")
            is not None
        ):
            stock_strength_1m_available += 1

        if (
            row.get("stockStrength3M")
            is not None
        ):
            stock_strength_3m_available += 1

        if (
            row.get("stockStrength6M")
            is not None
        ):
            stock_strength_6m_available += 1

        reasons = row.get(
            "researchReasons"
        )

        if (
            isinstance(reasons, dict)
            and any(reasons.values())
        ):
            reasons_available += 1

    stocks_path.write_text(
        json.dumps(
            stocks,
            ensure_ascii=False,
            separators=(",", ":")
        )
    )

    print({
        "stocks":
            len(stocks),

        "researchScoresApplied":
            updated,

        "fullyScored":
            fully_scored,

        "tailwindAvailable":
            tailwind_available,

        "stockStrength1M":
            stock_strength_1m_available,

        "stockStrength3M":
            stock_strength_3m_available,

        "stockStrength6M":
            stock_strength_6m_available,

        "researchReasonsAvailable":
            reasons_available,
    })


if __name__ == "__main__":
    main()
