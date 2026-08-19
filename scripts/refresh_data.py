import csv, io, json, os, re, time, zipfile
from pathlib import Path
from datetime import datetime, timezone
import requests

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
H={"User-Agent":"Mozilla/5.0 (compatible; IndiaMarketResearchDashboard/1.0)","Accept":"text/csv,application/json,text/plain,*/*"}

NSE_EQ="https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
NSE_SME="https://nsearchives.nseindia.com/emerge/corporates/content/SME_EQUITY_L.csv"
BSE_API="https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w?Group=&Scripcode=&industry=&segment=Equity&status=Active"

def get(url,headers=None,timeout=45):
    h=dict(H)
    if headers:h.update(headers)
    r=requests.get(url,headers=h,timeout=timeout)
    r.raise_for_status()
    return r

def parse_csv(text):
    text=text.lstrip("\ufeff")
    return list(csv.DictReader(io.StringIO(text)))

def load_nse():
    out=[]
    for url,board in [(NSE_EQ,"MAIN"),(NSE_SME,"SME")]:
        rows=parse_csv(get(url).text)
        for x in rows:
            clean={str(k).strip():v for k,v in x.items()}
            sym=(clean.get("SYMBOL") or "").strip()
            if not sym: continue
            name=(clean.get("NAME OF COMPANY") or clean.get("NAME_OF_COMPANY") or sym).strip()
            isin=(clean.get("ISIN NUMBER") or clean.get("ISIN_NUMBER") or "").strip()
            series=(clean.get("SERIES") or "").strip()
            d=(clean.get("DATE OF LISTING") or clean.get("DATE_OF_LISTING") or "").strip()
            out.append({"symbol":sym,"name":name,"isin":isin,"series":series,"listingDate":d,"exchange":"NSE","exchanges":["NSE"],"board":board})
    return out

def load_bse():
    # Official BSE API. If BSE changes/blocks this endpoint, the job preserves existing BSE rows instead of deleting them.
    r=get(BSE_API,{"Referer":"https://www.bseindia.com/","Origin":"https://www.bseindia.com"})
    j=r.json()
    rows=j.get("Table") or j.get("Table1") or (j if isinstance(j,list) else [])
    out=[]
    for x in rows:
        code=str(x.get("SCRIP_CD") or x.get("Scrip_cd") or x.get("SecurityCode") or "").strip()
        name=str(x.get("SCRIP_NAME") or x.get("Scrip_Name") or x.get("SecurityName") or x.get("Issuer_Name") or "").strip()
        sid=str(x.get("SCRIP_ID") or x.get("Scrip_Id") or code).strip()
        isin=str(x.get("ISIN_NUMBER") or x.get("ISIN") or "").strip()
        if not code and not sid: continue
        out.append({"symbol":sid or code,"bseCode":code,"name":name or sid or code,"isin":isin,"exchange":"BSE","exchanges":["BSE"],"board":"MAIN"})
    return out

def old_rows():
    try:return json.loads((DATA/"stocks.json").read_text())
    except:return []

def merge(nse,bse,old):
    # ISIN is primary merge key; exchange:symbol is fallback.
    oldmap={}
    for x in old:
        key=x.get("isin") or f"{x.get('exchange')}:{x.get('symbol')}"
        oldmap[key]=x
    merged={}
    for x in nse+bse:
        key=x.get("isin") or f"{x.get('exchange')}:{x.get('symbol')}"
        if key in merged:
            a=merged[key]
            a["exchanges"]=sorted(set((a.get("exchanges") or [a.get("exchange")])+(x.get("exchanges") or [x.get("exchange")])))
            if x.get("exchange")=="BSE": a["bseCode"]=x.get("bseCode")
            if x.get("exchange")=="NSE": a["nseSymbol"]=x.get("symbol")
            continue
        prev=oldmap.get(key,{})
        y={**prev,**x}
        y.update({
          "sector":prev.get("sector","Unclassified"),"industry":prev.get("industry","Unclassified"),
          "price":prev.get("price"),"changePct":prev.get("changePct"),"volume":prev.get("volume"),
          "turnoverCr":prev.get("turnoverCr"),"marketCapCr":prev.get("marketCapCr"),
          "technicalScore":prev.get("technicalScore"),"sectorStrength":prev.get("sectorStrength"),
          "macroSupport":prev.get("macroSupport"),"valueMigration":prev.get("valueMigration"),
          "futureGrowth":prev.get("futureGrowth"),"fundamentalQuality":prev.get("fundamentalQuality"),
          "capexScore":prev.get("capexScore"),"overallScore":prev.get("overallScore"),
          "dataStatus":prev.get("dataStatus","UNIVERSE_ONLY")
        })
        merged[key]=y
    # Preserve previous BSE rows if BSE endpoint was temporarily unavailable.
    if not bse:
        for k,x in oldmap.items():
            if "BSE" in (x.get("exchanges") or [x.get("exchange")]) and k not in merged: merged[k]=x
    return sorted(merged.values(),key=lambda x:(x.get("name") or "").upper())

def main():
    old=old_rows()
    nse=load_nse()
    try:
        bse=load_bse()
        print("BSE rows:",len(bse))
    except Exception as e:
        print("BSE sync failed; preserving old BSE data:",repr(e))
        bse=[]
    rows=merge(nse,bse,old)
    today=datetime.now(timezone.utc).date().isoformat()
    DATA.mkdir(exist_ok=True)
    (DATA/"stocks.json").write_text(json.dumps(rows,ensure_ascii=False,separators=(",",":")))
    nsec=sum("NSE" in (x.get("exchanges") or [x.get("exchange")]) for x in rows)
    bsec=sum("BSE" in (x.get("exchanges") or [x.get("exchange")]) for x in rows)
    meta={"generatedFrom":"Official NSE/BSE security masters","nseCount":nsec,"bseCount":bsec,"uniqueCount":len(rows),"lastUpdated":today,"mode":"FREE_EOD","note":"Scores are populated only when sufficient source data is collected."}
    (DATA/"meta.json").write_text(json.dumps(meta,indent=2))
    print(meta)

if __name__=="__main__": main()
