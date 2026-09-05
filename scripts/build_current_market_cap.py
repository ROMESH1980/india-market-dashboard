import csv
import io
import json
import re
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

STOCKS_PATH = DATA / "stocks.json"


# =========================================================
# SETTINGS
# =========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}

MAX_LOOKBACK_DAYS = 10


# =========================================================
# HELPERS
# =========================================================

def load_json(path, default):

    try:

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        return default


def save_json(path, data):

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def safe_float(value):

    try:

        if value is None:
            return None

        text = (
            str(value)
            .strip()
            .replace(",", "")
            .replace("₹", "")
        )

        if not text:
            return None

        number = float(text)

        if number <= 0:
            return None

        return number

    except Exception:

        return None


def normalize_text(value):

    text = (
        str(value or "")
        .upper()
        .strip()
    )

    text = re.sub(
        r"[^A-Z0-9]",
        "",
        text,
    )

    return text


def normalize_company_name(value):

    text = (
        str(value or "")
        .upper()
        .strip()
    )

    replacements = [
        "LIMITED",
        "LTD",
        "LTD.",
        "PRIVATE",
        "PVT",
        "PVT.",
        "INDIA",
        "THE",
    ]

    for word in replacements:

        text = re.sub(
            rf"\b{re.escape(word)}\b",
            " ",
            text,
        )

    text = re.sub(
        r"[^A-Z0-9]",
        "",
        text,
    )

    return text


def detect_stock_date(stocks):

    dates = []

    for row in stocks:

        value = row.get(
            "priceDate"
        )

        if not value:
            continue

        try:

            d = datetime.strptime(
                value,
                "%Y-%m-%d",
            ).date()

            dates.append(d)

        except Exception:

            pass

    if dates:
        return max(dates)

    return (
        datetime.now(timezone.utc)
        .date()
    )


# =========================================================
# NSE PR ZIP
# =========================================================

def pr_zip_url(date_obj):

    ddmmyy = date_obj.strftime(
        "%d%m%y"
    )

    return (
        "https://nsearchives.nseindia.com/"
        "archives/equities/bhavcopy/pr/"
        f"PR{ddmmyy}.zip"
    )


def download_pr_zip(date_obj):

    url = pr_zip_url(
        date_obj
    )

    print(
        f"Trying NSE PR bundle: "
        f"{date_obj.isoformat()}"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=45,
    )

    response.raise_for_status()

    return response.content, url


# =========================================================
# FIND MCAP CSV INSIDE PR ZIP
# =========================================================

def extract_market_cap_csv(
    zip_bytes,
    date_obj,
):

    expected = (
        "mcap"
        + date_obj.strftime(
            "%d%m%Y"
        )
        + ".csv"
    ).lower()

    with zipfile.ZipFile(
        io.BytesIO(zip_bytes)
    ) as z:

        names = z.namelist()

        print(
            "PR bundle files:",
            len(names),
        )

        # Exact expected filename
        for name in names:

            if (
                Path(name)
                .name
                .lower()
                ==
                expected
            ):

                print(
                    "Market-cap file:",
                    name,
                )

                return (
                    z.read(name)
                    .decode(
                        "utf-8-sig",
                        errors="ignore",
                    ),
                    name,
                )

        # Fallback:
        # Any CSV whose basename begins with "mcap"
        for name in names:

            base = (
                Path(name)
                .name
                .lower()
            )

            if (
                base.startswith(
                    "mcap"
                )
                and
                base.endswith(
                    ".csv"
                )
            ):

                print(
                    "Market-cap fallback file:",
                    name,
                )

                return (
                    z.read(name)
                    .decode(
                        "utf-8-sig",
                        errors="ignore",
                    ),
                    name,
                )

    raise RuntimeError(
        "Market-cap CSV not found "
        "inside NSE PR bundle"
    )


# =========================================================
# CSV PARSER
# =========================================================

def detect_header_row(rows):

    for index, row in enumerate(
        rows[:30]
    ):

        joined = " ".join(
            str(x)
            for x in row
        ).lower()

        has_market_cap = (
            "market"
            in joined
            and
            "cap"
            in joined
        )

        has_identity = (
            "symbol" in joined
            or
            "security" in joined
            or
            "isin" in joined
            or
            "name" in joined
        )

        if (
            has_market_cap
            and
            has_identity
        ):

            return index

    return None


def find_column(
    headers,
    keywords,
):

    for index, header in enumerate(
        headers
    ):

        low = (
            str(header)
            .strip()
            .lower()
        )

        for keyword in keywords:

            if keyword in low:
                return index

    return None


