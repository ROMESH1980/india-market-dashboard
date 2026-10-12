/* Shared surveillance lookup. Source: data/surveillance.json (verified only).
   Missing data MUST NOT be interpreted as "not under surveillance". */
(function(){
  "use strict";
  const statuses = new Map();
  let verifiedDate = "";
  const valid = new Set(["ASM","GSM","ESM"]);
  const ready = fetch("data/surveillance.json?v="+Date.now(),{cache:"no-store"})
    .then(r=>{if(!r.ok) throw Error("surveillance data unavailable");return r.json();})
    .then(data=>{
      if (!data || data.verified !== true || !data.asOfDate || !Array.isArray(data.rows)) return;
      verifiedDate=String(data.asOfDate);
      data.rows.forEach(r=>{
        const symbol=String(r.symbol||"").trim().toUpperCase();
        const tags=(Array.isArray(r.statuses)?r.statuses:[])
          .map(x=>String(x).toUpperCase()).filter(x=>valid.has(x));
        if(symbol && tags.length) statuses.set(symbol,[...new Set(tags)]);
      });
    }).catch(()=>{});
  function lookup(row){
    const key=String(row?.symbol||"").trim().toUpperCase();
    const tags=statuses.get(key)||[];
    return {text:tags.length?tags.join(" + "):"Unverified", tags, date:verifiedDate};
  }
  window.MMRSurveillance={ready,lookup};
})();
