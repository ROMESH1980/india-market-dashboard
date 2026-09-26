import json
import re
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

STOCKS_PATH = DATA_DIR / "stocks.json"
EVIDENCE_PATH = DATA_DIR / "company_evidence.json"

CANDIDATES_PATH = (
    DATA_DIR /
    "company_evidence_candidates.json"
)


# =========================================================
# SETTINGS
# =========================================================

TODAY = datetime.now(
    timezone.utc
).date()

RUN_DATE = TODAY.isoformat()

LOOKBACK_DAYS = 365

REQUEST_DELAY = 0.15
REQUEST_TIMEOUT = 20

# First production-safe batch.
MAX_SYMBOLS_PER_RUN = 350

# Keep only strongest/latest useful evidence
# per company and trigger.
MAX_CAPEX_EVENTS_PER_STOCK = 1
MAX_TAILWIND_EVENTS_PER_STOCK = 1


# =========================================================
# NSE
# =========================================================

NSE_HOME = "https://www.nseindia.com"

NSE_ANNOUNCEMENT_API = (
    "https://www.nseindia.com/api/"
    "corporate-announcements"
)

NSE_ANNOUNCEMENT_PAGE = (
    "https://www.nseindia.com/"
    "companies-listing/"
    "corporate-filings-announcements"
)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/124.0.0.0 "
        "Safari/537.36"
    ),
    "Accept": (
        "application/json,"
        "text/plain,*/*"
    ),
    "Accept-Language":
        "en-US,en;q=0.9",
    "Referer":
        NSE_ANNOUNCEMENT_PAGE,
    "Connection":
        "keep-alive",
}


# =========================================================
# CAPEX POSITIVE PHRASES
# =========================================================

CAPEX_VERY_STRONG = [
    "capacity expansion",
    "capacity addition",
    "capacity enhancement",
    "capacity augmentation",

    "increase in capacity",
    "enhancement of capacity",
    "expansion of capacity",
    "expanding capacity",

    "new manufacturing plant",
    "new manufacturing facility",
    "new manufacturing unit",

    "new production unit",
    "new production line",
    "additional production line",
    "new manufacturing line",

    "greenfield project",
    "greenfield expansion",
    "brownfield expansion",

    "plant expansion",
    "facility expansion",
    "manufacturing expansion",

    "setting up a plant",
    "setting up new plant",

    "setting up a facility",
    "setting up new facility",

    "setting up a manufacturing unit",
]


CAPEX_OPERATIONAL = [
    "commissioned",
    "commissioning",

    "commercial production",
    "commercial operations",

    "commenced production",
    "commencement of production",
    "commence production",

    "production commenced",
    "operations commenced",
    "commencement of operations",
]


CAPEX_MEDIUM = [
    "installed capacity",
    "production capacity",
    "capital expenditure",
    "capex",
]


