import csv
import io
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

NIFTY500_URL = (
    "https://www.niftyindices.com/"
    "IndexConstituent/ind_nifty500list.csv"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/csv,*/*",
}


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def download_nifty500():
    r = requests.get(
        NIFTY500_URL,
        headers=HEADERS,
        timeout=45
    )

    r.raise_for_status()

    text = r.content.decode(
        "utf-8-sig",
        errors="ignore"
    )

    return list(
        csv.DictReader(
            io.StringIO(text)
        )
    )


def build_nifty500_map():
    mapping = {}

    rows = download_nifty500()

    for row in rows:
        clean = {
            str(k).strip().upper():
                str(v).strip()
            for k, v in row.items()
        }

        symbol = clean.get(
            "SYMBOL",
            ""
        )

        industry = clean.get(
            "INDUSTRY",
            ""
        )

        if not symbol:
            continue

        mapping[symbol] = {
            "sector":
                industry or "Unclassified",

            "industry":
                industry or "Unclassified",

            "source":
                "Nifty Indices"
        }

    return mapping


def yahoo_classification(symbol):
    try:
        ticker = yf.Ticker(
            f"{symbol}.NS"
        )

        info = ticker.info or {}

        sector = (
            info.get("sector")
            or info.get("sectorDisp")
            or ""
        )

        industry = (
            info.get("industry")
            or info.get("industryDisp")
            or ""
        )

        sector = str(
            sector
        ).strip()

        industry = str(
            industry
        ).strip()

        if not sector and not industry:
            return symbol, None

        if not sector:
            sector = industry

        if not industry:
            industry = sector

        return symbol, {
            "sector":
                sector or "Unclassified",

            "industry":
                industry or "Unclassified",

            "source":
                "Yahoo Finance"
        }

    except Exception as e:
        print(
            f"{symbol}: classification unavailable: {e}"
        )

        return symbol, None


def main():

    DATA.mkdir(
        exist_ok=True
    )

    stocks = load_json(
        DATA / "stocks.json",
        []
    )

    existing = load_json(
        DATA / "sector_map.json",
        {}
    )

    # -------------------------
    # Step 1: Nifty 500
    # -------------------------

    try:
        nifty_map = (
            build_nifty500_map()
        )

        print(
            f"Nifty 500 classifications: "
            f"{len(nifty_map)}"
        )

    except Exception as e:
        print(
            f"Nifty 500 download failed: {e}"
        )

        nifty_map = {}

    sector_map = dict(existing)

    # Official Nifty data gets priority.
    for symbol, data in (
        nifty_map.items()
    ):
        sector_map[symbol] = data

    # -------------------------
    # Step 2: Find unclassified
    # -------------------------

    missing_symbols = []

    for row in stocks:

        symbol = row.get(
            "symbol"
        )

        if not symbol:
            continue

        current = sector_map.get(
            symbol,
            {}
        )

        sector = current.get(
            "sector"
        )

        industry = current.get(
            "industry"
        )

        missing = (
            not sector
            or sector == "Unclassified"
            or not industry
            or industry == "Unclassified"
        )

        if missing:
            missing_symbols.append(
                symbol
            )

    missing_symbols = list(
        dict.fromkeys(
            missing_symbols
        )
    )

    print({
        "totalStocks":
            len(stocks),

        "alreadyMapped":
            len(sector_map),

        "needFallback":
            len(missing_symbols)
    })

    # -------------------------
    # Step 3: Yahoo fallback
    # -------------------------

    yahoo_added = 0
    processed = 0

    with ThreadPoolExecutor(
        max_workers=8
    ) as executor:

        futures = {
            executor.submit(
                yahoo_classification,
                symbol
            ): symbol

            for symbol in (
                missing_symbols
            )
        }

        for future in as_completed(
            futures
        ):
            symbol, data = (
                future.result()
            )

            processed += 1

            if data:
                sector_map[
                    symbol
                ] = data

                yahoo_added += 1

            if processed % 50 == 0:
                print(
                    f"Classification progress: "
                    f"{processed}/"
                    f"{len(missing_symbols)}"
                )

    # -------------------------
    # Step 4: Save
    # -------------------------

    (
        DATA /
        "sector_map.json"
    ).write_text(
        json.dumps(
            sector_map,
            indent=2,
            ensure_ascii=False
        )
    )

    classified = 0
    unclassified = 0

    for symbol, data in (
        sector_map.items()
    ):

        sector = data.get(
            "sector"
        )

        if (
            sector
            and sector
            != "Unclassified"
        ):
            classified += 1
        else:
            unclassified += 1

    print({
        "nifty500Mapped":
            len(nifty_map),

        "yahooFallbackAdded":
            yahoo_added,

        "totalSectorMap":
            len(sector_map),

        "classified":
            classified,

        "unclassified":
            unclassified
    })


if __name__ == "__main__":
    main()
