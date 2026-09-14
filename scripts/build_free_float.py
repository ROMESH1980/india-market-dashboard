import json
import math
import re
import threading
import time
import xml.etree.ElementTree as ET

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

STOCKS_PATH = DATA_DIR / "stocks.json"
CACHE_PATH = DATA_DIR / "free_float_cache.json"


# =========================================================
# NSE CONFIG
# =========================================================

BASE_URL = "https://www.nseindia.com"

API_URL = (
    BASE_URL
    +
    "/api/corporate-share-holdings-master"
)


MAX_WORKERS = 8

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 12

MAX_RETRIES = 2
RETRY_DELAY = 0.70

READY_CACHE_DAYS = 100
PENDING_CACHE_DAYS = 1

SAVE_EVERY = 50


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    ),

    "Accept":
        "application/json,text/plain,*/*",

    "Accept-Language":
        "en-US,en;q=0.9",

    "Referer":
        (
            "https://www.nseindia.com/"
            "companies-listing/"
            "corporate-filings-shareholding-pattern"
        ),

    "Connection":
        "keep-alive",
}


# =========================================================
# THREAD LOCAL SESSION
# =========================================================

_thread_local = threading.local()


def get_session():

    session = getattr(
        _thread_local,
        "session",
        None,
    )

    if session is not None:
        return session

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    try:

        session.get(
            (
                BASE_URL
                +
                "/companies-listing/"
                "corporate-filings-shareholding-pattern"
            ),
            timeout=(
                CONNECT_TIMEOUT,
                READ_TIMEOUT,
            ),
        )

    except Exception:
        pass

    _thread_local.session = session

    return session


def reset_session():

    session = getattr(
        _thread_local,
        "session",
        None,
    )

    if session is not None:

        try:
            session.close()
        except Exception:
            pass

    _thread_local.session = None


# =========================================================
# JSON
# =========================================================

def load_json(
    path,
    default,
):

    try:

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        return default


