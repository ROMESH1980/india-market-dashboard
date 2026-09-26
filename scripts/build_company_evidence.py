import json
import re
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

import requests


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

STOCKS_PATH = DATA_DIR / "stocks.json"
EVIDENCE_PATH = DATA_DIR / "company_evidence.json"
CANDIDATES_PATH = DATA_DIR / "company_evidence_candidates.json"


# =========================================================
# SETTINGS
# =========================================================

TODAY = datetime.now(timezone.utc).date()
RUN_DATE = TODAY.isoformat()

# Keep first version conservative.
LOOKBACK_DAYS = 365

# Do not hammer NSE.
REQUEST_DELAY = 0.15
REQUEST_TIMEOUT = 20

# Safety limit. We do NOT want thousands of NSE requests
# to make the normal daily workflow extremely slow.
MAX_SYMBOLS_PER_RUN = 350


# =========================================================
# NSE
# =========================================================

NSE_HOME = "https://www.nseindia.com"

NSE_ANNOUNCEMENT_API = (
    "https://www.nseindia.com/api/"
    "corporate-announcements"
)

NSE_ANNOUNCEMENT_PAGE = (
    "https://www.nseindia.com/companies-listing/"
    "corporate-filings-announcements"
)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": NSE_ANNOUNCEMENT_PAGE,
    "Connection": "keep-alive",
}


# =========================================================
# STRONG EVENT PHRASES
# =========================================================

CAPEX_STRONG = [
    "capacity expansion",
    "capacity addition",
    "capacity enhancement",
    "capacity augmentation",
    "increase in capacity",
    "enhancement of capacity",
    "expansion of capacity",
    "expanding capacity",

    "new plant",
    "new manufacturing plant",
    "new manufacturing facility",
    "new facility",
    "new manufacturing unit",
    "new production unit",

    "greenfield project",
    "greenfield expansion",
    "brownfield expansion",

    "plant expansion",
    "facility expansion",
    "manufacturing expansion",

    "commissioned",
    "commissioning",
    "commercial production",
    "commercial operations",
    "commenced production",
    "commencement of production",
    "commence production",
    "production commenced",

    "new production line",
    "additional production line",
    "new manufacturing line",

    "setting up a plant",
    "setting up new plant",
    "setting up a facility",
    "setting up new facility",
    "setting up a manufacturing unit",

    "installed capacity",
    "production capacity",
]


CAPEX_INVESTMENT = [
    "capital expenditure",
    "capex",
    "investment",
    "invest",
    "crore",
    "million",
    "billion",
]


CAPEX_CONTEXT = [
    "plant",
    "facility",
    "manufacturing",
    "capacity",
    "production",
    "unit",
    "factory",
    "project",
    "expansion",
]


TAILWIND_STRONG = [
    "production linked incentive",
    "pli scheme",
    "pli incentive",

    "import substitution",
    "import-substitution",

    "localisation",
    "localization",
    "indigenisation",
    "indigenization",

    "china+1",
    "china + 1",
    "china plus one",

    "anti-dumping duty",
    "anti dumping duty",
    "safeguard duty",

    "government incentive",
    "government scheme",
    "government policy",

    "regulatory mandate",
    "regulatory change",

    "domestic procurement",
    "defence localisation",
    "defense localization",

    "energy transition",
    "renewable energy",
    "renewable capacity",

    "grid expansion",
    "transmission expansion",

    "railway modernisation",
    "railway modernization",

    "semiconductor mission",
    "semiconductor incentive",

    "infrastructure spending",
    "infrastructure investment",

    "export opportunity",
    "export demand",
]


# =========================================================
# GENERIC / FALSE-POSITIVE TEXT
# =========================================================

REJECT_TEXT = [
    "too many requests",
    "rate limited",
    "rate limit",
    "automated screening proxy",
    "structural-tailwind proxy",
    "proxy unavailable",
    "methodology.html",
    "insufficient data",
]


