const PAGE = 100;

let all = [];
let meta = {};
let page = 1;

/*
  Last activated / changed numeric column
  primary sorting column banega.
*/
let activeSortField = null;

const $ = id =>
  document.getElementById(id);


// =====================================================
// DISPLAY HELPERS
// =====================================================

function scoreClass(value) {
  const n = Number(value);

  if (n >= 75) return "hi";
  if (n >= 60) return "mid";

  return "";
}


function scoreVal(
  value,
  row = null,
  field = null,
  label = ""
) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return '<span class="pending">Pending</span>';
  }

  const number = Number(value);

  if (!row || !field) {
    return `
      <span class="score ${scoreClass(number)}">
        ${number.toFixed(0)}
      </span>
    `;
  }

  const symbol =
    encodeURIComponent(
      row.symbol || ""
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
    value === ""
  ) {
    return "—";
  }

  const n = Number(value);

  if (!Number.isFinite(n)) {
    return "—";
  }

  const sign =
    n > 0
      ? "+"
      : "";

  return `${sign}${n.toFixed(2)}%`;
}


function volumeVal(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "—";
  }

  return Number(value)
    .toLocaleString();
}


function ratioVal(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return '<span class="pending">—</span>';
  }

  return `
    <strong>
      ${Number(value).toFixed(2)}×
    </strong>
  `;
}


function marketCapVal(row) {

  const category =
    row.marketCapCategory;

  const marketCap =
    row.marketCapCr;

  if (
    !category &&
    (
      marketCap === null ||
      marketCap === undefined
    )
  ) {
    return '<span class="pending">Pending</span>';
  }

  let html = "";

  if (category) {
    html += `
      <div class="market-cap-category">
        ${category}
      </div>
    `;
  }

  if (
    marketCap !== null &&
    marketCap !== undefined &&
    marketCap !== ""
  ) {
    html += `
      <div class="market-cap-value">
        ₹${Number(marketCap).toLocaleString(
          "en-IN",
          {
            maximumFractionDigits: 0
          }
        )} Cr
      </div>
    `;
  }

  return html;
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
    el.value === ""
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
    value === ""
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
    $(selectId)?.value || "ALL";

  if (selected === "ALL") {
    return true;
  }

  return value === selected;
}


// =====================================================
// STOCK GROWTH
// =====================================================

function selectedStockGrowth(row) {

  const period =
    $("stockGrowthPeriod")
      ?.value || "3M";

  if (period === "1M") {
    return row.stockGrowth1M;
  }

  if (period === "6M") {
    return row.stockGrowth6M;
  }

  return row.stockGrowth3M;
}


// =====================================================
// SORT VALUE
// =====================================================

function sortValue(
  row,
  field
) {

  if (field === "marketCapCr") {
    return row.marketCapCr;
  }

  if (field === "price") {
    return row.price;
  }

  if (field === "changePct") {
    return row.changePct;
  }

  if (field === "todayDeliveryVolume") {
    return row.todayDeliveryVolume;
  }

  if (field === "avg5DayDeliveryVolume") {
    return row.avg5DayDeliveryVolume;
  }

  if (field === "deliveryVolumeRatio") {
    return row.deliveryVolumeRatio;
  }

  if (field === "sectorGrowth1M") {
    return row.sectorGrowth1M;
  }

  if (field === "stockGrowth") {
    return selectedStockGrowth(row);
  }

  if (field === "tmvScore") {
    return row.tmvScore;
  }

  if (field === "gfcScore") {
    return row.gfcScore;
  }

  if (field === "overallScore") {
    return row.overallScore;
  }

  return null;
}


// =====================================================
// FILTER ENGINE
// =====================================================

