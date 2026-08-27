import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


# =========================================================
# HELPERS
# =========================================================

def load_json(path, default):
    try:
        return json.loads(
            path.read_text()
        )
    except Exception:
        return default


def safe_float(value):
    try:
        if value is None:
            return None

        return float(value)

    except Exception:
        return None


def average_score(values):
    """
    Combined score tabhi calculate hoga
    jab group ke saare scores available hon.
    """

    clean = []

    for value in values:

        number = safe_float(
            value
        )

        if number is None:
            return None

        clean.append(
            number
        )

    if not clean:
        return None

    return round(
        sum(clean) /
        len(clean),
        2
    )


# =========================================================
# OVERALL SCORE
# =========================================================

def calc_overall(row):

    fields = {
        "macroSupport": 0.20,
        "valueMigration": 0.20,
        "futureGrowth": 0.20,
        "fundamentalQuality": 0.20,
        "capexScore": 0.10,
        "sectorStrength": 0.10,
    }

    # -----------------------------------------------------
    # Existing Overall methodology SAME rahegi.
    #
    # Tailwind aur Stock Strength Overall me
    # include nahi honge.
    # -----------------------------------------------------

    if any(
        row.get(field) is None
        for field in fields
    ):
        return None

    return round(
        sum(
            float(
                row[field]
            ) * weight

            for field, weight
            in fields.items()
        ),
        2
    )


# =========================================================
# COMBINED RESEARCH SCORES
# =========================================================

def calc_tmv(row):
    """
    T + M + VM

    Tailwind
    Macro
    Value Migration

    Equal-weight average.
    """

    return average_score([
        row.get(
            "tailwindScore"
        ),
        row.get(
            "macroSupport"
        ),
        row.get(
            "valueMigration"
        ),
    ])


def calc_gfc(row):
    """
    G + F + C

    Future Growth
    Fundamental Quality
    CAPEX

    Equal-weight average.
    """

    return average_score([
        row.get(
            "futureGrowth"
        ),
        row.get(
            "fundamentalQuality"
        ),
        row.get(
            "capexScore"
        ),
    ])


# =========================================================
# COMBINED DETAILS
# =========================================================

def detail_for(
    row,
    field
):

    reasons = (
        row.get(
            "researchReasons",
            {}
        )
        or {}
    )

    detail = (
        reasons.get(
            field,
            {}
        )
        or {}
    )

    if not isinstance(
        detail,
        dict
    ):
        detail = {}

    return {
        "reason":
            detail.get(
                "reason"
            )
            or "",

        "source":
            detail.get(
                "source"
            )
            or "",

        "sourceDate":
            detail.get(
                "sourceDate"
            )
            or "",

        "mode":
            detail.get(
                "mode"
            )
            or "",
    }


def build_tmv_details(row):

    return {

        "tailwind": {
            "score":
                row.get(
                    "tailwindScore"
                ),
            **detail_for(
                row,
                "tailwind"
            ),
        },

        "macro": {
            "score":
                row.get(
                    "macroSupport"
                ),
            **detail_for(
                row,
                "macro"
            ),
        },

        "valueMigration": {
            "score":
                row.get(
                    "valueMigration"
                ),
            **detail_for(
                row,
                "valueMigration"
            ),
        },
    }


def build_gfc_details(row):

    return {

        "futureGrowth": {
            "score":
                row.get(
                    "futureGrowth"
                ),
            **detail_for(
                row,
                "futureGrowth"
            ),
        },

        "fundamentalQuality": {
            "score":
                row.get(
                    "fundamentalQuality"
                ),
            **detail_for(
                row,
                "fundamentalQuality"
            ),
        },

        "capex": {
            "score":
                row.get(
                    "capexScore"
                ),
            **detail_for(
                row,
                "capex"
            ),
        },
    }


# =========================================================
# MAIN
# =========================================================

