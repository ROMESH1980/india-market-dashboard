import csv, io, json, zipfile
from pathlib import Path
from datetime import datetime, timezone
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
    rows=merge(load_nse(),old_rows())
    DATA.mkdir(exist_ok=True)
    today=datetime.now(timezone.utc).date().isoformat()
    (DATA/"stocks.json").write_text(json.dumps(rows,ensure_ascii=False,separators=(",",":")))
    meta={
        "generatedFrom":"Official NSE Equity + SME security master",
        "nseCount":len(rows),
        "uniqueCount":len(rows),
        "lastUpdated":today,
        "mode":"FREE_EOD",
        "note":"NSE-only dashboard."
    }
    (DATA/"meta.json").write_text(json.dumps(meta,indent=2))
    print(meta)

if __name__=="__main__":
    main()