# =========================================================
# JSON HELPERS
# =========================================================

def load_json(path, default):
    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def clean(value):
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def low(value):
    return clean(value).lower()


def contains_any(text, phrases):
    t = low(text)

    return any(
        phrase in t
        for phrase in phrases
    )


def reject_text(text):
    return contains_any(
        text,
        REJECT_TEXT,
    )


# =========================================================
# DATE
# =========================================================

def parse_date(value):
    value = clean(value)

    if not value:
        return None

    formats = [
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                value,
                fmt,
            ).date()
        except Exception:
            pass

    # Sometimes NSE sends extra milliseconds/timezone.
    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).date()
    except Exception:
        return None


def within_lookback(value):
    d = parse_date(value)

    if d is None:
        # We don't reject solely because date format changed.
        return True

    return (
        TODAY - timedelta(
            days=LOOKBACK_DAYS
        )
    ) <= d <= (
        TODAY + timedelta(days=1)
    )


# =========================================================
# NSE SESSION
# =========================================================

def make_session():
    s = requests.Session()

    s.headers.update(HEADERS)

    try:
        r = s.get(
            NSE_HOME,
            timeout=REQUEST_TIMEOUT,
        )

        print(
            "NSE session warm-up:",
            r.status_code,
        )

    except Exception as exc:
        print(
            "NSE session warm-up warning:",
            exc,
        )

    return s


# =========================================================
# ANNOUNCEMENT FIELD NORMALIZATION
# =========================================================

def first_value(row, keys):
    if not isinstance(row, dict):
        return ""

    for key in keys:
        value = row.get(key)

        if value not in (
            None,
            "",
        ):
            return clean(value)

    return ""


def normalize_announcement(row):
    symbol = first_value(
        row,
        [
            "symbol",
            "sm_name",
            "smName",
            "companySymbol",
        ],
    )

    company = first_value(
        row,
        [
            "company",
            "companyName",
            "sm_name",
            "desc",
        ],
    )

    subject = first_value(
        row,
        [
            "subject",
            "sub",
            "purpose",
            "announcementSubject",
        ],
    )

    description = first_value(
        row,
        [
            "desc",
            "description",
            "details",
            "remarks",
            "attchmntText",
            "announcement",
        ],
    )

    attachment = first_value(
        row,
        [
            "attchmntFile",
            "attachment",
            "attachmentFile",
            "fileName",
            "url",
        ],
    )

    broadcast_date = first_value(
        row,
        [
            "an_dt",
            "broadcastDate",
            "broadcastDateTime",
            "date",
            "sort_date",
        ],
    )

    # NSE often provides relative attachment paths.
    if attachment:
        if attachment.startswith("//"):
            attachment = (
                "https:" + attachment
            )

        elif attachment.startswith("/"):
            attachment = (
                NSE_HOME + attachment
            )

        elif not attachment.startswith(
            ("http://", "https://")
        ):
            # Common NSE announcement attachment host.
            attachment = (
                "https://nsearchives.nseindia.com/"
                "corporate/"
                + attachment.lstrip("/")
            )

    text = clean(
        " ".join(
            [
                subject,
                description,
            ]
        )
    )

    return {
        "symbol": symbol.upper(),
        "company": company,
        "subject": subject,
        "description": description,
        "text": text,
        "source": attachment,
        "sourceDate": broadcast_date,
    }


# =========================================================
# FETCH NSE ANNOUNCEMENTS
# =========================================================

