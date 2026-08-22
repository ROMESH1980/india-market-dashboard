import io
import json
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

AMFI_URL = (
    "https://portal.amfiindia.com/spages/"
    "AverageMarketCapitalization30Jun2026.xlsx"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
}


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def normalize_category(value, rank):
    text = str(value or "").strip().lower()

    if "large" in text:
        return "Large Cap"

    if "mid" in text:
        return "Mid Cap"

    if "small" in text:
        # Our dashboard custom split:
        # rank 251-500 = Small
        # rank 501+ = Micro
        if rank is not None and rank >= 501:
            return "Micro Cap"

        return "Small Cap"

    # Fallback using rank
    if rank is not None:
        if rank <= 100:
            return "Large Cap"

        if rank <= 250:
            return "Mid Cap"

        if rank <= 500:
            return "Small Cap"

        return "Micro Cap"

    return None


def main():
    stocks_path = DATA / "stocks.json"

    stocks = load_json(
        stocks_path,
        []
    )

    response = requests.get(
        AMFI_URL,
        headers=HEADERS,
        timeout=60,
    )

    response.raise_for_status()

    excel = pd.read_excel(
        io.BytesIO(response.content),
        sheet_name=0,
        header=None,
    )

    # Find header row dynamically
    header_row = None

    for i in range(min(20, len(excel))):
        row_text = " ".join(
            str(x)
            for x in excel.iloc[i].tolist()
        ).lower()

        if (
            "isin" in row_text
            and "categor" in row_text
        ):
            header_row = i
            break

    if header_row is None:
        raise RuntimeError(
            "AMFI header row not found"
        )

    df = pd.read_excel(
        io.BytesIO(response.content),
        sheet_name=0,
        header=header_row,
    )

    df.columns = [
        str(c).strip()
        for c in df.columns
    ]

    isin_col = None
    category_col = None
    rank_col = None

    for col in df.columns:
        low = col.lower()

        if isin_col is None and "isin" in low:
            isin_col = col

        if (
            category_col is None
            and "categor" in low
        ):
            category_col = col

        if (
            rank_col is None
            and (
                "sr. no" in low
                or "sr no" in low
                or low == "rank"
            )
        ):
            rank_col = col

    if isin_col is None:
        raise RuntimeError(
            "ISIN column not found"
        )

    if category_col is None:
        raise RuntimeError(
            "Category column not found"
        )

    category_by_isin = {}

    for _, row in df.iterrows():
        isin = str(
            row.get(isin_col, "")
        ).strip()

        if not isin or isin.lower() == "nan":
            continue

        rank = None

        if rank_col is not None:
            try:
                rank = int(
                    float(
                        row.get(rank_col)
                    )
                )
            except Exception:
                rank = None

        category = normalize_category(
            row.get(category_col),
            rank,
        )

        if category:
            category_by_isin[isin] = category

    matched = 0

    counts = {
        "Large Cap": 0,
        "Mid Cap": 0,
        "Small Cap": 0,
        "Micro Cap": 0,
    }

    for row in stocks:
        isin = str(
            row.get("isin") or ""
        ).strip()

        category = (
            category_by_isin.get(isin)
        )

        row["marketCapCategory"] = category

        if category:
            matched += 1

            counts[category] = (
                counts.get(category, 0) + 1
            )

    stocks_path.write_text(
        json.dumps(
            stocks,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )

    print({
        "stocks": len(stocks),
        "marketCapMatched": matched,
        "categoryCounts": counts,
    })


if __name__ == "__main__":
    main()
