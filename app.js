const PAGE = 100;

let all = [];
let meta = {};
let page = 1;

const $ = id =>
  document.getElementById(id);


// =====================================================
// DISPLAY HELPERS
// =====================================================

function scoreClass(value) {
  const n = Number(value);

  if (n >= 75) return 'hi';
  if (n >= 60) return 'mid';

  return '';
}


function scoreVal(
  value,
  row = null,
  field = null,
  label = ''
) {
  if (
    value === null ||
    value === undefined ||
    value === ''
  ) {
    return '<span class="pending">Pending</span>';
  }

  const number =
    Number(value);

  if (!row || !field) {
    return `
      <span class="score ${scoreClass(number)}">
        ${number.toFixed(0)}
      </span>
    `;
  }

  const symbol =
    encodeURIComponent(
      row.symbol || ''
    );

  const safeField =
    encodeURIComponent(field);

  const safeLabel =
    encodeURIComponent(
      label || field
    );

  return `
    <button
      type="button"
      class="score score-button ${scoreClass(number)}"
      data-symbol="${symbol}"
      data-field="${safeField}"
      data-label="${safeLabel}"
    >
      ${number.toFixed(0)}
      <span class="info-mark">ⓘ</span>
    </button>
  `;
}


function pct(value) {
  if (
    value === null ||
    value === undefined ||
    value === ''
  ) {
    return '—';
  }

  return `${Number(value).toFixed(2)}%`;
}


function volumeVal(value) {
  if (
    value === null ||
    value === undefined ||
    value === ''
  ) {
    return '—';
  }

  return Number(value)
    .toLocaleString();
}


function ratioVal(value) {
  if (
    value === null ||
    value === undefined ||
    value === ''
  ) {
    return '<span class="pending">—</span>';
  }

  return `
    <strong>
      ${Number(value).toFixed(2)}×
    </strong>
  `;
}


function textVal(value) {
  if (
    value === null ||
    value === undefined ||
    value === ''
  ) {
    return '<span class="pending">Pending</span>';
  }

  return value;
}


// =====================================================
// FILTER HELPERS
// =====================================================

function isActive(id) {
  return Boolean(
    $(id)?.checked
  );
}


function numberValue(id) {
  const el = $(id);

  if (
    !el ||
    el.value === ''
  ) {
    return null;
  }

  const value =
    Number(el.value);

  return Number.isFinite(value)
    ? value
    : null;
}


function abovePass(
  activeId,
  inputId,
  value
) {
  if (!isActive(activeId)) {
    return true;
  }

  const threshold =
    numberValue(inputId);

  if (threshold === null) {
    return true;
  }

  if (
    value === null ||
    value === undefined ||
    value === ''
  ) {
    return false;
  }

  return Number(value) >= threshold;
}


function selectPass(
  activeId,
  selectId,
  value
) {
  if (!isActive(activeId)) {
    return true;
  }

  const selected =
    $(selectId)?.value || 'ALL';

  if (selected === 'ALL') {
    return true;
  }

  return value === selected;
}


// =====================================================
// STOCK STRENGTH
// =====================================================

function selectedStockStrength(row) {
  const period =
    $('stockStrengthPeriod')
      ?.value || '3M';

  if (period === '1M') {
    return row.stockStrength1M;
  }

  if (period === '6M') {
    return row.stockStrength6M;
  }

  return row.stockStrength3M;
}


// =====================================================
// FILTER ENGINE
// =====================================================

