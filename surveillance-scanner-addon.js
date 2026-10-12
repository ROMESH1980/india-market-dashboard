/* Page 2 surveillance: load after early-signal-addon.js.
   Integrates with existing columns, filters, pagination, drawer and CSV. */
(function(){
 "use strict";
 if(typeof columns==="undefined" || !window.MMRSurveillance) return;
 const index=columns.findIndex(c=>c.field==="earlySignalStage");
 if(index<0 || columns.some(c=>c.field==="surveillanceStatus")) return;
 columns.splice(index+1,0,{
   field:"surveillanceStatus",label:"Surveillance",type:"select",filterable:true,
   options:["ASM","GSM","ESM","Unverified"]
 });
 const enrich=enrichRow;
 enrichRow=function(row,i){
   const result=enrich(row,i);
   result.surveillanceStatus=window.MMRSurveillance.lookup(result).text;
   return result;
 };
 // Multi-tag matches individual status filters.
 const originalFilter=passesColumnFilter;
 passesColumnFilter=function(row,field,state){
   if(field==="surveillanceStatus" && state.value){
     const tags=window.MMRSurveillance.lookup(row).tags;
     return state.value==="Unverified" ? !tags.length : tags.includes(state.value);
   }
   return originalFilter(row,field,state);
 };
 const render=renderTable;
 renderTable=function(){
   render();
   const trs=[...document.querySelectorAll("#tableBody tr")];
   const rows=filteredRows.slice((currentPage-1)*pageSize,currentPage*pageSize);
   if(!rows.length){
     const td=trs[0]?.querySelector("td[colspan]");
     if(td) td.colSpan=columns.length;
     return;
   }
   rows.forEach((row,i)=>{
     const tr=trs[i]; if(!tr) return;
     const td=tr.insertCell(4);
     const info=window.MMRSurveillance.lookup(row);
     td.className="surveillance-status";
     td.title=info.date?"Verified list: "+info.date:"No verified list available";
     td.textContent=info.text;
   });
   syncTopScrollbar();
 };
 const drawer=openDrawer;
 openDrawer=function(row){
   drawer(row);
   const overview=document.querySelector("#drawerBody .detail-section .detail-grid");
   if(overview){
     const item=document.createElement("div");
     item.className="detail-item";
     const label=document.createElement("div");
     label.className="detail-label"; label.textContent="Surveillance";
     const value=document.createElement("div");
     value.className="detail-value";
     const info=window.MMRSurveillance.lookup(row);
     value.textContent=info.text+(info.date?" (as of "+info.date+")":"");
     item.append(label,value); overview.appendChild(item);
   }
 };
 const originalCsv=exportCsv;
 exportCsv=function(){
   if(!filteredRows.length){ alert("No stocks match the current filters."); return; }
   const fields=[
     ["Stock","symbol"],["Company Name","companyName"],["Big Move Score","bigMoveScore"],
     ["Price","price"],["1W %","return1W"],["1M %","return1M"],["3M %","return3M"],
     ["6M %","return6M"],["RS","rsRating"],["Stock Momentum","stockMomentumRating"],
     ["Industry Rating","industryRating"],["Free Float ₹ Cr","freeFloatCr"],
     ["Prior Move %","priorMovePct"],["Retracement %","retracementPct"],
     ["Consolidation Days","consolidationDays"],["Volume Contraction","volumeContraction"],
     ["Volatility Contraction","volatilityContraction"],["Breakout Status","breakoutStatus"],
     ["Early Signal","earlySignalStage"],["Surveillance","surveillanceStatus"],
     ["Turnover Expansion","turnoverExpansion"],["Key Trigger","keyTrigger"]
   ];
   const header=fields.map(f=>f[0]);
   const values=filteredRows.map(r=>fields.map(f=>f[1]==="surveillanceStatus"
     ? window.MMRSurveillance.lookup(r).text : r[f[1]]??""));
   const csv="\\uFEFF"+[header,...values].map(row=>row.map(csvEscape).join(",")).join("\\r\\n");
   const url=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8;"}));
   const link=document.createElement("a");
   link.href=url;link.download="BIG_MOVE_SCANNER_SURVEILLANCE.csv";
   document.body.appendChild(link);link.click();link.remove();
   setTimeout(()=>URL.revokeObjectURL(url),1000);
 };
 const style=document.createElement("style");
 style.textContent=`
 #scannerTable th:nth-child(5),#scannerTable td:nth-child(5){
   min-width:105px!important;width:105px!important;max-width:110px!important;
   font-size:10px!important;white-space:normal!important}
 #scannerTable th:nth-child(5) .select-filter{width:100%!important;font-size:10px!important}
 `;
 document.head.appendChild(style);
 window.MMRSurveillance.ready.then(()=>{
   if(typeof allRows!=="undefined" && allRows.length){
     allRows.forEach(r=>r.surveillanceStatus=window.MMRSurveillance.lookup(r).text);
     applyFiltersAndRender();
   }
 });
})();
