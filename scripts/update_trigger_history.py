#!/usr/bin/env python3
"""Persist verified Big Move Scanner triggers and attach permanent source-backed history.

Reads data/big_move_scanner.json, merges newly verified trigger evidence into
data/trigger_history.json, and writes triggerHistory back to each scanner row.

IMPORTANT:
- triggerHistory is permanent source-backed history.
- keyTrigger remains the CURRENT scanner trigger only.
- Historical triggers are never injected back into keyTrigger.
- Existing history is never deleted by a normal daily rebuild.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SCANNER_PATH = DATA / "big_move_scanner.json"
HISTORY_PATH = DATA / "trigger_history.json"


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def clean(value) -> str:
    return " ".join(str(value or "").split()).strip()


def evidence_record(trigger_type: str, evidence) -> dict | None:
    if not isinstance(evidence, dict):
        return None

    source = clean(
        evidence.get("source")
        or evidence.get("sourceUrl")
        or evidence.get("url")
    )
    reason = clean(evidence.get("reason"))
    source_date = clean(
        evidence.get("sourceDate")
        or evidence.get("date")
    )

    if not source or not source.lower().startswith(("http://", "https://")):
        return None

    return {
        "type": trigger_type,
        "sourceDate": source_date,
        "sourceName": clean(evidence.get("sourceName")) or "NSE Filing",
        "source": source,
        "reason": reason,
        "verified": True,
    }


def current_verified_records(row: dict) -> list[dict]:
    out = []

    if row.get("capexVerified") is True:
        rec = evidence_record("CAPEX", row.get("capexEvidence"))
        if rec:
            out.append(rec)

    if row.get("industryTailwindVerified") is True:
        rec = evidence_record(
            "Industry Tailwind",
            row.get("industryTailwindEvidence"),
        )
        if rec:
            out.append(rec)

    generic = row.get("triggerEvidence")
    if isinstance(generic, list):
        for item in generic:
            if not isinstance(item, dict) or item.get("verified") is False:
                continue

            trigger_type = clean(
                item.get("type")
                or item.get("trigger")
                or item.get("label")
            )
            if not trigger_type:
                continue

            rec = evidence_record(trigger_type, item)
            if rec:
                out.append(rec)

    return out


def identity(item: dict) -> tuple[str, str, str]:
    return (
        clean(item.get("type")).casefold(),
        clean(item.get("sourceDate")),
        clean(item.get("source")),
    )


def merge_history(existing: list, incoming: list) -> list:
    merged = []
    seen = set()

    for item in [*(existing or []), *(incoming or [])]:
        if not isinstance(item, dict):
            continue

        key = identity(item)

        if not key[0] or not key[2] or key in seen:
            continue

        seen.add(key)
        merged.append(item)

    merged.sort(
        key=lambda x: (
            clean(x.get("sourceDate")),
            clean(x.get("type")),
        ),
        reverse=True,
    )

    return merged


def main() -> None:
    scanner = load_json(SCANNER_PATH, {})
    rows = scanner.get("rows") if isinstance(scanner, dict) else None

    if not isinstance(rows, list):
        raise RuntimeError("data/big_move_scanner.json rows missing")

    store = load_json(
        HISTORY_PATH,
        {
            "version": 1,
            "stocks": {},
        },
    )

    if not isinstance(store, dict):
        store = {
            "version": 1,
            "stocks": {},
        }

    stocks = store.setdefault("stocks", {})

    if not isinstance(stocks, dict):
        stocks = {}
        store["stocks"] = stocks

    added = 0
    stocks_with_history = 0

    for row in rows:
        if not isinstance(row, dict):
            continue

        symbol = clean(row.get("symbol")).upper()

        if not symbol:
            continue

        old = stocks.get(symbol, [])

        if not isinstance(old, list):
            old = []

        incoming = current_verified_records(row)
        before = len(old)
        history = merge_history(old, incoming)

        added += max(0, len(history) - before)

        if history:
            stocks[symbol] = history
            stocks_with_history += 1

        row["triggerHistory"] = history
        row["permanentVerifiedTrigger"] = bool(history)

        # IMPORTANT:
        # Do NOT modify row["keyTrigger"] here.
        # keyTrigger is CURRENT only; triggerHistory is permanent.

    now = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )

    store["version"] = 1
    store["updatedAt"] = now
    store["description"] = (
        "Permanent source-backed verified trigger history for Big Move Scanner. "
        "Normal daily rebuilds do not delete prior records. "
        "Current keyTrigger remains separate from historical triggers."
    )

    scanner["triggerHistoryUpdatedAt"] = now

    save_json(HISTORY_PATH, store)
    save_json(SCANNER_PATH, scanner)

    print(
        f"Trigger history updated: "
        f"stocks={stocks_with_history}, new_records={added}"
    )
    print(f"Saved: {HISTORY_PATH.relative_to(ROOT)}")
    print(f"Updated: {SCANNER_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
