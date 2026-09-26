import json
import re
from pathlib import Path
from datetime import datetime, timezone


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

STOCKS_PATH = DATA_DIR / "stocks.json"
RESEARCH_PATH = DATA_DIR / "company_research.json"
EVIDENCE_PATH = DATA_DIR / "company_evidence.json"

CANDIDATES_PATH = (
    DATA_DIR / "company_evidence_candidates.json"
)


RUN_DATE = (
    datetime.now(timezone.utc)
    .date()
    .isoformat()
)


# =========================================================
# SETTINGS
# =========================================================

CAPEX_KEYWORDS = [
    "capacity expansion",
    "capacity addition",
    "capacity enhancement",
    "capacity increase",
    "expanding capacity",
    "expanded capacity",

    "new plant",
    "new manufacturing plant",
    "new manufacturing facility",
    "new facility",
    "new unit",
    "new production unit",

    "greenfield",
    "brownfield",

    "commissioned",
    "commissioning",
    "commercial production",
    "commenced production",
    "commencement of production",
    "production commenced",

    "new production line",
    "new manufacturing line",
    "additional production line",

    "plant expansion",
    "facility expansion",
    "manufacturing expansion",

    "capital expenditure",
    "capex programme",
    "capex program",

    "setting up",
    "set up a plant",
    "setting up a plant",

    "installed capacity",
    "production capacity",

    "investment in capacity",
    "investment in plant",
    "investment in facility",
]


TAILWIND_KEYWORDS = [
    "import substitution",
    "localisation",
    "localization",
    "indigenisation",
    "indigenization",

    "china+1",
    "china plus one",
    "supply chain diversification",

    "government policy",
    "government scheme",
    "government incentive",

    "production linked incentive",
    "pli scheme",

    "regulatory change",
    "regulatory reform",

    "industry demand",
    "demand growth",
    "structural demand",

    "industry growth",
    "market growth",

    "electrification",
    "energy transition",

    "grid expansion",
    "transmission investment",

    "renewable capacity",
    "renewable energy",

    "defence localisation",
    "domestic procurement",

    "railway modernisation",
    "infrastructure spending",

    "semiconductor",
    "electronics localisation",

    "data centre",
    "data center",
    "cloud adoption",
    "ai infrastructure",

    "formalisation",
    "financialisation",

    "premiumisation",

    "export opportunity",
    "export demand",

    "technology transition",
]


# =========================================================
# INVALID / LOW-QUALITY EVIDENCE
# =========================================================

INVALID_SOURCE_PATTERNS = [
    "methodology.html",
    "#capex",
    "#tailwind",
    "#future-growth",
    "#fundamental",
]


INVALID_REASON_PATTERNS = [
    "too many requests",
    "rate limited",
    "rate limit",
    "failed",
    "error",
    "unavailable",
    "insufficient data",
    "proxy unavailable",
]


GENERIC_CAPEX_PATTERNS = [
    "capital expenditure is",
    "operating cash flow",
    "capex detected",
]


GENERIC_TAILWIND_PATTERNS = [
    "automated screening proxy",
    "structural-tailwind proxy",
]


# =========================================================
# HELPERS
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
        exist_ok=True
    )

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


def lower_text(value):
    return clean_text(value).lower()


def valid_http_source(source):
    source = clean_text(source)

    if not source:
        return False

    low = source.lower()

    if not (
        low.startswith("https://")
        or low.startswith("http://")
    ):
        return False

    for bad in INVALID_SOURCE_PATTERNS:
        if bad in low:
            return False

    return True


def reason_is_invalid(reason):
    low = lower_text(reason)

    if not low:
        return True

    for bad in INVALID_REASON_PATTERNS:
        if bad in low:
            return True

    return False


def contains_keyword(text, keywords):
    low = lower_text(text)

    if not low:
        return False

    return any(
        keyword in low
        for keyword in keywords
    )


