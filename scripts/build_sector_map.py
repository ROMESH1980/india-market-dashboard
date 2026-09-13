import csv
import io
import json
import time
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

NSE_HOME = "https://www.nseindia.com"

NSE_QUOTE_URL = (
    "https://www.nseindia.com/api/quote-equity"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "application/json,text/plain,"
        "text/html,*/*"
    ),
    "Accept-Language":
        "en-US,en;q=0.9",
    "Referer":
        "https://www.nseindia.com/",
}


# =====================================================
# BASIC HELPERS
# =====================================================

def load_json(path, default):
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return default


def clean_text(value):
    if value is None:
        return ""

    value = str(value).strip()

    if value.lower() in {
        "",
        "none",
        "null",
        "nan",
        "n/a",
        "na",
        "-"
    }:
        return ""

    return value


def is_valid_classification(data):
    if not isinstance(data, dict):
        return False

    sector = clean_text(
        data.get("sector")
    )

    industry = clean_text(
        data.get("industry")
    )

    if not sector:
        return False

    if not industry:
        return False

    if sector.lower() == "unclassified":
        return False

    if industry.lower() == "unclassified":
        return False

    return True


# =====================================================
# NIFTY 500
# =====================================================

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
                clean_text(v)
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

        if not industry:
            continue

        mapping[symbol] = {
            "sector":
                industry,

            "industry":
                industry,

            "source":
                "Nifty Indices"
        }

    return mapping


# =====================================================
# NSE SESSION
# =====================================================

def create_nse_session():

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    try:
        session.get(
            NSE_HOME,
            timeout=20
        )

    except Exception:
        pass

    return session


# =====================================================
# NSE CLASSIFICATION
# =====================================================

def extract_nse_classification(
    symbol,
    payload
):

    if not isinstance(
        payload,
        dict
    ):
        return None

    industry_info = (
        payload.get(
            "industryInfo"
        )
        or {}
    )

    if not isinstance(
        industry_info,
        dict
    ):
        industry_info = {}

    macro = clean_text(
        industry_info.get(
            "macro"
        )
    )

    sector = clean_text(
        industry_info.get(
            "sector"
        )
    )

    industry = clean_text(
        industry_info.get(
            "industry"
        )
    )

    basic_industry = clean_text(
        industry_info.get(
            "basicIndustry"
        )
    )

    # -----------------------------------------
    # Sector
    # -----------------------------------------

    final_sector = (
        sector
        or macro
        or industry
        or basic_industry
    )

    # -----------------------------------------
    # Industry
    #
    # Basic Industry is preferred because
    # dashboard momentum is industry-first.
    # -----------------------------------------

    final_industry = (
        basic_industry
        or industry
        or sector
        or macro
    )

    if (
        not final_sector
        and not final_industry
    ):
        return None

    if not final_sector:
        final_sector = (
            final_industry
        )

    if not final_industry:
        final_industry = (
            final_sector
        )

    return {
        "sector":
            final_sector,

        "industry":
            final_industry,

        "macro":
            macro,

        "nseIndustry":
            industry,

        "basicIndustry":
            basic_industry,

        "source":
            "NSE"
    }


def nse_classification(
    session,
    symbol
):

    try:

        r = session.get(
            NSE_QUOTE_URL,
            params={
                "symbol":
                    symbol
            },
            timeout=25
        )

        if r.status_code != 200:

            return (
                symbol,
                None
            )

        payload = r.json()

        data = (
            extract_nse_classification(
                symbol,
                payload
            )
        )

        return (
            symbol,
            data
        )

    except Exception as e:

        print(
            f"{symbol}: NSE classification "
            f"unavailable: {e}"
        )

        return (
            symbol,
            None
        )


# =====================================================
# YAHOO FALLBACK
# =====================================================

def yahoo_classification(
    symbol
):

    try:

        ticker = yf.Ticker(
            f"{symbol}.NS"
        )

        info = (
            ticker.info
            or {}
        )

        sector = clean_text(
            info.get(
                "sector"
            )
            or info.get(
                "sectorDisp"
            )
        )

        industry = clean_text(
            info.get(
                "industry"
            )
            or info.get(
                "industryDisp"
            )
        )

        if (
            not sector
            and not industry
        ):
            return (
                symbol,
                None
            )

        if not sector:
            sector = industry

        if not industry:
            industry = sector

        return (
            symbol,
            {
                "sector":
                    sector,

                "industry":
                    industry,

                "source":
                    "Yahoo Finance"
            }
        )

    except Exception as e:

        print(
            f"{symbol}: Yahoo classification "
            f"unavailable: {e}"
        )

        return (
            symbol,
            None
        )


# =====================================================
# FIND MISSING
# =====================================================

def find_missing_symbols(
    stocks,
    sector_map
):

    missing = []

    for row in stocks:

        symbol = clean_text(
            row.get(
                "symbol"
            )
        )

        if not symbol:
            continue

        current = (
            sector_map.get(
                symbol
            )
            or {}
        )

        if not is_valid_classification(
            current
        ):
            missing.append(
                symbol
            )

    return list(
        dict.fromkeys(
            missing
        )
    )