function filters() {
  const q =
    $('q')
      ?.value
      .trim()
      .toLowerCase() || '';

  return all.filter(row => {
    const searchable =
      (
        `${row.symbol || ''} ` +
        `${row.name || ''} ` +
        `${row.isin || ''} ` +
        `${row.sector || ''} ` +
        `${row.industry || ''}`
      ).toLowerCase();

    const searchPass =
      !q ||
      searchable.includes(q);

    const stockStrength =
      selectedStockStrength(row);

    return (
      searchPass &&

      selectPass(
        'activeMarketCap',
        'marketCapFilter',
        row.marketCapCategory
      ) &&

      abovePass(
        'activePrice',
        'abovePrice',
        row.price
      ) &&

      abovePass(
        'activeChange',
        'aboveChange',
        row.changePct
      ) &&

      abovePass(
        'activeTodayDelivery',
        'aboveTodayDelivery',
        row.todayDeliveryVolume
      ) &&

      abovePass(
        'active5DDelivery',
        'above5DDelivery',
        row.avg5DayDeliveryVolume
      ) &&

      abovePass(
        'activeDeliveryRatio',
        'aboveDeliveryRatio',
        row.deliveryVolumeRatio
      ) &&

      selectPass(
        'activeSector',
        'sectorFilter',
        row.sector
      ) &&

      selectPass(
        'activeIndustry',
        'industryFilter',
        row.industry
      ) &&

      abovePass(
        'activeSectorStrength',
        'aboveSectorStrength',
        row.sectorStrength
      ) &&

      abovePass(
        'activeStockStrength',
        'aboveStockStrength',
        stockStrength
      ) &&

      abovePass(
        'activeTailwind',
        'aboveTailwind',
        row.tailwindScore
      ) &&

      abovePass(
        'activeMacro',
        'aboveMacro',
        row.macroSupport
      ) &&

      abovePass(
        'activeVM',
        'aboveVM',
        row.valueMigration
      ) &&

      abovePass(
        'activeGrowth',
        'aboveGrowth',
        row.futureGrowth
      ) &&

      abovePass(
        'activeFundamental',
        'aboveFundamental',
        row.fundamentalQuality
      ) &&

      abovePass(
        'activeCapex',
        'aboveCapex',
        row.capexScore
      ) &&

      abovePass(
        'activeOverall',
        'aboveOverall',
        row.overallScore
      )
    );
  });
}


// =====================================================
// SORTING
// =====================================================

function rankStocks(rows) {
  return [...rows].sort(
    (a, b) => {
      const ao =
        a.overallScore;

      const bo =
        b.overallScore;

      if (
        ao != null &&
        bo == null
      ) {
        return -1;
      }

      if (
        ao == null &&
        bo != null
      ) {
        return 1;
      }

      if (
        ao != null &&
        bo != null &&
        Number(bo) !== Number(ao)
      ) {
        return (
          Number(bo) -
          Number(ao)
        );
      }

      const as =
        selectedStockStrength(a);

      const bs =
        selectedStockStrength(b);

      if (
        as != null &&
        bs != null &&
        Number(bs) !== Number(as)
      ) {
        return (
          Number(bs) -
          Number(as)
        );
      }

      if (
        a.deliveryVolumeRatio != null &&
        b.deliveryVolumeRatio != null &&
        Number(b.deliveryVolumeRatio) !==
        Number(a.deliveryVolumeRatio)
      ) {
        return (
          Number(b.deliveryVolumeRatio) -
          Number(a.deliveryVolumeRatio)
        );
      }

      return (
        a.name || ''
      ).localeCompare(
        b.name || ''
      );
    }
  );
}


// =====================================================
// DROPDOWNS
// =====================================================

function populateDropdowns() {
  const sectors = [
    ...new Set(
      all
        .map(
          row => row.sector
        )
        .filter(
          value =>
            value &&
            value !== 'Unclassified'
        )
    )
  ].sort();

  const industries = [
    ...new Set(
      all
        .map(
          row => row.industry
        )
        .filter(
          value =>
            value &&
            value !== 'Unclassified'
        )
    )
  ].sort();


  if ($('sectorFilter')) {
    $('sectorFilter').innerHTML =
      '<option value="ALL">All sectors</option>' +
      sectors
        .map(
          value =>
            `<option value="${value}">${value}</option>`
        )
        .join('');
  }


  if ($('industryFilter')) {
    $('industryFilter').innerHTML =
      '<option value="ALL">All industries</option>' +
      industries
        .map(
          value =>
            `<option value="${value}">${value}</option>`
        )
        .join('');
  }
}


// =====================================================
// PAGINATION
// =====================================================

