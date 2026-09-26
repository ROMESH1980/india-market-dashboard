import json
from pathlib import Path

# =========================================================
# BIG MOVE TRIGGER AUDIT
# =========================================================
# Purpose:
#   Audit WHY CAPEX / Industry Tailwind / Fundamental Trigger
#   is appearing before changing production scoring logic.
#
# This script DOES NOT modify:
#   - stocks.json
#   - big_move_scanner.json
#   - Big Move Score
#   - technical formulas
#   - frontend
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

STOCKS_PATH = DATA_DIR / "stocks.json"
SCANNER_PATH = DATA_DIR / "big_move_scanner.json"
OUTPUT_PATH = DATA_DIR / "big_move_trigger_audit.json"

AUDIT_SYMBOLS = [
    "ANTELOPUS",
    "KABRAEXTRU",
    "GNA",
    "BLISSGVS",
    "BAFNAPH",
]

AUDIT_FIELDS = [
    # Identity
    "symbol",
    "name",
    "companyName",
    "sector",
    "industry",

    # CAPEX
    "capexTrigger",
    "capex",
    "capexScore",
    "capexReason",
    "capexEvidence",

    # Tailwind
    "tailwind",
    "tailwindScore",
    "industryTailwind",
    "tailwindReason",
    "tailwindEvidence",

    # Other business triggers
    "earningsAcceleration",
    "earningsGrowth",
    "earningsTrigger",
    "marginExpansion",
    "marginTrigger",
    "orderWin",
    "orderBook",
    "orderTrigger",
    "capacityExpansion",
    "capacityTrigger",
    "newProduct",
    "newProductTrigger",
    "corporateAction",
    "corporateActionTrigger",
    "fundRaise",
    "fundRaising",
    "preferentialIssue",
    "warrants",
    "qip",

    # General research evidence
    "researchReasons",
    "researchEvidence",
    "evidence",
    "reasons",
    "reason",
    "futureGrowthReason",
    "fundamentalReason",
    "macroReason",
    "valueMigrationReason",
    "futureGrowthEvidence",
    "fundamentalEvidence",
    "macroEvidence",
    "valueMigrationEvidence",
]


def load_json(path, default):
    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return default


def save_json(path, data):
    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def clean_symbol(value):
    return str(value or "").strip().upper()


def compact_value(value):
    """
    Keep useful evidence, but avoid huge audit files.
    """
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        return value if value else None

    if isinstance(value, (int, float, bool)):
        return value

    if isinstance(value, list):
        out = []
        for item in value[:20]:
            cleaned = compact_value(item)
            if cleaned is not None:
                out.append(cleaned)
        return out or None

    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            cleaned = compact_value(item)
            if cleaned is not None:
                out[str(key)] = cleaned
        return out or None

    return str(value)


def extract_fields(row):
    result = {}

    for field in AUDIT_FIELDS:
        if field not in row:
            continue

        value = compact_value(
            row.get(field)
        )

        if value is not None:
            result[field] = value

    return result


def scanner_rows(payload):
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in [
            "stocks",
            "rows",
            "data",
            "results",
        ]:
            value = payload.get(key)

            if isinstance(value, list):
                return value

    return []


def main():
    print("=" * 58)
    print("BIG MOVE TRIGGER AUDIT")
    print("=" * 58)

    stocks = load_json(
        STOCKS_PATH,
        [],
    )

    scanner_payload = load_json(
        SCANNER_PATH,
        {},
    )

    if not isinstance(stocks, list):
        raise RuntimeError(
            "data/stocks.json must contain a list"
        )

    scanner = scanner_rows(
        scanner_payload
    )

    stocks_by_symbol = {
        clean_symbol(row.get("symbol")): row
        for row in stocks
        if isinstance(row, dict)
        and clean_symbol(row.get("symbol"))
    }

    scanner_by_symbol = {
        clean_symbol(row.get("symbol")): row
        for row in scanner
        if isinstance(row, dict)
        and clean_symbol(row.get("symbol"))
    }

    audit_rows = []

    for symbol in AUDIT_SYMBOLS:
        stock = stocks_by_symbol.get(
            symbol,
            {},
        )

        scan = scanner_by_symbol.get(
            symbol,
            {},
        )

        audit = {
            "symbol": symbol,

            # What Page 2 currently shows
            "scannerOutput": {
                "fundamentalTrigger":
                    scan.get("fundamentalTrigger"),

                "fundamentalTriggers":
                    scan.get("fundamentalTriggers"),

                "businessTriggers":
                    scan.get("businessTriggers"),

                "structuralTriggers":
                    scan.get("structuralTriggers"),

                "keyTrigger":
                    scan.get("keyTrigger"),

                "phase1Score":
                    scan.get("phase1Score"),

                "bigMoveScore":
                    scan.get("bigMoveScore"),
            },

            # Why stocks.json may be producing those triggers
            "sourceResearchFields":
                extract_fields(stock),
        }

        # Simple audit flags — informational only.
        source = audit["sourceResearchFields"]

        capex_has_reason = any(
            source.get(key) is not None
            for key in [
                "capexReason",
                "capexEvidence",
                "researchReasons",
                "researchEvidence",
                "evidence",
            ]
        )

        tailwind_has_reason = any(
            source.get(key) is not None
            for key in [
                "tailwindReason",
                "tailwindEvidence",
                "researchReasons",
                "researchEvidence",
                "evidence",
            ]
        )

        audit["auditFlags"] = {
            "capexHasEvidenceField":
                capex_has_reason,

            "tailwindHasEvidenceField":
                tailwind_has_reason,

            "capexShown":
                "CAPEX"
                in (
                    scan.get("businessTriggers")
                    or scan.get("fundamentalTriggers")
                    or []
                ),

            "industryTailwindShown":
                "Industry Tailwind"
                in (
                    scan.get("businessTriggers")
                    or scan.get("fundamentalTriggers")
                    or []
                ),
        }

        audit_rows.append(
            audit
        )

    output = {
        "purpose":
            (
                "Audit CAPEX / Industry Tailwind / Fundamental Trigger "
                "evidence before tightening production trigger rules."
            ),

        "productionDataModified":
            False,

        "symbols":
            AUDIT_SYMBOLS,

        "rows":
            audit_rows,
    }

    save_json(
        OUTPUT_PATH,
        output,
    )

    print(
        f"Audit written: {OUTPUT_PATH}"
    )

    for row in audit_rows:
        flags = row["auditFlags"]

        print(
            f'{row["symbol"]}: '
            f'CAPEX={flags["capexShown"]} '
            f'CAPEX_EVIDENCE={flags["capexHasEvidenceField"]} | '
            f'TAILWIND={flags["industryTailwindShown"]} '
            f'TAILWIND_EVIDENCE={flags["tailwindHasEvidenceField"]}'
        )

    print("=" * 58)
    print("AUDIT COMPLETE — production scanner unchanged")
    print("=" * 58)


if __name__ == "__main__":
    main()