# =====================================================
# MAIN
# =====================================================

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

    if not isinstance(
        existing,
        dict
    ):
        existing = {}

    sector_map = dict(
        existing
    )

    print({
        "totalStocks":
            len(stocks),

        "existingSectorMap":
            len(sector_map)
    })


    # =================================================
    # STEP 1
    # LOAD NIFTY 500
    # =================================================

    try:

        nifty_map = (
            build_nifty500_map()
        )

        print(
            "Nifty 500 classifications:",
            len(nifty_map)
        )

    except Exception as e:

        print(
            "Nifty 500 download failed:",
            e
        )

        nifty_map = {}


    # =================================================
    # STEP 2
    # APPLY NIFTY ONLY TO MISSING STOCKS
    #
    # Do not overwrite better NSE/Yahoo mappings.
    # =================================================

    nifty_added = 0

    for (
        symbol,
        data
    ) in nifty_map.items():

        current = (
            sector_map.get(
                symbol
            )
            or {}
        )

        if not is_valid_classification(
            current
        ):

            sector_map[
                symbol
            ] = data

            nifty_added += 1

    print({
        "niftyFallbackAdded":
            nifty_added
    })


    # =================================================
    # STEP 3
    # FIND REMAINING UNCLASSIFIED
    # =================================================

    missing_symbols = (
        find_missing_symbols(
            stocks,
            sector_map
        )
    )

    print({
        "needNSEClassification":
            len(missing_symbols)
    })


    # =================================================
    # STEP 4
    # NSE CLASSIFICATION
    #
    # Only unresolved stocks are queried.
    # =================================================

    nse_added = 0

    still_missing = []

    if missing_symbols:

        session = (
            create_nse_session()
        )

        total = len(
            missing_symbols
        )

        for index, symbol in enumerate(
            missing_symbols,
            start=1
        ):

            _, data = (
                nse_classification(
                    session,
                    symbol
                )
            )

            if (
                data
                and
                is_valid_classification(
                    data
                )
            ):

                sector_map[
                    symbol
                ] = data

                nse_added += 1

            else:

                still_missing.append(
                    symbol
                )

            if (
                index % 50 == 0
                or
                index == total
            ):

                print(
                    "NSE classification progress: "
                    f"{index}/{total}"
                )

            # Gentle throttle to reduce
            # NSE blocking/rate limiting.
            time.sleep(
                0.12
            )

    print({
        "nseAdded":
            nse_added,

        "remainingAfterNSE":
            len(still_missing)
    })


    # =================================================
    # STEP 5
    # YAHOO FALLBACK
    #
    # Only stocks NSE could not classify.
    # =================================================

    yahoo_added = 0

    processed = 0

    if still_missing:

        with ThreadPoolExecutor(
            max_workers=6
        ) as executor:

            futures = {

                executor.submit(
                    yahoo_classification,
                    symbol
                ):
                    symbol

                for symbol
                in still_missing
            }

            for future in as_completed(
                futures
            ):

                try:

                    symbol, data = (
                        future.result()
                    )

                except Exception as e:

                    processed += 1

                    print(
                        "Yahoo worker error:",
                        e
                    )

                    continue

                processed += 1

                if (
                    data
                    and
                    is_valid_classification(
                        data
                    )
                ):

                    sector_map[
                        symbol
                    ] = data

                    yahoo_added += 1

                if (
                    processed % 50 == 0
                    or
                    processed
                    == len(
                        still_missing
                    )
                ):

                    print(
                        "Yahoo classification "
                        "progress: "
                        f"{processed}/"
                        f"{len(still_missing)}"
                    )


    # =================================================
    # STEP 6
    # ENSURE EVERY STOCK HAS ENTRY
    # =================================================

    for row in stocks:

        symbol = clean_text(
            row.get(
                "symbol"
            )
        )

        if not symbol:
            continue

        current = (
            sector_map.get(
                symbol
            )
            or {}
        )

        if not is_valid_classification(
            current
        ):

            sector_map[
                symbol
            ] = {
                "sector":
                    "Unclassified",

                "industry":
                    "Unclassified",

                "source":
                    "Unavailable"
            }


    # =================================================
    # STEP 7
    # SAVE
    # =================================================

    output_path = (
        DATA /
        "sector_map.json"
    )

    output_path.write_text(
        json.dumps(
            sector_map,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


    # =================================================
    # STEP 8
    # SUMMARY
    # =================================================

    classified = 0

    unclassified = 0

    source_counts = {}

    for row in stocks:

        symbol = clean_text(
            row.get(
                "symbol"
            )
        )

        if not symbol:
            continue

        data = (
            sector_map.get(
                symbol
            )
            or {}
        )

        if is_valid_classification(
            data
        ):

            classified += 1

        else:

            unclassified += 1

        source = clean_text(
            data.get(
                "source"
            )
        ) or "Unknown"

        source_counts[
            source
        ] = (
            source_counts.get(
                source,
                0
            )
            + 1
        )

    print({
        "totalStocks":
            len(stocks),

        "classified":
            classified,

        "unclassified":
            unclassified,

        "classificationPct":
            round(
                (
                    classified /
                    len(stocks) *
                    100
                )
                if stocks
                else 0,
                2
            ),

        "niftyAdded":
            nifty_added,

        "nseAdded":
            nse_added,

        "yahooAdded":
            yahoo_added,

        "sources":
            source_counts
    })


if __name__ == "__main__":
    main()