function getFilteredData() {
  return rankStocks(
    filters()
  );
}


function totalPagesFor(rows) {
  return Math.max(
    1,
    Math.ceil(
      rows.length /
      PAGE
    )
  );
}


function updatePageControls(
  pages
) {
  if ($('page')) {
    $('page').textContent =
      `Page ${page} / ${pages}`;
  }

  if ($('prev')) {
    $('prev').disabled =
      page <= 1;
  }

  if ($('next')) {
    $('next').disabled =
      page >= pages;
  }

  if ($('gotoPage')) {
    $('gotoPage').max =
      pages;

    $('gotoPage').value =
      page;
  }
}


function goToPage(value) {
  const filtered =
    getFilteredData();

  const pages =
    totalPagesFor(
      filtered
    );

  let target =
    Number(value);

  if (
    !Number.isFinite(target)
  ) {
    target = 1;
  }

  target =
    Math.round(target);

  if (target < 1) {
    target = 1;
  }

  if (target > pages) {
    target = pages;
  }

  page =
    target;

  render();

  const wrap =
    document.querySelector(
      '.tablewrap'
    );

  if (wrap) {
    wrap.scrollTop = 0;
  }
}


// =====================================================
// TABLE RENDER
// =====================================================

function render() {
  const filtered =
    getFilteredData();

  const pages =
    totalPagesFor(
      filtered
    );

  if (page > pages) {
    page = pages;
  }

  if (page < 1) {
    page = 1;
  }

  const rows =
    filtered.slice(
      (page - 1) * PAGE,
      page * PAGE
    );


  if ($('resultCount')) {
    $('resultCount').textContent =
      `${filtered.length.toLocaleString()} matched`;
  }


  updatePageControls(
    pages
  );


  $('rows').innerHTML =
    rows.map(row => {
      const stockStrength =
        selectedStockStrength(row);

      return `
        <tr>

          <td class="stock-col">

            <div class="name">
              ${row.name || row.symbol}
            </div>

            <div class="sub">
              ${row.symbol || '—'}
              •
              ${row.isin || '—'}
              •
              ${row.board || ''}
            </div>

          </td>


          <td>
            ${textVal(
              row.marketCapCategory
            )}
          </td>


          <td>
            ${
              row.price == null
                ? '<span class="pending">Pending EOD</span>'
                : `₹${Number(row.price).toFixed(2)}`
            }
          </td>


          <td>
            ${pct(
              row.changePct
            )}
          </td>


          <td>
            ${volumeVal(
              row.todayDeliveryVolume
            )}
          </td>


          <td>
            ${volumeVal(
              row.avg5DayDeliveryVolume
            )}
          </td>


          <td>
            ${ratioVal(
              row.deliveryVolumeRatio
            )}
          </td>


          <td>
            ${row.sector || 'Unclassified'}
          </td>


          <td>
            ${row.industry || 'Unclassified'}
          </td>


          <td>
            ${scoreVal(
              row.sectorStrength
            )}
          </td>


          <td>
            ${scoreVal(
              stockStrength
            )}
          </td>


          <td>
            ${scoreVal(
              row.tailwindScore,
              row,
              'tailwind',
              'Tailwind'
            )}
          </td>


          <td>
            ${scoreVal(
              row.macroSupport,
              row,
              'macro',
              'Macro'
            )}
          </td>


          <td>
            ${scoreVal(
              row.valueMigration,
              row,
              'valueMigration',
              'Value Migration'
            )}
          </td>


          <td>
            ${scoreVal(
              row.futureGrowth,
              row,
              'futureGrowth',
              'Future Growth'
            )}
          </td>


          <td>
            ${scoreVal(
              row.fundamentalQuality,
              row,
              'fundamentalQuality',
              'Fundamental'
            )}
          </td>


          <td>
            ${scoreVal(
              row.capexScore,
              row,
              'capex',
              'CAPEX'
            )}
          </td>


          <td>
            ${scoreVal(
              row.overallScore
            )}
          </td>

        </tr>
      `;
    }).join('');


  attachScoreButtons();

  syncTopScrollbarWidth();
}


