import csv
import io
import json
import zipfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

H = {
    "User-Agent": "Mozilla/5.0 (compatible; NSEMarketDashboard/1.0)",
    "Accept": "text/csv,*/*",
}

NSE_EQ = (
    "https://nsearchives.nseindia.com/"
    "content/equities/EQUITY_L.csv"
)

NSE_SME = (
    "https://nsearchives.nseindia.com/"
    "emerge/corporates/content/SME_EQUITY_L.csv"
)


def get(url, timeout=45):
    r = requests.get(
        url,
        headers=H,
        timeout=timeout,
    )

    r.raise_for_status()

    return r


def parse_csv(text):
    return list(
        csv.DictReader(
            io.StringIO(
                text.lstrip("\ufeff")
            )
        )
    )


# =========================================================
# LOAD NSE EOD BHAVCOPY
# =========================================================

def load_eod_prices():

    today = (
        datetime.now(timezone.utc)
        .date()
    )

    for back in range(0, 7):

        d = today - timedelta(days=back)

        # Saturday / Sunday skip
        if d.weekday() >= 5:
            continue

        yyyymmdd = d.strftime("%Y%m%d")

        url = (
            "https://nsearchives.nseindia.com/content/cm/"
            f"BhavCopy_NSE_CM_0_0_0_{yyyymmdd}_F_0000.csv.zip"
        )

        try:

            r = get(url)

            with zipfile.ZipFile(
                io.BytesIO(r.content)
            ) as z:

                names = z.namelist()

                if not names:
                    continue

                target = names[0]

                text = z.read(
                    target
                ).decode(
                    "utf-8-sig",
                    errors="ignore",
                )

                rows = list(
                    csv.DictReader(
                        io.StringIO(text)
                    )
                )

                prices = {}

                for x in rows:

                    clean = {
                        str(k).strip().upper():
                        str(v).strip()

                        for k, v
                        in x.items()
                    }

                    symbol = (
                        clean.get("TCKRSYMB")
                        or clean.get("SYMBOL")
                        or ""
                    )

                    series = (
                        clean.get("SCTYSRS")
                        or clean.get("SERIES")
                        or ""
                    )

                    if not symbol:
                        continue


                    # =========================
                    # PRICE
                    # =========================

                    close = (
                        clean.get("CLSPRIC")
                        or clean.get("CLOSE")
                        or clean.get("CLOSE_PRICE")
                    )

                    prev = (
                        clean.get("PRVSCLSGPRIC")
                        or clean.get("PREVCLOSE")
                        or clean.get("PREV_CLOSE")
                    )


                    # =========================
                    # TOTAL TRADED VOLUME
                    # =========================

                    volume = (
                        clean.get("TTLTRADGQTY")
                        or clean.get("TOTTRDQTY")
                        or clean.get(
                            "TOTAL_TRADED_QUANTITY"
                        )
                    )


                    # =========================
                    # TOTAL TRADED VALUE
                    # =========================

                    value = (
                        clean.get("TTLTRFVAL")
                        or clean.get("TOTTRDVAL")
                        or clean.get(
                            "TOTAL_TRADED_VALUE"
                        )
                    )


                    # =========================
                    # CONVERT TO NUMBERS
                    # =========================

                    try:
                        close = float(close)
                    except Exception:
                        close = None

                    try:
                        prev = float(prev)
                    except Exception:
                        prev = None

                    try:
                        volume = float(volume)
                    except Exception:
                        volume = None

                    try:
                        value = float(value)
                    except Exception:
                        value = None


                    # =========================
                    # CHANGE %
                    # =========================

                    change_pct = None

                    if (
                        close is not None
                        and prev not in (None, 0)
                    ):

                        change_pct = (
                            (
                                close - prev
                            )
                            / prev
                        ) * 100


                    # =========================
                    # SAVE EOD DATA
                    # =========================

                    prices[
                        (
                            symbol,
                            series,
                        )
                    ] = {

                        "price":
                            close,

                        "changePct":
                            change_pct,

                        # Keep old field
                        "volume":
                            volume,

                        # New explicit field
                        "todayVolume":
                            volume,

                        "turnoverCr": (
                            value / 10000000
                            if value is not None
                            else None
                        ),

                        "priceDate":
                            d.isoformat(),
                    }


                print(
                    f"UDiFF EOD file loaded for {d}: "
                    f"{len(prices)} securities"
                )

                return (
                    prices,
                    d.isoformat(),
                )


        except Exception as e:

            print(
                f"UDiFF EOD unavailable for {d}: {e}"
            )


    print(
        "No recent NSE UDiFF EOD file found"
    )

    return {}, None


# =========================================================
# LOAD NSE SECURITY MASTER
# =========================================================

def load_nse():

    out = []

    for url, board in [

        (
            NSE_EQ,
            "MAIN",
        ),

        (
            NSE_SME,
            "SME",
        ),

    ]:

        for x in parse_csv(
            get(url).text
        ):

            clean = {
                str(k).strip(): v
                for k, v
                in x.items()
            }

            sym = (
                clean.get("SYMBOL")
                or ""
            ).strip()

            if not sym:
                continue


            out.append({

                "symbol":
                    sym,

                "name": (
                    clean.get(
                        "NAME OF COMPANY"
                    )
                    or clean.get(
                        "NAME_OF_COMPANY"
                    )
                    or sym
                ).strip(),

                "isin": (
                    clean.get(
                        "ISIN NUMBER"
                    )
                    or clean.get(
                        "ISIN_NUMBER"
                    )
                    or ""
                ).strip(),

                "series": (
                    clean.get("SERIES")
                    or ""
                ).strip(),

                "listingDate": (
                    clean.get(
                        "DATE OF LISTING"
                    )
                    or clean.get(
                        "DATE_OF_LISTING"
                    )
                    or ""
                ).strip(),

                "exchange":
                    "NSE",

                "board":
                    board,
            })

    return out


