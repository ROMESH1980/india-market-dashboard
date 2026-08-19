const PAGE=100;let all=[],meta={},page=1;
const $=id=>document.getElementById(id);
const val=x=>x===null||x===undefined||x===''?'<span class="pending">Pending</span>':`<span class="score ${x>=75?'hi':x>=60?'mid':''}">${Math.round(x)}</span>`;
function filters(){
 const q=$('q').value.trim().toLowerCase(),ex=$('exchange').value,bd=$('board').value,st=$('status').value;
 return all.filter(s=>(!q||`${s.symbol} ${s.name} ${s.isin}`.toLowerCase().includes(q))&&(ex==='ALL'||s.exchange===ex||(s.exchanges||[]).includes(ex))&&(bd==='ALL'||s.board===bd)&&(st==='ALL'||(st==='READY'?s.overallScore!==null:s.overallScore===null)));
}
function render(){
 const f=filters(),pages=Math.max(1,Math.ceil(f.length/PAGE));page=Math.min(page,pages);
 const rows=f.slice((page-1)*PAGE,page*PAGE);
 $('resultCount').textContent=`${f.length.toLocaleString()} securities matched`;
 $('page').textContent=`Page ${page} / ${pages}`;
 $('prev').disabled=page<=1;$('next').disabled=page>=pages;
 $('rows').innerHTML=rows.map(s=>`<tr><td><div class="name">${s.name}</div><div class="sub">${s.symbol} • ${s.isin||'—'} • ${s.board||''}</div></td><td><span class="tag">${(s.exchanges||[s.exchange]).join(' + ')}</span></td><td>${s.price==null?'<span class="pending">Pending EOD</span>':`₹${Number(s.price).toFixed(2)}`}</td><td>${s.sector||'Unclassified'}</td><td>${val(s.sectorStrength)}</td><td>${val(s.macroSupport)}</td><td>${val(s.valueMigration)}</td><td>${val(s.futureGrowth)}</td><td>${val(s.fundamentalQuality)}</td><td>${val(s.capexScore)}</td><td>${val(s.overallScore)}</td></tr>`).join('');
}
async function init(){
 [all,meta]=await Promise.all([fetch('data/stocks.json').then(r=>r.json()),fetch('data/meta.json').then(r=>r.json())]);
 $('mode').textContent=`${meta.mode} • Updated ${meta.lastUpdated}`;
 $('stats').innerHTML=`<div class="stat"><b>${Number(meta.uniqueCount||all.length).toLocaleString()}</b><span>Unique securities</span></div><div class="stat"><b>${Number(meta.nseCount||0).toLocaleString()}</b><span>NSE incl. SME</span></div><div class="stat"><b>${Number(meta.bseCount||0).toLocaleString()}</b><span>BSE synced</span></div><div class="stat"><b>${all.filter(s=>s.overallScore!==null).length.toLocaleString()}</b><span>Fully scored</span></div>`;
 render();
}
['q','exchange','board','status'].forEach(id=>$(id).addEventListener(id==='q'?'input':'change',()=>{page=1;render()}));
$('prev').onclick=()=>{page--;render();scrollTo({top:360,behavior:'smooth'})};$('next').onclick=()=>{page++;render();scrollTo({top:360,behavior:'smooth'})};init();