def parse_mcap_csv(text):

    raw_rows = list(
        csv.reader(
            io.StringIO(text)
        )
    )

    raw_rows = [
        row
        for row in raw_rows
        if any(
            str(x).strip()
            for x in row
        )
    ]

    if not raw_rows:

        raise RuntimeError(
            "Market-cap CSV is empty"
        )

    header_row = detect_header_row(
        raw_rows
    )

    if header_row is None:

        print(
            "First 10 rows from market-cap file:"
        )

        for row in raw_rows[:10]:
            print(row)

        raise RuntimeError(
            "Could not detect market-cap CSV header"
        )

    headers = [
        str(x).strip()
        for x
        in raw_rows[
            header_row
        ]
    ]

    print(
        "Market-cap columns:"
    )

    print(
        headers
    )

    symbol_col = find_column(
        headers,
        [
            "symbol",
            "security symbol",
            "ticker",
        ],
    )

    isin_col = find_column(
        headers,
        [
            "isin",
        ],
    )

    name_col = find_column(
        headers,
        [
            "security name",
            "name of security",
            "security",
            "company name",
            "name",
        ],
    )

    market_cap_col = None

    for index, header in enumerate(
        headers
    ):

        low = (
            str(header)
            .strip()
            .lower()
        )

        if (
            "market"
            in low
            and
            "cap"
            in low
        ):

            market_cap_col = index
            break

    if market_cap_col is None:

        raise RuntimeError(
            "Market-cap column not found"
        )

    print({
        "symbolColumn":
            symbol_col,

        "isinColumn":
            isin_col,

        "nameColumn":
            name_col,

        "marketCapColumn":
            market_cap_col,
    })

    by_symbol = {}
    by_isin = {}
    by_name = {}

    parsed = 0

    for row in raw_rows[
        header_row + 1:
    ]:

        if (
            len(row)
            <= market_cap_col
        ):
            continue

        market_cap_rs = (
            safe_float(
                row[
                    market_cap_col
                ]
            )
        )

        if market_cap_rs is None:
            continue

        # NSE MCAP file reports market cap in rupees.
        # Convert Rs. to Rs. Crore.
        market_cap_cr = (
            market_cap_rs
            /
            10_000_000
        )

        symbol = None
        isin = None
        name = None

        if (
            symbol_col is not None
            and
            len(row) > symbol_col
        ):

            symbol = normalize_text(
                row[
                    symbol_col
                ]
            )

        if (
            isin_col is not None
            and
            len(row) > isin_col
        ):

            isin = normalize_text(
                row[
                    isin_col
                ]
            )

        if (
            name_col is not None
            and
            len(row) > name_col
        ):

            name = normalize_company_name(
                row[
                    name_col
                ]
            )

        item = {

            "marketCapCr":
                round(
                    market_cap_cr,
                    2,
                ),

            "symbol":
                symbol,

            "isin":
                isin,

            "name":
                name,
        }

        if symbol:
            by_symbol[
                symbol
            ] = item

        if isin:
            by_isin[
                isin
            ] = item

        if name:
            by_name[
                name
            ] = item

        parsed += 1

    print(
        "Market-cap rows parsed:",
        parsed,
    )

    return {

        "bySymbol":
            by_symbol,

        "byIsin":
            by_isin,

        "byName":
            by_name,

        "parsed":
            parsed,
    }


# =========================================================
# LOAD LATEST NSE MARKET CAP REPORT
# =========================================================

def load_latest_market_cap_report(
    preferred_date,
):

    last_error = None

    for back in range(
        0,
        MAX_LOOKBACK_DAYS + 1,
    ):

        d = (
            preferred_date
            -
            timedelta(
                days=back
            )
        )

        # Skip weekend
        if d.weekday() >= 5:
            continue

        try:

            zip_bytes, url = (
                download_pr_zip(
                    d
                )
            )

            text, filename = (
                extract_market_cap_csv(
                    zip_bytes,
                    d,
                )
            )

            parsed = parse_mcap_csv(
                text
            )

            if (
                parsed[
                    "parsed"
                ]
                <= 0
            ):

                raise RuntimeError(
                    "No market-cap rows parsed"
                )

            return {

                "date":
                    d.isoformat(),

                "url":
                    url,

                "filename":
                    filename,

                "data":
                    parsed,
            }

        except Exception as exc:

            last_error = exc

            print(
                f"Market-cap report unavailable "
                f"for {d}: {exc}"
            )

    raise RuntimeError(
        "No usable NSE PR market-cap report "
        f"found. Last error: {last_error}"
    )


# =========================================================
# APPLY MARKET CAP TO STOCKS.JSON
# =========================================================

