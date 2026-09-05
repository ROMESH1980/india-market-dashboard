const PAGE_SIZE = 100;
const MIN_MARKET_CAP_CR = 100;

let allStocks = [];
let filteredStocks = [];
let currentPage = 1;
let activeSortField = null;

let multiTimeframeMarketView = {};
let metaDataGlobal = {};


/* =====================================================
   DOM HELPERS
===================================================== */

function el(id) {
  return document.getElementById(id);
}


function num(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return null;
  }

  const n = Number(value);

  return Number.isFinite(n)
    ? n
    : null;
}


function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


/* =====================================================
   PERMANENT UNIVERSE RULE
===================================================== */

function passesPermanentUniverseRule(row) {
  const marketCap = num(row.marketCapCr);

  if (marketCap === null) {
    return true;
  }

  return marketCap >= MIN_MARKET_CAP_CR;
}


/* =====================================================
   TODAY VOLUME
===================================================== */

function totalVolume(row) {
  const candidates = [
    row.todayVolume,
    row.totalVolume,
    row.volume,
    row.mtoTradedVolume,
    row.tradedVolume,
    row.totalTradedVolume,
    row.totalTradedQty,
    row.totalTradedQuantity,
    row.totalTradeQuantity,
    row.ttq
  ];

  for (const value of candidates) {
    const n = num(value);

    if (n !== null) {
      return n;
    }
  }

  return null;
}


/* =====================================================
   TODAY DELIVERY VOLUME
===================================================== */

function todayDeliveryVolume(row) {
  const candidates = [
    row.todayDeliveryVolume,
    row.deliveryVolume,
    row.deliveryQty,
    row.deliveryQuantity,
    row.deliverableQty,
    row.deliverableQuantity
  ];

  for (const value of candidates) {
    const n = num(value);

    if (n !== null) {
      return n;
    }
  }

  return null;
}


/* =====================================================
   5D AVG DELIVERY VOLUME
===================================================== */

function avg5DayDelivery(row) {
  const candidates = [
    row.avg5DayDeliveryVolume,
    row.avg5DDeliveryVolume,
    row.fiveDayAvgDeliveryVolume,
    row.delivery5DayAvg
  ];

  for (const value of candidates) {
    const n = num(value);

    if (n !== null) {
      return n;
    }
  }

  return null;
}


/* =====================================================
   DELIVERY TIMES
===================================================== */

function deliveryTimes(row) {
  const direct = num(
    row.deliveryVolumeRatio ??
    row.deliveryTimes
  );

  if (direct !== null) {
    return direct;
  }

  const today = todayDeliveryVolume(row);
  const avg = avg5DayDelivery(row);

  if (
    today === null ||
    avg === null ||
    avg <= 0
  ) {
    return null;
  }

  return today / avg;
}


/* =====================================================
   DELIVERY %
===================================================== */

function deliveryPercentage(row) {
  const directCandidates = [
    row.deliveryPct,
    row.deliveryPercent,
    row.deliveryPercentage,
    row.deliverablePct,
    row.deliverablePercentage
  ];

  for (const value of directCandidates) {
    const n = num(value);

    if (n !== null) {
      if (
        n > 0 &&
        n <= 1
      ) {
        return n * 100;
      }

      return n;
    }
  }

  const delivery = todayDeliveryVolume(row);
  const volume = totalVolume(row);

  if (
    delivery === null ||
    volume === null ||
    volume <= 0
  ) {
    return null;
  }

  return (
    delivery /
    volume
  ) * 100;
}


/* =====================================================
   5L VOLUME + 5% MOVE
===================================================== */

function qualifiesHighVolumeMove(row) {
  const volume = totalVolume(row);
  const change = num(row.changePct);

  if (
    volume === null ||
    change === null
  ) {
    return false;
  }

  return (
    volume >= 500000 &&
    Math.abs(change) >= 5
  );
}


/* =====================================================
   RS RATING
===================================================== */

function rsRating(row) {
  const rating = num(row.rsRating);

  if (rating === null) {
    return null;
  }

  return Math.max(
    1,
    Math.min(
      99,
      Math.round(rating)
    )
  );
}


function rsRatingLabel(value) {
  const rating = num(value);

  if (rating === null) {
    return "Pending";
  }

  if (rating >= 90) {
    return "Elite";
  }

  if (rating >= 80) {
    return "Leader";
  }

  if (rating >= 70) {
    return "Strong";
  }

  if (rating >= 50) {
    return "Average";
  }

  if (rating >= 30) {
    return "Weak";
  }

  return "Very Weak";
}


function rsRatingClass(value) {
  const rating = num(value);

  if (rating === null) {
    return "rs-pending";
  }

  if (rating >= 90) {
    return "rs-elite";
  }

  if (rating >= 80) {
    return "rs-leader";
  }

  if (rating >= 70) {
    return "rs-strong";
  }

  if (rating >= 50) {
    return "rs-average";
  }

  if (rating >= 30) {
    return "rs-weak";
  }

  return "rs-very-weak";
}


function rsRatingVal(row) {
  const rating = rsRating(row);

  if (rating === null) {
    return `
      <span class="pending">
        Pending
      </span>
    `;
  }

  const label =
    row.rsLabel ||
    rsRatingLabel(rating);

  const cls =
    rsRatingClass(rating);

  return `
    <div class="rs-rating ${cls}">
      <strong>
        ${rating}
      </strong>

      <small>
        ${escapeHtml(label)}
      </small>
    </div>
  `;
}


/* =====================================================
   STOCK GROWTH
===================================================== */

function selectedStockGrowth(row) {
  const period =
    el("stockGrowthPeriod")?.value ||
    "3M";

  if (period === "1M") {
    return num(row.stockGrowth1M);
  }

  if (period === "6M") {
    return num(row.stockGrowth6M);
  }

  return num(row.stockGrowth3M);
}


/* =====================================================
   FORMATTERS
===================================================== */

function formatNumber(value) {
  const n = num(value);

  if (n === null) {
    return "—";
  }

  return n.toLocaleString(
    "en-IN",
    {
      maximumFractionDigits: 0
    }
  );
}


function formatPrice(value) {
  const n = num(value);

  if (n === null) {
    return `
      <span class="pending">
        Pending EOD
      </span>
    `;
  }

  return `₹${n.toLocaleString(
    "en-IN",
    {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }
  )}`;
}


function formatPct(value) {
  const n = num(value);

  if (n === null) {
    return `
      <span class="pending">
        —
      </span>
    `;
  }

  const sign =
    n > 0
      ? "+"
      : "";

  const cls =
    n > 0
      ? "positive"
      : n < 0
        ? "negative"
        : "";

  return `
    <span class="${cls}">
      ${sign}${n.toFixed(2)}%
    </span>
  `;
}


function formatPlainPct(value) {
  const n = num(value);

  if (n === null) {
    return `
      <span class="pending">
        —
      </span>
    `;
  }

  return `${n.toFixed(2)}%`;
}


function formatTimes(value) {
  const n = num(value);

  if (n === null) {
    return `
      <span class="pending">
        —
      </span>
    `;
  }

  return `${n.toFixed(2)}x`;
}