# =========================================================
# LOAD OLD STOCKS.JSON
# =========================================================

def old_rows():

    try:

        return json.loads(
            (
                DATA /
                "stocks.json"
            ).read_text()
        )

    except Exception:

        return []


# =========================================================
# MERGE OLD + NEW UNIVERSE
# =========================================================

def merge(
    nse,
    old,
):

    oldmap = {}

    for x in old:

        key = (
            x.get("isin")
            or x.get("symbol")
        )

        if key:
            oldmap[key] = x


    merged = {}


    for x in nse:

        key = (
            x.get("isin")
            or x.get("symbol")
        )

        prev = oldmap.get(
            key,
            {},
        )

        y = {
            **prev,
            **x,
        }


        for field, default in [

            (
                "sector",
                "Unclassified",
            ),

            (
                "industry",
                "Unclassified",
            ),

            (
                "price",
                None,
            ),

            (
                "changePct",
                None,
            ),

            (
                "volume",
                None,
            ),

            # New explicit field
            (
                "todayVolume",
                None,
            ),

            (
                "turnoverCr",
                None,
            ),

            (
                "sectorStrength",
                None,
            ),

            (
                "macroSupport",
                None,
            ),

            (
                "valueMigration",
                None,
            ),

            (
                "futureGrowth",
                None,
            ),

            (
                "fundamentalQuality",
                None,
            ),

            (
                "capexScore",
                None,
            ),

            (
                "overallScore",
                None,
            ),

            (
                "dataStatus",
                "UNIVERSE_ONLY",
            ),

        ]:

            if field not in y:
                y[field] = default


        y["exchange"] = "NSE"


        y.pop(
            "exchanges",
            None,
        )

        y.pop(
            "bseCode",
            None,
        )


        merged[key] = y


    return sorted(

        merged.values(),

        key=lambda x: (
            x.get("name")
            or ""
        ).upper(),

    )


# =========================================================
# MAIN
# =========================================================

def main():

    rows = merge(
        load_nse(),
        old_rows(),
    )


    prices, market_date = (
        load_eod_prices()
    )


    # =========================
    # SECTOR MAP
    # =========================

    try:

        sector_map = json.loads(
            (
                DATA /
                "sector_map.json"
            ).read_text()
        )

    except Exception:

        sector_map = {}


    matched_prices = 0


    # =========================
    # APPLY EOD DATA
    # =========================

    for row in rows:

        symbol = row.get(
            "symbol"
        )

        series = (
            row.get("series")
            or ""
        )


        # -------------------------
        # Sector / Industry
        # -------------------------

        s = sector_map.get(
            symbol,
            {},
        )

        if s:

            row["sector"] = s.get(
                "sector",
                row.get(
                    "sector",
                    "Unclassified",
                ),
            )

            row["industry"] = s.get(
                "industry",
                row.get(
                    "industry",
                    "Unclassified",
                ),
            )


        # -------------------------
        # EOD Price Data
        # -------------------------

        p = prices.get(
            (
                symbol,
                series,
            )
        )


        if p is None:

            p = prices.get(
                (
                    symbol,
                    "",
                )
            )


        if p:

            row["price"] = (
                p.get("price")
            )

            row["changePct"] = (
                p.get(
                    "changePct"
                )
            )


            # OLD COMPATIBILITY FIELD
            row["volume"] = (
                p.get(
                    "volume"
                )
            )


            # NEW EXPLICIT TODAY VOLUME
            row["todayVolume"] = (
                p.get(
                    "todayVolume"
                )
            )


            row["turnoverCr"] = (
                p.get(
                    "turnoverCr"
                )
            )

            row["priceDate"] = (
                p.get(
                    "priceDate"
                )
            )

            row["dataStatus"] = (
                "EOD_READY"
            )


            matched_prices += 1


    # =========================
    # WRITE STOCKS.JSON
    # =========================

    DATA.mkdir(
        exist_ok=True
    )


    today = (
        datetime.now(
            timezone.utc
        )
        .date()
        .isoformat()
    )


    (
        DATA /
        "stocks.json"
    ).write_text(

        json.dumps(

            rows,

            ensure_ascii=False,

            separators=(
                ",",
                ":",
            ),

        )
    )


    # =========================
    # META.JSON
    # =========================

    meta = {

        "generatedFrom": (
            "Official NSE Equity + SME security master "
            "+ NSE UDiFF EOD bhavcopy"
        ),

        "nseCount":
            len(rows),

        "uniqueCount":
            len(rows),

        "eodPriceCount":
            len(prices),

        "matchedPriceCount":
            matched_prices,

        # Actual NSE bhavcopy date
        "marketDate":
            market_date,

        "lastUpdated":
            today,

        "mode":
            "FREE_EOD",

        "note":
            "NSE-only dashboard.",
    }


    (
        DATA /
        "meta.json"
    ).write_text(

        json.dumps(
            meta,
            indent=2,
        )
    )


    print(meta)


if __name__ == "__main__":
    main()
