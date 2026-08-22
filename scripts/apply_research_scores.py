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

    if any(
        row.get(k) is None
        for k in fields
    ):
        return None

    return round(
        sum(
            float(row[k]) * weight
            for k, weight
            in fields.items()
        ),
        2
    )


def main():

    stocks_path = (
        DATA / "stocks.json"
    )

    scores_path = (
        DATA / "research_scores.json"
    )

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

    fields = [
        "sectorStrength",
        "stockStrength1M",
        "stockStrength3M",
        "stockStrength6M",
        "strengthBenchmark",
        "macroSupport",
        "valueMigration",
        "futureGrowth",
        "fundamentalQuality",
        "capexScore",
    ]

    fully_scored = 0

    for row in stocks:

        symbol = row.get(
            "symbol",
            ""
        )

        score = scores.get(
            symbol,
            {}
        )

        for field in fields:
            if field in score:
                row[field] = (
                    score[field]
                )

        row["overallScore"] = (
            calc_overall(row)
        )

        if (
            row["overallScore"]
            is not None
        ):
            fully_scored += 1

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

        "fullyScored":
            fully_scored
    })


if __name__ == "__main__":
    main()