function filters() {

  const q =
    $("q")
      ?.value
      .trim()
      .toLowerCase() || "";

  return all.filter(row => {

    const searchable =
      (
        `${row.symbol || ""} ` +
        `${row.name || ""} ` +
        `${row.isin || ""} ` +
        `${row.sector || ""} ` +
        `${row.industry || ""}`
      ).toLowerCase();

    const searchPass =
      !q ||
      searchable.includes(q);

    const stockGrowth =
      selectedStockGrowth(row);

    return (

      searchPass &&

      abovePass(
        "activeMarketCap",
        "aboveMarketCap",
        row.marketCapCr
      ) &&

      abovePass(
        "activePrice",
        "abovePrice",
        row.price
      ) &&

      abovePass(
        "activeChange",
        "aboveChange",
        row.changePct
      ) &&

      abovePass(
        "activeTodayDelivery",
        "aboveTodayDelivery",
        row.todayDeliveryVolume
      ) &&

      abovePass(
        "active5DDelivery",
        "above5DDelivery",
        row.avg5DayDeliveryVolume
      ) &&

      abovePass(
        "activeDeliveryRatio",
        "aboveDeliveryRatio",
        row.deliveryVolumeRatio
      ) &&

      selectPass(
        "activeSector",
        "sectorFilter",
        row.sector
      ) &&

      selectPass(
        "activeIndustry",
        "industryFilter",
        row.industry
      ) &&

      abovePass(
        "activeSectorGrowth",
        "aboveSectorGrowth",
        row.sectorGrowth1M
      ) &&

      abovePass(
        "activeStockGrowth",
        "aboveStockGrowth",
        stockGrowth
      ) &&

      abovePass(
        "activeTMV",
        "aboveTMV",
        row.tmvScore
      ) &&

      abovePass(
        "activeGFC",
        "aboveGFC",
        row.gfcScore
      ) &&

      abovePass(
        "activeOverall",
        "aboveOverall",
        row.overallScore
      )
    );
  });
}


// =====================================================
// SORTING
// =====================================================

function compareNumericDesc(
  a,
  b,
  field
) {

  const av =
    sortValue(
      a,
      field
    );

  const bv =
    sortValue(
      b,
      field
    );

  const aValid =
    av !== null &&
    av !== undefined &&
    av !== "" &&
    Number.isFinite(
      Number(av)
    );

  const bValid =
    bv !== null &&
    bv !== undefined &&
    bv !== "" &&
    Number.isFinite(
      Number(bv)
    );


  // Both valid
  if (
    aValid &&
    bValid
  ) {

    const diff =
      Number(bv) -
      Number(av);

    if (diff !== 0) {
      return diff;
    }
  }


  // A valid, B pending
  if (
    aValid &&
    !bValid
  ) {
    return -1;
  }


  // B valid, A pending
  if (
    !aValid &&
    bValid
  ) {
    return 1;
  }


  return 0;
}


