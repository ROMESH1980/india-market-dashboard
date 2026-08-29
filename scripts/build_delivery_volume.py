import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NSEMarketDashboard/1.0)",
    "Accept": "text/plain,text/csv,*/*",
}

# =========================================================
# DEBUG ONLY
# =========================================================

DEBUG_SYMBOLS = {
    "NIRAJISPAT",
    "SECMARK",
}

DEBUG_SESSION_COUNT = 12


# =========================================================
# JSON HELPER
# =========================================================

def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


# =========================================================
# SAFE NUMBER
# =========================================================

def to_float(value):
    try:
        if value is None:
            return None

        value = str(value).strip()

        if value == "":
            return None

        return float(value)

    except Exception:
        return None


# =========================================================
# FETCH NSE MTO FILE
# =========================================================

def fetch_mto_for_date(d):

    ddmmyyyy = d.strftime("%d%m%Y")

    url = (
        "https://nsearchives.nseindia.com/"
        f"archives/equities/mto/MTO_{ddmmyyyy}.DAT"
    )

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=45,
    )

    r.raise_for_status()

    delivery = {}

    for line in r.text.splitlines():

        line = line.strip()

        if not line.startswith("20,"):
            continue

        parts = [
            p.strip()
            for p in line.split(",")
        ]

        if len(parts) < 7:
            continue

        symbol = parts[2]
        series = parts[3]

        traded_qty = to_float(parts[4])
        deliverable_qty = to_float(parts[5])
        delivery_pct = to_float(parts[6])

        if not symbol:
            continue

        delivery[(symbol, series)] = {
            "tradedQty": traded_qty,
            "deliverableQty": deliverable_qty,
            "deliveryPct": delivery_pct,
        }

    if not delivery:
        raise ValueError(
            f"No delivery rows found for {d}"
        )

    return delivery


# =========================================================
# GET VALID NSE TRADING SESSIONS
# =========================================================

def get_last_trading_sessions(required=12):

    today = datetime.now(timezone.utc).date()

    sessions = []

    # Search deeper because debug needs
    # historical records beyond only 5 sessions.
    for back in range(0, 35):

        d = today - timedelta(days=back)

        if d.weekday() >= 5:
            continue

        try:

            data = fetch_mto_for_date(d)

            sessions.append({
                "date": d,
                "data": data,
            })

            print(
                f"Delivery session loaded: "
                f"{d} ({len(data)} rows)"
            )

            if len(sessions) >= required:
                break

        except Exception as e:

            print(
                f"Skipping {d}: {e}"
            )

    if len(sessions) < required:

        print(
            f"Warning: only {len(sessions)} "
            f"valid trading sessions found"
        )

    return sessions


# =========================================================
# FIND SYMBOL / SERIES
# =========================================================

def find_delivery_record(
    session_data,
    symbol,
    series,
):

    record = session_data.get(
        (symbol, series)
    )

    if record is None:

        record = session_data.get(
            (symbol, "EQ")
        )

    return record


# =========================================================
# DEBUG PRINT
# =========================================================

def print_symbol_debug(
    symbol,
    series,
    sessions,
):

    print("\n")
    print("=" * 70)
    print(f"DEBUG DELIVERY HISTORY: {symbol}")
    print(f"Series requested: {series}")
    print("=" * 70)

    available_delivery_values = []

    for session in sessions:

        d = session["date"]

        record = find_delivery_record(
            session["data"],
            symbol,
            series,
        )

        if record is None:

            print(
                f"{d} | MISSING"
            )

            continue

        traded = to_float(
            record.get("tradedQty")
        )

        delivered = to_float(
            record.get("deliverableQty")
        )

        pct = to_float(
            record.get("deliveryPct")
        )

        print(
            f"{d}"
            f" | Traded={traded}"
            f" | Delivery={delivered}"
            f" | Delivery%={pct}"
        )

        if delivered is not None:

            available_delivery_values.append({
                "date": d.isoformat(),
                "value": delivered,
            })

    print("-" * 70)

    print(
        "Available delivery records:"
    )

    for x in available_delivery_values:

        print(
            f"{x['date']} = {x['value']}"
        )

    print("=" * 70)
    print("\n")


