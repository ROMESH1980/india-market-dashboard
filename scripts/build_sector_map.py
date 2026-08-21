import csv
import io
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/csv,*/*"
}


def load_existing():
    path = DATA / "sector_map.json"

    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def download_nifty500():
    r = requests.get(URL, headers=HEADERS, timeout=45)
    r.raise_for_status()

    text = r.content.decode("utf-8-sig", errors="ignore")
    return list(csv.DictReader(io.StringIO(text)))


def main():
    sector_map = load_existing()
    rows = download_nifty500()

    added = 0

    for row in rows:
        clean = {
            str(k).strip().upper(): str(v).strip()
            for k, v in row.items()
        }

        symbol = clean.get("SYMBOL", "")
        industry = clean.get("INDUSTRY", "")

        if not symbol:
            continue

        current = sector_map.get(symbol, {})

        sector_map[symbol] = {
            "sector": current.get("sector") or industry or "Unclassified",
            "industry": current.get("industry") or industry or "Unclassified"
        }

        added += 1

    DATA.mkdir(exist_ok=True)

    (DATA / "sector_map.json").write_text(
        json.dumps(
            sector_map,
            indent=2,
            ensure_ascii=False
        )
    )

   
        print({
        "nifty500Rows": len(rows),
        "mappedRows": added,
        "totalSectorMap": len(sector_map)
    })


if __name__ == "__main__":
    main()