function rankStocks(rows) {

  return [...rows].sort(
    (a, b) => {

      // =================================================
      // PRIMARY SORT:
      // LAST ACTIVATED / CHANGED NUMERIC FILTER
      // =================================================

      if (activeSortField) {

        const primary =
          compareNumericDesc(
            a,
            b,
            activeSortField
          );

        if (primary !== 0) {
          return primary;
        }
      }


      // =================================================
      // SECONDARY SORT:
      // OVERALL SCORE HIGH TO LOW
      // =================================================

      if (
        activeSortField !==
        "overallScore"
      ) {

        const overall =
          compareNumericDesc(
            a,
            b,
            "overallScore"
          );

        if (overall !== 0) {
          return overall;
        }
      }


      // =================================================
      // FINAL TIE BREAK:
      // COMPANY NAME
      // =================================================

      return (
        a.name || ""
      ).localeCompare(
        b.name || ""
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
            value !== "Unclassified"
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
            value !== "Unclassified"
        )
    )
  ].sort();


  if ($("sectorFilter")) {

    $("sectorFilter").innerHTML =
      '<option value="ALL">All sectors</option>' +
      sectors
        .map(
          value =>
            `<option value="${value}">${value}</option>`
        )
        .join("");
  }


  if ($("industryFilter")) {

    $("industryFilter").innerHTML =
      '<option value="ALL">All industries</option>' +
      industries
        .map(
          value =>
            `<option value="${value}">${value}</option>`
        )
        .join("");
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

  if ($("page")) {
    $("page").textContent =
      `Page ${page} / ${pages}`;
  }

  if ($("prev")) {
    $("prev").disabled =
      page <= 1;
  }

  if ($("next")) {
    $("next").disabled =
      page >= pages;
  }

  if ($("gotoPage")) {

    $("gotoPage").max =
      pages;

    $("gotoPage").value =
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
      ".tablewrap"
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


  if ($("resultCount")) {

    $("resultCount").textContent =
      `${filtered.length.toLocaleString()} matched`;
  }


  updatePageControls(
    pages
  );


  if (!$("rows")) {
    return;
  }


  $("rows").innerHTML =
    rows.map(row => {

      const stockGrowth =
        selectedStockGrowth(row);

      return `
        <tr>

          <td class="stock-col">

            <div class="name">
              ${row.name || row.symbol}
            </div>

            <div class="sub">
              ${row.symbol || "—"}
              •
              ${row.isin || "—"}
              •
              ${row.board || ""}
            </div>

          </td>


          <td>
            ${marketCapVal(row)}
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
            ${row.sector || "Unclassified"}
          </td>


          <td>
            ${row.industry || "Unclassified"}
          </td>


          <td>
            ${pct(
              row.sectorGrowth1M
            )}
          </td>


          <td>
            ${pct(
              stockGrowth
            )}
          </td>


          <td>
            ${scoreVal(
              row.tmvScore,
              row,
              "tmv",
              "T + M + VM"
            )}
          </td>


          <td>
            ${scoreVal(
              row.gfcScore,
              row,
              "gfc",
              "G + F + C"
            )}
          </td>


          <td>
            ${scoreVal(
              row.overallScore
            )}
          </td>

        </tr>
      `;
    }).join("");


  attachScoreButtons();

  syncTopScrollbarWidth();
}


// =====================================================
// REASON HELPERS
// =====================================================

function safeDetail(detail) {

  if (
    !detail ||
    typeof detail !== "object"
  ) {

    return {
      score: null,
      reason: "",
      source: "",
      sourceDate: "",
      mode: ""
    };
  }

  return {

    score:
      detail.score ?? null,

    reason:
      detail.reason || "",

    source:
      detail.source || "",

    sourceDate:
      detail.sourceDate || "",

    mode:
      detail.mode || ""
  };
}


function modeText(mode) {

  if (mode === "VERIFIED") {
    return "VERIFIED";
  }

  if (
    mode === "AUTOMATED" ||
    mode === "AUTOMATED_PROXY"
  ) {
    return "Automated";
  }

  return "";
}


function combinedBlock(
  title,
  detail
) {

  const d =
    safeDetail(detail);


  const scoreText =
    d.score == null
      ? "Pending"
      : `${Number(d.score).toFixed(0)} / 100`;


  const mode =
    modeText(
      d.mode
    );


  const reason =
    d.reason ||
    "Detailed reason/source has not yet been added.";


  const sourceDate =
    d.sourceDate
      ? `Source date: ${d.sourceDate}`
      : "";


  const source =
    d.source
      ? `
        <a
          href="${d.source}"
          target="_blank"
          rel="noopener noreferrer"
          class="reason-source-link"
        >
          View Source
        </a>
      `
      : "";


  return `
    <div style="
      padding:12px 0;
      border-bottom:1px solid rgba(255,255,255,.10);
    ">

      <div style="
        font-weight:800;
        margin-bottom:6px;
      ">
        ${title}
      </div>

      <div style="
        margin-bottom:6px;
      ">
        Score:
        <strong>
          ${scoreText}
        </strong>

        ${
          mode
            ? ` • ${mode}`
            : ""
        }
      </div>

      <div style="
        margin-bottom:6px;
        line-height:1.5;
      ">
        ${reason}
      </div>

      <div class="reason-source-date">
        ${sourceDate}
      </div>

      ${source}

    </div>
  `;
}


// =====================================================
// COMBINED SCORE MODAL
// =====================================================

function openCombinedModal(
  row,
  field,
  label
) {

  if ($("reasonTitle")) {

    $("reasonTitle").textContent =
      `${row.symbol} • ${label}`;
  }


  let score = null;

  let details = null;

  let blocks = "";


  if (
    field === "tmv"
  ) {

    score =
      row.tmvScore;

    details =
      row.tmvDetails || {};

    blocks =

      combinedBlock(
        "Tailwind",
        details.tailwind
      )

      +

      combinedBlock(
        "Macro",
        details.macro
      )

      +

      combinedBlock(
        "Value Migration",
        details.valueMigration
      );
  }


  else if (
    field === "gfc"
  ) {

    score =
      row.gfcScore;

    details =
      row.gfcDetails || {};

    blocks =

      combinedBlock(
        "Future Growth",
        details.futureGrowth
      )

      +

      combinedBlock(
        "Fundamental Quality",
        details.fundamentalQuality
      )

      +

      combinedBlock(
        "CAPEX",
        details.capex
      );
  }


  if ($("reasonScore")) {

    $("reasonScore").textContent =

      score == null
        ? "Combined Score: Pending"
        : `Combined Score: ${Number(score).toFixed(0)} / 100`;
  }


  if ($("reasonText")) {

    $("reasonText").innerHTML =
      blocks;
  }


  if ($("reasonSourceDate")) {

    $("reasonSourceDate").textContent =
      "";
  }


  if ($("reasonSourceLink")) {

    $("reasonSourceLink")
      .style.display =
        "none";
  }


  const modal =
    $("reasonModal");


  if (!modal) {
    return;
  }


  modal.classList.add(
    "open"
  );


  modal.setAttribute(
    "aria-hidden",
    "false"
  );
}


// =====================================================
// OPEN REASON MODAL
// =====================================================

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


  if (
    field === "tmv" ||
    field === "gfc"
  ) {

    openCombinedModal(
      row,
      field,
      label
    );

    return;
  }
}


// =====================================================
// CLOSE MODAL
// =====================================================

function closeReasonModal() {

  const modal =
    $("reasonModal");


  if (!modal) {
    return;
  }


  modal.classList.remove(
    "open"
  );


  modal.setAttribute(
    "aria-hidden",
    "true"
  );
}


function attachScoreButtons() {

  document
    .querySelectorAll(
      ".score-button"
    )
    .forEach(button => {

      button.onclick =
        () => {

          openReasonModal(

            decodeURIComponent(
              button.dataset.symbol || ""
            ),

            decodeURIComponent(
              button.dataset.field || ""
            ),

            decodeURIComponent(
              button.dataset.label || ""
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
    $("topScrollInner");

  const wrap =
    document.querySelector(
      ".tablewrap"
    );

  const table =
    $("stockTable");


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
    $("topScroll");

  const wrap =
    document.querySelector(
      ".tablewrap"
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
    "scroll",
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
    "scroll",
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
    "resize",
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
    "—"
  );
}


function updateDates() {

  const updated =
    meta.lastUpdated || "—";


  const marketDate =
    latestMarketDate();


  if ($("dashboardDate")) {

    $("dashboardDate").textContent =
      `Updated: ${updated}`;
  }


  if ($("marketDate")) {

    $("marketDate").textContent =
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
        "Unclassified"
    ).length;


  const eodReady =
    Number(
      meta.matchedPriceCount ||
      meta.eodPriceCount ||
      0
    );


  if (!$("stats")) {
    return;
  }


  $("stats").innerHTML = `

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
        cache: "no-store"
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
// FILTER / SORT MAPPING
// =====================================================

const filterIds = [

  "q",

  "activeMarketCap",
  "aboveMarketCap",

  "activePrice",
  "abovePrice",

  "activeChange",
  "aboveChange",

  "activeTodayDelivery",
  "aboveTodayDelivery",

  "active5DDelivery",
  "above5DDelivery",

  "activeDeliveryRatio",
  "aboveDeliveryRatio",

  "activeSector",
  "sectorFilter",

  "activeIndustry",
  "industryFilter",

  "activeSectorGrowth",
  "aboveSectorGrowth",

  "activeStockGrowth",
  "stockGrowthPeriod",
  "aboveStockGrowth",

  "activeTMV",
  "aboveTMV",

  "activeGFC",
  "aboveGFC",

  "activeOverall",
  "aboveOverall"
];


const sortFieldByElement = {

  activeMarketCap:
    "marketCapCr",

  aboveMarketCap:
    "marketCapCr",


  activePrice:
    "price",

  abovePrice:
    "price",


  activeChange:
    "changePct",

  aboveChange:
    "changePct",


  activeTodayDelivery:
    "todayDeliveryVolume",

  aboveTodayDelivery:
    "todayDeliveryVolume",


  active5DDelivery:
    "avg5DayDeliveryVolume",

  above5DDelivery:
    "avg5DayDeliveryVolume",


  activeDeliveryRatio:
    "deliveryVolumeRatio",

  aboveDeliveryRatio:
    "deliveryVolumeRatio",


  activeSectorGrowth:
    "sectorGrowth1M",

  aboveSectorGrowth:
    "sectorGrowth1M",


  activeStockGrowth:
    "stockGrowth",

  stockGrowthPeriod:
    "stockGrowth",

  aboveStockGrowth:
    "stockGrowth",


  activeTMV:
    "tmvScore",

  aboveTMV:
    "tmvScore",


  activeGFC:
    "gfcScore",

  aboveGFC:
    "gfcScore",


  activeOverall:
    "overallScore",

  aboveOverall:
    "overallScore"
};


// =====================================================
// FILTER EVENTS
// =====================================================

function setupFilterEvents() {

  filterIds.forEach(id => {

    const el =
      $(id);


    if (!el) {
      return;
    }


    const eventType =
      el.type === "checkbox" ||
      el.tagName === "SELECT"
        ? "change"
        : "input";


    el.addEventListener(
      eventType,
      () => {

        /*
          Agar numeric filter se interaction hua,
          usi column ko sorting priority do.
        */

        const mappedField =
          sortFieldByElement[id];


        if (mappedField) {

          /*
            Checkbox OFF kiya ho aur wahi
            current sort field ho to default
            Overall ranking par wapas jao.
          */

          if (
            el.type === "checkbox" &&
            !el.checked
          ) {

            if (
              activeSortField ===
              mappedField
            ) {

              activeSortField =
                null;
            }
          }

          else {

            activeSortField =
              mappedField;
          }
        }


        page = 1;

        render();
      }
    );
  });
}


// =====================================================
// SET FILTER HELPERS
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


// =====================================================
// STRONG SETUP
// =====================================================

function applyStrongSetup() {

  /*
    Strong Setup:
    T + M + VM >= 70
    G + F + C >= 70
    Overall >= 70

    Strong Setup ranking =
    Overall High -> Low
  */


  setCheckbox(
    "activeTMV",
    true
  );

  setValue(
    "aboveTMV",
    70
  );


  setCheckbox(
    "activeGFC",
    true
  );

  setValue(
    "aboveGFC",
    70
  );


  setCheckbox(
    "activeOverall",
    true
  );

  setValue(
    "aboveOverall",
    70
  );


  activeSortField =
    "overallScore";


  page = 1;

  render();
}


// =====================================================
// RESET
// =====================================================

function resetFilters() {

  filterIds.forEach(id => {

    const el =
      $(id);


    if (!el) {
      return;
    }


    if (
      el.type ===
      "checkbox"
    ) {

      el.checked =
        false;
    }


    else if (
      id ===
      "stockGrowthPeriod"
    ) {

      el.value =
        "3M";
    }


    else if (
      el.tagName ===
      "SELECT"
    ) {

      el.value =
        "ALL";
    }


    else {

      el.value =
        "";
    }

  });


  activeSortField =
    null;


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
          "data/stocks.json"
        ),

        fetchJSON(
          "data/meta.json"
        )

      ]);


    populateDropdowns();

    renderStats();

    updateDates();

    setupTopScrollbar();

    setupFilterEvents();

    render();


    if ($("strongSetup")) {

      $("strongSetup").onclick =
        applyStrongSetup;
    }


    if ($("resetScores")) {

      $("resetScores").onclick =
        resetFilters;
    }


    if ($("prev")) {

      $("prev").onclick =
        () => {

          goToPage(
            page - 1
          );
        };
    }


    if ($("next")) {

      $("next").onclick =
        () => {

          goToPage(
            page + 1
          );
        };
    }


    if ($("gotoPage")) {

      $("gotoPage")
        .addEventListener(
          "keydown",
          event => {

            if (
              event.key ===
              "Enter"
            ) {

              goToPage(
                $("gotoPage").value
              );
            }
          }
        );


      $("gotoPage")
        .addEventListener(
          "change",
          () => {

            goToPage(
              $("gotoPage").value
            );
          }
        );
    }


    if ($("closeReasonModal")) {

      $("closeReasonModal").onclick =
        closeReasonModal;
    }


    if ($("reasonModal")) {

      $("reasonModal")
        .addEventListener(
          "click",
          event => {

            if (
              event.target ===
              $("reasonModal")
            ) {

              closeReasonModal();
            }
          }
        );
    }


    document.addEventListener(
      "keydown",
      event => {

        if (
          event.key ===
          "Escape"
        ) {

          closeReasonModal();
        }
      }
    );


    syncTopScrollbarWidth();

  }

  catch (error) {

    console.error(
      error
    );


    if ($("resultCount")) {

      $("resultCount").textContent =
        "Dashboard data failed to load";
    }
  }
}


init();