def fetch_symbol_announcements(
    session,
    symbol,
):
    """
    Fetch recent corporate announcements for one symbol.

    IMPORTANT:
    Failure returns [] instead of stopping daily workflow.
    """

    params = {
        "index": "equities",
        "symbol": symbol,
    }

    try:
        r = session.get(
            NSE_ANNOUNCEMENT_API,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )

        if r.status_code != 200:
            print(
                f"{symbol}: NSE HTTP "
                f"{r.status_code}"
            )
            return []

        data = r.json()

        if isinstance(data, list):
            rows = data

        elif isinstance(data, dict):
            rows = (
                data.get("data")
                or data.get("rows")
                or data.get("announcements")
                or []
            )

        else:
            rows = []

        out = []

        for raw in rows:
            item = normalize_announcement(
                raw
            )

            # Protect against endpoint returning
            # announcements for multiple symbols.
            item_symbol = item.get(
                "symbol",
                "",
            )

            if (
                item_symbol
                and item_symbol != symbol.upper()
            ):
                continue

            if not within_lookback(
                item.get("sourceDate")
            ):
                continue

            out.append(item)

        return out

    except Exception as exc:
        print(
            f"{symbol}: NSE announcement "
            f"fetch warning: {exc}"
        )

        return []


# =========================================================
# EVENT CLASSIFICATION
# =========================================================

def detect_capex(text):
    """
    Conservative CAPEX detector.

    Strong expansion language qualifies directly.

    Generic 'investment/capex' requires plant/capacity/
    manufacturing context.
    """

    if reject_text(text):
        return False, []

    t = low(text)

    matches = [
        phrase
        for phrase in CAPEX_STRONG
        if phrase in t
    ]

    if matches:
        return True, matches[:6]

    investment_matches = [
        phrase
        for phrase in CAPEX_INVESTMENT
        if phrase in t
    ]

    context_matches = [
        phrase
        for phrase in CAPEX_CONTEXT
        if phrase in t
    ]

    if (
        investment_matches
        and context_matches
    ):
        matches = (
            investment_matches[:3]
            + context_matches[:3]
        )

        return True, matches

    return False, []


def detect_tailwind(text):
    """
    Tailwind must contain an explicit structural driver.
    Generic sector growth language is NOT enough.
    """

    if reject_text(text):
        return False, []

    t = low(text)

    matches = [
        phrase
        for phrase in TAILWIND_STRONG
        if phrase in t
    ]

    if not matches:
        return False, []

    return True, matches[:6]


# =========================================================
# CANDIDATE QUALITY
# =========================================================

def valid_source(source):
    source = clean(source)

    if not source:
        return False

    return source.startswith(
        ("https://", "http://")
    )


def build_reason(
    trigger_type,
    announcement,
    matches,
):
    subject = clean(
        announcement.get("subject")
    )

    description = clean(
        announcement.get("description")
    )

    if subject and description:
        base = (
            f"{subject}: {description}"
        )

    else:
        base = (
            subject
            or description
            or announcement.get(
                "text",
                ""
            )
        )

    base = clean(base)

    # Keep JSON manageable.
    if len(base) > 700:
        base = base[:697] + "..."

    if trigger_type == "capex":
        prefix = (
            "NSE filing indicates a possible "
            "company-specific CAPEX/expansion event."
        )

    else:
        prefix = (
            "NSE filing indicates a possible "
            "structural industry tailwind event."
        )

    matched = ", ".join(matches)

    return clean(
        f"{prefix} "
        f"Matched: {matched}. "
        f"Filing: {base}"
    )


def candidate_record(
    trigger_type,
    announcement,
    matches,
):
    source = clean(
        announcement.get("source")
    )

    if not valid_source(source):
        return None

    return {
        "type": trigger_type,

        "reason": build_reason(
            trigger_type,
            announcement,
            matches,
        ),

        "subject": clean(
            announcement.get("subject")
        ),

        "details": clean(
            announcement.get(
                "description"
            )
        ),

        "source": source,

        "sourceDate": clean(
            announcement.get(
                "sourceDate"
            )
        ),

        "matchedTerms": matches,

        "sourceType":
            "NSE_CORPORATE_ANNOUNCEMENT",

        "candidateStatus":
            "REVIEW_REQUIRED",

        "candidateBuilt":
            RUN_DATE,
    }


# =========================================================
# DEDUPE
# =========================================================

def candidate_key(item):
    return (
        low(item.get("source")),
        low(item.get("subject")),
        low(item.get("sourceDate")),
    )


