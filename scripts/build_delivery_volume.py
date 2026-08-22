import csv
import io
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


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def fetch_mto_for_date(d):
    ddmmyyyy = d.strftime("%d%m%Y")

    url = (
        "https://nsearchives.nseindia.com/"
        f"archives/equities/mto/MTO_{ddmmyyyy}.DAT"
    )

    r = requests.get(
        url,
        headers=HEADERS,
        timeout=45
    )

    r.raise_for_status()

    text = r.text

    delivery = {}

    for line in text.splitlines():
        line = line.strip()

        if not line.startswith("20,"):
            continue

        parts = [
            p.strip()
            for p in line.split(",")
        ]

        # Expected structure:
        # 20, SrNo, Symbol, Series,
        # QtyTraded, DeliverableQty, Delivery%
        if len(parts) < 7:
            continue

        symbol = parts[2]
        series = parts[3]

        try:
            deliverable_qty = float(
                parts[5]
            )
        except Exception:
            continue

        delivery[(symbol, series)] = (
            deliverable_qty
        )

    if not delivery:
        raise ValueError(
            f"No delivery rows found for {d}"
        )

    return delivery


def get_last_trading_sessions(required=6):
    today = (
        datetime.now(timezone.utc)
        .date()
    )

    sessions = []

    # Search far enough back to safely skip
    # weekends + exchange holidays.
    for back in range(0, 20):
        d = today - timedelta(days=back)

        if d.weekday() >= 5:
            continue

        try:
            data = fetch_mto_for_date(d)

            sessions.append(
                {
                    "date": d,
                    "data": data
                }
            )

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


def main():
    stocks_path = DATA / "stocks.json"

    stocks = load_json(
        stocks_path,
        []
    )

    # Today + previous 5 valid trading sessions
    sessions = get_last_trading_sessions(
        required=6
    )

    if not sessions:
        raise RuntimeError(
            "No valid NSE delivery sessions found"
        )

    today_session = sessions[0]
    previous_sessions = sessions[1:6]

    today_date = (
        today_session["date"]
        .isoformat()
    )

    updated = 0

    for row in stocks:
        symbol = row.get("symbol")
        series = row.get("series") or ""

        if not symbol:
            continue

        today_delivery = (
            today_session["data"]
            .get((symbol, series))
        )

        if today_delivery is None:
            today_delivery = (
                today_session["data"]
                .get((symbol, "EQ"))
            )

        previous_values = []

        for session in previous_sessions:
            value = (
                session["data"]
                .get((symbol, series))
            )

            if value is None:
                value = (
                    session["data"]
                    .get((symbol, "EQ"))
                )

            if value is not None:
                previous_values.append(
                    float(value)
                )

        avg_5d = None
        ratio = None

        if previous_values:
            avg_5d = (
                sum(previous_values)
                / len(previous_values)
            )

        if (
            today_delivery is not None
            and avg_5d is not None
            and avg_5d > 0
        ):
            ratio = (
                float(today_delivery)
                / float(avg_5d)
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

        row["deliveryDate"] = today_date

        if ratio is not None:
            updated += 1

    stocks_path.write_text(
        json.dumps(
            stocks,
            ensure_ascii=False,
            separators=(",", ":")
        )
    )

    print({
        "todayTradingDate":
            today_date,

        "validSessionsUsed":
            [
                x["date"].isoformat()
                for x in sessions
            ],

        "deliveryRatiosCalculated":
            updated
    })


if __name__ == "__main__":
    main()