// =====================================================
// SCORE REASON / SOURCE
// =====================================================

function getReasonData(
  row,
  field
) {
  const research =
    row.researchReasons || {};

  const direct =
    research[field] || {};

  let reason =
    direct.reason ||
    row[`${field}Reason`] ||
    '';

  let source =
    direct.source ||
    row[`${field}Source`] ||
    '';

  let sourceDate =
    direct.sourceDate ||
    row[`${field}SourceDate`] ||
    '';


  if (
    field === 'valueMigration' &&
    !reason
  ) {
    reason =
      'Automated score based on current price momentum and turnover percentile.';
  }


  if (
    field === 'macro' &&
    !reason
  ) {
    reason =
      'Automated sector-level macro support score based on the dashboard rule set.';
  }


  if (!reason) {
    reason =
      'Detailed reason/source has not yet been added for this stock.';
  }


  return {
    reason,
    source,
    sourceDate
  };
}


function openReasonModal(
  symbol,
  field,
  label
) {
  const row =
    all.find(
      item =>
        item.symbol === symbol
    );

  if (!row) {
    return;
  }

  let value = null;

  if (field === 'tailwind') {
    value =
      row.tailwindScore;
  }

  else if (field === 'macro') {
    value =
      row.macroSupport;
  }

  else if (
    field === 'valueMigration'
  ) {
    value =
      row.valueMigration;
  }

  else if (
    field === 'futureGrowth'
  ) {
    value =
      row.futureGrowth;
  }

  else if (
    field === 'fundamentalQuality'
  ) {
    value =
      row.fundamentalQuality;
  }

  else if (
    field === 'capex'
  ) {
    value =
      row.capexScore;
  }


  const detail =
    getReasonData(
      row,
      field
    );


  $('reasonTitle').textContent =
    `${row.symbol} • ${label}`;


  $('reasonScore').textContent =
    value == null
      ? 'Score: Pending'
      : `Score: ${Number(value).toFixed(0)} / 100`;


  $('reasonText').textContent =
    detail.reason;


  $('reasonSourceDate').textContent =
    detail.sourceDate
      ? `Source date: ${detail.sourceDate}`
      : '';


  const link =
    $('reasonSourceLink');


  if (detail.source) {
    link.href =
      detail.source;

    link.style.display =
      'inline-flex';

    link.textContent =
      'View Source';
  }
  else {
    link.removeAttribute(
      'href'
    );

    link.style.display =
      'none';
  }


  const modal =
    $('reasonModal');

  modal.classList.add(
    'open'
  );

  modal.setAttribute(
    'aria-hidden',
    'false'
  );
}


function closeReasonModal() {
  const modal =
    $('reasonModal');

  if (!modal) {
    return;
  }

  modal.classList.remove(
    'open'
  );

  modal.setAttribute(
    'aria-hidden',
    'true'
  );
}


function attachScoreButtons() {
  document
    .querySelectorAll(
      '.score-button'
    )
    .forEach(button => {
      button.onclick =
        () => {
          openReasonModal(
            decodeURIComponent(
              button.dataset.symbol || ''
            ),
            decodeURIComponent(
              button.dataset.field || ''
            ),
            decodeURIComponent(
              button.dataset.label || ''
            )
          );
        };
    });
}


// =====================================================
// TOP SCROLLBAR
// =====================================================

function syncTopScrollbarWidth() {
  const inner =
    $('topScrollInner');

  const wrap =
    document.querySelector(
      '.tablewrap'
    );

  const table =
    $('stockTable');

  if (
    !inner ||
    !wrap ||
    !table
  ) {
    return;
  }

  inner.style.width =
    `${table.scrollWidth}px`;
}


function setupTopScrollbar() {
  const top =
    $('topScroll');

  const wrap =
    document.querySelector(
      '.tablewrap'
    );

  if (
    !top ||
    !wrap
  ) {
    return;
  }

  let topSync = false;
  let tableSync = false;


  top.addEventListener(
    'scroll',
    () => {
      if (tableSync) {
        return;
      }

      topSync = true;

      wrap.scrollLeft =
        top.scrollLeft;

      topSync = false;
    }
  );


  wrap.addEventListener(
    'scroll',
    () => {
      if (topSync) {
        return;
      }

      tableSync = true;

      top.scrollLeft =
        wrap.scrollLeft;

      tableSync = false;
    }
  );


  window.addEventListener(
    'resize',
    syncTopScrollbarWidth
  );
}