def add_unique(
    container,
    item,
):
    if item is None:
        return

    key = candidate_key(item)

    existing = {
        candidate_key(x)
        for x in container
        if isinstance(x, dict)
    }

    if key not in existing:
        container.append(item)


# =========================================================
# VERIFIED EVIDENCE CHECK
# =========================================================

def verified_exists(
    evidence_stocks,
    symbol,
    trigger_type,
):
    stock = (
        evidence_stocks.get(
            symbol,
            {}
        )
        or {}
    )

    if not isinstance(stock, dict):
        return False

    block = (
        stock.get(
            trigger_type,
            {}
        )
        or {}
    )

    if not isinstance(block, dict):
        return False

    reason = clean(
        block.get("reason")
    )

    source = clean(
        block.get("source")
    )

    return bool(
        reason
        and valid_source(source)
    )


# =========================================================
# SYMBOL UNIVERSE
# =========================================================

def load_symbols():
    stocks = load_json(
        STOCKS_PATH,
        [],
    )

    rows = []

    for row in stocks:
        if not isinstance(row, dict):
            continue

        symbol = clean(
            row.get("symbol")
        ).upper()

        if not symbol:
            continue

        rows.append(
            {
                "symbol": symbol,
                "name": clean(
                    row.get("name")
                ),
                "board": clean(
                    row.get("board")
                ),
                "changePct":
                    row.get("changePct"),
                "todayVolume":
                    row.get(
                        "todayVolume"
                    ),
            }
        )

    # -----------------------------------------------------
    # Priority:
    # scan actively traded / moving names first.
    #
    # This keeps daily NSE API requests controlled.
    # It does NOT decide whether a trigger is valid.
    # -----------------------------------------------------

    def priority(row):
        change = row.get(
            "changePct"
        )

        volume = row.get(
            "todayVolume"
        )

        try:
            change = abs(
                float(change)
            )
        except Exception:
            change = 0.0

        try:
            volume = float(
                volume
            )
        except Exception:
            volume = 0.0

        return (
            change,
            volume,
        )

    rows.sort(
        key=priority,
        reverse=True,
    )

    return rows[
        :MAX_SYMBOLS_PER_RUN
    ]


# =========================================================
# MAIN BUILD
# =========================================================