def unique_list(values):
    result = []
    seen = set()

    for value in values:
        value = clean_text(value)

        if not value:
            continue

        key = value.lower()

        if key in seen:
            continue

        seen.add(key)
        result.append(value)

    return result


# =========================================================
# CAPEX VALIDATION
# =========================================================

def capex_candidate_valid(reason, source):
    reason_low = lower_text(reason)

    if reason_is_invalid(reason):
        return False

    if not valid_http_source(source):
        return False

    # Reject generic CAPEX / OCF scoring evidence.
    for bad in GENERIC_CAPEX_PATTERNS:
        if bad in reason_low:
            return False

    if not contains_keyword(
        reason,
        CAPEX_KEYWORDS
    ):
        return False

    return True


# =========================================================
# TAILWIND VALIDATION
# =========================================================

def tailwind_candidate_valid(reason, source):
    reason_low = lower_text(reason)

    if reason_is_invalid(reason):
        return False

    if not valid_http_source(source):
        return False

    for bad in GENERIC_TAILWIND_PATTERNS:
        if bad in reason_low:
            return False

    if not contains_keyword(
        reason,
        TAILWIND_KEYWORDS
    ):
        return False

    return True


# =========================================================
# RESEARCH BLOCK EXTRACTION
# =========================================================

def research_reason_block(stock_data, key):
    if not isinstance(stock_data, dict):
        return {}

    reasons = (
        stock_data.get(
            "researchReasons",
            {}
        )
        or {}
    )

    if not isinstance(reasons, dict):
        return {}

    block = (
        reasons.get(
            key,
            {}
        )
        or {}
    )

    if not isinstance(block, dict):
        return {}

    return block


def candidate_from_block(
    symbol,
    trigger_type,
    block
):
    reason = clean_text(
        block.get("reason")
    )

    source = clean_text(
        block.get("source")
    )

    source_date = clean_text(
        block.get("sourceDate")
    )

    mode = clean_text(
        block.get("mode")
    )

    if trigger_type == "capex":
        valid = capex_candidate_valid(
            reason,
            source
        )

    elif trigger_type == "tailwind":
        valid = tailwind_candidate_valid(
            reason,
            source
        )

    else:
        valid = False

    if not valid:
        return None

    return {
        "symbol": symbol,
        "type": trigger_type,
        "reason": reason,
        "source": source,
        "sourceDate": source_date,
        "originalMode": mode,
        "candidateStatus": "REVIEW_REQUIRED",
        "candidateBuilt": RUN_DATE,
    }


# =========================================================
# VERIFIED EVIDENCE PROTECTION
# =========================================================

def existing_verified_block(
    evidence_stocks,
    symbol,
    key
):
    stock = (
        evidence_stocks.get(
            symbol,
            {}
        )
        or {}
    )

    if not isinstance(stock, dict):
        return {}

    block = (
        stock.get(
            key,
            {}
        )
        or {}
    )

    if not isinstance(block, dict):
        return {}

    reason = clean_text(
        block.get("reason")
    )

    source = clean_text(
        block.get("source")
    )

    if not reason:
        return {}

    if not valid_http_source(source):
        return {}

    return block


# =========================================================
# BUILD CANDIDATES
# =========================================================