def apply_market_cap(
    stocks,
    report,
):

    data = report[
        "data"
    ]

    by_symbol = data[
        "bySymbol"
    ]

    by_isin = data[
        "byIsin"
    ]

    by_name = data[
        "byName"
    ]

    stats = {

        "stocks":
            len(stocks),

        "matchedByIsin":
            0,

        "matchedBySymbol":
            0,

        "matchedByName":
            0,

        "unmatched":
            0,

        "marketCapCalculated":
            0,
    }

    for row in stocks:

        symbol = normalize_text(
            row.get(
                "symbol"
            )
        )

        isin = normalize_text(
            row.get(
                "isin"
            )
        )

        name = normalize_company_name(
            row.get(
                "name"
            )
        )

        info = None
        match_type = None

        # ISIN first - safest
        if (
            isin
            and
            isin in by_isin
        ):

            info = (
                by_isin[
                    isin
                ]
            )

            match_type = (
                "ISIN"
            )

            stats[
                "matchedByIsin"
            ] += 1

        # Symbol fallback
        elif (
            symbol
            and
            symbol in by_symbol
        ):

            info = (
                by_symbol[
                    symbol
                ]
            )

            match_type = (
                "SYMBOL"
            )

            stats[
                "matchedBySymbol"
            ] += 1

        # Company-name fallback
        elif (
            name
            and
            name in by_name
        ):

            info = (
                by_name[
                    name
                ]
            )

            match_type = (
                "NAME"
            )

            stats[
                "matchedByName"
            ] += 1

        # No match
        if not info:

            row[
                "marketCapCr"
            ] = None

            row[
                "marketCapDate"
            ] = None

            row[
                "marketCapSource"
            ] = None

            row[
                "marketCapMatchType"
            ] = None

            stats[
                "unmatched"
            ] += 1

            continue

        market_cap_cr = (
            info.get(
                "marketCapCr"
            )
        )

        row[
            "marketCapCr"
        ] = (
            market_cap_cr
        )

        row[
            "marketCapDate"
        ] = (
            report[
                "date"
            ]
        )

        row[
            "marketCapSource"
        ] = (
            "NSE PR Market Capitalisation"
        )

        row[
            "marketCapMatchType"
        ] = (
            match_type
        )

        stats[
            "marketCapCalculated"
        ] += 1

    return stats


# =========================================================
# MAIN
# =========================================================

def main():

    stocks = load_json(
        STOCKS_PATH,
        [],
    )

    if not isinstance(
        stocks,
        list,
    ):

        raise RuntimeError(
            "stocks.json must contain a list"
        )

    if not stocks:

        raise RuntimeError(
            "stocks.json is empty"
        )

    print(
        "=============================================="
    )

    print(
        "BUILD CURRENT MARKET CAP - BULK NSE REPORT"
    )

    print(
        "=============================================="
    )

    preferred_date = (
        detect_stock_date(
            stocks
        )
    )

    print(
        "Preferred market date:",
        preferred_date,
    )

    # =====================================================
    # LOAD NSE BULK MARKET-CAP REPORT
    # =====================================================

    report = (
        load_latest_market_cap_report(
            preferred_date
        )
    )

    print()

    print(
        "NSE market-cap report loaded:"
    )

    print(
        {
            "date":
                report[
                    "date"
                ],

            "file":
                report[
                    "filename"
                ],

            "url":
                report[
                    "url"
                ],
        }
    )

    # =====================================================
    # APPLY MARKET CAPS
    # =====================================================

    stats = apply_market_cap(
        stocks,
        report,
    )

    save_json(
        STOCKS_PATH,
        stocks,
    )

    # =====================================================
    # COVERAGE
    # =====================================================

    coverage = 0

    if stats[
        "stocks"
    ]:

        coverage = (

            stats[
                "marketCapCalculated"
            ]

            /
            stats[
                "stocks"
            ]

            *
            100
        )

    stats[
        "coveragePct"
    ] = round(
        coverage,
        2,
    )

    stats[
        "reportDate"
    ] = report[
        "date"
    ]

    stats[
        "reportFile"
    ] = report[
        "filename"
    ]

    # =====================================================
    # LOG
    # =====================================================

    print()

    print(
        "=============================================="
    )

    print(
        "CURRENT MARKET CAP COMPLETE"
    )

    print(
        "=============================================="
    )

    print(
        json.dumps(
            stats,
            indent=2,
        )
    )

    print()

    print(
        "SOURCE:"
    )

    print(
        "Official NSE PR daily market-cap file"
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "No individual NSE quote API calls are used."
    )

    print(
        "AMFI average market cap is NOT used "
        "as current marketCapCr."
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
