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
# JSON HELPER
# =========================================================

def load_json(path, default):
    try:
        return json.loads(
            path.read_text()
        )
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

        # NSE MTO:
        # 20,
        # Sr No,
        # Symbol,
        # Series,
        # Quantity Traded,
        # Deliverable Quantity,
        # Delivery %

        if len(parts) < 7:
            continue

        symbol = parts[2]
        series = parts[3]

        traded_qty = to_float(
            parts[4]
        )

        deliverable_qty = to_float(
            parts[5]
        )

        delivery_pct = to_float(
            parts[6]
        )

        if not symbol:
            continue

        delivery[
            (
                symbol,
                series,
            )
        ] = {

            "tradedQty":
                traded_qty,

            "deliverableQty":
                deliverable_qty,

            "deliveryPct":
                delivery_pct,
        }


    if not delivery:

        raise ValueError(
            f"No delivery rows found for {d}"
        )


    return delivery


# =========================================================
# LAST VALID TRADING SESSIONS
# =========================================================

def get_last_trading_sessions(
    required=6
):

    today = (
        datetime.now(timezone.utc)
        .date()
    )

    sessions = []

    # Enough range for weekends
    # and exchange holidays.

    for back in range(0, 20):

        d = today - timedelta(
            days=back
        )

        if d.weekday() >= 5:
            continue

        try:

            data = fetch_mto_for_date(
                d
            )

            sessions.append({

                "date":
                    d,

                "data":
                    data,
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
            f"Warning: only "
            f"{len(sessions)} valid trading "
            f"sessions found"
        )


    return sessions


# =========================================================
# FIND SYMBOL
# =========================================================

def find_delivery_record(
    session_data,
    symbol,
    series,
):

    record = session_data.get(
        (
            symbol,
            series,
        )
    )

    # Main-board fallback

    if record is None:

        record = session_data.get(
            (
                symbol,
                "EQ",
            )
        )

    return record


# =========================================================
# MAIN
# =========================================================

def main():

    stocks_path = (
        DATA /
        "stocks.json"
    )

    meta_path = (
        DATA /
        "meta.json"
    )


    stocks = load_json(
        stocks_path,
        [],
    )


    # Today + previous 5
    # valid trading sessions

    sessions = (
        get_last_trading_sessions(
            required=6
        )
    )


    if not sessions:

        raise RuntimeError(
            "No valid NSE delivery sessions found"
        )


    today_session = (
        sessions[0]
    )

    previous_sessions = (
        sessions[1:6]
    )

    today_date = (
        today_session["date"]
        .isoformat()
    )


    updated_today_volume = 0
    updated_delivery_volume = 0
    updated_ratio = 0
    updated_delivery_pct = 0


    # =====================================================
    # PROCESS STOCKS
    # =====================================================

    for row in stocks:

        symbol = row.get(
            "symbol"
        )

        series = (
            row.get("series")
            or ""
        )

        if not symbol:
            continue


        # -------------------------------------------------
        # TODAY MTO
        # -------------------------------------------------

        today_record = (
            find_delivery_record(
                today_session["data"],
                symbol,
                series,
            )
        )


        today_volume = None
        today_delivery = None
        official_delivery_pct = None


        if today_record:

            today_volume = (
                to_float(
                    today_record.get(
                        "tradedQty"
                    )
                )
            )

            today_delivery = (
                to_float(
                    today_record.get(
                        "deliverableQty"
                    )
                )
            )

            official_delivery_pct = (
                to_float(
                    today_record.get(
                        "deliveryPct"
                    )
                )
            )


        # -------------------------------------------------
        # PREVIOUS 5 DELIVERY SESSIONS
        # -------------------------------------------------

        previous_values = []


        for session in previous_sessions:

            record = (
                find_delivery_record(
                    session["data"],
                    symbol,
                    series,
                )
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
        # 5D AVG DELIVERY
        # -------------------------------------------------

        avg_5d = None

        if previous_values:

            avg_5d = (
                sum(previous_values)
                /
                len(previous_values)
            )


        # -------------------------------------------------
        # DELIVERY TIMES
        #
        # Today Delivery /
        # Previous 5-session Avg Delivery
        # -------------------------------------------------

        ratio = None

        if (
            today_delivery is not None
            and avg_5d is not None
            and avg_5d > 0
        ):

            ratio = (
                today_delivery
                /
                avg_5d
            )


        # -------------------------------------------------
        # DELIVERY %
        # -------------------------------------------------

        delivery_pct = None


        # First preference:
        # Official NSE MTO %

        if official_delivery_pct is not None:

            delivery_pct = (
                official_delivery_pct
            )


        # Safety fallback

        elif (
            today_delivery is not None
            and today_volume is not None
            and today_volume > 0
        ):

            delivery_pct = (
                today_delivery
                /
                today_volume
                *
                100
            )


        # =================================================
        # SAVE TODAY TOTAL VOLUME
        # =================================================
        #
        # IMPORTANT:
        # NSE MTO Quantity Traded is now
        # authoritative for website Today Volume.
        #

        row["todayVolume"] = (

            round(today_volume)

            if today_volume is not None

            else None
        )


        # Keep old "volume" field synchronized
        # for frontend/backward compatibility.

        row["volume"] = (

            round(today_volume)

            if today_volume is not None

            else None
        )


        # Helpful source cross-check

        row["mtoTradedVolume"] = (

            round(today_volume)

            if today_volume is not None

            else None
        )


        # =================================================
        # SAVE DELIVERY DATA
        # =================================================

        row["todayDeliveryVolume"] = (

            round(today_delivery)

            if today_delivery is not None

            else None
        )


        row["avg5DayDeliveryVolume"] = (

            round(
                avg_5d,
                2,
            )

            if avg_5d is not None

            else None
        )


        row["deliveryVolumeRatio"] = (

            round(
                ratio,
                2,
            )

            if ratio is not None

            else None
        )


        row["deliveryPct"] = (

            round(
                delivery_pct,
                2,
            )

            if delivery_pct is not None

            else None
        )


        row["deliveryDate"] = (
            today_date
        )


        # =================================================
        # COUNTS
        # =================================================

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
    # UPDATE META.JSON
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


    meta["volumeSource"] = (
        "Official NSE MTO Quantity Traded"
    )


    # =====================================================
    # WRITE META.JSON
    # =====================================================

    meta_path.write_text(

        json.dumps(
            meta,
            indent=2,
        )
    )


    # =====================================================
    # LOG
    # =====================================================

    print({

        "todayTradingDate":
            today_date,

        "validSessionsUsed": [

            x["date"].isoformat()
            for x in sessions
        ],

        "todayVolumesCalculated":
            updated_today_volume,

        "deliveryVolumesCalculated":
            updated_delivery_volume,

        "deliveryRatiosCalculated":
            updated_ratio,

        "deliveryPctCalculated":
            updated_delivery_pct,

        "volumeSource":
            "NSE MTO Quantity Traded",
    })


if __name__ == "__main__":
    main()
