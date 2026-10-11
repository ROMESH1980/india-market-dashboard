/* MY MARKET RESEARCH — Page 2 Early Signal addon.
   Add <script src="early-signal-addon.js"></script> immediately after the existing
   inline scanner <script> block and before </body>. No other page is affected. */
(function () {
  'use strict';
  if (typeof columns === 'undefined' || typeof enrichRow !== 'function') {
    console.error('Early Signal addon: Page 2 scanner code was not found.');
    return;
  }
  const allowed = ['Early Watch', 'Developing Setup', 'Breakout Confirmed', 'No Early Signal'];
  const position = columns.findIndex(c => c.field === 'breakoutStatus');
  if (position < 0 || columns.some(c => c.field === 'earlySignalStage')) return;
  columns.splice(position + 1, 0, {
    field: 'earlySignalStage', label: 'Early Signal', type: 'select',
    filterable: true, options: allowed
  });
  const originalEnrichRow = enrichRow;
  enrichRow = function (row, index) {
    const result = originalEnrichRow(row, index);
    const stage = row.earlySignalStage ?? row.early_signal_stage;
    result.earlySignalStage = allowed.includes(stage) ? stage : 'No Early Signal';
    return result;
  };
  function stageBadge(stage) {
    const safe = allowed.includes(stage) ? stage : 'No Early Signal';
    const cls = safe === 'Early Watch' ? 'badge-yellow'
      : safe === 'Developing Setup' ? 'badge-green'
      : safe === 'Breakout Confirmed' ? 'badge-blue' : '';
    const icon = safe === 'Early Watch' ? '🟡 ' : safe === 'Developing Setup' ? '🟢 '
      : safe === 'Breakout Confirmed' ? '🔵 ' : '';
    return cls ? `<span class="badge ${cls}">${icon}${safe}</span>`
      : '<span class="muted">—</span>';
  }
  const originalRenderTable = renderTable;
  renderTable = function () {
    originalRenderTable();
    const body = document.getElementById('tableBody');
    if (!body) return;
    const start = (currentPage - 1) * pageSize;
    const rows = filteredRows.slice(start, start + pageSize);
    const trs = [...body.querySelectorAll('tr')];
    if (!rows.length) {
      const td = trs[0]?.querySelector('td[colspan]');
      if (td) td.colSpan = columns.length;
      return;
    }
    rows.forEach((row, i) => {
      const tr = trs[i];
      if (!tr || tr.cells.length < 4) return;
      const td = tr.insertCell(3);
      td.innerHTML = stageBadge(row.earlySignalStage);
    });
    syncTopScrollbar();
  };
  const originalOpenDrawer = openDrawer;
  openDrawer = function (row) {
    originalOpenDrawer(row);
    const overview = document.querySelector('#drawerBody .detail-section .detail-grid');
    if (overview) {
      const div = document.createElement('div');
      div.className = 'detail-item';
      div.innerHTML = `<div class="detail-label">Early Signal</div><div class="detail-value">${stageBadge(row.earlySignalStage)}</div>`;
      overview.appendChild(div);
    }
  };
  const originalExportCsv = exportCsv;
  exportCsv = function () {
    // Preserve all existing export fields, with Early Signal added next to Breakout Status.
    const rows = filteredRows;
    if (!rows.length) {
      alert('No stocks match the current filters.');
      return;
    }
    const header = ['Stock','Company Name','Big Move Score','Price','1W %','1M %','3M %','6M %',
      'RS','Stock Momentum','Industry Rating','Free Float ₹ Cr','Prior Move %','Retracement %',
      'Consolidation Days','Volume Contraction','Volatility Contraction','Breakout Status',
      'Early Signal','Turnover Expansion','Key Trigger'];
    const data = rows.map(r => [r.symbol,r.companyName,r.bigMoveScore,r.price,r.return1W,r.return1M,
      r.return3M,r.return6M,r.rsRating,r.stockMomentumRating,r.industryRating,r.freeFloatCr,
      r.priorMovePct,r.retracementPct,r.consolidationDays,normalizeText(r.volumeContraction),
      normalizeText(r.volatilityContraction),r.breakoutStatus,r.earlySignalStage,r.turnoverExpansion,r.keyTrigger]);
    const content = '\uFEFF' + [header,...data].map(row => row.map(csvEscape).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([content],{type:'text/csv;charset=utf-8;'}));
    const a = document.createElement('a');
    a.href = url;
    a.download = `BIG_MOVE_SCANNER_${String(marketDate || 'latest').replace(/[^\d-]/g,'')}_${rows.length}_stocks.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const originalShowLoadError = showLoadError;
  showLoadError = function (error) {
    originalShowLoadError(error);
    const td = document.querySelector('#tableBody td[colspan]');
    if (td) td.colSpan = columns.length;
  };
  const style = document.createElement('style');
  style.textContent = `
    #scannerTable th:nth-child(4),#scannerTable td:nth-child(4){min-width:145px!important;width:145px!important;max-width:145px!important}
    #scannerTable th:nth-child(4) .select-filter{font-size:10px;width:100%}
    #scannerTable th:nth-child(5),#scannerTable td:nth-child(5){min-width:66px!important;width:66px!important;max-width:none!important}
    #scannerTable th:nth-child(6),#scannerTable td:nth-child(6),#scannerTable th:nth-child(7),#scannerTable td:nth-child(7),#scannerTable th:nth-child(8),#scannerTable td:nth-child(8),#scannerTable th:nth-child(9),#scannerTable td:nth-child(9){min-width:66px!important;width:66px!important;max-width:none!important}
    #scannerTable th:nth-child(10),#scannerTable td:nth-child(10){min-width:58px!important;width:58px!important;max-width:none!important}
    #scannerTable th:nth-child(11),#scannerTable td:nth-child(11){min-width:90px!important;width:90px!important;max-width:none!important}
    #scannerTable th:nth-child(12),#scannerTable td:nth-child(12){min-width:86px!important;width:86px!important;max-width:none!important}
    #scannerTable th:nth-child(13),#scannerTable td:nth-child(13){min-width:96px!important;width:96px!important;max-width:none!important}
    #scannerTable th:nth-child(14),#scannerTable td:nth-child(14),#scannerTable th:nth-child(15),#scannerTable td:nth-child(15){min-width:82px!important;width:82px!important;max-width:none!important}
    #scannerTable th:nth-child(16),#scannerTable td:nth-child(16){min-width:92px!important;width:92px!important;max-width:none!important}
    #scannerTable th:nth-child(17),#scannerTable td:nth-child(17),#scannerTable th:nth-child(18),#scannerTable td:nth-child(18){min-width:94px!important;width:94px!important;max-width:none!important}
    #scannerTable th:nth-child(19),#scannerTable td:nth-child(19){min-width:76px!important;width:76px!important;max-width:76px!important}
    #scannerTable th:nth-child(20),#scannerTable td:nth-child(20){min-width:150px!important;width:150px!important;max-width:150px!important}
    #scannerTable tbody td:nth-child(20){white-space:nowrap!important;text-overflow:ellipsis!important}
    #scannerTable tbody td:nth-child(19){white-space:nowrap!important;text-overflow:clip!important}
  `;
  document.head.appendChild(style);
})();