// =====================================================
// DATES + STATS
// =====================================================

function latestMarketDate() {
  const delivery =
    all.find(
      row =>
        row.deliveryDate
    )?.deliveryDate;

  if (delivery) {
    return delivery;
  }

  return (
    all.find(
      row =>
        row.priceDate
    )?.priceDate ||
    '—'
  );
}


function updateDates() {
  const updated =
    meta.lastUpdated || '—';

  const marketDate =
    latestMarketDate();


  if ($('dashboardDate')) {
    $('dashboardDate')
      .textContent =
      `Updated: ${updated}`;
  }


  if ($('marketDate')) {
    $('marketDate')
      .textContent =
      `Market / Delivery: ${marketDate}`;
  }
}


function renderStats() {
  const scored =
    all.filter(
      row =>
        row.overallScore !== null &&
        row.overallScore !== undefined
    ).length;


  const classified =
    all.filter(
      row =>
        row.sector &&
        row.sector !==
        'Unclassified'
    ).length;


  const eodReady =
    Number(
      meta.matchedPriceCount ||
      meta.eodPriceCount ||
      0
    );


  $('stats').innerHTML = `

    <div class="stat compact-stat">
      <b>
        ${Number(
          meta.uniqueCount ||
          all.length
        ).toLocaleString()}
      </b>

      <span>
        Unique securities
      </span>
    </div>


    <div class="stat compact-stat">
      <b>
        ${eodReady.toLocaleString()}
      </b>

      <span>
        EOD price ready
      </span>
    </div>


    <div class="stat compact-stat">
      <b>
        ${classified.toLocaleString()}
      </b>

      <span>
        Sector classified
      </span>
    </div>


    <div class="stat compact-stat">
      <b>
        ${scored.toLocaleString()}
      </b>

      <span>
        Fully scored
      </span>
    </div>

  `;
}


// =====================================================
// DATA
// =====================================================

async function fetchJSON(url) {
  const response =
    await fetch(
      `${url}?v=${Date.now()}`,
      {
        cache: 'no-store'
      }
    );

  if (!response.ok) {
    throw new Error(
      `Failed to load ${url}: ${response.status}`
    );
  }

  return response.json();
}


// =====================================================
// FILTER EVENTS
// =====================================================

const filterIds = [

  'q',

  'activeMarketCap',
  'marketCapFilter',

  'activePrice',
  'abovePrice',

  'activeChange',
  'aboveChange',

  'activeTodayDelivery',
  'aboveTodayDelivery',

  'active5DDelivery',
  'above5DDelivery',

  'activeDeliveryRatio',
  'aboveDeliveryRatio',

  'activeSector',
  'sectorFilter',

  'activeIndustry',
  'industryFilter',

  'activeSectorStrength',
  'aboveSectorStrength',

  'activeStockStrength',
  'stockStrengthPeriod',
  'aboveStockStrength',

  'activeTailwind',
  'aboveTailwind',

  'activeMacro',
  'aboveMacro',

  'activeVM',
  'aboveVM',

  'activeGrowth',
  'aboveGrowth',

  'activeFundamental',
  'aboveFundamental',

  'activeCapex',
  'aboveCapex',

  'activeOverall',
  'aboveOverall'
];


function setupFilterEvents() {
  filterIds.forEach(id => {
    const el = $(id);

    if (!el) {
      return;
    }

    const eventType =
      el.type === 'checkbox' ||
      el.tagName === 'SELECT'
        ? 'change'
        : 'input';

    el.addEventListener(
      eventType,
      () => {
        page = 1;

        render();
      }
    );
  });
}


// =====================================================
// STRONG SETUP
// =====================================================

