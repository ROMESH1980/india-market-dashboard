import json
import math
from datetime import datetime, timezone
from pathlib import Path


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

STOCKS_PATH = DATA_DIR / "stocks.json"
OUTPUT_PATH = DATA_DIR / "big_move_scanner.json"


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
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def num(value):
    """
    Safe numeric conversion.

    IMPORTANT:
    None / blank / Pending / dash must remain None.
    Do NOT convert missing values to zero.
    """

    if value is None:
        return None

    if isinstance(value, str):
        text = (
            value
            .replace(",", "")
            .replace("%", "")
            .replace("₹", "")
            .strip()
        )

        if not text:
            return None

        if text.lower() in {
            "-",
            "—",
            "na",
            "n/a",
            "none",
            "null",
            "pending",
        }:
            return None

        value = text

    try:
        result = float(value)

        if not math.isfinite(result):
            return None

        return result

    except Exception:
        return None


def integer(value):
    value = num(value)

    if value is None:
        return None

    return int(round(value))


def text(value):
    if value is None:
        return ""

    return str(value).strip()


def first_value(row, keys):
    for key in keys:
        value = row.get(key)

        if value is None:
            continue

        if isinstance(value, str):
            if not value.strip():
                continue

        return value

    return None


def first_number(row, keys):
    for key in keys:
        value = num(
            row.get(key)
        )

        if value is not None:
            return value

    return None


def clamp(value, low, high):
    return max(
        low,
        min(
            high,
            value,
        ),
    )


# =========================================================
# RETURNS
# =========================================================

def stock_return(row, period):
    """
    Support multiple field names so existing Page 1 backend
    does not need to change.
    """

    candidates = {
        "1M": [
            "stockGrowth1M",
            "stockReturn1M",
            "return1M",
            "priceChange1M",
            "change1M",
        ],

        "3M": [
            "stockGrowth3M",
            "stockReturn3M",
            "return3M",
            "priceChange3M",
            "change3M",
        ],

        "6M": [
            "stockGrowth6M",
            "stockReturn6M",
            "return6M",
            "priceChange6M",
            "change6M",
        ],

        "1Y": [
            "stockGrowth1Y",
            "stockReturn1Y",
            "return1Y",
            "priceChange1Y",
            "change1Y",
            "return12M",
        ],
    }

    return first_number(
        row,
        candidates.get(
            period,
            [],
        ),
    )


# =========================================================
# FUNDAMENTAL / BUSINESS TRIGGERS
# =========================================================

def score_like(value):
    value = num(value)

    if value is None:
        return None

    return value