def build():
    evidence = load_json(
        EVIDENCE_PATH,
        {},
    )

    evidence_stocks = (
        evidence.get(
            "stocks",
            {}
        )
        or {}
    )

    universe = load_symbols()

    session = make_session()

    stocks_out = {}

    scanned = 0
    announcements_seen = 0

    capex_count = 0
    tailwind_count = 0

    fetch_failures = 0

    print(
        "Evidence scan universe:",
        len(universe),
    )

    for index, stock in enumerate(
        universe,
        start=1,
    ):
        symbol = stock["symbol"]

        try:
            announcements = (
                fetch_symbol_announcements(
                    session,
                    symbol,
                )
            )

        except Exception as exc:
            print(
                symbol,
                "unexpected fetch error:",
                exc,
            )

            fetch_failures += 1
            continue

        scanned += 1

        if not announcements:
            if (
                index % 50 == 0
            ):
                print(
                    f"Progress {index}/"
                    f"{len(universe)}"
                )

            time.sleep(
                REQUEST_DELAY
            )

            continue

        announcements_seen += len(
            announcements
        )

        capex_items = []
        tailwind_items = []

        for announcement in announcements:
            text = announcement.get(
                "text",
                "",
            )

            # -----------------------------
            # CAPEX
            # -----------------------------

            if not verified_exists(
                evidence_stocks,
                symbol,
                "capex",
            ):
                is_capex, matches = (
                    detect_capex(text)
                )

                if is_capex:
                    item = candidate_record(
                        "capex",
                        announcement,
                        matches,
                    )

                    add_unique(
                        capex_items,
                        item,
                    )

            # -----------------------------
            # TAILWIND
            # -----------------------------

            if not verified_exists(
                evidence_stocks,
                symbol,
                "tailwind",
            ):
                is_tailwind, matches = (
                    detect_tailwind(text)
                )

                if is_tailwind:
                    item = candidate_record(
                        "tailwind",
                        announcement,
                        matches,
                    )

                    add_unique(
                        tailwind_items,
                        item,
                    )

        if (
            capex_items
            or tailwind_items
        ):
            stock_block = {
                "name":
                    stock.get("name"),

                "board":
                    stock.get("board"),
            }

            if capex_items:
                stock_block[
                    "capex"
                ] = capex_items

                capex_count += len(
                    capex_items
                )

            if tailwind_items:
                stock_block[
                    "tailwind"
                ] = tailwind_items

                tailwind_count += len(
                    tailwind_items
                )

            stocks_out[
                symbol
            ] = stock_block

        if index % 50 == 0:
            print(
                f"Progress {index}/"
                f"{len(universe)} | "
                f"CAPEX={capex_count} | "
                f"Tailwind={tailwind_count}"
            )

        time.sleep(
            REQUEST_DELAY
        )

    result = {
        "_meta": {
            "description": (
                "NSE corporate-announcement evidence "
                "candidates for Big Move Scanner."
            ),

            "updated":
                RUN_DATE,

            "status":
                "REVIEW_REQUIRED",

            "lookbackDays":
                LOOKBACK_DAYS,

            "maxSymbolsPerRun":
                MAX_SYMBOLS_PER_RUN,

            "important": (
                "Candidates are NOT verified triggers. "
                "Review source filing before promoting "
                "evidence to company_evidence.json."
            ),

            "rules": {
                "capex": (
                    "Requires explicit company-specific "
                    "capacity/plant/facility/commissioning/"
                    "production expansion evidence."
                ),

                "tailwind": (
                    "Requires explicit structural driver "
                    "such as PLI, import substitution, "
                    "localisation, China+1, policy or "
                    "regulatory change."
                ),

                "scoreRule": (
                    "CAPEX score or Tailwind score alone "
                    "does NOT create a trigger."
                ),
            },

            "counts": {
                "symbolsScanned":
                    scanned,

                "announcementsSeen":
                    announcements_seen,

                "symbolsWithCandidates":
                    len(stocks_out),

                "capexCandidates":
                    capex_count,

                "tailwindCandidates":
                    tailwind_count,

                "fetchFailures":
                    fetch_failures,
            },
        },

        "stocks":
            stocks_out,
    }

    return result


# =========================================================
# RUN
# =========================================================

def main():
    print(
        "Starting NSE company evidence "
        "candidate scan..."
    )

    try:
        result = build()

    except Exception as exc:
        # -------------------------------------------------
        # FAIL-SAFE:
        # Evidence collection must NOT destroy the normal
        # daily NSE market-data workflow.
        # -------------------------------------------------

        print(
            "Company evidence collector warning:",
            exc,
        )

        result = {
            "_meta": {
                "description": (
                    "NSE corporate-announcement evidence "
                    "candidate scan."
                ),

                "updated":
                    RUN_DATE,

                "status":
                    "FETCH_FAILED_SAFE",

                "error":
                    clean(exc),

                "important": (
                    "Normal market-data workflow may "
                    "continue. No verified evidence was "
                    "modified."
                ),
            },

            "stocks": {},
        }

    save_json(
        CANDIDATES_PATH,
        result,
    )

    counts = (
        result.get(
            "_meta",
            {}
        )
        .get(
            "counts",
            {}
        )
    )

    print(
        "Evidence candidate build complete."
    )

    print(
        json.dumps(
            counts,
            indent=2,
        )
    )

    print(
        "Output:",
        CANDIDATES_PATH,
    )

    print(
        "IMPORTANT: company_evidence.json "
        "was NOT modified."
    )


if __name__ == "__main__":
    main()
