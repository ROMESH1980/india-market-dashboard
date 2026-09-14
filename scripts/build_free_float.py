import io
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


# =========================================================
# CONFIG
# =========================================================

BASE_URL = "https://www.nseindia.com"

SHAREHOLDING_PAGE = (
    "https://www.nseindia.com/"
    "companies-listing/"
    "corporate-filings-shareholding-pattern"
)

TEST_SYMBOLS = [
    "RELIANCE",
    "TCS",
    "INFY",
    "TITAN",
    "ASHOKLEY",
    "ACUTAAS",
    "AWL",
    "RIIL",
]

TIMEOUT = (5, 12)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com/",
}


# =========================================================
# SESSION
# =========================================================

def build_session():
    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    print("Warming NSE session...")

    try:
        response = session.get(
            BASE_URL,
            timeout=TIMEOUT,
        )

        print(
            "Warmup status:",
            response.status_code,
        )

        print(
            "Warmup bytes:",
            len(response.content),
        )

    except Exception as exc:
        print(
            "Warmup failed:",
            repr(exc),
        )

    return session


# =========================================================
# TEXT HELPERS
# =========================================================

def clean_text(value):
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def row_text(row):
    try:
        values = row.tolist()

    except Exception:
        values = list(row)

    return " ".join(
        clean_text(value).lower()
        for value in values
        if clean_text(value)
    )


# =========================================================
# LINK EXTRACTION
# =========================================================

def extract_links(
    html,
    page_url,
):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    all_links = []

    xbrl_links = []

    for anchor in soup.find_all(
        "a"
    ):
        href = clean_text(
            anchor.get("href")
        )

        if not href:
            continue

        label = clean_text(
            anchor.get_text(
                " ",
                strip=True,
            )
        )

        absolute = urljoin(
            page_url,
            href,
        )

        item = {
            "label": label,
            "href": href,
            "url": absolute,
        }

        all_links.append(
            item
        )

        test = (
            href
            +
            " "
            +
            label
        ).lower()

        if any(
            token in test
            for token in [
                "xbrl",
                "ixbrl",
                ".xml",
                "shareholding",
            ]
        ):
            xbrl_links.append(
                item
            )

    return (
        all_links,
        xbrl_links,
    )


# =========================================================
# TABLE ANALYSIS
# =========================================================

def inspect_tables(
    html,
):
    try:
        tables = pd.read_html(
            io.StringIO(
                html
            )
        )

    except Exception as exc:
        print(
            "pandas.read_html FAILED:",
            repr(exc),
        )

        return []

    print(
        "HTML tables found:",
        len(tables),
    )

    for index, table in enumerate(
        tables[:15]
    ):
        print()
        print(
            f"TABLE #{index}"
        )

        print(
            "Shape:",
            table.shape,
        )

        print(
            "Columns:"
        )

        for column in table.columns:
            print(
                "   ",
                clean_text(column),
            )

        sample = []

        try:
            for _, row in table.head(
                8
            ).iterrows():
                text = row_text(
                    row
                )

                if text:
                    sample.append(
                        text[:500]
                    )

        except Exception as exc:
            print(
                "Sample error:",
                repr(exc),
            )

        print(
            "Sample:"
        )

        for item in sample[:5]:
            print(
                "   ",
                item,
            )

    return tables


# =========================================================
# FIND POSSIBLE PUBLIC TABLE / ROW
# =========================================================

def inspect_public_rows(
    tables,
):
    print()
    print(
        "Searching tables for PUBLIC / LOCKED / TOTAL rows..."
    )

    matches = 0

    for table_index, table in enumerate(
        tables
    ):
        try:
            for row_index, row in table.iterrows():

                text = row_text(
                    row
                )

                if not text:
                    continue

                interesting = (
                    "public"
                    in text
                    or
                    "locked"
                    in text
                    or
                    "total public"
                    in text
                )

                if not interesting:
                    continue

                matches += 1

                print(
                    f"Table {table_index}, "
                    f"row {row_index}:"
                )

                print(
                    "   ",
                    text[:800],
                )

                if matches >= 20:
                    return

        except Exception:
            continue

    if matches == 0:
        print(
            "NO PUBLIC/LOCKED ROWS FOUND"
        )