def positive_flag(value):
    """
    Converts common boolean / score / string values
    into True / False / None.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return value

    numeric = num(value)

    if numeric is not None:
        return numeric >= 60

    value = str(value).strip().lower()

    if value in {
        "yes",
        "true",
        "strong",
        "positive",
        "present",
        "active",
        "high",
        "good",
        "bullish",
    }:
        return True

    if value in {
        "no",
        "false",
        "weak",
        "negative",
        "absent",
        "low",
    }:
        return False

    return None


# =========================================================
# STRUCTURAL TRIGGERS — STRICT EVIDENCE MODE
# =========================================================
#
# IMPORTANT:
# A structural trigger is NOT created from a broad keyword alone.
# The SAME evidence/reason fragment must contain:
#   1) a structural-theme keyword, AND
#   2) company-specific action / impact evidence.
#
# This deliberately prefers false negatives over false positives.
# Structural triggers remain DISPLAY-ONLY and are NOT added to
# Big Move Score.
# =========================================================

STRUCTURAL_TRIGGER_RULES = [
    (
        "Government / Regulation",
        [
            "government", "regulation", "regulatory", "policy", "scheme",
            "pli", "rera", "subsidy", "incentive", "mandate", "tariff",
            "duty", "government order", "government spending",
        ],
    ),
    (
        "Technology / Disruption",
        [
            "technology", "technological", "disruption", "digital",
            "artificial intelligence", " ai ", "automation", "robotics",
            "electric vehicle", " ev ", "5g", "semiconductor", "cloud",
            "data center", "digitisation", "digitalisation",
        ],
    ),
    (
        "Global / Supply Chain",
        [
            "china+1", "china plus one", "supply chain", "supply-chain",
            "global sourcing", "export opportunity", "import substitution",
            "friendshoring", "reshoring", "global shift", "us sourcing",
            "europe sourcing",
        ],
    ),
    (
        "Consumer Shift",
        [
            "premiumization", "premiumisation", "consumer shift",
            "consumer habit", "income growth", "discretionary spending",
            "formalization", "formalisation", "sip culture",
            "financialization", "financialisation", "urbanisation",
            "urbanization",
        ],
    ),
    (
        "Industry Consolidation",
        [
            "industry consolidation", "market consolidation",
            "competitor exit", "competitor exits", "market share gain",
            "market-share gain", "share gain", "organized players",
            "organised players", "weak competitor",
        ],
    ),
    (
        "Raw Material Cycle",
        [
            "raw material", "raw-material", "commodity cycle", "metal cycle",
            "metal prices", "crude oil", "crude price", "oil price",
            "input cost", "input costs", "feedstock",
        ],
    ),
    (
        "External Shock",
        [
            "covid", "pandemic", "external shock", "geopolitical shock",
            "geopolitical crisis", "war disruption", "supply disruption",
            "natural disaster", "lockdown",
        ],
    ),
]


# Strong company-specific evidence/action words.
# Generic words such as "growth", "opportunity", "positive", "tailwind"
# are intentionally NOT enough by themselves.
STRUCTURAL_ACTION_EVIDENCE = [
    "company announced",
    "company has",
    "company is",
    "management said",
    "management expects",
    "received order",
    "order received",
    "secured order",
    "won order",
    "order win",
    "awarded",
    "approved",
    "approval",
    "commissioned",
    "commercial production",
    "commenced production",
    "started production",
    "capacity expansion",
    "expanded capacity",
    "expanding capacity",
    "new capacity",
    "capex",
    "capital expenditure",
    "investment",
    "investing",
    "plant expansion",
    "new plant",
    "new facility",
    "launched",
    "new product",
    "product launch",
    "entered",
    "entry into",
    "signed",
    "agreement",
    "partnership",
    "joint venture",
    "acquired",
    "acquisition",
    "merger",
    "export order",
    "exports increased",
    "export growth",
    "market share gained",
    "market share gain",
    "share gain",
    "beneficiary",
    "benefiting",
    "benefitted",
    "benefited",
    "revenue increased",
    "revenue growth",
    "margin improved",
    "margin expansion",
    "cost reduced",
    "cost reduction",
    "savings",
]


def _collect_research_fragments(value, fragments):
    """
    Preserve individual evidence/reason strings.

    Keeping fragments separate is important:
    a structural keyword in one unrelated reason must NOT combine with
    an action word found somewhere else in the stock record.
    """
    if value is None:
        return

    if isinstance(value, dict):
        for key, item in value.items():
            key_lower = str(key).lower()

            if (
                "url" in key_lower
                or key_lower in {"link", "href"}
            ):
                continue

            _collect_research_fragments(
                item,
                fragments,
            )

        return

    if isinstance(
        value,
        (list, tuple, set),
    ):
        for item in value:
            _collect_research_fragments(
                item,
                fragments,
            )

        return

    if (
        isinstance(value, str)
        and value.strip()
    ):
        fragments.append(
            value.strip().lower()
        )


def structural_evidence_fragments(row):
    """
    Read only existing research reason/evidence fields.
    Sector/industry names alone are NOT treated as structural evidence.
    """
    fragments = []

    fields = [
        "researchReasons",
        "researchEvidence",
        "evidence",
        "reasons",
        "reason",
        "tailwindReason",
        "macroReason",
        "valueMigrationReason",
        "futureGrowthReason",
        "fundamentalReason",
        "capexReason",
        "tailwindEvidence",
        "macroEvidence",
        "valueMigrationEvidence",
        "futureGrowthEvidence",
        "fundamentalEvidence",
        "capexEvidence",
        "triggerReason",
        "triggerReasons",
        "keyTriggerReason",
        "businessTriggerReason",
        "structuralTriggerReason",
        "structuralTriggerReasons",
    ]

    for field in fields:
        _collect_research_fragments(
            row.get(field),
            fragments,
        )

    # Preserve compatibility with future reason/evidence fields,
    # but still ignore unrelated normal stock fields.
    for key, value in row.items():
        key_lower = str(key).lower()

        if key in fields:
            continue

        if (
            "reason" in key_lower
            or "evidence" in key_lower
        ):
            _collect_research_fragments(
                value,
                fragments,
            )

    # Remove duplicates while preserving order.
    unique = []
    seen = set()

    for fragment in fragments:
        if fragment not in seen:
            seen.add(fragment)
            unique.append(fragment)

    return unique


def _contains_any(text_value, keywords):
    padded = f" {text_value} "

    return any(
        keyword in padded
        for keyword in keywords
    )


def _has_company_specific_action(fragment, row):
    """
    Require concrete action/impact evidence in the SAME fragment.

    A company/symbol mention strengthens evidence, but is not mandatory
    because many existing research reasons are written without repeating
    the company name.
    """
    padded = f" {fragment} "

    if any(
        action in padded
        for action in STRUCTURAL_ACTION_EVIDENCE
    ):
        return True

    # Extra strict company-name/symbol + measurable impact fallback.
    symbol = str(
        row.get("symbol")
        or ""
    ).strip().lower()

    company_name = str(
        row.get("name")
        or row.get("companyName")
        or ""
    ).strip().lower()

    company_mentioned = (
        (
            symbol
            and f" {symbol} " in padded
        )
        or
        (
            company_name
            and company_name in fragment
        )
    )

    measurable_impact_words = [
        "revenue",
        "sales",
        "margin",
        "profit",
        "ebitda",
        "capacity",
        "order book",
        "orders",
        "exports",
        "market share",
        "cost",
        "volume",
    ]

    return (
        company_mentioned
        and any(
            word in padded
            for word in measurable_impact_words
        )
    )


def detect_structural_triggers(row):
    """
    STRICT RULE:
    Structural theme keyword + company-specific action/impact evidence
    must occur in the SAME research fragment.

    This prevents examples such as:
      - pharma industry text -> Technology trigger
      - generic policy discussion -> Government trigger
      - generic input-cost mention -> Raw Material trigger
    """
    fragments = structural_evidence_fragments(
        row
    )

    if not fragments:
        return []

    detected = []

    for trigger_name, keywords in STRUCTURAL_TRIGGER_RULES:
        matched = False

        for fragment in fragments:
            if not _contains_any(
                fragment,
                keywords,
            ):
                continue

            if not _has_company_specific_action(
                fragment,
                row,
            ):
                continue

            matched = True
            break

        if matched:
            detected.append(
                trigger_name
            )

    return detected


def merge_unique_triggers(*groups):
    out=[]
    seen=set()
    for group in groups:
        for item in group or []:
            if item not in seen:
                seen.add(item)
                out.append(item)
    return out

def detect_triggers(row):
    """
    Build trigger list from existing research fields.

    This does NOT invent a trigger.
    It only uses fields already available in stocks.json.
    """

    triggers = []

    # -----------------------------------------------------
    # Earnings Acceleration
    # -----------------------------------------------------

    earnings_flag = first_value(
        row,
        [
            "earningsAcceleration",
            "earningsGrowth",
            "earningsTrigger",
        ],
    )

    if positive_flag(earnings_flag) is True:
        triggers.append(
            "Earnings Acceleration"
        )

    # -----------------------------------------------------
    # Margin Expansion
    # -----------------------------------------------------

    margin_flag = first_value(
        row,
        [
            "marginExpansion",
            "marginTrigger",
        ],
    )

    if positive_flag(margin_flag) is True:
        triggers.append(
            "Margin Expansion"
        )

    # -----------------------------------------------------
    # Order Win / Order Book
    # -----------------------------------------------------

    order_flag = first_value(
        row,
        [
            "orderWin",
            "orderBook",
            "orderTrigger",
        ],
    )

    if positive_flag(order_flag) is True:
        triggers.append(
            "Order Win / Order Book"
        )

    # -----------------------------------------------------
    # CAPEX
    # -----------------------------------------------------

    capex_value = first_value(
        row,
        [
            "capexTrigger",
            "capex",
            "capexScore",
        ],
    )

    capex_score = score_like(
        capex_value
    )

    if (
        positive_flag(capex_value) is True
        or
        (
            capex_score is not None
            and capex_score >= 70
        )
    ):
        triggers.append(
            "CAPEX"
        )

    # -----------------------------------------------------
    # Capacity Expansion
    # -----------------------------------------------------

    capacity_flag = first_value(
        row,
        [
            "capacityExpansion",
            "capacityTrigger",
        ],
    )

    if positive_flag(capacity_flag) is True:
        triggers.append(
            "Capacity Expansion"
        )

    # -----------------------------------------------------
    # New Product
    # -----------------------------------------------------

    new_product = first_value(
        row,
        [
            "newProduct",
            "newProductTrigger",
        ],
    )

    if positive_flag(new_product) is True:
        triggers.append(
            "New Product"
        )

    # -----------------------------------------------------
    # Corporate Action
    # -----------------------------------------------------

    corporate_action = first_value(
        row,
        [
            "corporateAction",
            "corporateActionTrigger",
        ],
    )

    if positive_flag(corporate_action) is True:
        triggers.append(
            "Corporate Action"
        )

    # -----------------------------------------------------
    # Fund Raise / Warrants / QIP
    # -----------------------------------------------------

    fund_raise = first_value(
        row,
        [
            "fundRaise",
            "fundRaising",
            "preferentialIssue",
            "warrants",
            "qip",
        ],
    )

    if positive_flag(fund_raise) is True:
        triggers.append(
            "Fund Raise / Warrants / QIP"
        )

    # -----------------------------------------------------
    # Industry Tailwind
    # -----------------------------------------------------

    tailwind = first_value(
        row,
        [
            "tailwind",
            "tailwindScore",
            "industryTailwind",
        ],
    )

    tailwind_score = score_like(
        tailwind
    )

    if (
        positive_flag(tailwind) is True
        or
        (
            tailwind_score is not None
            and tailwind_score >= 70
        )
    ):
        triggers.append(
            "Industry Tailwind"
        )

    # remove duplicates, preserve order
    clean = []

    seen = set()

    for item in triggers:
        if item in seen:
            continue

        seen.add(item)
        clean.append(item)

    return clean


def choose_key_trigger(triggers):
    """
    Higher-value event trigger gets priority.
    """

    priority = [
        "Earnings Acceleration",
        "Margin Expansion",
        "Order Win / Order Book",
        "Capacity Expansion",
        "CAPEX",
        "Fund Raise / Warrants / QIP",
        "New Product",
        "Corporate Action",
        "Industry Tailwind",
    ]

    for item in priority:
        if item in triggers:
            return item

    return None


# =========================================================
# PHASE-1 SCORE
# =========================================================

def calculate_phase1_score(
    rs_rating,
    stock_momentum,
    industry_rating,
    return_1m,
    return_3m,
    return_6m,
    return_1y,
    triggers,
):
    """
    Phase-1 preliminary score.

    MAX = 100 here.

    build_big_move_technical.py later rescales
    this phase to 55 points and adds technical 45 points.
    """

    score = 0.0

    # -----------------------------------------------------
    # RS Rating : 25 points
    # -----------------------------------------------------

    if rs_rating is not None:
        score += (
            clamp(
                rs_rating,
                0,
                100,
            )
            / 100
            * 25
        )

    # -----------------------------------------------------
    # Stock Momentum : 20 points
    # -----------------------------------------------------

    if stock_momentum is not None:
        score += (
            clamp(
                stock_momentum,
                0,
                100,
            )
            / 100
            * 20
        )

    # -----------------------------------------------------
    # Industry Rating : 15 points
    # -----------------------------------------------------

    if industry_rating is not None:
        score += (
            clamp(
                industry_rating,
                0,
                100,
            )
            / 100
            * 15
        )

    # -----------------------------------------------------
    # Multi-period return strength : 20 points
    # -----------------------------------------------------

    return_score = 0.0

    if return_1m is not None:
        if return_1m >= 20:
            return_score += 5
        elif return_1m >= 10:
            return_score += 4
        elif return_1m >= 5:
            return_score += 3
        elif return_1m > 0:
            return_score += 2

    if return_3m is not None:
        if return_3m >= 40:
            return_score += 5
        elif return_3m >= 25:
            return_score += 4
        elif return_3m >= 15:
            return_score += 3
        elif return_3m > 0:
            return_score += 2

    if return_6m is not None:
        if return_6m >= 60:
            return_score += 5
        elif return_6m >= 40:
            return_score += 4
        elif return_6m >= 20:
            return_score += 3
        elif return_6m > 0:
            return_score += 2

    if return_1y is not None:
        if return_1y >= 100:
            return_score += 5
        elif return_1y >= 60:
            return_score += 4
        elif return_1y >= 30:
            return_score += 3
        elif return_1y > 0:
            return_score += 2

    score += min(
        20,
        return_score,
    )

    # -----------------------------------------------------
    # Fundamental / business triggers : 20 points
    # -----------------------------------------------------

    trigger_count = len(
        triggers
    )

    if trigger_count >= 4:
        score += 20

    elif trigger_count == 3:
        score += 17

    elif trigger_count == 2:
        score += 13

    elif trigger_count == 1:
        score += 8

    return int(
        round(
            clamp(
                score,
                0,
                100,
            )
        )
    )


# =========================================================
# PRELIMINARY SETUP STATUS
# =========================================================

def preliminary_status(score):
    if score >= 80:
        return "High Potential"

    if score >= 70:
        return "Watchlist"

    if score >= 60:
        return "Developing"

    return "Early"


# =========================================================
# MISSING CONDITIONS
# =========================================================

def initial_missing_conditions(
    rs_rating,
    stock_momentum,
    industry_rating,
    free_float_shares,
    free_float_pct,
):
    missing = []

    if rs_rating is None:
        missing.append(
            "RS"
        )

    if stock_momentum is None:
        missing.append(
            "Stock Momentum"
        )

    if industry_rating is None:
        missing.append(
            "Industry Rating"
        )

    if (
        free_float_shares is None
        and
        free_float_pct is None
    ):
        missing.append(
            "Free Float"
        )

    # Technical engine runs after this script.
    missing.append(
        "Technical Analysis"
    )

    return missing


# =========================================================
# BUILD ROW
# =========================================================

def build_scanner_row(stock):
    symbol = text(
        stock.get(
            "symbol"
        )
    ).upper()

    name = text(
        first_value(
            stock,
            [
                "name",
                "companyName",
                "company",
            ],
        )
    )

    price = first_number(
        stock,
        [
            "price",
            "close",
            "lastPrice",
            "ltp",
        ],
    )

    change_pct = first_number(
        stock,
        [
            "changePct",
            "changePercent",
            "pctChange",
            "pChange",
        ],
    )

    return_1m = stock_return(
        stock,
        "1M",
    )

    return_3m = stock_return(
        stock,
        "3M",
    )

    return_6m = stock_return(
        stock,
        "6M",
    )

    return_1y = stock_return(
        stock,
        "1Y",
    )

    rs_rating = first_number(
        stock,
        [
            "rsRating",
        ],
    )

    stock_momentum = first_number(
        stock,
        [
            "stockMomentumRating",
        ],
    )

    industry_rating = first_number(
        stock,
        [
            "industryRating",
        ],
    )

    # =====================================================
    # FREE FLOAT
    #
    # Values originate from build_free_float.py.
    #
    # freeFloatShares:
    # exact filing-derived Public Shares minus locked
    # public shares.
    #
    # It is NOT estimated from Market Cap / Price.
    # =====================================================

    free_float_shares = integer(
        stock.get(
            "freeFloatShares"
        )
    )

    free_float_pct = num(
        stock.get(
            "freeFloatPct"
        )
    )

    free_float_status = (
        text(
            stock.get(
                "freeFloatStatus"
            )
        )
        or
        "PENDING"
    )

    free_float_date = (
        stock.get(
            "freeFloatDate"
        )
    )

    free_float_source = (
        stock.get(
            "freeFloatSource"
        )
    )

    free_float_source_url = (
        stock.get(
            "freeFloatSourceUrl"
        )
    )

    free_float_method = (
        stock.get(
            "freeFloatMethod"
        )
    )

    free_float_estimated = (
        stock.get(
            "freeFloatEstimated"
        )
    )

    public_shares = integer(
        stock.get(
            "publicShares"
        )
    )

    public_holding_pct = num(
        stock.get(
            "publicHoldingPct"
        )
    )

    public_locked_shares = integer(
        stock.get(
            "publicLockedShares"
        )
    )

    business_triggers = detect_triggers(
        stock
    )

    structural_triggers = detect_structural_triggers(
        stock
    )

    triggers = merge_unique_triggers(
        business_triggers,
        structural_triggers,
    )

    key_trigger = (
        " • ".join(triggers)
        if triggers
        else None
    )

    phase1_score = calculate_phase1_score(
        rs_rating=rs_rating,
        stock_momentum=stock_momentum,
        industry_rating=industry_rating,
        return_1m=return_1m,
        return_3m=return_3m,
        return_6m=return_6m,
        return_1y=return_1y,
        triggers=business_triggers,
    )

    setup_status = preliminary_status(
        phase1_score
    )

    missing = initial_missing_conditions(
        rs_rating=rs_rating,
        stock_momentum=stock_momentum,
        industry_rating=industry_rating,
        free_float_shares=free_float_shares,
        free_float_pct=free_float_pct,
    )

    sector = text(
        stock.get(
            "sector"
        )
    )

    industry = text(
        stock.get(
            "industry"
        )
    )

    market_cap = first_number(
        stock,
        [
            "marketCapCr",
            "marketCap",
            "currentMarketCapCr",
        ],
    )

    market_cap_category = text(
        first_value(
            stock,
            [
                "marketCapCategory",
                "mcapCategory",
            ],
        )
    )

    board = text(
        stock.get(
            "board"
        )
    )

    series = text(
        stock.get(
            "series"
        )
    )

    row = {
        # -------------------------------------------------
        # Identity
        # -------------------------------------------------

        "symbol":
            symbol,

        "name":
            name,

        "board":
            board,

        "series":
            series,

        "sector":
            sector,

        "industry":
            industry,

        # -------------------------------------------------
        # Market data
        # -------------------------------------------------

        "price":
            price,

        "changePct":
            change_pct,

        "marketCapCr":
            market_cap,

        "marketCapCategory":
            market_cap_category,

        # -------------------------------------------------
        # Returns
        # -------------------------------------------------

        "return1M":
            return_1m,

        "return3M":
            return_3m,

        "return6M":
            return_6m,

        "return1Y":
            return_1y,

        # -------------------------------------------------
        # Ratings
        # -------------------------------------------------

        "rsRating":
            rs_rating,

        "stockMomentumRating":
            stock_momentum,

        "industryRating":
            industry_rating,

        # -------------------------------------------------
        # FREE FLOAT
        # -------------------------------------------------

        "freeFloatPct":
            (
                round(
                    free_float_pct,
                    4,
                )
                if free_float_pct is not None
                else None
            ),

        "freeFloatShares":
            free_float_shares,

        "freeFloatStatus":
            free_float_status,

        "freeFloatDate":
            free_float_date,

        "freeFloatSource":
            free_float_source,

        "freeFloatSourceUrl":
            free_float_source_url,

        "freeFloatMethod":
            free_float_method,

        "freeFloatEstimated":
            free_float_estimated,

        # Keep underlying filing values too.
        "publicShares":
            public_shares,

        "publicHoldingPct":
            public_holding_pct,

        "publicLockedShares":
            public_locked_shares,

        # -------------------------------------------------
        # Fundamental / business triggers
        # -------------------------------------------------

        "fundamentalTrigger":
            bool(
                business_triggers
            ),

        "fundamentalTriggers":
            business_triggers,

        "businessTriggers":
            business_triggers,

        "structuralTriggers":
            structural_triggers,

        "keyTrigger":
            key_trigger,

        # -------------------------------------------------
        # Phase-1 score
        # -------------------------------------------------

        "phase1Score":
            phase1_score,

        "bigMoveScore":
            phase1_score,

        "setupStatus":
            setup_status,

        # -------------------------------------------------
        # Technical placeholders
        #
        # build_big_move_technical.py fills these afterward.
        # -------------------------------------------------

        "priorMovePct":
            None,

        "movePeriod":
            None,

        "moveStartDate":
            None,

        "movePeakDate":
            None,

        "moveStartPrice":
            None,

        "movePeakPrice":
            None,

        "retracementPct":
            None,

        "consolidationDays":
            None,

        "volumeContraction":
            None,

        "volumeContractionRatio":
            None,

        "volatilityContraction":
            None,

        "volatilityContractionRatio":
            None,

        "breakoutStatus":
            None,

        "breakoutDistancePct":
            None,

        "turnoverExpansion":
            None,

        "technicalScore":
            None,

        "technicalStatus":
            "PENDING",

        "technicalDetails":
            None,

        # -------------------------------------------------
        # Missing
        # -------------------------------------------------

        "missingConditions":
            missing,
    }

    return row


# =========================================================
# MARKET DATE
# =========================================================

def detect_market_date(stocks):
    dates = []

    for stock in stocks:
        value = first_value(
            stock,
            [
                "marketDate",
                "date",
                "priceDate",
                "eodDate",
            ],
        )

        if value:
            dates.append(
                str(value)
            )

    if not dates:
        return None

    # Most common / latest-looking value.
    return sorted(
        dates
    )[-1]


# =========================================================
# SUMMARY
# =========================================================

def build_summary(rows):
    total = len(
        rows
    )

    score_80 = sum(
        1
        for row in rows
        if (
            num(
                row.get(
                    "bigMoveScore"
                )
            )
            is not None
            and
            num(
                row.get(
                    "bigMoveScore"
                )
            )
            >= 80
        )
    )

    trigger_present = sum(
        1
        for row in rows
        if row.get(
            "fundamentalTrigger"
        )
        is True
    )

    free_float_ready = sum(
        1
        for row in rows
        if (
            row.get(
                "freeFloatShares"
            )
            is not None
            or
            row.get(
                "freeFloatPct"
            )
            is not None
        )
    )

    return {
        "scannerUniverse":
            total,

        "score80Plus":
            score_80,

        "triggerPresent":
            trigger_present,

        "freeFloatReady":
            free_float_ready,

        # Technical engine recalculates these later.
        "nearBreakout":
            0,

        "breakout":
            0,
    }


# =========================================================
# MAIN
# =========================================================

def main():
    print(
        "=============================================="
    )

    print(
        "BUILD BIG MOVE SCANNER"
    )

    print(
        "=============================================="
    )

    stocks = load_json(
        STOCKS_PATH,
        [],
    )

    if (
        not isinstance(
            stocks,
            list,
        )
        or
        not stocks
    ):
        raise RuntimeError(
            "data/stocks.json is missing or empty"
        )

    rows = []

    skipped = 0

    for stock in stocks:
        if not isinstance(
            stock,
            dict,
        ):
            skipped += 1
            continue

        symbol = text(
            stock.get(
                "symbol"
            )
        )

        if not symbol:
            skipped += 1
            continue

        row = build_scanner_row(
            stock
        )

        rows.append(
            row
        )

    # Default Page 2 ranking before technical engine.
    rows.sort(
        key=lambda row: (
            num(
                row.get(
                    "bigMoveScore"
                )
            )
            if num(
                row.get(
                    "bigMoveScore"
                )
            )
            is not None
            else -1
        ),
        reverse=True,
    )

    market_date = detect_market_date(
        stocks
    )

    summary = build_summary(
        rows
    )

    now = (
        datetime.now(
            timezone.utc
        )
        .replace(
            microsecond=0
        )
        .isoformat()
    )

    output = {
        "marketDate":
            market_date,

        "generatedAt":
            now,

        "scannerVersion":
            "2.1",

        "methodology": {
            "phase1":
                (
                    "RS + Stock Momentum + Industry Rating + "
                    "multi-period price strength + existing "
                    "fundamental/business triggers."
                ),

            "structuralTriggers":
                (
                    "Structural triggers are display-only and require a "
                    "theme keyword plus company-specific action/impact "
                    "evidence in the same research fragment. They do not "
                    "add points to Big Move Score."
                ),

            "technical":
                (
                    "Technical fields are added by "
                    "build_big_move_technical.py after this step."
                ),

            "freeFloat":
                (
                    "Free Float Shares and Free Float % are carried "
                    "from build_free_float.py. Free Float Shares are "
                    "filing-derived Public Shares less locked-in "
                    "Public Shares; not estimated from Market Cap / Price."
                ),

            "freeFloatScore":
                (
                    "Free Float is currently displayed/filterable but "
                    "NOT yet included in Big Move Score. Thresholds will "
                    "be calibrated after coverage/distribution validation."
                ),
        },

        "summary":
            summary,

        "rows":
            rows,
    }

    save_json(
        OUTPUT_PATH,
        output,
    )

    print({
        "stocksInput":
            len(stocks),

        "scannerRows":
            len(rows),

        "skipped":
            skipped,

        "score80Plus":
            summary[
                "score80Plus"
            ],

        "triggerPresent":
            summary[
                "triggerPresent"
            ],

        "freeFloatReady":
            summary[
                "freeFloatReady"
            ],

        "marketDate":
            market_date,
    })

    print(
        "Saved:"
    )

    print(
        OUTPUT_PATH
    )

    print()
    print(
        "IMPORTANT:"
    )
    print(
        "Free Float is NOT included in Big Move Score yet."
    )
    print(
        "build_big_move_technical.py runs after this file and "
        "adds technical score / breakout / consolidation fields."
    )
    print(
        "=============================================="
    )


if __name__ == "__main__":
    main()