def build_candidates():
    stocks = load_json(
        STOCKS_PATH,
        []
    )

    research = load_json(
        RESEARCH_PATH,
        {}
    )

    evidence = load_json(
        EVIDENCE_PATH,
        {}
    )

    research_stocks = (
        research.get(
            "stocks",
            {}
        )
        or {}
    )

    evidence_stocks = (
        evidence.get(
            "stocks",
            {}
        )
        or {}
    )

    stock_symbols = []

    for row in stocks:
        if not isinstance(row, dict):
            continue

        symbol = clean_text(
            row.get("symbol")
        )

        if symbol:
            stock_symbols.append(symbol)

    # Also include symbols already present in research.
    stock_symbols.extend(
        research_stocks.keys()
    )

    stock_symbols = unique_list(
        stock_symbols
    )

    candidates = {}

    capex_candidates = 0
    tailwind_candidates = 0

    verified_capex_skipped = 0
    verified_tailwind_skipped = 0

    for symbol in stock_symbols:
        stock_research = (
            research_stocks.get(
                symbol,
                {}
            )
            or {}
        )

        if not isinstance(
            stock_research,
            dict
        ):
            continue

        symbol_candidates = {}

        # ---------------------------------------------
        # CAPEX
        # ---------------------------------------------

        already_verified_capex = (
            existing_verified_block(
                evidence_stocks,
                symbol,
                "capex"
            )
        )

        if already_verified_capex:
            verified_capex_skipped += 1

        else:
            capex_block = (
                research_reason_block(
                    stock_research,
                    "capex"
                )
            )

            capex_candidate = (
                candidate_from_block(
                    symbol,
                    "capex",
                    capex_block
                )
            )

            if capex_candidate:
                symbol_candidates[
                    "capex"
                ] = capex_candidate

                capex_candidates += 1

        # ---------------------------------------------
        # TAILWIND
        # ---------------------------------------------

        already_verified_tailwind = (
            existing_verified_block(
                evidence_stocks,
                symbol,
                "tailwind"
            )
        )

        if already_verified_tailwind:
            verified_tailwind_skipped += 1

        else:
            tailwind_block = (
                research_reason_block(
                    stock_research,
                    "tailwind"
                )
            )

            tailwind_candidate = (
                candidate_from_block(
                    symbol,
                    "tailwind",
                    tailwind_block
                )
            )

            if tailwind_candidate:
                symbol_candidates[
                    "tailwind"
                ] = tailwind_candidate

                tailwind_candidates += 1

        if symbol_candidates:
            candidates[
                symbol
            ] = symbol_candidates

    return {
        "_meta": {
            "description":
                (
                    "Candidate company-level evidence for "
                    "Big Move Scanner review."
                ),

            "updated":
                RUN_DATE,

            "status":
                "REVIEW_REQUIRED",

            "important":
                (
                    "Entries in this file are NOT verified "
                    "Big Move triggers. Only approved evidence "
                    "should be promoted to company_evidence.json."
                ),

            "rules": {
                "capex":
                    (
                        "Requires company-specific expansion/"
                        "capacity/plant/facility/commissioning "
                        "language plus a usable HTTP source."
                    ),

                "tailwind":
                    (
                        "Requires structural industry-driver "
                        "language plus a usable HTTP source."
                    ),

                "rejected":
                    (
                        "Methodology links, rate-limit/error text, "
                        "generic CAPEX/OCF ratios and automated "
                        "screening-proxy descriptions."
                    ),
            },

            "counts": {
                "symbols":
                    len(candidates),

                "capexCandidates":
                    capex_candidates,

                "tailwindCandidates":
                    tailwind_candidates,

                "verifiedCapexSkipped":
                    verified_capex_skipped,

                "verifiedTailwindSkipped":
                    verified_tailwind_skipped,
            },
        },

        "stocks":
            candidates,
    }


# =========================================================
# MAIN
# =========================================================

def main():
    candidates = (
        build_candidates()
    )

    save_json(
        CANDIDATES_PATH,
        candidates
    )

    # IMPORTANT:
    # We deliberately DO NOT write to company_evidence.json.
    #
    # Existing manually verified evidence remains untouched.
    # Candidate evidence must first be reviewed/verified.

    counts = (
        candidates.get(
            "_meta",
            {}
        )
        .get(
            "counts",
            {}
        )
    )

    print(
        "Company evidence candidate build complete"
    )

    print(
        json.dumps(
            counts,
            indent=2
        )
    )

    print(
        "Output:",
        CANDIDATES_PATH
    )

    print(
        "Verified evidence file was NOT modified:",
        EVIDENCE_PATH
    )


if __name__ == "__main__":
    main()
