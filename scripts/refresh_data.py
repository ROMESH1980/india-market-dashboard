import csv, io, json, zipfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
import requests

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
H={"User-Agent":"Mozilla/5.0 (compatible; NSEMarketDashboard/1.0)","Accept":"text/csv,*/*"}
NSE_EQ="https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
NSE_SME="https://nsearchives.nseindia.com/emerge/corporates/content/SME_EQUITY_L.csv"

def get(url,timeout=45):
    r=requests.get(url,headers=H,timeout=timeout)
    r.raise_for_status()
    return r

def parse_csv(text):
    return list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
def load_eod_prices():
    today = datetime.now(timezone.utc).date()

    # Weekend/holiday ke case me pichhle kuch din try karega
    for back in range(0, 7):
        d = today - timedelta(days=back)

        if d.weekday() >= 5:
            continue

        ddmmyy = d.strftime("%d%m%y")
        ddmmyyyy = d.strftime("%d%m%Y")

        url = f"https://nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PR{ddmmyy}.zip"

        try:
            r = get(url)

            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                target = None

                for name in z.namelist():
                    low = name.lower()

                    if low == f"bc{ddmmyyyy}.csv":
                        target = name
                        break

                if not target:
                    continue

                text = z.read(target).decode("utf-8", errors="ignore")
                rows = list(csv.DictReader(io.StringIO(text)))

                prices = {}

                for x in rows:
                    clean = {
                        str(k).strip().upper(): str(v).strip()
                        for k, v in x.items()
                    }

                    symbol = clean.get("SYMBOL", "")
                    series = clean.get("SERIES", "")

                    if not symbol:
                        continue

                    close = clean.get("CLOSE") or clean.get("CLOSE_PRICE")
                    prev = clean.get("PREVCLOSE") or clean.get("PREV_CLOSE")
                    volume = clean.get("TOTTRDQTY") or clean.get("TOTAL_TRADED_QUANTITY")
                    value = clean.get("TOTTRDVAL") or clean.get("TOTAL_TRADED_VALUE")

                    try:
                        close = float(close)
                    except:
                        close = None

                    try:
                        prev = float(prev)
                    except:
                        prev = None

                    try:
                        volume = float(volume)
                    except:
                        volume = None

                    try:
                        value = float(value)
                    except:
                        value = None

                    change_pct = None

                    if close is not None and prev not in (None, 0):
                        change_pct = ((close - prev) / prev) * 100

                    prices[(symbol, series)] = {
                        "price": close,
                        "changePct": change_pct,
                        "volume": volume,
                        "turnoverCr": value / 10000000 if value is not None else None,
                        "priceDate": d.isoformat()
                    }

                print(f"EOD price file loaded for {d}: {len(prices)} securities")
                return prices

        except Exception as e:
            print(f"EOD file unavailable for {d}: {e}")

    print("No recent NSE EOD price file found")
    return {}
def load_nse():
    out=[]
    for url,board in [(NSE_EQ,"MAIN"),(NSE_SME,"SME")]:
        for x in parse_csv(get(url).text):
            clean={str(k).strip():v for k,v in x.items()}
            sym=(clean.get("SYMBOL") or "").strip()
            if not sym:
                continue
            out.append({
                "symbol":sym,
                "name":(clean.get("NAME OF COMPANY") or clean.get("NAME_OF_COMPANY") or sym).strip(),
                "isin":(clean.get("ISIN NUMBER") or clean.get("ISIN_NUMBER") or "").strip(),
                "series":(clean.get("SERIES") or "").strip(),
                "listingDate":(clean.get("DATE OF LISTING") or clean.get("DATE_OF_LISTING") or "").strip(),
                "exchange":"NSE",
                "board":board
            })
    return out

def old_rows():
    try:
        return json.loads((DATA/"stocks.json").read_text())
    except:
        return []

def merge(nse,old):
    oldmap={}
    for x in old:
        key=x.get("isin") or x.get("symbol")
        if key:
            oldmap[key]=x
    merged={}
    for x in nse:
        key=x.get("isin") or x.get("symbol")
        prev=oldmap.get(key,{})
        y={**prev,**x}
        for field,default in [
            ("sector","Unclassified"),("industry","Unclassified"),("price",None),
            ("changePct",None),("volume",None),("turnoverCr",None),
            ("sectorStrength",None),("macroSupport",None),("valueMigration",None),
            ("futureGrowth",None),("fundamentalQuality",None),
            ("capexScore",None),("overallScore",None),("dataStatus","UNIVERSE_ONLY")
        ]:
            if field not in y:
                y[field]=default
        y["exchange"]="NSE"
        y.pop("exchanges",None)
        y.pop("bseCode",None)
        merged[key]=y
    return sorted(merged.values(),key=lambda x:(x.get("name") or "").upper())

def main():
    rows = merge(load_nse(), old_rows())
    prices = load_eod_prices()

    for row in rows:
        symbol = row.get("symbol")
        series = row.get("series") or ""

        p = prices.get((symbol, series))

        if p is None:
            p = prices.get((symbol, ""))

        if p:
            row["price"] = p.get("price")
            row["changePct"] = p.get("changePct")
            row["volume"] = p.get("volume")
            row["turnoverCr"] = p.get("turnoverCr")
            row["priceDate"] = p.get("priceDate")
            row["dataStatus"] = "EOD_READY"

    DATA.mkdir(exist_ok=True)

    today = datetime.now(timezone.utc).date().isoformat()

    (DATA / "stocks.json").write_text(
        json.dumps(
            rows,
            ensure_ascii=False,
            separators=(",", ":")
        )
    )

    meta = {
        "generatedFrom": "Official NSE Equity + SME security master + NSE EOD price file",
        "nseCount": len(rows),
        "uniqueCount": len(rows),
        "eodPriceCount": len(prices),
        "lastUpdated": today,
        "mode": "FREE_EOD",
        "note": "NSE-only dashboard."
    }

    (DATA / "meta.json").write_text(
        json.dumps(meta, indent=2)
    )

    print(meta)

if __name__ == "__main__":
    main()