# =========================================================
# MAIN
# =========================================================

def main():

    stocks_path = DATA / "stocks.json"
    meta_path = DATA / "meta.json"

    stocks = load_json(
        stocks_path,
        [],
    )

    # Load more sessions for debugging
    sessions = get_last_trading_sessions(
        required=DEBUG_SESSION_COUNT
    )

    if not sessions:

        raise RuntimeError(
            "No valid NSE delivery sessions found"
        )

    today_session = sessions[0]

    # Existing website calculation:
    # previous 5 GLOBAL NSE sessions.
    previous_sessions = sessions[1:6]

    today_date = (
        today_session["date"].isoformat()
    )

    print("\n")
    print("==================================================")
    print("GLOBAL SESSIONS USED FOR CURRENT 5D CALCULATION")
    print("==================================================")

    for session in previous_sessions:
        print(
            session["date"].isoformat()
        )

    print("==================================================")
    print("\n")


    updated_today_volume = 0
    updated_delivery_volume = 0
    updated_ratio = 0
    updated_delivery_pct = 0

    full_5day_average_count = 0
    incomplete_5day_count = 0


    # =====================================================
    # PROCESS STOCKS
    # =====================================================

    for row in stocks:

        symbol = row.get("symbol")

        series = (
            row.get("series")
            or ""
        )

        if not symbol:
            continue


        # -------------------------------------------------
        # PRINT DEBUG HISTORY
        # -------------------------------------------------

        if symbol in DEBUG_SYMBOLS:

            print_symbol_debug(
                symbol,
                series,
                sessions,
            )


        # -------------------------------------------------
        # TODAY
        # -------------------------------------------------

        today_record = find_delivery_record(
            today_session["data"],
            symbol,
            series,
        )

        today_volume = None
        today_delivery = None
        official_delivery_pct = None

        if today_record:

            today_volume = to_float(
                today_record.get(
                    "tradedQty"
                )
            )

            today_delivery = to_float(
                today_record.get(
                    "deliverableQty"
                )
            )

            official_delivery_pct = to_float(
                today_record.get(
                    "deliveryPct"
                )
            )


        # -------------------------------------------------
        # PREVIOUS 5 GLOBAL NSE SESSIONS
        # -------------------------------------------------

        previous_values = []

        for session in previous_sessions:

            record = find_delivery_record(
                session["data"],
                symbol,
                series,
            )

            if not record:
                continue

            value = to_float(
                record.get(
                    "deliverableQty"
                )
            )

            if value is not None:

                previous_values.append(
                    value
                )


        # -------------------------------------------------
        # STRICT CURRENT RULE:
        # 5 / 5 GLOBAL SESSION VALUES REQUIRED
        # -------------------------------------------------

        avg_5d = None

        if len(previous_values) == 5:

            avg_5d = (
                sum(previous_values)
                / 5
            )

            full_5day_average_count += 1

        else:

            incomplete_5day_count += 1


        # -------------------------------------------------
        # DELIVERY TIMES
        # -------------------------------------------------

        ratio = None

        if (
            today_delivery is not None
            and avg_5d is not None
            and avg_5d > 0
        ):

            ratio = (
                today_delivery
                / avg_5d
            )


        # -------------------------------------------------
        # DELIVERY %
        # -------------------------------------------------

        delivery_pct = None

        if official_delivery_pct is not None:

            delivery_pct = (
                official_delivery_pct
            )

        elif (
            today_delivery is not None
            and today_volume is not None
            and today_volume > 0
        ):

            delivery_pct = (
                today_delivery
                / today_volume
                * 100
            )


        # -------------------------------------------------
        # SAVE
        # -------------------------------------------------

        row["todayVolume"] = (
            round(today_volume)
            if today_volume is not None
            else None
        )

        row["volume"] = (
            round(today_volume)
            if today_volume is not None
            else None
        )

        row["mtoTradedVolume"] = (
            round(today_volume)
            if today_volume is not None
            else None
        )

        row["todayDeliveryVolume"] = (
            round(today_delivery)
            if today_delivery is not None
            else None
        )

        row["avg5DayDeliveryVolume"] = (
            round(avg_5d, 2)
            if avg_5d is not None
            else None
        )

        row["deliveryVolumeRatio"] = (
            round(ratio, 2)
            if ratio is not None
            else None
        )

        row["deliveryPct"] = (
            round(delivery_pct, 2)
            if delivery_pct is not None
            else None
        )

        row["deliveryDate"] = (
            today_date
        )

        row["deliveryHistoryCount"] = (
            len(previous_values)
        )


        # -------------------------------------------------
        # EXTRA DEBUG FOR TARGET SYMBOLS
        # -------------------------------------------------

        if symbol in DEBUG_SYMBOLS:

            print(
                f"CURRENT CALCULATION {symbol}"
            )

            print(
                f"Today Delivery = "
                f"{today_delivery}"
            )

            print(
                f"Previous values used = "
                f"{previous_values}"
            )

            print(
                f"History count = "
                f"{len(previous_values)}"
            )

            print(
                f"5D Avg = "
                f"{avg_5d}"
            )

            print(
                f"Delivery Times = "
                f"{ratio}"
            )

            print("\n")


        # -------------------------------------------------
        # COUNTS
        # -------------------------------------------------

        if today_volume is not None:
            updated_today_volume += 1

        if today_delivery is not None:
            updated_delivery_volume += 1

        if ratio is not None:
            updated_ratio += 1

        if delivery_pct is not None:
            updated_delivery_pct += 1


    # =====================================================
    # WRITE STOCKS.JSON
    # =====================================================

    stocks_path.write_text(
        json.dumps(
            stocks,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


    # =====================================================
    # META
    # =====================================================

    meta = load_json(
        meta_path,
        {},
    )

    meta["deliveryDate"] = (
        today_date
    )

    meta["deliverySessionsUsed"] = [
        x["date"].isoformat()
        for x in sessions
    ]

    meta["todayVolumeCount"] = (
        updated_today_volume
    )

    meta["deliveryVolumeCount"] = (
        updated_delivery_volume
    )

    meta["deliveryRatioCount"] = (
        updated_ratio
    )

    meta["deliveryPctCount"] = (
        updated_delivery_pct
    )

    meta["full5DayDeliveryAverageCount"] = (
        full_5day_average_count
    )

    meta["incomplete5DayDeliveryCount"] = (
        incomplete_5day_count
    )

    meta["deliveryAverageRule"] = (
        "Strict previous 5 global NSE sessions required"
    )

    meta["volumeSource"] = (
        "Official NSE MTO Quantity Traded"
    )

    meta_path.write_text(
        json.dumps(
            meta,
            indent=2,
        )
    )


    # =====================================================
    # FINAL LOG
    # =====================================================

    print({
        "todayTradingDate":
            today_date,

        "debugSessionsLoaded":
            len(sessions),

        "current5DCalculationSessions": [
            x["date"].isoformat()
            for x in previous_sessions
        ],

        "todayVolumesCalculated":
            updated_today_volume,

        "deliveryVolumesCalculated":
            updated_delivery_volume,

        "full5DayAveragesCalculated":
            full_5day_average_count,

        "incomplete5DayHistories":
            incomplete_5day_count,

        "deliveryRatiosCalculated":
            updated_ratio,

        "deliveryPctCalculated":
            updated_delivery_pct,

        "volumeSource":
            "NSE MTO",
    })


if __name__ == "__main__":
    main()