# =========================================================
# FETCH ONE TEST SYMBOL
# =========================================================

def diagnose_symbol(
    session,
    symbol,
):
    print()
    print(
        "=" * 80
    )

    print(
        f"SYMBOL: {symbol}"
    )

    print(
        "=" * 80
    )

    url = (
        SHAREHOLDING_PAGE
        +
        f"?symbol={symbol}&tabIndex=equity"
    )

    print(
        "Shareholding URL:"
    )

    print(
        url
    )

    try:
        response = session.get(
            url,
            timeout=TIMEOUT,
        )

    except Exception as exc:
        print(
            "PAGE REQUEST FAILED:",
            repr(exc),
        )

        return

    print(
        "HTTP status:",
        response.status_code,
    )

    print(
        "Content-Type:",
        response.headers.get(
            "content-type"
        ),
    )

    print(
        "Response bytes:",
        len(
            response.content
        ),
    )

    html = response.text

    lower_html = html.lower()

    print(
        "Contains symbol:",
        symbol.lower()
        in lower_html,
    )

    print(
        "Contains 'public':",
        "public"
        in lower_html,
    )

    print(
        "Contains 'xbrl':",
        "xbrl"
        in lower_html,
    )

    print(
        "Contains 'locked':",
        "locked"
        in lower_html,
    )

    print()
    print(
        "First 500 chars:"
    )

    print(
        html[:500]
        .replace(
            "\n",
            " "
        )
    )

    all_links, xbrl_links = extract_links(
        html,
        url,
    )

    print()
    print(
        "Total <a> links:",
        len(all_links),
    )

    print(
        "Possible XBRL/shareholding links:",
        len(xbrl_links),
    )

    for index, item in enumerate(
        xbrl_links[:15],
        start=1,
    ):
        print(
            f"{index}. LABEL:",
            item["label"][:150],
        )

        print(
            "   URL:",
            item["url"],
        )

    tables = inspect_tables(
        html
    )

    inspect_public_rows(
        tables
    )

    # =====================================================
    # TRY FIRST XBRL-LIKE LINK
    # =====================================================

    if not xbrl_links:

        print()
        print(
            "RESULT:"
        )

        print(
            "NO XBRL LINK FOUND IN SERVER HTML"
        )

        print(
            "Likely cause: NSE page loads filing links "
            "via JavaScript/API instead of static HTML."
        )

        return

    filing_url = xbrl_links[
        0
    ]["url"]

    print()
    print(
        "-" * 80
    )

    print(
        "Testing first XBRL-like link:"
    )

    print(
        filing_url
    )

    try:
        filing_response = session.get(
            filing_url,
            timeout=TIMEOUT,
        )

    except Exception as exc:
        print(
            "XBRL REQUEST FAILED:",
            repr(exc),
        )

        return

    print(
        "XBRL HTTP status:",
        filing_response.status_code,
    )

    print(
        "XBRL Content-Type:",
        filing_response.headers.get(
            "content-type"
        ),
    )

    print(
        "XBRL bytes:",
        len(
            filing_response.content
        ),
    )

    filing_text = (
        filing_response.text
    )

    print(
        "XBRL contains PUBLIC:",
        "public"
        in filing_text.lower(),
    )

    print(
        "XBRL contains LOCKED:",
        "locked"
        in filing_text.lower(),
    )

    filing_tables = inspect_tables(
        filing_text
    )

    inspect_public_rows(
        filing_tables
    )


# =========================================================
# MAIN
# =========================================================

def main():
    print(
        "=" * 80
    )

    print(
        "NSE FREE FLOAT DIAGNOSTIC"
    )

    print(
        "=" * 80
    )

    print(
        "This run DOES NOT modify data/stocks.json."
    )

    print(
        "This run DOES NOT calculate Market Cap / Price."
    )

    print(
        "Testing only known NSE symbols."
    )

    session = build_session()

    for symbol in TEST_SYMBOLS:
        diagnose_symbol(
            session,
            symbol,
        )

    print()
    print(
        "=" * 80
    )

    print(
        "DIAGNOSTIC COMPLETE"
    )

    print(
        "=" * 80
    )


if __name__ == "__main__":
    main()