CAPEX_INVESTMENT = [
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


# =========================================================
# NEGATIVE CAPEX EVENTS
# =========================================================

# If these occur in the filing summary, the filing should
# NOT be treated as a positive expansion trigger.
CAPEX_NEGATIVE = [
    "postponement",
    "postponed",

    "delay",
    "delayed",
    "defer",
    "deferred",

    "cancel",
    "cancelled",
    "canceled",
    "cancellation",

    "withdraw",
    "withdrawn",

    "suspend",
    "suspended",
    "suspension",

    "shutdown",
    "shut down",

    "closure",
    "closed",

    "discontinue",
    "discontinued",
    "discontinuation",

    "abandon",
    "abandoned",

    "termination",
    "terminated",

    "halt",
    "halted",

    "temporary stoppage",
    "stoppage of production",

    "production stopped",
    "operations stopped",

    "plant closed",
    "plant shutdown",
]


# =========================================================
# TAILWIND PHRASES
# =========================================================

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
# GENERIC / BAD TEXT
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
            path.read_text(
                encoding="utf-8"
            )
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

    return clean(
        value
    ).lower()


def contains_any(
    text,
    phrases,
):

    t = low(text)

    return any(
        phrase in t
        for phrase in phrases
    )


def matched_phrases(
    text,
    phrases,
):

    t = low(text)

    return [
        phrase
        for phrase in phrases
        if phrase in t
    ]


def reject_text(text):

    return contains_any(
        text,
        REJECT_TEXT,
    )


# =========================================================
# DATE HELPERS
# =========================================================

DATE_FORMATS = [
    "%d-%b-%Y %H:%M:%S",
    "%d-%b-%Y",

    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y",

    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",

    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y",
]


def parse_date(value):

    value = clean(value)

    if not value:
        return None

    for fmt in DATE_FORMATS:

        try:

            return datetime.strptime(
                value,
                fmt,
            )

        except Exception:

            pass

    try:

        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

    except Exception:

        return None


def date_only(value):

    dt = parse_date(value)

    if dt is None:
        return None

    return dt.date()


def within_lookback(value):

    d = date_only(value)

    if d is None:
        return True

    minimum = (
        TODAY -
        timedelta(
            days=LOOKBACK_DAYS
        )
    )

    maximum = (
        TODAY +
        timedelta(days=1)
    )

    return (
        minimum <= d <= maximum
    )


# =========================================================
# NSE SESSION
# =========================================================

def make_session():

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    try:

        response = session.get(
            NSE_HOME,
            timeout=REQUEST_TIMEOUT,
        )

        print(
            "NSE session warm-up:",
            response.status_code,
        )

    except Exception as exc:

        print(
            "NSE session warm-up warning:",
            exc,
        )

    return session


# =========================================================
# NORMALIZE NSE ANNOUNCEMENT
# =========================================================

def first_value(
    row,
    keys,
):

    if not isinstance(
        row,
        dict,
    ):
        return ""

    for key in keys:

        value = row.get(
            key
        )

        if value not in (
            None,
            "",
        ):

            return clean(
                value
            )

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

    if attachment:

        if attachment.startswith(
            "//"
        ):

            attachment = (
                "https:" +
                attachment
            )

        elif attachment.startswith(
            "/"
        ):

            attachment = (
                NSE_HOME +
                attachment
            )

        elif not attachment.startswith(
            (
                "http://",
                "https://",
            )
        ):

            attachment = (
                "https://"
                "nsearchives.nseindia.com/"
                "corporate/"
                +
                attachment.lstrip("/")
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
        "symbol":
            symbol.upper(),

        "company":
            company,

        "subject":
            subject,

        "description":
            description,

        "text":
            text,

        "source":
            attachment,

        "sourceDate":
            broadcast_date,
    }


# =========================================================
# FETCH ANNOUNCEMENTS
# =========================================================

def fetch_symbol_announcements(
    session,
    symbol,
):

    params = {
        "index":
            "equities",

        "symbol":
            symbol,
    }

    try:

        response = session.get(
            NSE_ANNOUNCEMENT_API,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:

            print(
                f"{symbol}: "
                f"NSE HTTP "
                f"{response.status_code}"
            )

            return []

        data = response.json()

        if isinstance(
            data,
            list,
        ):

            rows = data

        elif isinstance(
            data,
            dict,
        ):

            rows = (
                data.get("data")
                or data.get("rows")
                or data.get(
                    "announcements"
                )
                or []
            )

        else:

            rows = []

        output = []

        for raw in rows:

            item = (
                normalize_announcement(
                    raw
                )
            )

            item_symbol = (
                item.get(
                    "symbol",
                    ""
                )
            )

            if (
                item_symbol
                and
                item_symbol !=
                symbol.upper()
            ):
                continue

            if not within_lookback(
                item.get(
                    "sourceDate"
                )
            ):
                continue

            output.append(
                item
            )

        return output

    except Exception as exc:

        print(
            f"{symbol}: "
            "NSE announcement "
            f"fetch warning: {exc}"
        )

        return []


# =========================================================
# CAPEX CLASSIFICATION
# =========================================================

def detect_capex(text):

    if reject_text(text):

        return (
            False,
            [],
            0,
            "REJECTED_GENERIC",
        )

    # -----------------------------------------------------
    # IMPORTANT:
    # Negative operational events must override positive
    # keyword matches.
    #
    # Example:
    # "Postponement of commercial production"
    # contains "commercial production", but is NOT
    # a positive CAPEX trigger.
    # -----------------------------------------------------

    negative_matches = (
        matched_phrases(
            text,
            CAPEX_NEGATIVE,
        )
    )

    if negative_matches:

        return (
            False,
            negative_matches,
            0,
            "REJECTED_NEGATIVE_EVENT",
        )

    very_strong = (
        matched_phrases(
            text,
            CAPEX_VERY_STRONG,
        )
    )

    if very_strong:

        return (
            True,
            very_strong[:6],
            100,
            "CAPACITY_EXPANSION",
        )

    operational = (
        matched_phrases(
            text,
            CAPEX_OPERATIONAL,
        )
    )

    if operational:

        return (
            True,
            operational[:6],
            90,
            "COMMISSIONING_OR_PRODUCTION",
        )

    medium = (
        matched_phrases(
            text,
            CAPEX_MEDIUM,
        )
    )

    context = (
        matched_phrases(
            text,
            CAPEX_CONTEXT,
        )
    )

    if (
        medium
        and context
    ):

        return (
            True,
            (
                medium[:3]
                +
                context[:3]
            ),
            75,
            "CAPEX_WITH_CONTEXT",
        )

    investment = (
        matched_phrases(
            text,
            CAPEX_INVESTMENT,
        )
    )

    if (
        investment
        and context
    ):

        return (
            True,
            (
                investment[:3]
                +
                context[:3]
            ),
            65,
            "INVESTMENT_WITH_CONTEXT",
        )

    return (
        False,
        [],
        0,
        "NO_CAPEX_EVENT",
    )


# =========================================================
# TAILWIND CLASSIFICATION
# =========================================================

def detect_tailwind(text):

    if reject_text(text):

        return (
            False,
            [],
            0,
        )

    matches = (
        matched_phrases(
            text,
            TAILWIND_STRONG,
        )
    )

    if not matches:

        return (
            False,
            [],
            0,
        )

    return (
        True,
        matches[:6],
        90,
    )


# =========================================================
# SOURCE
# =========================================================

def valid_source(source):

    source = clean(
        source
    )

    if not source:
        return False

    return source.startswith(
        (
            "https://",
            "http://",
        )
    )


# =========================================================
# BUILD REASON
# =========================================================

def build_reason(
    trigger_type,
    announcement,
    matches,
    event_class,
):

    subject = clean(
        announcement.get(
            "subject"
        )
    )

    description = clean(
        announcement.get(
            "description"
        )
    )

    if (
        subject
        and description
    ):

        filing_text = (
            f"{subject}: "
            f"{description}"
        )

    else:

        filing_text = (
            subject
            or description
            or announcement.get(
                "text",
                ""
            )
        )

    filing_text = clean(
        filing_text
    )

    if len(
        filing_text
    ) > 700:

        filing_text = (
            filing_text[:697]
            +
            "..."
        )

    if trigger_type == "capex":

        prefix = (
            "NSE filing indicates "
            "a possible company-specific "
            "CAPEX/expansion event."
        )

    else:

        prefix = (
            "NSE filing indicates "
            "a possible structural "
            "industry tailwind event."
        )

    matched = ", ".join(
        matches
    )

    return clean(
        f"{prefix} "
        f"Event class: {event_class}. "
        f"Matched: {matched}. "
        f"Filing: {filing_text}"
    )


# =========================================================
# CANDIDATE RECORD
# =========================================================

def candidate_record(
    trigger_type,
    announcement,
    matches,
    strength,
    event_class,
):

    source = clean(
        announcement.get(
            "source"
        )
    )

    if not valid_source(
        source
    ):
        return None

    return {
        "type":
            trigger_type,

        "eventClass":
            event_class,

        "evidenceStrength":
            strength,

        "reason":
            build_reason(
                trigger_type,
                announcement,
                matches,
                event_class,
            ),

        "subject":
            clean(
                announcement.get(
                    "subject"
                )
            ),

        "details":
            clean(
                announcement.get(
                    "description"
                )
            ),

        "source":
            source,

        "sourceDate":
            clean(
                announcement.get(
                    "sourceDate"
                )
            ),

        "matchedTerms":
            matches,

        "sourceType":
            "NSE_CORPORATE_ANNOUNCEMENT",

        "candidateStatus":
            "REVIEW_REQUIRED",

        "candidateBuilt":
            RUN_DATE,
    }


# =========================================================
# VERIFIED EVIDENCE PROTECTION
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

    if not isinstance(
        stock,
        dict,
    ):
        return False

    block = (
        stock.get(
            trigger_type,
            {}
        )
        or {}
    )

    if not isinstance(
        block,
        dict,
    ):
        return False

    reason = clean(
        block.get(
            "reason"
        )
    )

    source = clean(
        block.get(
            "source"
        )
    )

    return bool(
        reason
        and
        valid_source(
            source
        )
    )


# =========================================================
# DEDUPLICATION
# =========================================================

def candidate_identity(item):

    return (
        low(
            item.get(
                "source"
            )
        ),
        low(
            item.get(
                "details"
            )
        ),
    )


def dedupe_candidates(items):

    output = []
    seen = set()

    for item in items:

        if not isinstance(
            item,
            dict,
        ):
            continue

        key = (
            candidate_identity(
                item
            )
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        output.append(
            item
        )

    return output


# =========================================================
# BEST EVENT SELECTION
# =========================================================

def candidate_sort_key(item):

    strength = item.get(
        "evidenceStrength",
        0,
    )

    try:

        strength = int(
            strength
        )

    except Exception:

        strength = 0

    dt = parse_date(
        item.get(
            "sourceDate"
        )
    )

    if dt is None:

        timestamp = 0

    else:

        try:

            timestamp = (
                dt.timestamp()
            )

        except Exception:

            timestamp = 0

    # Stronger evidence first.
    # For same strength, latest first.
    return (
        strength,
        timestamp,
    )


def select_best_candidates(
    items,
    limit,
):

    items = dedupe_candidates(
        items
    )

    items.sort(
        key=candidate_sort_key,
        reverse=True,
    )

    return items[:limit]


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

        if not isinstance(
            row,
            dict,
        ):
            continue

        symbol = clean(
            row.get(
                "symbol"
            )
        ).upper()

        if not symbol:
            continue

        rows.append(
            {
                "symbol":
                    symbol,

                "name":
                    clean(
                        row.get(
                            "name"
                        )
                    ),

                "board":
                    clean(
                        row.get(
                            "board"
                        )
                    ),

                "changePct":
                    row.get(
                        "changePct"
                    ),

                "todayVolume":
                    row.get(
                        "todayVolume"
                    ),
            }
        )

    # -----------------------------------------------------
    # Active/moving stocks first.
    # This only controls request priority.
    # It does NOT decide evidence validity.
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
                float(
                    change
                )
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

    universe = (
        load_symbols()
    )

    session = (
        make_session()
    )

    stocks_out = {}

    symbols_scanned = 0
    announcements_seen = 0

    raw_capex_matches = 0
    raw_tailwind_matches = 0

    negative_capex_rejected = 0

    final_capex_candidates = 0
    final_tailwind_candidates = 0

    fetch_failures = 0

    print(
        "Evidence scan universe:",
        len(universe),
    )

    for index, stock in enumerate(
        universe,
        start=1,
    ):

        symbol = stock[
            "symbol"
        ]

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

        symbols_scanned += 1

        announcements_seen += len(
            announcements
        )

        capex_items = []
        tailwind_items = []

        capex_already_verified = (
            verified_exists(
                evidence_stocks,
                symbol,
                "capex",
            )
        )

        tailwind_already_verified = (
            verified_exists(
                evidence_stocks,
                symbol,
                "tailwind",
            )
        )

        for announcement in announcements:

            text = announcement.get(
                "text",
                "",
            )

            # =============================================
            # CAPEX
            # =============================================

            if not capex_already_verified:

                (
                    is_capex,
                    capex_matches,
                    capex_strength,
                    capex_event_class,
                ) = detect_capex(
                    text
                )

                if (
                    capex_event_class
                    ==
                    "REJECTED_NEGATIVE_EVENT"
                ):

                    negative_capex_rejected += 1

                if is_capex:

                    raw_capex_matches += 1

                    item = (
                        candidate_record(
                            "capex",
                            announcement,
                            capex_matches,
                            capex_strength,
                            capex_event_class,
                        )
                    )

                    if item is not None:

                        capex_items.append(
                            item
                        )

            # =============================================
            # TAILWIND
            # =============================================

            if not tailwind_already_verified:

                (
                    is_tailwind,
                    tailwind_matches,
                    tailwind_strength,
                ) = detect_tailwind(
                    text
                )

                if is_tailwind:

                    raw_tailwind_matches += 1

                    item = (
                        candidate_record(
                            "tailwind",
                            announcement,
                            tailwind_matches,
                            tailwind_strength,
                            "STRUCTURAL_TAILWIND",
                        )
                    )

                    if item is not None:

                        tailwind_items.append(
                            item
                        )

        # =================================================
        # KEEP ONLY BEST EVENT(S)
        # =================================================

        capex_items = (
            select_best_candidates(
                capex_items,
                MAX_CAPEX_EVENTS_PER_STOCK,
            )
        )

        tailwind_items = (
            select_best_candidates(
                tailwind_items,
                MAX_TAILWIND_EVENTS_PER_STOCK,
            )
        )

        if (
            capex_items
            or
            tailwind_items
        ):

            block = {
                "name":
                    stock.get(
                        "name"
                    ),

                "board":
                    stock.get(
                        "board"
                    ),
            }

            if capex_items:

                block[
                    "capex"
                ] = capex_items

                final_capex_candidates += len(
                    capex_items
                )

            if tailwind_items:

                block[
                    "tailwind"
                ] = tailwind_items

                final_tailwind_candidates += len(
                    tailwind_items
                )

            stocks_out[
                symbol
            ] = block

        if index % 50 == 0:

            print(
                f"Progress "
                f"{index}/"
                f"{len(universe)} | "
                f"CAPEX="
                f"{final_capex_candidates} | "
                f"Tailwind="
                f"{final_tailwind_candidates} | "
                f"Negative rejected="
                f"{negative_capex_rejected}"
            )

        time.sleep(
            REQUEST_DELAY
        )

    # =====================================================
    # RESULT
    # =====================================================

    result = {
        "_meta": {
            "description": (
                "NSE corporate-announcement "
                "evidence candidates for "
                "Big Move Scanner."
            ),

            "updated":
                RUN_DATE,

            "status":
                "REVIEW_REQUIRED",

            "lookbackDays":
                LOOKBACK_DAYS,

            "maxSymbolsPerRun":
                MAX_SYMBOLS_PER_RUN,

            "maxCapexEventsPerStock":
                MAX_CAPEX_EVENTS_PER_STOCK,

            "maxTailwindEventsPerStock":
                MAX_TAILWIND_EVENTS_PER_STOCK,

            "important": (
                "Candidates are NOT verified "
                "Big Move triggers. "
                "Review the NSE source filing "
                "before promoting evidence to "
                "company_evidence.json."
            ),

            "rules": {
                "capex": (
                    "Requires explicit "
                    "company-specific capacity, "
                    "plant, facility, commissioning "
                    "or production-expansion "
                    "evidence."
                ),

                "negativeCapex": (
                    "Postponed, delayed, deferred, "
                    "cancelled, suspended, shutdown, "
                    "closure and similar negative "
                    "events are rejected before "
                    "positive keyword matching."
                ),

                "deduplication": (
                    "Repeated filings are reduced "
                    "to the strongest/latest useful "
                    "candidate for each company."
                ),

                "tailwind": (
                    "Requires an explicit structural "
                    "driver such as PLI, import "
                    "substitution, localisation, "
                    "China+1, policy or regulatory "
                    "change."
                ),

                "scoreRule": (
                    "CAPEX score or Tailwind score "
                    "alone does NOT create a "
                    "Big Move trigger."
                ),
            },

            "counts": {
                "symbolsScanned":
                    symbols_scanned,

                "announcementsSeen":
                    announcements_seen,

                "rawCapexMatches":
                    raw_capex_matches,

                "negativeCapexRejected":
                    negative_capex_rejected,

                "rawTailwindMatches":
                    raw_tailwind_matches,

                "symbolsWithCandidates":
                    len(
                        stocks_out
                    ),

                "capexCandidates":
                    final_capex_candidates,

                "tailwindCandidates":
                    final_tailwind_candidates,

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

        # =================================================
        # FAIL-SAFE
        #
        # Evidence collection must never destroy the
        # normal daily market-data workflow.
        # =================================================

        print(
            "Company evidence "
            "collector warning:",
            exc,
        )

        result = {
            "_meta": {
                "description": (
                    "NSE corporate-announcement "
                    "evidence candidate scan."
                ),

                "updated":
                    RUN_DATE,

                "status":
                    "FETCH_FAILED_SAFE",

                "error":
                    clean(
                        exc
                    ),

                "important": (
                    "Normal market-data workflow "
                    "may continue. "
                    "company_evidence.json was "
                    "not modified."
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
        "Evidence candidate "
        "build complete."
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
        "IMPORTANT: "
        "company_evidence.json "
        "was NOT modified."
    )


if __name__ == "__main__":
    main()