def main():

    stocks_path = (
        DATA /
        "stocks.json"
    )

    scores_path = (
        DATA /
        "research_scores.json"
    )


    stocks = load_json(
        stocks_path,
        []
    )


    score_data = load_json(
        scores_path,
        {}
    )


    scores = (
        score_data.get(
            "stocks",
            {}
        )
        or {}
    )


    # =====================================================
    # FIELDS COPIED FROM RESEARCH SCORES
    # =====================================================

    fields = [

        # ---------------------------------------------
        # ACTUAL GROWTH %
        # ---------------------------------------------

        "sectorGrowth1M",

        "stockGrowth1M",
        "stockGrowth3M",
        "stockGrowth6M",


        # ---------------------------------------------
        # STRENGTH SCORES
        # ---------------------------------------------

        "sectorStrength",

        "stockStrength1M",
        "stockStrength3M",
        "stockStrength6M",

        "strengthBenchmark",


        # ---------------------------------------------
        # RESEARCH SCORES
        # ---------------------------------------------

        "tailwindScore",

        "macroSupport",

        "valueMigration",

        "futureGrowth",

        "fundamentalQuality",

        "capexScore",


        # ---------------------------------------------
        # REASONS / SOURCES
        # ---------------------------------------------

        "researchReasons",
    ]


    # =====================================================
    # COUNTERS
    # =====================================================

    updated = 0

    fully_scored = 0

    tmv_available = 0

    gfc_available = 0

    sector_growth_available = 0

    stock_growth_1m_available = 0

    stock_growth_3m_available = 0

    stock_growth_6m_available = 0

    tailwind_available = 0

    stock_strength_1m_available = 0

    stock_strength_3m_available = 0

    stock_strength_6m_available = 0

    reasons_available = 0


    # =====================================================
    # APPLY
    # =====================================================

    for row in stocks:

        symbol = row.get(
            "symbol",
            ""
        )

        if not symbol:
            continue


        score = (
            scores.get(
                symbol,
                {}
            )
            or {}
        )


        if score:
            updated += 1


        # -------------------------------------------------
        # COPY RESEARCH FIELDS
        # -------------------------------------------------

        for field in fields:

            if field in score:

                row[field] = (
                    score[field]
                )


        # =================================================
        # COMBINED SCORE 1
        # TAILWIND + MACRO + VALUE MIGRATION
        # =================================================

        row["tmvScore"] = (
            calc_tmv(
                row
            )
        )


        row["tmvDetails"] = (
            build_tmv_details(
                row
            )
        )


        # =================================================
        # COMBINED SCORE 2
        # FUTURE GROWTH + FUNDAMENTAL + CAPEX
        # =================================================

        row["gfcScore"] = (
            calc_gfc(
                row
            )
        )


        row["gfcDetails"] = (
            build_gfc_details(
                row
            )
        )


        # =================================================
        # OVERALL SCORE
        # =================================================

        row["overallScore"] = (
            calc_overall(
                row
            )
        )


        # =================================================
        # COUNTERS
        # =================================================

        if (
            row.get(
                "overallScore"
            )
            is not None
        ):
            fully_scored += 1


        if (
            row.get(
                "tmvScore"
            )
            is not None
        ):
            tmv_available += 1


        if (
            row.get(
                "gfcScore"
            )
            is not None
        ):
            gfc_available += 1


        if (
            row.get(
                "sectorGrowth1M"
            )
            is not None
        ):
            sector_growth_available += 1


        if (
            row.get(
                "stockGrowth1M"
            )
            is not None
        ):
            stock_growth_1m_available += 1


        if (
            row.get(
                "stockGrowth3M"
            )
            is not None
        ):
            stock_growth_3m_available += 1


        if (
            row.get(
                "stockGrowth6M"
            )
            is not None
        ):
            stock_growth_6m_available += 1


        if (
            row.get(
                "tailwindScore"
            )
            is not None
        ):
            tailwind_available += 1


        if (
            row.get(
                "stockStrength1M"
            )
            is not None
        ):
            stock_strength_1m_available += 1


        if (
            row.get(
                "stockStrength3M"
            )
            is not None
        ):
            stock_strength_3m_available += 1


        if (
            row.get(
                "stockStrength6M"
            )
            is not None
        ):
            stock_strength_6m_available += 1


        reasons = row.get(
            "researchReasons"
        )


        if (
            isinstance(
                reasons,
                dict
            )
            and
            any(
                reasons.values()
            )
        ):
            reasons_available += 1


    # =====================================================
    # SAVE
    # =====================================================

    stocks_path.write_text(

        json.dumps(
            stocks,
            ensure_ascii=False,
            separators=(
                ",",
                ":"
            )
        )

    )


    # =====================================================
    # LOG
    # =====================================================

    print({

        "stocks":
            len(stocks),

        "researchScoresApplied":
            updated,

        "fullyScored":
            fully_scored,

        "tmvScoreAvailable":
            tmv_available,

        "gfcScoreAvailable":
            gfc_available,

        "sectorGrowth1M":
            sector_growth_available,

        "stockGrowth1M":
            stock_growth_1m_available,

        "stockGrowth3M":
            stock_growth_3m_available,

        "stockGrowth6M":
            stock_growth_6m_available,

        "tailwindAvailable":
            tailwind_available,

        "stockStrength1M":
            stock_strength_1m_available,

        "stockStrength3M":
            stock_strength_3m_available,

        "stockStrength6M":
            stock_strength_6m_available,

        "researchReasonsAvailable":
            reasons_available,

    })


if __name__ == "__main__":
    main()