function setCheckbox(
  id,
  checked
) {
  if ($(id)) {
    $(id).checked =
      checked;
  }
}


function setValue(
  id,
  value
) {
  if ($(id)) {
    $(id).value =
      value;
  }
}


function applyStrongSetup() {
  setCheckbox(
    'activeDeliveryRatio',
    true
  );

  setValue(
    'aboveDeliveryRatio',
    1
  );


  setCheckbox(
    'activeSectorStrength',
    true
  );

  setValue(
    'aboveSectorStrength',
    60
  );


  setCheckbox(
    'activeStockStrength',
    true
  );

  setValue(
    'stockStrengthPeriod',
    '3M'
  );

  setValue(
    'aboveStockStrength',
    70
  );


  setCheckbox(
    'activeTailwind',
    true
  );

  setValue(
    'aboveTailwind',
    70
  );


  setCheckbox(
    'activeMacro',
    true
  );

  setValue(
    'aboveMacro',
    70
  );


  setCheckbox(
    'activeVM',
    true
  );

  setValue(
    'aboveVM',
    70
  );


  setCheckbox(
    'activeGrowth',
    true
  );

  setValue(
    'aboveGrowth',
    70
  );


  setCheckbox(
    'activeFundamental',
    true
  );

  setValue(
    'aboveFundamental',
    60
  );


  setCheckbox(
    'activeCapex',
    true
  );

  setValue(
    'aboveCapex',
    60
  );


  setCheckbox(
    'activeOverall',
    true
  );

  setValue(
    'aboveOverall',
    70
  );


  page = 1;

  render();
}


// =====================================================
// RESET
// =====================================================

function resetFilters() {
  filterIds.forEach(id => {
    const el = $(id);

    if (!el) {
      return;
    }

    if (
      el.type === 'checkbox'
    ) {
      el.checked =
        false;
    }

    else if (
      id ===
      'stockStrengthPeriod'
    ) {
      el.value =
        '3M';
    }

    else if (
      el.tagName ===
      'SELECT'
    ) {
      el.value =
        'ALL';
    }

    else {
      el.value =
        '';
    }
  });


  page = 1;

  render();
}


// =====================================================
// INIT
// =====================================================

async function init() {
  try {
    [
      all,
      meta
    ] =
      await Promise.all([
        fetchJSON(
          'data/stocks.json'
        ),
        fetchJSON(
          'data/meta.json'
        )
      ]);


    populateDropdowns();

    renderStats();

    updateDates();

    setupTopScrollbar();

    setupFilterEvents();

    render();


    if ($('strongSetup')) {
      $('strongSetup').onclick =
        applyStrongSetup;
    }


    if ($('resetScores')) {
      $('resetScores').onclick =
        resetFilters;
    }


    if ($('prev')) {
      $('prev').onclick =
        () => {
          goToPage(
            page - 1
          );
        };
    }


    if ($('next')) {
      $('next').onclick =
        () => {
          goToPage(
            page + 1
          );
        };
    }


    if ($('gotoPage')) {
      $('gotoPage')
        .addEventListener(
          'keydown',
          event => {
            if (
              event.key ===
              'Enter'
            ) {
              goToPage(
                $('gotoPage').value
              );
            }
          }
        );


      $('gotoPage')
        .addEventListener(
          'change',
          () => {
            goToPage(
              $('gotoPage').value
            );
          }
        );
    }


    if ($('closeReasonModal')) {
      $('closeReasonModal').onclick =
        closeReasonModal;
    }


    if ($('reasonModal')) {
      $('reasonModal')
        .addEventListener(
          'click',
          event => {
            if (
              event.target ===
              $('reasonModal')
            ) {
              closeReasonModal();
            }
          }
        );
    }


    document.addEventListener(
      'keydown',
      event => {
        if (
          event.key ===
          'Escape'
        ) {
          closeReasonModal();
        }
      }
    );


    syncTopScrollbarWidth();

  }

  catch (error) {
    console.error(error);

    if ($('resultCount')) {
      $('resultCount').textContent =
        'Dashboard data failed to load';
    }
  }
}


init();