def save_json(
    path,
    data,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp = path.with_suffix(
        path.suffix + ".tmp"
    )

    temp.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temp.replace(
        path
    )


# =========================================================
# BASIC HELPERS
# =========================================================

def clean_text(
    value,
):

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def normalize_key(
    value,
):

    return re.sub(
        r"[^a-z0-9]",
        "",
        clean_text(
            value
        ).lower(),
    )


def safe_float(
    value,
):

    if value is None:
        return None

    if isinstance(
        value,
        str,
    ):

        value = (
            value
            .replace(",", "")
            .replace("%", "")
            .replace("₹", "")
            .strip()
        )

        if not value:
            return None

        if value.lower() in {
            "-",
            "—",
            "na",
            "n/a",
            "none",
            "null",
            "nan",
            "pending",
        }:
            return None

    try:

        result = float(
            value
        )

        if not math.isfinite(
            result
        ):
            return None

        return result

    except Exception:

        return None


def safe_int(
    value,
):

    result = safe_float(
        value
    )

    if result is None:
        return None

    return int(
        round(
            result
        )
    )


def utc_now():

    return (
        datetime.now(
            timezone.utc
        )
        .replace(
            microsecond=0
        )
        .isoformat()
    )


# =========================================================
# PAYLOAD
# =========================================================

def normalize_stock_payload(
    payload,
):

    if isinstance(
        payload,
        list,
    ):

        return (
            payload,
            None,
        )

    if isinstance(
        payload,
        dict,
    ):

        for key in (
            "stocks",
            "rows",
            "data",
        ):

            value = payload.get(
                key
            )

            if isinstance(
                value,
                list,
            ):

                return (
                    value,
                    key,
                )

    raise RuntimeError(
        "stocks.json must be a list or contain "
        "stocks / rows / data list"
    )


# =========================================================
# CACHE
# =========================================================

def cache_age_days(
    entry,
):

    if not isinstance(
        entry,
        dict,
    ):

        return None

    cached_at = entry.get(
        "cachedAt"
    )

    if not cached_at:
        return None

    try:

        timestamp = datetime.fromisoformat(
            str(
                cached_at
            ).replace(
                "Z",
                "+00:00",
            )
        )

        if timestamp.tzinfo is None:

            timestamp = timestamp.replace(
                tzinfo=timezone.utc
            )

        return (
            datetime.now(
                timezone.utc
            )
            -
            timestamp
        ).total_seconds() / 86400

    except Exception:

        return None


def cache_fresh(
    entry,
):

    age = cache_age_days(
        entry
    )

    if age is None:
        return False

    status = clean_text(
        entry.get(
            "status"
        )
    ).upper()

    if status == "READY":

        return (
            age <=
            READY_CACHE_DAYS
        )

    if status == "PENDING":

        return (
            age <=
            PENDING_CACHE_DAYS
        )

    return False


# =========================================================
# HTTP
# =========================================================

def request_json(
    url,
    params=None,
):

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        session = get_session()

        try:

            response = session.get(
                url,
                params=params,
                timeout=(
                    CONNECT_TIMEOUT,
                    READ_TIMEOUT,
                ),
            )

            if response.status_code in {
                401,
                403,
                429,
            }:

                raise RuntimeError(
                    f"HTTP {response.status_code}"
                )

            response.raise_for_status()

            return response.json()

        except Exception as exc:

            last_error = exc

            reset_session()

            if attempt < MAX_RETRIES:

                time.sleep(
                    RETRY_DELAY
                    *
                    attempt
                )

    raise RuntimeError(
        str(
            last_error
        )
    )


def request_bytes(
    url,
):

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        session = get_session()

        try:

            response = session.get(
                url,
                timeout=(
                    CONNECT_TIMEOUT,
                    READ_TIMEOUT,
                ),
            )

            if response.status_code in {
                401,
                403,
                429,
            }:

                raise RuntimeError(
                    f"HTTP {response.status_code}"
                )

            response.raise_for_status()

            return response.content

        except Exception as exc:

            last_error = exc

            reset_session()

            if attempt < MAX_RETRIES:

                time.sleep(
                    RETRY_DELAY
                    *
                    attempt
                )

    raise RuntimeError(
        str(
            last_error
        )
    )


# =========================================================
# BOARD / INDEX
# =========================================================

def preferred_indexes(
    stock,
):

    board = clean_text(
        stock.get(
            "board"
        )
    ).lower()

    series = clean_text(
        stock.get(
            "series"
        )
    ).lower()

    if (
        "sme"
        in board
        or
        series in {
            "sm",
            "st",
        }
    ):

        return [
            "sme",
            "equities",
        ]

    return [
        "equities",
        "sme",
    ]


# =========================================================
# API RESPONSE ROW EXTRACTION
# =========================================================

def collect_dict_rows(
    value,
):

    rows = []

    if isinstance(
        value,
        list,
    ):

        for item in value:

            if isinstance(
                item,
                dict,
            ):

                rows.append(
                    item
                )

                rows.extend(
                    collect_dict_rows(
                        item
                    )
                )

            elif isinstance(
                item,
                list,
            ):

                rows.extend(
                    collect_dict_rows(
                        item
                    )
                )

    elif isinstance(
        value,
        dict,
    ):

        for child in value.values():

            if isinstance(
                child,
                dict,
            ):

                rows.append(
                    child
                )

                rows.extend(
                    collect_dict_rows(
                        child
                    )
                )

            elif isinstance(
                child,
                list,
            ):

                rows.extend(
                    collect_dict_rows(
                        child
                    )
                )

    return rows


def fuzzy_value(
    row,
    candidates,
):

    if not isinstance(
        row,
        dict,
    ):

        return None

    normalized = {
        normalize_key(
            key
        ):
            value

        for key, value
        in row.items()
    }

    # exact normalized match
    for candidate in candidates:

        key = normalize_key(
            candidate
        )

        if key in normalized:

            return normalized[
                key
            ]

    # substring match
    for candidate in candidates:

        target = normalize_key(
            candidate
        )

        for key, value in normalized.items():

            if (
                target in key
                or
                key in target
            ):

                return value

    return None


# =========================================================
# DATE
# =========================================================

def parse_date(
    value,
):

    text = clean_text(
        value
    )

    if not text:
        return None

    formats = (
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d %b %Y",
        "%d %B %Y",
    )

    for fmt in formats:

        try:

            return datetime.strptime(
                text,
                fmt,
            )

        except Exception:

            pass

    return None


# =========================================================
# IDENTIFY API FILING ROW
# =========================================================

def normalize_api_filing(
    row,
    expected_symbol,
):

    symbol = clean_text(
        fuzzy_value(
            row,
            (
                "symbol",
                "nseSymbol",
                "companySymbol",
            ),
        )
    ).upper()

    company = clean_text(
        fuzzy_value(
            row,
            (
                "company",
                "companyName",
                "name",
            ),
        )
    )

    public_pct = safe_float(
        fuzzy_value(
            row,
            (
                "public",
                "publicPct",
                "publicPercentage",
                "publicShareholding",
                "publicShareholdingPercentage",
                "publicHolding",
                "publicHoldingPct",
            ),
        )
    )

    promoter_pct = safe_float(
        fuzzy_value(
            row,
            (
                "promoter",
                "promoterPct",
                "promoterGroup",
                "promoterGroupPct",
                "promoterPercentage",
            ),
        )
    )

    employee_pct = safe_float(
        fuzzy_value(
            row,
            (
                "employeeTrust",
                "employeeTrustPct",
                "employeeTrustPercentage",
                "sharesHeldByEmployeeTrusts",
            ),
        )
    )

    as_on = clean_text(
        fuzzy_value(
            row,
            (
                "asOnDate",
                "ason",
                "date",
                "shareholdingDate",
            ),
        )
    )

    submission = clean_text(
        fuzzy_value(
            row,
            (
                "submissionDate",
                "submittedDate",
            ),
        )
    )

    broadcast = clean_text(
        fuzzy_value(
            row,
            (
                "broadcastDate",
                "broadcastDateTime",
                "broadcastDatetime",
            ),
        )
    )

    xbrl = clean_text(
        fuzzy_value(
            row,
            (
                "xbrl",
                "xbrlUrl",
                "xbrlFile",
                "xbrlFileLink",
                "xbrlLink",
                "fileUrl",
                "attachment",
            ),
        )
    )

    if (
        expected_symbol
        and
        symbol
        and
        symbol != expected_symbol
    ):

        return None

    if (
        public_pct is None
        and
        not xbrl
        and
        not as_on
    ):

        return None

    return {
        "symbol":
            symbol
            or
            expected_symbol,

        "company":
            company,

        "publicPct":
            public_pct,

        "promoterPct":
            promoter_pct,

        "employeeTrustPct":
            employee_pct,

        "asOnDate":
            as_on,

        "submissionDate":
            submission,

        "broadcastDate":
            broadcast,

        "xbrlUrl":
            xbrl,

        "_date":
            parse_date(
                as_on
            ),
    }


def choose_latest_filing(
    payload,
    symbol,
):

    raw_rows = []

    if isinstance(
        payload,
        list,
    ):

        raw_rows.extend(
            item
            for item in payload
            if isinstance(
                item,
                dict,
            )
        )

    elif isinstance(
        payload,
        dict,
    ):

        raw_rows.append(
            payload
        )

        raw_rows.extend(
            collect_dict_rows(
                payload
            )
        )

    filings = []

    for row in raw_rows:

        filing = normalize_api_filing(
            row,
            symbol,
        )

        if filing is not None:

            filings.append(
                filing
            )

    if not filings:

        return None

    dated = [
        filing
        for filing in filings
        if filing[
            "_date"
        ]
        is not None
    ]

    if dated:

        dated.sort(
            key=lambda item:
                item[
                    "_date"
                ],
            reverse=True,
        )

        return dated[
            0
        ]

    return filings[
        0
    ]


# =========================================================
# XBRL URL
# =========================================================

def normalize_xbrl_url(
    value,
):

    url = clean_text(
        value
    )

    if not url:
        return None

    # Sometimes response can contain HTML anchor
    href_match = re.search(
        r"""href=["']([^"']+)["']""",
        url,
        flags=re.IGNORECASE,
    )

    if href_match:

        url = href_match.group(
            1
        )

    # Sometimes filename/path is embedded in text.
    xml_match = re.search(
        r"""(https?://[^\s"'<>]+\.xml(?:\?[^\s"'<>]*)?)""",
        url,
        flags=re.IGNORECASE,
    )

    if xml_match:

        url = xml_match.group(
            1
        )

    elif ".xml" in url.lower():

        match = re.search(
            r"""([^\s"'<>]+\.xml(?:\?[^\s"'<>]*)?)""",
            url,
            flags=re.IGNORECASE,
        )

        if match:

            url = match.group(
                1
            )

    if url.startswith(
        "//"
    ):

        return (
            "https:"
            +
            url
        )

    return urljoin(
        BASE_URL,
        url,
    )


# =========================================================
# XML HELPERS
# =========================================================

def local_name(
    tag,
):

    if "}" in tag:

        return tag.split(
            "}",
            1,
        )[
            1
        ]

    if ":" in tag:

        return tag.split(
            ":",
            1,
        )[
            1
        ]

    return tag


def normalized_concept(
    text,
):

    return re.sub(
        r"[^a-z0-9]",
        "",
        clean_text(
            text
        ).lower(),
    )


# =========================================================
# XBRL CONTEXT MAP
# =========================================================

def build_context_map(
    root,
):

    contexts = {}

    for element in root.iter():

        if local_name(
            element.tag
        ).lower() != "context":

            continue

        context_id = element.attrib.get(
            "id"
        )

        if not context_id:
            continue

        text_parts = []

        for child in element.iter():

            child_name = local_name(
                child.tag
            )

            child_text = clean_text(
                child.text
            )

            if child_text:

                text_parts.append(
                    child_name
                    +
                    "="
                    +
                    child_text
                )

            for attr_value in child.attrib.values():

                if attr_value:

                    text_parts.append(
                        clean_text(
                            attr_value
                        )
                    )

        contexts[
            context_id
        ] = normalized_concept(
            " ".join(
                text_parts
            )
        )

    return contexts


# =========================================================
# XBRL FACT COLLECTION
# =========================================================

def collect_facts(
    root,
    contexts,
):

    facts = []

    for element in root.iter():

        context_ref = element.attrib.get(
            "contextRef"
        )

        if not context_ref:
            continue

        value = safe_float(
            element.text
        )

        if value is None:
            continue

        concept = normalized_concept(
            local_name(
                element.tag
            )
        )

        context = contexts.get(
            context_ref,
            "",
        )

        facts.append(
            {
                "concept":
                    concept,

                "context":
                    context,

                "value":
                    value,
            }
        )

    return facts


# =========================================================
# FACT SCORING
# =========================================================

def public_context_score(
    context,
):

    score = 0

    if "public" in context:
        score += 10

    if "publicshareholder" in context:
        score += 15

    if "promoter" in context:
        score -= 20

    if "nonpromoter" in context:
        score -= 8

    if "employeetrust" in context:
        score -= 10

    return score


def shares_concept_score(
    concept,
):

    score = 0

    if "sharesheld" in concept:
        score += 10

    if "numberofsharesheld" in concept:
        score += 15

    if "totalnumberofsharesheld" in concept:
        score += 25

    if "totalnosharesheld" in concept:
        score += 25

    if "totalsharesheld" in concept:
        score += 22

    if "percentage" in concept:
        score -= 30

    if "percent" in concept:
        score -= 30

    if "locked" in concept:
        score -= 40

    if "pledged" in concept:
        score -= 40

    return score


def locked_concept_score(
    concept,
):

    score = 0

    if "locked" in concept:
        score += 25

    if "shares" in concept:
        score += 10

    if "number" in concept:
        score += 5

    if "percentage" in concept:
        score -= 25

    if "percent" in concept:
        score -= 25

    return score


# =========================================================
# XBRL EXTRACTION
# =========================================================

def parse_xbrl(
    content,
):

    try:

        root = ET.fromstring(
            content
        )

    except Exception as exc:

        raise RuntimeError(
            "Invalid XBRL/XML: "
            +
            str(exc)
        )

    contexts = build_context_map(
        root
    )

    facts = collect_facts(
        root,
        contexts,
    )

    public_candidates = []

    locked_candidates = []

    for fact in facts:

        context_score = public_context_score(
            fact[
                "context"
            ]
        )

        share_score = shares_concept_score(
            fact[
                "concept"
            ]
        )

        locked_score = locked_concept_score(
            fact[
                "concept"
            ]
        )

        public_total_score = (
            context_score
            +
            share_score
        )

        if (
            public_total_score >= 20
            and
            fact[
                "value"
            ] > 0
        ):

            public_candidates.append(
                (
                    public_total_score,
                    fact,
                )
            )

        total_locked_score = (
            context_score
            +
            locked_score
        )

        if (
            total_locked_score >= 20
            and
            fact[
                "value"
            ] >= 0
        ):

            locked_candidates.append(
                (
                    total_locked_score,
                    fact,
                )
            )

    if not public_candidates:

        return {
            "publicShares":
                None,

            "lockedPublicShares":
                None,
        }

    public_candidates.sort(
        key=lambda item:
            (
                item[
                    0
                ],
                item[
                    1
                ][
                    "value"
                ],
            ),
        reverse=True,
    )

    public_shares = safe_int(
        public_candidates[
            0
        ][
            1
        ][
            "value"
        ]
    )

    locked_shares = 0

    if locked_candidates:

        locked_candidates.sort(
            key=lambda item:
                (
                    item[
                        0
                    ],
                    item[
                        1
                    ][
                        "value"
                    ],
                ),
            reverse=True,
        )

        locked_shares = safe_int(
            locked_candidates[
                0
            ][
                1
            ][
                "value"
            ]
        )

        if locked_shares is None:

            locked_shares = 0

    if (
        public_shares is not None
        and
        locked_shares >
        public_shares
    ):

        locked_shares = 0

    return {
        "publicShares":
            public_shares,

        "lockedPublicShares":
            locked_shares,
    }


# =========================================================
# FETCH NSE FILING
# =========================================================

def get_latest_filing(
    stock,
):

    symbol = clean_text(
        stock.get(
            "symbol"
        )
    ).upper()

    if not symbol:

        return None

    errors = []

    for index_name in preferred_indexes(
        stock
    ):

        try:

            payload = request_json(
                API_URL,
                params={
                    "index":
                        index_name,

                    "symbol":
                        symbol,
                },
            )

        except Exception as exc:

            errors.append(
                (
                    index_name
                    +
                    ": "
                    +
                    str(exc)
                )
            )

            continue

        filing = choose_latest_filing(
            payload,
            symbol,
        )

        if filing is not None:

            filing[
                "index"
            ] = index_name

            return filing

    if errors:

        raise RuntimeError(
            " | ".join(
                errors
            )
        )

    return None


# =========================================================
# FETCH ONE STOCK
# =========================================================

def fetch_one_stock(
    stock,
):

    symbol = clean_text(
        stock.get(
            "symbol"
        )
    ).upper()

    if not symbol:

        return (
            symbol,
            {
                "status":
                    "PENDING",

                "reason":
                    "Missing symbol",

                "cachedAt":
                    utc_now(),

                "freeFloatEstimated":
                    False,
            },
        )

    try:

        filing = get_latest_filing(
            stock
        )

    except Exception as exc:

        return (
            symbol,
            {
                "status":
                    "PENDING",

                "reason":
                    "API: "
                    +
                    str(exc),

                "cachedAt":
                    utc_now(),

                "freeFloatEstimated":
                    False,
            },
        )

    if filing is None:

        return (
            symbol,
            {
                "status":
                    "PENDING",

                "reason":
                    "No NSE shareholding filing returned",

                "cachedAt":
                    utc_now(),

                "freeFloatEstimated":
                    False,
            },
        )

    public_pct = filing.get(
        "publicPct"
    )

    xbrl_url = normalize_xbrl_url(
        filing.get(
            "xbrlUrl"
        )
    )

    if not xbrl_url:

        return (
            symbol,
            {
                "status":
                    "PENDING",

                "publicHoldingPct":
                    public_pct,

                "freeFloatPct":
                    public_pct,

                "freeFloatDate":
                    filing.get(
                        "asOnDate"
                    ),

                "reason":
                    "NSE filing found but XBRL URL missing",

                "freeFloatSource":
                    "NSE Corporate Share Holdings API",

                "freeFloatEstimated":
                    False,

                "cachedAt":
                    utc_now(),
            },
        )

    try:

        content = request_bytes(
            xbrl_url
        )

    except Exception as exc:

        return (
            symbol,
            {
                "status":
                    "PENDING",

                "publicHoldingPct":
                    public_pct,

                "freeFloatPct":
                    public_pct,

                "freeFloatDate":
                    filing.get(
                        "asOnDate"
                    ),

                "freeFloatSource":
                    "NSE Corporate Share Holdings API",

                "freeFloatSourceUrl":
                    xbrl_url,

                "reason":
                    "XBRL download failed: "
                    +
                    str(exc),

                "freeFloatEstimated":
                    False,

                "cachedAt":
                    utc_now(),
            },
        )

    try:

        xbrl_values = parse_xbrl(
            content
        )

    except Exception as exc:

        return (
            symbol,
            {
                "status":
                    "PENDING",

                "publicHoldingPct":
                    public_pct,

                "freeFloatPct":
                    public_pct,

                "freeFloatDate":
                    filing.get(
                        "asOnDate"
                    ),

                "freeFloatSource":
                    "NSE Corporate Share Holdings API + XBRL",

                "freeFloatSourceUrl":
                    xbrl_url,

                "reason":
                    "XBRL parse failed: "
                    +
                    str(exc),

                "freeFloatEstimated":
                    False,

                "cachedAt":
                    utc_now(),
            },
        )

    public_shares = xbrl_values.get(
        "publicShares"
    )

    locked_shares = (
        xbrl_values.get(
            "lockedPublicShares"
        )
        or
        0
    )

    if (
        public_shares is None
        or
        public_shares <= 0
    ):

        return (
            symbol,
            {
                "status":
                    "PENDING",

                "publicHoldingPct":
                    public_pct,

                "freeFloatPct":
                    public_pct,

                "freeFloatDate":
                    filing.get(
                        "asOnDate"
                    ),

                "freeFloatSource":
                    "NSE Corporate Share Holdings API + XBRL",

                "freeFloatSourceUrl":
                    xbrl_url,

                "reason":
                    "Exact Public Shares fact not found in XBRL",

                "freeFloatEstimated":
                    False,

                "cachedAt":
                    utc_now(),
            },
        )

    if (
        locked_shares < 0
        or
        locked_shares >
        public_shares
    ):

        locked_shares = 0

    free_float_shares = (
        public_shares
        -
        locked_shares
    )

    if free_float_shares <= 0:

        return (
            symbol,
            {
                "status":
                    "PENDING",

                "reason":
                    "Invalid tradable public share result",

                "cachedAt":
                    utc_now(),

                "freeFloatEstimated":
                    False,
            },
        )

    free_float_pct = None

    if (
        public_pct is not None
        and
        public_shares > 0
    ):

        free_float_pct = (
            public_pct
            *
            (
                free_float_shares
                /
                public_shares
            )
        )

    result = {
        "status":
            "READY",

        "publicShares":
            public_shares,

        "publicHoldingPct":
            (
                round(
                    public_pct,
                    4,
                )
                if public_pct is not None
                else None
            ),

        "publicLockedShares":
            locked_shares,

        "freeFloatShares":
            free_float_shares,

        "freeFloatPct":
            (
                round(
                    free_float_pct,
                    4,
                )
                if free_float_pct is not None
                else None
            ),

        "freeFloatDate":
            filing.get(
                "asOnDate"
            ),

        "freeFloatSubmissionDate":
            filing.get(
                "submissionDate"
            ),

        "freeFloatSource":
            "NSE Corporate Share Holdings API + XBRL",

        "freeFloatSourceUrl":
            xbrl_url,

        "freeFloatMethod":
            (
                "Exact Public Shares less "
                "Locked-in Public Shares"
            ),

        "freeFloatMethodologyNote":
            (
                "Filing-derived tradable public shares proxy. "
                "Not the NSE Indices official free-float factor."
            ),

        "freeFloatEstimated":
            False,

        "cachedAt":
            utc_now(),
    }

    return (
        symbol,
        result,
    )


# =========================================================
# APPLY RESULT
# =========================================================

FREE_FLOAT_FIELDS = (
    "publicShares",
    "publicHoldingPct",
    "publicLockedShares",
    "freeFloatShares",
    "freeFloatPct",
    "freeFloatDate",
    "freeFloatSubmissionDate",
    "freeFloatSource",
    "freeFloatSourceUrl",
    "freeFloatMethod",
    "freeFloatMethodologyNote",
    "freeFloatEstimated",
)


def apply_result(
    stock,
    result,
):

    status = clean_text(
        result.get(
            "status",
            "PENDING",
        )
    ).upper()

    stock[
        "freeFloatStatus"
    ] = status

    for field in FREE_FLOAT_FIELDS:

        if field in result:

            stock[
                field
            ] = result.get(
                field
            )

        elif status != "READY":

            if field == "freeFloatEstimated":

                stock[
                    field
                ] = False

            else:

                stock[
                    field
                ] = None

    if status == "READY":

        stock.pop(
            "freeFloatReason",
            None,
        )

    else:

        stock[
            "freeFloatReason"
        ] = result.get(
            "reason"
        )


# =========================================================
# MAIN
# =========================================================

def main():

    start_time = time.time()

    print(
        "==============================================",
        flush=True,
    )

    print(
        "BUILD FREE FLOAT - NSE API + XBRL",
        flush=True,
    )

    print(
        "==============================================",
        flush=True,
    )

    print(
        f"Workers: {MAX_WORKERS}",
        flush=True,
    )

    print(
        "No Market Cap / Price estimation.",
        flush=True,
    )

    print()

    payload = load_json(
        STOCKS_PATH,
        None,
    )

    if payload is None:

        raise RuntimeError(
            "data/stocks.json missing or invalid"
        )

    stocks, list_key = normalize_stock_payload(
        payload
    )

    cache = load_json(
        CACHE_PATH,
        {},
    )

    if not isinstance(
        cache,
        dict,
    ):

        cache = {}

    symbol_map = {}

    for stock in stocks:

        if not isinstance(
            stock,
            dict,
        ):
            continue

        symbol = clean_text(
            stock.get(
                "symbol"
            )
        ).upper()

        if symbol:

            symbol_map[
                symbol
            ] = stock

    stats = {
        "stocks":
            len(
                symbol_map
            ),

        "cacheUsed":
            0,

        "fetched":
            0,

        "ready":
            0,

        "pending":
            0,

        "errors":
            0,
    }

    to_fetch = []

    # =====================================================
    # CACHE
    # =====================================================

    for symbol, stock in symbol_map.items():

        cached = cache.get(
            symbol
        )

        if cache_fresh(
            cached
        ):

            apply_result(
                stock,
                cached,
            )

            stats[
                "cacheUsed"
            ] += 1

            if (
                clean_text(
                    cached.get(
                        "status"
                    )
                ).upper()
                ==
                "READY"
            ):

                stats[
                    "ready"
                ] += 1

            else:

                stats[
                    "pending"
                ] += 1

        else:

            to_fetch.append(
                stock
            )

    print(
        f"Universe    : {stats['stocks']}",
        flush=True,
    )

    print(
        f"Fresh cache : {stats['cacheUsed']}",
        flush=True,
    )

    print(
        f"Need fetch  : {len(to_fetch)}",
        flush=True,
    )

    print()

    # =====================================================
    # FETCH
    # =====================================================

    completed = 0

    reason_counts = {}

    if to_fetch:

        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS
        ) as executor:

            futures = {}

            for stock in to_fetch:

                symbol = clean_text(
                    stock.get(
                        "symbol"
                    )
                ).upper()

                future = executor.submit(
                    fetch_one_stock,
                    stock,
                )

                futures[
                    future
                ] = symbol

            for future in as_completed(
                futures
            ):

                fallback_symbol = futures[
                    future
                ]

                completed += 1

                try:

                    symbol, result = future.result()

                    if not symbol:

                        symbol = fallback_symbol

                except Exception as exc:

                    symbol = fallback_symbol

                    result = {
                        "status":
                            "PENDING",

                        "reason":
                            "Worker error: "
                            +
                            str(exc),

                        "freeFloatEstimated":
                            False,

                        "cachedAt":
                            utc_now(),
                    }

                    stats[
                        "errors"
                    ] += 1

                cache[
                    symbol
                ] = result

                stock = symbol_map.get(
                    symbol
                )

                if stock is not None:

                    apply_result(
                        stock,
                        result,
                    )

                stats[
                    "fetched"
                ] += 1

                status = clean_text(
                    result.get(
                        "status"
                    )
                ).upper()

                if status == "READY":

                    stats[
                        "ready"
                    ] += 1

                else:

                    stats[
                        "pending"
                    ] += 1

                    reason = clean_text(
                        result.get(
                            "reason"
                        )
                    )

                    if reason:

                        short_reason = reason[
                            :120
                        ]

                        reason_counts[
                            short_reason
                        ] = (
                            reason_counts.get(
                                short_reason,
                                0,
                            )
                            +
                            1
                        )

                if (
                    completed <= 10
                    or
                    completed % 25 == 0
                    or
                    completed
                    ==
                    len(
                        to_fetch
                    )
                ):

                    elapsed = (
                        time.time()
                        -
                        start_time
                    )

                    rate = (
                        completed
                        /
                        elapsed
                        if elapsed > 0
                        else 0
                    )

                    print(
                        f"[{completed}/{len(to_fetch)}] "
                        f"ready={stats['ready']} "
                        f"pending={stats['pending']} "
                        f"errors={stats['errors']} "
                        f"rate={rate:.2f}/sec",
                        flush=True,
                    )

                    # Useful diagnostic for first 10.
                    if (
                        completed <= 10
                        and
                        status != "READY"
                    ):

                        print(
                            f"  {symbol}: "
                            f"{result.get('reason')}",
                            flush=True,
                        )

                if (
                    completed % SAVE_EVERY
                    ==
                    0
                ):

                    save_json(
                        CACHE_PATH,
                        cache,
                    )

    # =====================================================
    # SAVE
    # =====================================================

    save_json(
        CACHE_PATH,
        cache,
    )

    if list_key is None:

        output_payload = stocks

    else:

        payload[
            list_key
        ] = stocks

        output_payload = payload

    save_json(
        STOCKS_PATH,
        output_payload,
    )

    # =====================================================
    # SUMMARY
    # =====================================================

    total = stats[
        "stocks"
    ]

    coverage = (
        round(
            stats[
                "ready"
            ]
            /
            total
            *
            100,
            2,
        )
        if total
        else 0
    )

    elapsed = (
        time.time()
        -
        start_time
    )

    print()
    print(
        "==============================================",
        flush=True,
    )

    print(
        "FREE FLOAT SUMMARY",
        flush=True,
    )

    print(
        "==============================================",
        flush=True,
    )

    print(
        json.dumps(
            {
                **stats,

                "coveragePct":
                    coverage,

                "elapsedSeconds":
                    round(
                        elapsed,
                        2,
                    ),

                "elapsedMinutes":
                    round(
                        elapsed / 60,
                        2,
                    ),

                "workers":
                    MAX_WORKERS,
            },
            indent=2,
        ),
        flush=True,
    )

    if reason_counts:

        print()
        print(
            "TOP PENDING REASONS",
            flush=True,
        )

        for reason, count in sorted(
            reason_counts.items(),
            key=lambda item:
                item[
                    1
                ],
            reverse=True,
        )[:10]:

            print(
                f"{count:5d}  {reason}",
                flush=True,
            )

    print()
    print(
        "Method:",
        flush=True,
    )

    print(
        "Free Float Shares = "
        "Exact Public Shares - Locked-in Public Shares",
        flush=True,
    )

    print(
        "Free Float % = Public Holding % adjusted "
        "for locked public shares",
        flush=True,
    )

    print(
        "Source = NSE corporate-share-holdings-master "
        "+ official filing XBRL",
        flush=True,
    )

    print(
        "No Market Cap / Price estimation is used.",
        flush=True,
    )

    print(
        "This is a filing-derived tradable public float proxy, "
        "not the NSE Indices official free-float factor.",
        flush=True,
    )

    print(
        "==============================================",
        flush=True,
    )


if __name__ == "__main__":
    main()