function formatScore(value) {
  const n = num(value);

  if (n === null) {
    return `
      <span class="pending">
        Pending
      </span>
    `;
  }

  return Math.round(n);
}


/* =====================================================
   MARKET CAP
===================================================== */

function marketCapVal(row) {
  const category = row.marketCapCategory;
  const marketCap = num(row.marketCapCr);

  if (
    !category &&
    marketCap === null
  ) {
    return `
      <span class="pending">
        Pending
      </span>
    `;
  }

  let html = "";

  if (category) {
    html += `
      <div class="market-cap-category">
        ${escapeHtml(category)}
      </div>
    `;
  }

  if (marketCap !== null) {
    html += `
      <div class="market-cap-value">
        ₹${marketCap.toLocaleString(
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


/* =====================================================
   5L + 5% STATUS
===================================================== */

function highVolumeMoveVal(row) {
  const volume = totalVolume(row);
  const change = num(row.changePct);

  if (
    volume === null ||
    change === null
  ) {
    return `
      <span class="pending">
        —
      </span>
    `;
  }

  if (qualifiesHighVolumeMove(row)) {
    return `
      <span class="setup-yes">
        YES
      </span>
    `;
  }

  return `
    <span class="setup-no">
      NO
    </span>
  `;
}


/* =====================================================
   RESEARCH DETAILS
===================================================== */

function normalizeDetailItem(title, item) {
  if (!item) {
    return null;
  }

  if (
    typeof item === "number" ||
    typeof item === "string"
  ) {
    return {
      title,
      score: item,
      reason: "",
      source: "",
      sourceDate: "",
      mode: ""
    };
  }

  return {
    title,

    score:
      item.score ??
      item.value ??
      "",

    reason:
      item.reason ??
      "",

    source:
      item.source ??
      "",

    sourceDate:
      item.sourceDate ??
      "",

    mode:
      item.mode ??
      ""
  };
}


function buildCombinedReasonHtml(details) {
  if (!details) {
    return `
      <div class="pending">
        Details not available.
      </div>
    `;
  }

  const items = [];

  if (Array.isArray(details)) {
    for (const item of details) {
      items.push(
        normalizeDetailItem(
          item.title ||
          item.name ||
          "Research",
          item
        )
      );
    }
  } else {
    const keyMap = {
      tailwind: "Tailwind",
      macro: "Macro",
      macroSupport: "Macro",
      valueMigration: "Value Migration",
      futureGrowth: "Future Growth",
      fundamental: "Fundamental",
      fundamentalQuality: "Fundamental",
      capex: "CAPEX",
      capexScore: "CAPEX"
    };

    for (
      const [key, title]
      of Object.entries(keyMap)
    ) {
      if (details[key]) {
        items.push(
          normalizeDetailItem(
            title,
            details[key]
          )
        );
      }
    }

    if (!items.length) {
      for (
        const [key, value]
        of Object.entries(details)
      ) {
        if (
          value &&
          typeof value === "object"
        ) {
          items.push(
            normalizeDetailItem(
              key,
              value
            )
          );
        }
      }
    }
  }

  const validItems =
    items.filter(Boolean);

  if (!validItems.length) {
    return `
      <div class="pending">
        Details not available.
      </div>
    `;
  }

  return validItems
    .map(item => {
      const reason =
        escapeHtml(
          item.reason ||
          "No reason available."
        );

      const score =
        item.score !== ""
          ? escapeHtml(item.score)
          : "—";

      const mode =
        item.mode
          ? `
            <div>
              <strong>Mode:</strong>
              ${escapeHtml(item.mode)}
            </div>
          `
          : "";

      const sourceDate =
        item.sourceDate
          ? `
            <div>
              <strong>Date:</strong>
              ${escapeHtml(item.sourceDate)}
            </div>
          `
          : "";

      const source =
        item.source
          ? `
            <div class="detail-source">
              <strong>Source:</strong>
              ${escapeHtml(item.source)}
            </div>
          `
          : "";

      return `
        <div class="reason-section">

          <h3>
            ${escapeHtml(item.title)}
            — ${score}
          </h3>

          <p>
            ${reason}
          </p>

          ${mode}

          ${sourceDate}

          ${source}

        </div>
      `;
    })
    .join("");
}


/* =====================================================
   STANDARD RESEARCH MODAL
===================================================== */

function openReasonModal(
  title,
  score,
  details
) {
  const modal = el("reasonModal");

  if (!modal) {
    return;
  }

  const card =
    modal.querySelector(
      ".reason-modal-card"
    );

  card?.classList.remove(
    "market-view-modal-card"
  );

  el("reasonTitle").textContent =
    title;

  el("reasonScore").textContent =
    score !== null &&
    score !== undefined
      ? `Score: ${Math.round(Number(score))}`
      : "Score: Pending";

  el("reasonText").innerHTML =
    buildCombinedReasonHtml(details);

  el("reasonSourceDate").textContent =
    "";

  const sourceLink =
    el("reasonSourceLink");

  if (sourceLink) {
    sourceLink.style.display = "none";
  }

  modal.classList.add("open");

  modal.setAttribute(
    "aria-hidden",
    "false"
  );
}


function closeReasonModal() {
  const modal = el("reasonModal");

  if (!modal) {
    return;
  }

  const card =
    modal.querySelector(
      ".reason-modal-card"
    );

  card?.classList.remove(
    "market-view-modal-card"
  );

  modal.classList.remove("open");

  modal.setAttribute(
    "aria-hidden",
    "true"
  );
}


/* =====================================================
   SCORE BUTTON
===================================================== */

function researchScoreButton(
  rowIndex,
  type,
  score
) {
  const n = num(score);

  if (n === null) {
    return `
      <span class="pending">
        Pending
      </span>
    `;
  }

  return `
    <button
      type="button"
      class="score-info-button"
      data-row-index="${rowIndex}"
      data-reason-type="${type}"
    >

      ${Math.round(n)}

      <span class="info-icon">
        ⓘ
      </span>

    </button>
  `;
}


/* =====================================================
   FILTER HELPERS
===================================================== */

function inputNumber(id) {
  const element = el(id);

  if (!element) {
    return null;
  }

  if (element.value === "") {
    return null;
  }

  return num(element.value);
}


function checked(id) {
  return Boolean(
    el(id)?.checked
  );
}


/* =====================================================
   FILTERING
===================================================== */

function passesFilters(row) {
  if (
    !passesPermanentUniverseRule(row)
  ) {
    return false;
  }

  const q =
    (
      el("q")?.value ||
      ""
    )
      .trim()
      .toLowerCase();

  if (q) {
    const haystack = [
      row.symbol,
      row.name,
      row.companyName,
      row.isin,
      row.sector,
      row.industry
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    if (!haystack.includes(q)) {
      return false;
    }
  }


  if (checked("activeMarketCap")) {
    const enteredThreshold =
      inputNumber(
        "aboveMarketCap"
      );

    const threshold =
      enteredThreshold === null
        ? MIN_MARKET_CAP_CR
        : Math.max(
            MIN_MARKET_CAP_CR,
            enteredThreshold
          );

    const value =
      num(row.marketCapCr);

    if (value === null) {
      return false;
    }

    if (value < threshold) {
      return false;
    }
  }


  if (checked("activePrice")) {
    const threshold =
      inputNumber("abovePrice");

    const value =
      num(row.price);

    if (value === null) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  if (checked("activeChange")) {
    const threshold =
      inputNumber("aboveChange");

    const value =
      num(row.changePct);

    if (value === null) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  if (checked("activeTodayVolume")) {
    const threshold =
      inputNumber(
        "aboveTodayVolume"
      );

    const value =
      totalVolume(row);

    if (value === null) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  if (checked("activeTodayDelivery")) {
    const threshold =
      inputNumber(
        "aboveTodayDelivery"
      );

    const value =
      todayDeliveryVolume(row);

    if (value === null) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  if (checked("active5DDelivery")) {
    const threshold =
      inputNumber(
        "above5DDelivery"
      );

    const value =
      avg5DayDelivery(row);

    if (value === null) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  if (checked("activeDeliveryRatio")) {
    const threshold =
      inputNumber(
        "aboveDeliveryRatio"
      );

    const value =
      deliveryTimes(row);

    if (value === null) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  if (checked("activeDeliveryPct")) {
    const threshold =
      inputNumber(
        "aboveDeliveryPct"
      );

    const value =
      deliveryPercentage(row);

    if (value === null) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  if (
    checked("activeHighVolMove") &&
    !qualifiesHighVolumeMove(row)
  ) {
    return false;
  }


  if (checked("activeRS")) {
    const threshold =
      inputNumber("aboveRS");

    const value =
      rsRating(row);

    if (value === null) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  if (checked("activeSector")) {
    const value =
      el("sectorFilter")?.value ||
      "";

    if (
      value &&
      row.sector !== value
    ) {
      return false;
    }
  }


  if (checked("activeIndustry")) {
    const value =
      el("industryFilter")?.value ||
      "";

    if (
      value &&
      row.industry !== value
    ) {
      return false;
    }
  }


  if (checked("activeSectorGrowth")) {
    const threshold =
      inputNumber(
        "aboveSectorGrowth"
      );

    const value =
      num(row.sectorGrowth1M);

    if (value === null) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  if (checked("activeStockGrowth")) {
    const threshold =
      inputNumber(
        "aboveStockGrowth"
      );

    const value =
      selectedStockGrowth(row);

    if (value === null) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  if (checked("activeTMV")) {
    const threshold =
      inputNumber("aboveTMV");

    const value =
      num(row.tmvScore);

    if (value === null) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  if (checked("activeGFC")) {
    const threshold =
      inputNumber("aboveGFC");

    const value =
      num(row.gfcScore);

    if (value === null) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  if (checked("activeOverall")) {
    const threshold =
      inputNumber(
        "aboveOverall"
      );

    const value =
      num(row.overallScore);

    if (value === null) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }

  return true;
}


/* =====================================================
   SORT VALUES
===================================================== */

function sortValue(
  row,
  field
) {
  switch (field) {
    case "marketCapCr":
      return num(row.marketCapCr);

    case "price":
      return num(row.price);

    case "changePct":
      return num(row.changePct);

    case "todayVolume":
      return totalVolume(row);

    case "todayDeliveryVolume":
      return todayDeliveryVolume(row);

    case "avg5DayDeliveryVolume":
      return avg5DayDelivery(row);

    case "deliveryVolumeRatio":
      return deliveryTimes(row);

    case "deliveryPct":
      return deliveryPercentage(row);

    case "highVolMove":
      if (
        !qualifiesHighVolumeMove(row)
      ) {
        return null;
      }

      return Math.abs(
        num(row.changePct) || 0
      );

    case "rsRating":
      return rsRating(row);

    case "sectorGrowth1M":
      return num(row.sectorGrowth1M);

    case "stockGrowth":
      return selectedStockGrowth(row);

    case "tmvScore":
      return num(row.tmvScore);

    case "gfcScore":
      return num(row.gfcScore);

    case "overallScore":
      return num(row.overallScore);

    default:
      return null;
  }
}


/* =====================================================
   SORT
===================================================== */

function compareNumericDesc(
  a,
  b,
  field
) {
  const av =
    sortValue(a, field);

  const bv =
    sortValue(b, field);

  if (
    av === null &&
    bv === null
  ) {
    return 0;
  }

  if (av === null) {
    return 1;
  }

  if (bv === null) {
    return -1;
  }

  if (bv !== av) {
    return bv - av;
  }

  return 0;
}


function rankStocks(rows) {
  return [...rows]
    .sort(
      (a, b) => {
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

        if (
          activeSortField !==
          "changePct"
        ) {
          const changeSort =
            compareNumericDesc(
              a,
              b,
              "changePct"
            );

          if (changeSort !== 0) {
            return changeSort;
          }
        }

        const nameA =
          (
            a.name ||
            a.companyName ||
            a.symbol ||
            ""
          )
            .toLowerCase();

        const nameB =
          (
            b.name ||
            b.companyName ||
            b.symbol ||
            ""
          )
            .toLowerCase();

        return nameA.localeCompare(
          nameB
        );
      }
    );
}


/* =====================================================
   ACTIVE SORT MAP
===================================================== */

const sortFieldByActiveCheckbox = {
  activeMarketCap:
    "marketCapCr",

  activePrice:
    "price",

  activeChange:
    "changePct",

  activeTodayVolume:
    "todayVolume",

  activeTodayDelivery:
    "todayDeliveryVolume",

  active5DDelivery:
    "avg5DayDeliveryVolume",

  activeDeliveryRatio:
    "deliveryVolumeRatio",

  activeDeliveryPct:
    "deliveryPct",

  activeHighVolMove:
    "highVolMove",

  activeRS:
    "rsRating",

  activeSectorGrowth:
    "sectorGrowth1M",

  activeStockGrowth:
    "stockGrowth",

  activeTMV:
    "tmvScore",

  activeGFC:
    "gfcScore",

  activeOverall:
    "overallScore"
};


function updateActiveSortFromCheckbox(
  checkboxId
) {
  const checkbox =
    el(checkboxId);

  const field =
    sortFieldByActiveCheckbox[
      checkboxId
    ];

  if (
    !checkbox ||
    !field
  ) {
    return;
  }

  if (checkbox.checked) {
    activeSortField =
      field;
  } else if (
    activeSortField === field
  ) {
    activeSortField =
      findAnotherActiveSortField();
  }
}


function findAnotherActiveSortField() {
  for (
    const [
      checkboxId,
      field
    ]
    of Object.entries(
      sortFieldByActiveCheckbox
    )
  ) {
    if (
      el(checkboxId)?.checked
    ) {
      return field;
    }
  }

  return null;
}


/* =====================================================
   DROPDOWNS
===================================================== */

function fillSelectOptions(
  id,
  values
) {
  const select =
    el(id);

  if (!select) {
    return;
  }

  const current =
    select.value;

  const unique =
    [...new Set(
      values
        .filter(Boolean)
        .map(
          value =>
            String(value).trim()
        )
        .filter(Boolean)
    )]
      .sort(
        (a, b) =>
          a.localeCompare(b)
      );

  select.innerHTML =
    `
      <option value="">
        All
      </option>
    `;

  for (const value of unique) {
    const option =
      document.createElement(
        "option"
      );

    option.value =
      value;

    option.textContent =
      value;

    select.appendChild(
      option
    );
  }

  if (unique.includes(current)) {
    select.value =
      current;
  }
}


function populateDropdowns() {
  fillSelectOptions(
    "sectorFilter",
    allStocks.map(
      row => row.sector
    )
  );

  fillSelectOptions(
    "industryFilter",
    allStocks.map(
      row => row.industry
    )
  );
}


/* =====================================================
   RENDER TABLE
===================================================== */

function renderRows() {
  const tbody =
    el("rows");

  if (!tbody) {
    return;
  }

  filteredStocks =
    rankStocks(
      allStocks.filter(
        passesFilters
      )
    );

  const total =
    filteredStocks.length;

  const totalPages =
    Math.max(
      1,
      Math.ceil(
        total /
        PAGE_SIZE
      )
    );

  if (
    currentPage >
    totalPages
  ) {
    currentPage =
      totalPages;
  }

  if (currentPage < 1) {
    currentPage = 1;
  }

  const start =
    (
      currentPage -
      1
    ) *
    PAGE_SIZE;

  const pageRows =
    filteredStocks.slice(
      start,
      start + PAGE_SIZE
    );

  tbody.innerHTML =
    pageRows
      .map(row => {
        const globalIndex =
          allStocks.indexOf(row);

        const companyName =
          escapeHtml(
            row.name ||
            row.companyName ||
            row.symbol ||
            "—"
          );

        const symbol =
          escapeHtml(
            row.symbol ||
            ""
          );

        const sector =
          escapeHtml(
            row.sector ||
            "—"
          );

        const industry =
          escapeHtml(
            row.industry ||
            "—"
          );

        const stockGrowth =
          selectedStockGrowth(row);

        const deliveryPct =
          deliveryPercentage(row);

        const volume =
          totalVolume(row);

        return `
          <tr>

            <td>
              <div class="stock-cell">

                <strong>
                  ${companyName}
                </strong>

                ${
                  symbol
                    ? `
                      <small>
                        ${symbol}
                      </small>
                    `
                    : ""
                }

              </div>
            </td>


            <td>
              ${marketCapVal(row)}
            </td>


            <td>
              ${formatPrice(row.price)}
            </td>


            <td>
              ${formatPct(row.changePct)}
            </td>


            <td>
              ${
                volume === null
                  ? `
                    <span class="pending">
                      —
                    </span>
                  `
                  : formatNumber(volume)
              }
            </td>


            <td>
              ${
                todayDeliveryVolume(row) === null
                  ? `
                    <span class="pending">
                      —
                    </span>
                  `
                  : formatNumber(
                      todayDeliveryVolume(row)
                    )
              }
            </td>


            <td>
              ${
                avg5DayDelivery(row) === null
                  ? `
                    <span class="pending">
                      —
                    </span>
                  `
                  : formatNumber(
                      avg5DayDelivery(row)
                    )
              }
            </td>


            <td>
              ${formatTimes(
                deliveryTimes(row)
              )}
            </td>


            <td>
              ${formatPlainPct(
                deliveryPct
              )}
            </td>


            <td>
              ${highVolumeMoveVal(row)}
            </td>


            <td>
              ${rsRatingVal(row)}
            </td>


            <td>
              ${sector}
            </td>


            <td>
              ${industry}
            </td>


            <td>
              ${formatPct(
                row.sectorGrowth1M
              )}
            </td>


            <td>
              ${formatPct(
                stockGrowth
              )}
            </td>


            <td>
              ${researchScoreButton(
                globalIndex,
                "tmv",
                row.tmvScore
              )}
            </td>


            <td>
              ${researchScoreButton(
                globalIndex,
                "gfc",
                row.gfcScore
              )}
            </td>


            <td>
              <strong class="overall-score">
                ${formatScore(
                  row.overallScore
                )}
              </strong>
            </td>

          </tr>
        `;
      })
      .join("");

  if (el("resultCount")) {
    el("resultCount").textContent =
      `${total.toLocaleString(
        "en-IN"
      )} matched`;
  }

  if (el("page")) {
    el("page").textContent =
      `Page ${currentPage} of ${totalPages}`;
  }

  if (el("prev")) {
    el("prev").disabled =
      currentPage <= 1;
  }

  if (el("next")) {
    el("next").disabled =
      currentPage >= totalPages;
  }

  syncTopScrollbar();

  setupReasonButtons();
}


/* =====================================================
   RESEARCH BUTTON EVENTS
===================================================== */

function setupReasonButtons() {
  document
    .querySelectorAll(
      ".score-info-button"
    )
    .forEach(
      button => {
        button.addEventListener(
          "click",
          () => {
            const index =
              Number(
                button.dataset.rowIndex
              );

            const type =
              button.dataset.reasonType;

            const row =
              allStocks[index];

            if (!row) {
              return;
            }

            if (type === "tmv") {
              openReasonModal(
                `${
                  row.symbol ||
                  row.name ||
                  "Stock"
                } — T + M + VM`,
                row.tmvScore,
                row.tmvDetails
              );

              return;
            }

            if (type === "gfc") {
              openReasonModal(
                `${
                  row.symbol ||
                  row.name ||
                  "Stock"
                } — G + F + C`,
                row.gfcScore,
                row.gfcDetails
              );
            }
          }
        );
      }
    );
}


/* =====================================================
   FILTER EVENTS
===================================================== */

function applyFilterChange() {
  currentPage = 1;
  renderRows();
}


function setupFilterEvents() {
  el("q")
    ?.addEventListener(
      "input",
      () => {
        currentPage = 1;
        renderRows();
      }
    );

  for (
    const checkboxId
    of Object.keys(
      sortFieldByActiveCheckbox
    )
  ) {
    el(checkboxId)
      ?.addEventListener(
        "change",
        () => {
          updateActiveSortFromCheckbox(
            checkboxId
          );

          applyFilterChange();
        }
      );
  }

  const numericInputs = [
    "aboveMarketCap",
    "abovePrice",
    "aboveChange",
    "aboveTodayVolume",
    "aboveTodayDelivery",
    "above5DDelivery",
    "aboveDeliveryRatio",
    "aboveDeliveryPct",
    "aboveRS",
    "aboveSectorGrowth",
    "aboveStockGrowth",
    "aboveTMV",
    "aboveGFC",
    "aboveOverall"
  ];

  numericInputs.forEach(
    id => {
      el(id)
        ?.addEventListener(
          "input",
          applyFilterChange
        );
    }
  );

  el("activeSector")
    ?.addEventListener(
      "change",
      applyFilterChange
    );

  el("sectorFilter")
    ?.addEventListener(
      "change",
      applyFilterChange
    );

  el("activeIndustry")
    ?.addEventListener(
      "change",
      applyFilterChange
    );

  el("industryFilter")
    ?.addEventListener(
      "change",
      applyFilterChange
    );

  el("stockGrowthPeriod")
    ?.addEventListener(
      "change",
      () => {
        if (
          checked(
            "activeStockGrowth"
          )
        ) {
          activeSortField =
            "stockGrowth";
        }

        applyFilterChange();
      }
    );
}


/* =====================================================
   RESET
===================================================== */

function resetFilters() {
  if (el("q")) {
    el("q").value = "";
  }

  const checkboxes =
    document.querySelectorAll(
      '.filter-row input[type="checkbox"]'
    );

  checkboxes.forEach(
    checkbox => {
      checkbox.checked =
        false;
    }
  );

  const inputs =
    document.querySelectorAll(
      '.filter-row input:not([type="checkbox"])'
    );

  inputs.forEach(
    input => {
      input.value =
        "";
    }
  );

  if (el("sectorFilter")) {
    el("sectorFilter").value =
      "";
  }

  if (el("industryFilter")) {
    el("industryFilter").value =
      "";
  }

  if (el("stockGrowthPeriod")) {
    el("stockGrowthPeriod").value =
      "3M";
  }

  activeSortField = null;
  currentPage = 1;

  renderRows();
}


/* =====================================================
   PAGINATION
===================================================== */

function setupPagination() {
  el("prev")
    ?.addEventListener(
      "click",
      () => {
        if (currentPage > 1) {
          currentPage--;

          renderRows();

          scrollTableTop();
        }
      }
    );

  el("next")
    ?.addEventListener(
      "click",
      () => {
        const totalPages =
          Math.max(
            1,
            Math.ceil(
              filteredStocks.length /
              PAGE_SIZE
            )
          );

        if (
          currentPage <
          totalPages
        ) {
          currentPage++;

          renderRows();

          scrollTableTop();
        }
      }
    );

  el("gotoPage")
    ?.addEventListener(
      "change",
      () => {
        const requested =
          Number(
            el("gotoPage").value
          );

        const totalPages =
          Math.max(
            1,
            Math.ceil(
              filteredStocks.length /
              PAGE_SIZE
            )
          );

        if (
          Number.isFinite(requested)
        ) {
          currentPage =
            Math.min(
              Math.max(
                1,
                Math.floor(requested)
              ),
              totalPages
            );

          renderRows();

          scrollTableTop();
        }
      }
    );
}


function scrollTableTop() {
  const wrap =
    el("tableWrap");

  if (wrap) {
    wrap.scrollTop = 0;
  }
}


/* =====================================================
   TOP SCROLLBAR
===================================================== */

function syncTopScrollbar() {
  const topScroll =
    el("topScroll");

  const topInner =
    el("topScrollInner");

  const tableWrap =
    el("tableWrap");

  const table =
    tableWrap?.querySelector(
      "table"
    );

  if (
    !topScroll ||
    !topInner ||
    !tableWrap ||
    !table
  ) {
    return;
  }

  topInner.style.width =
    `${table.scrollWidth}px`;
}


function setupScrollSync() {
  const topScroll =
    el("topScroll");

  const tableWrap =
    el("tableWrap");

  if (
    !topScroll ||
    !tableWrap
  ) {
    return;
  }

  let syncing = false;

  topScroll.addEventListener(
    "scroll",
    () => {
      if (syncing) {
        return;
      }

      syncing = true;

      tableWrap.scrollLeft =
        topScroll.scrollLeft;

      syncing = false;
    }
  );

  tableWrap.addEventListener(
    "scroll",
    () => {
      if (syncing) {
        return;
      }

      syncing = true;

      topScroll.scrollLeft =
        tableWrap.scrollLeft;

      syncing = false;
    }
  );

  window.addEventListener(
    "resize",
    syncTopScrollbar
  );
}


/* =====================================================
   MARKET SIGNAL HELPERS
===================================================== */

function getEquityRegime(score) {
  const n = num(score);

  if (n === null) {
    return {
      text: "Pending",
      emoji: "⚪",
      className: "market-signal-pending"
    };
  }

  if (n >= 75) {
    return {
      text: "Aggressive Stocks",
      emoji: "🟢🟢",
      className: "market-signal-aggressive"
    };
  }

  if (n >= 65) {
    return {
      text: "Stocks Overweight",
      emoji: "🟢",
      className: "market-signal-overweight"
    };
  }

  if (n >= 55) {
    return {
      text: "Selective Buying",
      emoji: "🟢",
      className: "market-signal-selective"
    };
  }

  if (n >= 45) {
    return {
      text: "Warning",
      emoji: "🟡",
      className: "market-signal-warning"
    };
  }

  if (n >= 35) {
    return {
      text: "Equity Reduce",
      emoji: "🟠",
      className: "market-signal-reduce"
    };
  }

  return {
    text: "Defensive",
    emoji: "🔴",
    className: "market-signal-defensive"
  };
}


function getGoldRegime(score) {
  const n = num(score);

  if (n === null) {
    return {
      text: "Pending",
      emoji: "⚪",
      className: "market-signal-pending"
    };
  }

  if (n >= 75) {
    return {
      text: "Very Strong",
      emoji: "🟢🟢",
      className: "market-signal-aggressive"
    };
  }

  if (n >= 65) {
    return {
      text: "Strong",
      emoji: "🟢",
      className: "market-signal-overweight"
    };
  }

  if (n >= 55) {
    return {
      text: "Positive",
      emoji: "🟢",
      className: "market-signal-selective"
    };
  }

  if (n >= 45) {
    return {
      text: "Neutral / Cautious",
      emoji: "🟡",
      className: "market-signal-warning"
    };
  }

  if (n >= 35) {
    return {
      text: "Weak / Correction",
      emoji: "🟠",
      className: "market-signal-reduce"
    };
  }

  return {
    text: "Weak",
    emoji: "🔴",
    className: "market-signal-defensive"
  };
}


function getAssetRegime(
  score,
  assetType
) {
  if (assetType === "gold") {
    return getGoldRegime(score);
  }

  return getEquityRegime(score);
}


/* =====================================================
   HEADER MONTHLY / WEEKLY / DAILY
===================================================== */

function averageMarketViewScore(
  timeframe
) {
  const segments = [
    multiTimeframeMarketView?.nifty50,
    multiTimeframeMarketView?.midcap100,
    multiTimeframeMarketView?.smallcap100
  ];

  const values =
    segments
      .map(
        segment =>
          num(segment?.[timeframe])
      )
      .filter(
        value =>
          value !== null
      );

  if (!values.length) {
    return null;
  }

  return (
    values.reduce(
      (sum, value) =>
        sum + value,
      0
    ) /
    values.length
  );
}


function regimeCardClass(score) {
  const n = num(score);

  if (n === null) {
    return "regime-pending";
  }

  if (n >= 75) {
    return "regime-aggressive";
  }

  if (n >= 65) {
    return "regime-overweight";
  }

  if (n >= 55) {
    return "regime-selective";
  }

  if (n >= 45) {
    return "regime-warning";
  }

  if (n >= 35) {
    return "regime-reduce";
  }

  return "regime-defensive";
}


function updateSingleRegimeCard(
  timeframe,
  cardId,
  scoreId,
  textId
) {
  const card =
    el(cardId);

  const scoreElement =
    el(scoreId);

  const textElement =
    el(textId);

  if (
    !card ||
    !scoreElement ||
    !textElement
  ) {
    return;
  }

  const score =
    averageMarketViewScore(
      timeframe
    );

  card.classList.remove(
    "regime-pending",
    "regime-aggressive",
    "regime-overweight",
    "regime-selective",
    "regime-warning",
    "regime-reduce",
    "regime-defensive"
  );

  card.classList.add(
    regimeCardClass(score)
  );

  if (score === null) {
    scoreElement.textContent =
      "—";

    textElement.textContent =
      "Pending";

    return;
  }

  const rounded =
    Math.round(score);

  const regime =
    getEquityRegime(score);

  scoreElement.textContent =
    rounded;

  textElement.textContent =
    `${regime.emoji} ${regime.text}`;
}


function updateHeaderRegimeCards() {
  updateSingleRegimeCard(
    "monthly",
    "monthlyRegime",
    "monthlyRegimeScore",
    "monthlyRegimeText"
  );

  updateSingleRegimeCard(
    "weekly",
    "weeklyRegime",
    "weeklyRegimeScore",
    "weeklyRegimeText"
  );

  updateSingleRegimeCard(
    "daily",
    "dailyRegime",
    "dailyRegimeScore",
    "dailyRegimeText"
  );
}


/* =====================================================
   MARKET VIEW CARD
===================================================== */

function updateMarketViewCard() {
  const card =
    el("marketViewCard");

  const signal =
    el("marketViewCardSignal");

  if (
    !card ||
    !signal
  ) {
    return;
  }

  const nifty =
    multiTimeframeMarketView?.nifty50 ||
    {};

  const midcap =
    multiTimeframeMarketView?.midcap100 ||
    {};

  const smallcap =
    multiTimeframeMarketView?.smallcap100 ||
    {};

  const values = [
    num(nifty.overall),
    num(midcap.overall),
    num(smallcap.overall)
  ].filter(
    value =>
      value !== null
  );

  if (!values.length) {
    signal.textContent =
      "Largecap • Midcap • Smallcap • SME • Gold";

    return;
  }

  const average =
    values.reduce(
      (sum, value) =>
        sum + value,
      0
    ) /
    values.length;

  const regime =
    getEquityRegime(
      average
    );

  signal.textContent =
    `${regime.emoji} ${regime.text}`;
}


/* =====================================================
   MARKET VIEW CELL
===================================================== */

function marketViewSignalHtml(
  score,
  signalData,
  assetType
) {
  const n =
    num(score);

  if (n === null) {
    return `
      <div class="market-view-score market-signal-pending">

        <strong>
          —
        </strong>

        <span>
          ⚪ Pending
        </span>

      </div>
    `;
  }

  const fallback =
    getAssetRegime(
      n,
      assetType
    );

  const emoji =
    signalData?.emoji ||
    fallback.emoji;

  const label =
    signalData?.label ||
    fallback.text;

  const signalName =
    signalData?.signal ||
    "";

  let className =
    fallback.className;

  if (signalName === "aggressive") {
    className =
      "market-signal-aggressive";
  } else if (
    signalName === "overweight"
  ) {
    className =
      "market-signal-overweight";
  } else if (
    signalName === "selective"
  ) {
    className =
      "market-signal-selective";
  } else if (
    signalName === "warning"
  ) {
    className =
      "market-signal-warning";
  } else if (
    signalName === "reduce"
  ) {
    className =
      "market-signal-reduce";
  } else if (
    signalName === "defensive"
  ) {
    className =
      "market-signal-defensive";
  }

  return `
    <div class="market-view-score ${className}">

      <strong>
        ${Math.round(n)}
      </strong>

      <span>
        ${escapeHtml(emoji)}
        ${escapeHtml(label)}
      </span>

    </div>
  `;
}


/* =====================================================
   MULTI TIMEFRAME MARKET VIEW
===================================================== */

function buildMultiTimeframeMarketViewHtml(
  marketView
) {
  const assetOrder = [
    "nifty50",
    "midcap100",
    "smallcap100",
    "sme",
    "gold"
  ];

  const rows =
    assetOrder
      .map(key => {
        const asset =
          marketView?.[key];

        if (!asset) {
          return "";
        }

        const assetType =
          asset.type ||
          (
            key === "gold"
              ? "gold"
              : "equity"
          );

        let name =
          asset.name ||
          key;

        if (
          key === "gold" &&
          !name.includes("🥇")
        ) {
          name =
            `🥇 ${name}`;
        }

        return `
          <tr>

            <td class="market-view-name">

              <strong>
                ${escapeHtml(name)}
              </strong>

            </td>


            <td>
              ${marketViewSignalHtml(
                asset.daily,
                asset.dailySignal,
                assetType
              )}
            </td>


            <td>
              ${marketViewSignalHtml(
                asset.weekly,
                asset.weeklySignal,
                assetType
              )}
            </td>


            <td>
              ${marketViewSignalHtml(
                asset.monthly,
                asset.monthlySignal,
                assetType
              )}
            </td>


            <td>
              ${marketViewSignalHtml(
                asset.overall,
                asset.overallSignal,
                assetType
              )}
            </td>

          </tr>
        `;
      })
      .join("");

  if (!rows) {
    return `
      <div class="market-view-empty">

        <strong>
          Multi-Timeframe Market View data not available.
        </strong>

      </div>
    `;
  }

  const marketDate =
    metaDataGlobal?.marketRegimeDate ||
    metaDataGlobal?.marketDate ||
    metaDataGlobal?.deliveryDate ||
    "—";

  return `
    <div class="market-view-wrapper">

      <table class="market-view-table">

        <thead>

          <tr>

            <th>
              Asset / Segment
            </th>

            <th>
              DAILY
            </th>

            <th>
              WEEKLY
            </th>

            <th>
              MONTHLY
            </th>

            <th>
              Overall
            </th>

          </tr>

        </thead>


        <tbody>
          ${rows}
        </tbody>

      </table>

    </div>


    <div class="market-view-note">

      <strong>
        Score Interpretation
      </strong>

      <div class="market-view-legend">

        <span>
          75–100 🟢🟢 Aggressive / Very Strong
        </span>

        <span>
          65–74 🟢 Overweight / Strong
        </span>

        <span>
          55–64 🟢 Selective / Positive
        </span>

        <span>
          45–54 🟡 Warning / Neutral
        </span>

        <span>
          35–44 🟠 Reduce / Weak
        </span>

        <span>
          0–34 🔴 Defensive
        </span>

      </div>

    </div>


    <div class="market-view-footer">

      <strong>
        Data as of:
        ${escapeHtml(marketDate)}
      </strong>

    </div>
  `;
}


/* =====================================================
   OPEN MARKET VIEW MODAL
===================================================== */

function openMarketViewModal() {
  const modal =
    el("reasonModal");

  if (!modal) {
    return;
  }

  const card =
    modal.querySelector(
      ".reason-modal-card"
    );

  card?.classList.add(
    "market-view-modal-card"
  );

  el("reasonTitle").textContent =
    "Multi-Timeframe Market View";

  el("reasonScore").textContent =
    "Largecap • Midcap • Smallcap • SME • Gold";

  el("reasonText").innerHTML =
    buildMultiTimeframeMarketViewHtml(
      multiTimeframeMarketView
    );

  el("reasonSourceDate").textContent =
    "";

  const sourceLink =
    el("reasonSourceLink");

  if (sourceLink) {
    sourceLink.style.display =
      "none";
  }

  modal.classList.add(
    "open"
  );

  modal.setAttribute(
    "aria-hidden",
    "false"
  );
}


/* =====================================================
   MARKET VIEW CARD EVENTS
===================================================== */

function setupMarketViewCardEvents() {
  const card =
    el("marketViewCard");

  if (!card) {
    return;
  }

  card.addEventListener(
    "click",
    openMarketViewModal
  );

  card.addEventListener(
    "keydown",
    event => {
      if (
        event.key === "Enter" ||
        event.key === " "
      ) {
        event.preventDefault();

        openMarketViewModal();
      }
    }
  );
}


/* =====================================================
   STATS
===================================================== */

function updateStats(
  stocks,
  meta
) {
  if (el("totalStocks")) {
    el("totalStocks").textContent =
      stocks.length.toLocaleString(
        "en-IN"
      );
  }

  const eodReady =
    stocks.filter(
      row =>
        num(row.price) !== null
    ).length;

  if (el("eodReady")) {
    el("eodReady").textContent =
      eodReady.toLocaleString(
        "en-IN"
      );
  }

  const marketCapReady =
    stocks.filter(
      row =>
        num(row.marketCapCr) !== null
    ).length;

  if (el("marketCapReady")) {
    el("marketCapReady").textContent =
      marketCapReady.toLocaleString(
        "en-IN"
      );
  }

  const fullyScored =
    stocks.filter(
      row =>
        num(row.overallScore) !== null
    ).length;

  if (el("fullyScored")) {
    el("fullyScored").textContent =
      fullyScored.toLocaleString(
        "en-IN"
      );
  }

  const dateCandidates = [
    meta?.marketDate,
    meta?.deliveryDate,
    meta?.date,
    meta?.asOfDate,

    stocks.find(
      row =>
        row.marketDate
    )?.marketDate,

    stocks.find(
      row =>
        row.date
    )?.date
  ];

  let marketDate =
    null;

  for (const value of dateCandidates) {
    if (value) {
      marketDate =
        value;

      break;
    }
  }

  if (el("marketDate")) {
    el("marketDate").textContent =
      marketDate ||
      "—";
  }
}


/* =====================================================
   MODAL EVENTS
===================================================== */

function setupModalEvents() {
  el("closeReasonModal")
    ?.addEventListener(
      "click",
      closeReasonModal
    );

  el("reasonModal")
    ?.addEventListener(
      "click",
      event => {
        if (
          event.target ===
          el("reasonModal")
        ) {
          closeReasonModal();
        }
      }
    );

  document.addEventListener(
    "keydown",
    event => {
      if (event.key === "Escape") {
        closeReasonModal();
      }
    }
  );
}


/* =====================================================
   LOAD JSON
===================================================== */

async function fetchJson(path) {
  const separator =
    path.includes("?")
      ? "&"
      : "?";

  const url =
    `${path}${separator}t=${Date.now()}`;

  const response =
    await fetch(
      url,
      {
        cache: "no-store"
      }
    );

  if (!response.ok) {
    throw new Error(
      `Unable to load ${path}: ${response.status}`
    );
  }

  return response.json();
}


/* =====================================================
   INITIALIZE
===================================================== */

async function init() {
  try {
    const [
      stockData,
      metaData
    ] =
      await Promise.all([
        fetchJson(
          "data/stocks.json"
        ),

        fetchJson(
          "data/meta.json"
        )
          .catch(
            () => ({})
          )
      ]);

    metaDataGlobal =
      metaData ||
      {};

    let loadedStocks = [];

    if (
      Array.isArray(stockData)
    ) {
      loadedStocks =
        stockData;
    } else if (
      Array.isArray(
        stockData?.stocks
      )
    ) {
      loadedStocks =
        stockData.stocks;
    }

    allStocks =
      loadedStocks.filter(
        passesPermanentUniverseRule
      );

    multiTimeframeMarketView =
      metaData?.multiTimeframeMarketView ||
      {};

    populateDropdowns();

    updateStats(
      allStocks,
      metaData
    );


    /* =========================
       FIX HEADER SIGNALS
    ========================== */

    updateHeaderRegimeCards();


    updateMarketViewCard();

    setupFilterEvents();

    setupPagination();

    setupScrollSync();

    setupModalEvents();

    setupMarketViewCardEvents();

    el("resetScores")
      ?.addEventListener(
        "click",
        resetFilters
      );

    activeSortField =
      null;

    renderRows();

    console.log(
      `MY MARKET RESEARCH loaded: `
      +
      `${allStocks.length} stocks `
      +
      `(Known Market Cap >= ₹${MIN_MARKET_CAP_CR} Cr + Pending)`
    );

    console.log(
      "Multi-Timeframe Market View:",
      multiTimeframeMarketView
    );

    console.log(
      "Header regime:",
      {
        daily:
          averageMarketViewScore(
            "daily"
          ),

        weekly:
          averageMarketViewScore(
            "weekly"
          ),

        monthly:
          averageMarketViewScore(
            "monthly"
          )
      }
    );

    const rsReady =
      allStocks.filter(
        row =>
          rsRating(row) !== null
      ).length;

    console.log(
      `RS Rating ready: ${rsReady}/${allStocks.length}`
    );

  } catch (error) {
    console.error(
      "Dashboard load error:",
      error
    );

    if (el("rows")) {
      el("rows").innerHTML =
        `
          <tr>

            <td
              colspan="18"
              class="error-cell"
            >

              Data load failed.

              Please refresh the page
              or check data/stocks.json.

            </td>

          </tr>
        `;
    }
  }
}


/* =====================================================
   START
===================================================== */

document.addEventListener(
  "DOMContentLoaded",
  init
);
/* =====================================================
   CSV / EXCEL DOWNLOAD
===================================================== */

function exportNumber(value) {

  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "";
  }

  if (typeof value === "number") {
    return Number.isFinite(value)
      ? value
      : "";
  }

  const cleaned =
    String(value)
      .replace(/,/g, "")
      .replace(/₹/g, "")
      .replace(/\s*Cr\s*/gi, "")
      .replace(/%/g, "")
      .replace(/x/gi, "")
      .trim();

  if (!cleaned) {
    return "";
  }

  const n = Number(cleaned);

  return Number.isFinite(n)
    ? n
    : "";
}

function exportStockGrowthPeriod() {
  return (
    el("stockGrowthPeriod")?.value ||
    "3M"
  );
}


function buildExportRows() {

  /*
   IMPORTANT:
   Current page ke 100 rows use nahi karne.

   Same filters + same search + same sorting ko
   dobara allStocks par apply karenge.
  */

  const rows =
    rankStocks(
      allStocks.filter(
        passesFilters
      )
    );


  const growthPeriod =
    exportStockGrowthPeriod();


  return rows.map(
    row => {

      const volume =
        totalVolume(row);

      const delivery =
        todayDeliveryVolume(row);

      const avgDelivery =
        avg5DayDelivery(row);

      const deliveryRatio =
        deliveryTimes(row);

      const deliveryPct =
        deliveryPercentage(row);

      const stockGrowth =
        selectedStockGrowth(row);

      const rs =
        rsRating(row);


      return {

        "Stock":
          row.name ||
          row.companyName ||
          row.symbol ||
          "",

        "Symbol":
          row.symbol ||
          "",

        "Market Cap Category":
          row.marketCapCategory ||
          "",

        "Market Cap ₹ Cr":
          exportNumber(
            row.marketCapCr
          ),

        "Price ₹":
          exportNumber(
            row.price
          ),

        "Change %":
          exportNumber(
            row.changePct
          ),

        "Today Volume":
          exportNumber(
            volume
          ),

        "Today Delivery Vol":
          exportNumber(
            delivery
          ),

        "5D Avg Delivery Vol":
          exportNumber(
            avgDelivery
          ),

        "Delivery Times":
          exportNumber(
            deliveryRatio
          ),

        "Delivery %":
          exportNumber(
            deliveryPct
          ),

        "5L Vol + 5% Move":
          qualifiesHighVolumeMove(row)
            ? "YES"
            : "NO",

        "RS Rating":
          exportNumber(
            rs
          ),

        "RS Label":
          rs === null
            ? ""
            : (
                row.rsLabel ||
                rsRatingLabel(rs)
              ),

        "Sector":
          row.sector ||
          "",

        "Industry":
          row.industry ||
          "",

        "Sector Growth 1M %":
          exportNumber(
            row.sectorGrowth1M
          ),

        [`Stock Growth ${growthPeriod} %`]:
          exportNumber(
            stockGrowth
          ),

        "T + M + VM":
          exportNumber(
            row.tmvScore
          ),

        "G + F + C":
          exportNumber(
            row.gfcScore
          ),

        "Overall":
          exportNumber(
            row.overallScore
          )
      };
    }
  );
}


/* =====================================================
   FILE NAME
===================================================== */

function exportFileName(extension) {

  const marketDate =
    metaDataGlobal?.marketDate ||
    metaDataGlobal?.deliveryDate ||
    new Date()
      .toISOString()
      .slice(0, 10);


  const matchedCount =
    allStocks.filter(
      passesFilters
    ).length;


  return (
    `MY_MARKET_RESEARCH_` +
    `${marketDate}_` +
    `${matchedCount}_stocks.` +
    extension
  );
}


/* =====================================================
   CSV ESCAPE
===================================================== */

function csvCell(value) {

  if (
    value === null ||
    value === undefined
  ) {
    return "";
  }


  const text =
    String(value);


  if (
    text.includes(",") ||
    text.includes('"') ||
    text.includes("\n") ||
    text.includes("\r")
  ) {

    return (
      '"' +
      text.replaceAll(
        '"',
        '""'
      ) +
      '"'
    );
  }


  return text;
}


/* =====================================================
   DOWNLOAD BLOB
===================================================== */

function downloadBlob(
  blob,
  filename
) {

  const url =
    URL.createObjectURL(
      blob
    );


  const link =
    document.createElement(
      "a"
    );


  link.href =
    url;

  link.download =
    filename;


  document.body.appendChild(
    link
  );


  link.click();


  link.remove();


  setTimeout(
    () => {
      URL.revokeObjectURL(
        url
      );
    },
    1000
  );
}


/* =====================================================
   CSV DOWNLOAD
===================================================== */

function downloadCSV() {

  const rows =
    buildExportRows();


  if (!rows.length) {

    alert(
      "Current filters me download karne ke liye koi stock nahi hai."
    );

    return;
  }


  const headers =
    Object.keys(
      rows[0]
    );


  const lines = [];


  lines.push(
    headers
      .map(csvCell)
      .join(",")
  );


  for (const row of rows) {

    lines.push(

      headers
        .map(
          header =>
            csvCell(
              row[header]
            )
        )
        .join(",")

    );
  }


  /*
   UTF-8 BOM:
   Excel me company/sector names aur ₹
   correctly open hon.
  */

  const csv =
    "\uFEFF" +
    lines.join(
      "\r\n"
    );


  const blob =
    new Blob(
      [csv],
      {
        type:
          "text/csv;charset=utf-8;"
      }
    );


  downloadBlob(
    blob,
    exportFileName(
      "csv"
    )
  );
}


/* =====================================================
   EXCEL DOWNLOAD
===================================================== */

function downloadExcel() {

  const rows =
    buildExportRows();


  if (!rows.length) {

    alert(
      "Current filters me download karne ke liye koi stock nahi hai."
    );

    return;
  }


  if (
    typeof XLSX ===
    "undefined"
  ) {

    alert(
      "Excel library load nahi hui. Ctrl + F5 karke dobara try karein."
    );

    return;
  }


  const worksheet =
    XLSX.utils.json_to_sheet(
      rows
    );


  /* =========================
     COLUMN WIDTHS
  ========================== */

  worksheet["!cols"] = [

    { wch: 32 }, // Stock
    { wch: 14 }, // Symbol
    { wch: 20 }, // MCap category
    { wch: 18 }, // MCap
    { wch: 14 }, // Price
    { wch: 12 }, // Change
    { wch: 18 }, // Volume
    { wch: 20 }, // Delivery
    { wch: 22 }, // Avg delivery
    { wch: 16 }, // Delivery times
    { wch: 14 }, // Delivery %
    { wch: 18 }, // 5L + 5%
    { wch: 12 }, // RS
    { wch: 14 }, // RS label
    { wch: 24 }, // Sector
    { wch: 28 }, // Industry
    { wch: 20 }, // Sector growth
    { wch: 20 }, // Stock growth
    { wch: 14 }, // TMV
    { wch: 14 }, // GFC
    { wch: 12 }  // Overall
  ];


  const workbook =
    XLSX.utils.book_new();


  XLSX.utils.book_append_sheet(
    workbook,
    worksheet,
    "Market Research"
  );


  XLSX.writeFile(
    workbook,
    exportFileName(
      "xlsx"
    )
  );
}


/* =====================================================
   MAIN DOWNLOAD
===================================================== */

function downloadCurrentResults() {

  const format =
    el("downloadFormat")?.value ||
    "csv";


  if (format === "xlsx") {

    downloadExcel();

    return;
  }


  downloadCSV();
}


/* =====================================================
   DOWNLOAD EVENT
===================================================== */

function setupDownload() {

  const button =
    el("downloadData");


  if (!button) {

    console.warn(
      "Download button not found."
    );

    return;
  }


  button.addEventListener(
    "click",
    downloadCurrentResults
  );
}


/* =====================================================
   INITIALIZE DOWNLOAD
===================================================== */

if (
  document.readyState ===
  "loading"
) {

  document.addEventListener(
    "DOMContentLoaded",
    setupDownload
  );

} else {

  setupDownload();

}
