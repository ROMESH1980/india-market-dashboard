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
   TODAY TURNOVER (APPROX ₹ CR)
===================================================== */

function todayTurnoverCr(row) {
  const price = num(row.price);
  const volume = totalVolume(row);

  if (
    price === null ||
    volume === null
  ) {
    return null;
  }

  return (
    price *
    volume
  ) / 10000000;
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


function formatTurnoverCr(value) {
  const n = num(value);

  if (n === null) {
    return `
      <span class="pending">
        —
      </span>
    `;
  }

  return `₹${n.toLocaleString(
    "en-IN",
    {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }
  )} Cr`;
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


  if (checked("activeTodayTurnover")) {
    const threshold =
      inputNumber(
        "aboveTodayTurnover"
      );

    const value =
      todayTurnoverCr(row);

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

    case "todayTurnoverCr":
      return todayTurnoverCr(row);

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

  activeTodayTurnover:
    "todayTurnoverCr",

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

        const turnover =
          todayTurnoverCr(row);

        return `
          <tr>

            <!-- STOCK -->

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


            <!-- MARKET CAP -->

            <td>
              ${marketCapVal(row)}
            </td>


            <!-- PRICE -->

            <td>
              ${formatPrice(row.price)}
            </td>


            <!-- CHANGE -->

            <td>
              ${formatPct(row.changePct)}
            </td>


            <!-- TODAY VOLUME -->

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


            <!-- TODAY TURNOVER -->

            <td>
              ${formatTurnoverCr(
                turnover
              )}
            </td>


            <!-- TODAY DELIVERY -->

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


            <!-- 5D AVG DELIVERY -->

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


            <!-- DELIVERY TIMES -->

            <td>
              ${formatTimes(
                deliveryTimes(row)
              )}
            </td>


            <!-- DELIVERY % -->

            <td>
              ${formatPlainPct(
                deliveryPct
              )}
            </td>


            <!-- 5L + 5% MOVE -->

            <td>
              ${highVolumeMoveVal(row)}
            </td>


            <!-- RS RATING -->

            <td>
              ${rsRatingVal(row)}
            </td>


            <!-- SECTOR -->

            <td>
              ${sector}
            </td>


            <!-- INDUSTRY -->

            <td>
              ${industry}
            </td>


            <!-- SECTOR GROWTH -->

            <td>
              ${formatPct(
                row.sectorGrowth1M
              )}
            </td>


            <!-- STOCK GROWTH -->

            <td>
              ${formatPct(
                stockGrowth
              )}
            </td>


            <!-- T + M + VM -->

            <td>
              ${researchScoreButton(
                globalIndex,
                "tmv",
                row.tmvScore
              )}
            </td>


            <!-- G + F + C -->

            <td>
              ${researchScoreButton(
                globalIndex,
                "gfc",
                row.gfcScore
              )}
            </td>


            <!-- OVERALL -->

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
    "aboveTodayTurnover",
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
          currentPage -= 1;
          renderRows();
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
          currentPage += 1;
          renderRows();
        }
      }
    );

  el("gotoPage")
    ?.addEventListener(
      "change",
      () => {
        const requested =
          Number(
            el("gotoPage")?.value
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
              totalPages,
              Math.max(
                1,
                Math.floor(requested)
              )
            );

          renderRows();
        }

        if (el("gotoPage")) {
          el("gotoPage").value =
            "";
        }
      }
    );
}


/* =====================================================
   TOP HORIZONTAL SCROLLBAR
===================================================== */

function syncTopScrollbar() {
  const topScroll =
    el("topScroll");

  const topScrollInner =
    el("topScrollInner");

  const tableWrap =
    el("tableWrap");

  if (
    !topScroll ||
    !topScrollInner ||
    !tableWrap
  ) {
    return;
  }

  topScrollInner.style.width =
    `${tableWrap.scrollWidth}px`;

  topScroll.scrollLeft =
    tableWrap.scrollLeft;
}


function setupTopScrollbar() {
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

  let syncingFromTop =
    false;

  let syncingFromTable =
    false;

  topScroll.addEventListener(
    "scroll",
    () => {
      if (syncingFromTable) {
        return;
      }

      syncingFromTop =
        true;

      tableWrap.scrollLeft =
        topScroll.scrollLeft;

      syncingFromTop =
        false;
    }
  );

  tableWrap.addEventListener(
    "scroll",
    () => {
      if (syncingFromTop) {
        return;
      }

      syncingFromTable =
        true;

      topScroll.scrollLeft =
        tableWrap.scrollLeft;

      syncingFromTable =
        false;
    }
  );

  window.addEventListener(
    "resize",
    syncTopScrollbar
  );
}


/* =====================================================
   STANDARD MODAL EVENTS
===================================================== */

function setupReasonModalEvents() {
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
      if (
        event.key ===
        "Escape"
      ) {
        closeReasonModal();
      }
    }
  );
}


/* =====================================================
   MARKET VIEW REGIME HELPERS
===================================================== */

function getEquityRegime(score) {
  const n = num(score);

  if (n === null) {
    return {
      label: "Pending",
      icon: "⚪",
      action: "Data pending"
    };
  }

  if (n >= 75) {
    return {
      label: "Strong Risk-ON",
      icon: "🟢🟢",
      action: "Aggressive Stocks"
    };
  }

  if (n >= 65) {
    return {
      label: "Risk-ON",
      icon: "🟢",
      action: "Stocks overweight"
    };
  }

  if (n >= 55) {
    return {
      label: "Mild Risk-ON",
      icon: "🟢",
      action: "Selective buying"
    };
  }

  if (n >= 45) {
    return {
      label: "Warning",
      icon: "🟡",
      action: "New buying reduce"
    };
  }

  if (n >= 35) {
    return {
      label: "Risk-OFF",
      icon: "🟠",
      action: "Equity exposure reduce"
    };
  }

  return {
    label: "Strong Risk-OFF",
    icon: "🔴",
    action:
      "Capital protection / G-Sec / Gold / Cash"
  };
}


function getGoldRegime(score) {
  const n = num(score);

  if (n === null) {
    return {
      label: "Pending",
      icon: "⚪",
      action: "Data pending"
    };
  }

  if (n >= 75) {
    return {
      label: "Strong Positive",
      icon: "🟢🟢",
      action: "Strong Gold preference"
    };
  }

  if (n >= 65) {
    return {
      label: "Positive",
      icon: "🟢",
      action: "Gold overweight"
    };
  }

  if (n >= 55) {
    return {
      label: "Mild Positive",
      icon: "🟢",
      action: "Selective Gold allocation"
    };
  }

  if (n >= 45) {
    return {
      label: "Neutral",
      icon: "🟡",
      action: "Balanced allocation"
    };
  }

  if (n >= 35) {
    return {
      label: "Weak",
      icon: "🟠",
      action: "Gold exposure reduce"
    };
  }

  return {
    label: "Strong Weakness",
    icon: "🔴",
    action: "Avoid overweight Gold"
  };
}


/* =====================================================
   MARKET VIEW SCORE HELPERS
===================================================== */

function marketViewOverallScore(item) {
  if (!item) {
    return null;
  }

  const direct =
    num(item.overall);

  if (direct !== null) {
    return direct;
  }

  const values = [
    num(item.daily),
    num(item.weekly),
    num(item.monthly)
  ]
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


function averageMarketViewScore() {
  const candidates = [
    multiTimeframeMarketView.nifty50,
    multiTimeframeMarketView.midcap100,
    multiTimeframeMarketView.smallcap100
  ];

  const scores =
    candidates
      .map(
        marketViewOverallScore
      )
      .filter(
        value =>
          value !== null
      );

  if (!scores.length) {
    return null;
  }

  return (
    scores.reduce(
      (sum, value) =>
        sum + value,
      0
    ) /
    scores.length
  );
}


/* =====================================================
   MARKET VIEW CARD
===================================================== */

function updateMarketViewCard() {
  const signalEl =
    el("marketViewCardSignal");

  if (!signalEl) {
    return;
  }

  const averageScore =
    averageMarketViewScore();

  if (averageScore === null) {
    signalEl.innerHTML =
      `
        <span class="market-view-dot market-view-dot-pending">
        </span>

        Data Pending
      `;

    return;
  }

  const regime =
    getEquityRegime(
      averageScore
    );

  signalEl.innerHTML =
    `
      <span
        class="market-view-dot"
        aria-hidden="true"
      ></span>

      ${escapeHtml(regime.action)}
    `;
}


/* =====================================================
   MARKET VIEW SIGNAL HTML
===================================================== */

function marketViewSignalHtml(
  score,
  isGold = false
) {
  const n = num(score);

  if (n === null) {
    return `
      <span class="market-view-score pending">
        —
      </span>
    `;
  }

  const regime =
    isGold
      ? getGoldRegime(n)
      : getEquityRegime(n);

  return `
    <div class="market-view-signal-cell">

      <strong class="market-view-score">
        ${Math.round(n)}
      </strong>

      <span class="market-view-regime">
        ${regime.icon}
        ${escapeHtml(regime.label)}
      </span>

    </div>
  `;
}


/* =====================================================
   BUILD MARKET VIEW TABLE
===================================================== */

function buildMultiTimeframeMarketViewHtml() {
  const rows = [
    {
      key: "nifty50",
      label: "NIFTY 50 / Largecap",
      gold: false
    },
    {
      key: "midcap100",
      label: "NIFTY Midcap 100",
      gold: false
    },
    {
      key: "smallcap100",
      label: "NIFTY Smallcap 100",
      gold: false
    },
    {
      key: "sme",
      label: "NIFTY SME Emerge",
      gold: false
    },
    {
      key: "gold",
      label: "Gold",
      gold: true
    }
  ];

  const body =
    rows
      .map(item => {
        const data =
          multiTimeframeMarketView[
            item.key
          ] || {};

        const overall =
          marketViewOverallScore(
            data
          );

        return `
          <tr>

            <td class="market-view-name">
              ${escapeHtml(item.label)}
            </td>

            <td>
              ${marketViewSignalHtml(
                data.daily,
                item.gold
              )}
            </td>

            <td>
              ${marketViewSignalHtml(
                data.weekly,
                item.gold
              )}
            </td>

            <td>
              ${marketViewSignalHtml(
                data.monthly,
                item.gold
              )}
            </td>

            <td>
              ${marketViewSignalHtml(
                overall,
                item.gold
              )}
            </td>

          </tr>
        `;
      })
      .join("");

  const proxyRows =
    rows.filter(item => {
      const data =
        multiTimeframeMarketView[
          item.key
        ];

      return Boolean(
        data?.proxy
      );
    });

  const proxyNote =
    proxyRows.length
      ? `
        <div class="market-view-note">
          * Smallcap / SME values marked by available dashboard proxy data
          where official index history is unavailable.
        </div>
      `
      : "";

  return `
    <div class="market-view-wrapper">

      <table class="market-view-table">

        <thead>

          <tr>
            <th>
              Asset / Index
            </th>

            <th>
              Daily
            </th>

            <th>
              Weekly
            </th>

            <th>
              Monthly
            </th>

            <th>
              Overall
            </th>
          </tr>

        </thead>

        <tbody>
          ${body}
        </tbody>

      </table>

      ${proxyNote}

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
    "Current Multi-Timeframe Market View";

  el("reasonScore").textContent =
    "";

  el("reasonText").innerHTML =
    buildMultiTimeframeMarketViewHtml();

  const generatedDate =
    metaDataGlobal.marketDate ||
    metaDataGlobal.deliveryDate ||
    metaDataGlobal.lastUpdated ||
    "";

  el("reasonSourceDate").textContent =
    generatedDate
      ? `Market data: ${generatedDate}`
      : "";

  const sourceLink =
    el("reasonSourceLink");

  if (sourceLink) {
    sourceLink.style.display =
      "none";
  }

  modal.classList.add("open");

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

function updateStats() {
  if (el("totalStocks")) {
    el("totalStocks").textContent =
      allStocks.length
        .toLocaleString("en-IN");
  }

  const eodReady =
    allStocks.filter(
      row =>
        num(row.price) !== null
    ).length;

  if (el("eodReady")) {
    el("eodReady").textContent =
      eodReady
        .toLocaleString("en-IN");
  }

  const marketCapReady =
    allStocks.filter(
      row =>
        num(row.marketCapCr) !== null
    ).length;

  if (el("marketCapReady")) {
    el("marketCapReady").textContent =
      marketCapReady
        .toLocaleString("en-IN");
  }

  const fullyScored =
    allStocks.filter(
      row =>
        num(row.tmvScore) !== null &&
        num(row.gfcScore) !== null &&
        num(row.overallScore) !== null
    ).length;

  if (el("fullyScored")) {
    el("fullyScored").textContent =
      fullyScored
        .toLocaleString("en-IN");
  }
}


/* =====================================================
   MARKET DATE
===================================================== */

function updateMarketDate() {
  const marketDate =
    metaDataGlobal.marketDate ||
    metaDataGlobal.deliveryDate ||
    metaDataGlobal.lastUpdated ||
    "—";

  if (el("marketDate")) {
    el("marketDate").textContent =
      marketDate;
  }
}


/* =====================================================
   HEADER REGIME
===================================================== */

function updateHeaderRegime() {
  updateMarketViewCard();
}


/* =====================================================
   INIT DATA
===================================================== */

async function init() {
  try {
    const cacheBuster =
      Date.now();

    const [
      stocksResponse,
      metaResponse
    ] =
      await Promise.all([
        fetch(
          `data/stocks.json?v=${cacheBuster}`
        ),
        fetch(
          `data/meta.json?v=${cacheBuster}`
        )
      ]);

    if (!stocksResponse.ok) {
      throw new Error(
        `stocks.json HTTP ${stocksResponse.status}`
      );
    }

    if (!metaResponse.ok) {
      throw new Error(
        `meta.json HTTP ${metaResponse.status}`
      );
    }

    const stocksData =
      await stocksResponse.json();

    const metaData =
      await metaResponse.json();

    metaDataGlobal =
      metaData || {};

    multiTimeframeMarketView =
      metaDataGlobal
        .multiTimeframeMarketView ||
      metaDataGlobal
        .marketView ||
      {};

    const sourceStocks =
      Array.isArray(stocksData)
        ? stocksData
        : (
            stocksData.stocks ||
            []
          );

    allStocks =
      sourceStocks.filter(
        passesPermanentUniverseRule
      );

    populateDropdowns();

    updateStats();

    updateMarketDate();

    updateHeaderRegime();

    setupFilterEvents();

    setupPagination();

    setupTopScrollbar();

    setupReasonModalEvents();

    setupMarketViewCardEvents();

    el("resetScores")
      ?.addEventListener(
        "click",
        resetFilters
      );

    renderRows();

  } catch (error) {
    console.error(
      "Dashboard initialization failed:",
      error
    );

    const tbody =
      el("rows");

    if (tbody) {
      tbody.innerHTML =
        `
          <tr>
            <td
              colspan="19"
              class="pending"
            >
              Unable to load market data.
            </td>
          </tr>
        `;
    }

    if (el("resultCount")) {
      el("resultCount").textContent =
        "0 matched";
    }
  }
}


document.addEventListener(
  "DOMContentLoaded",
  init
);
/* =====================================================
   EXPORT HELPERS
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


function exportRoundedNumber(
  value,
  decimals = 2
) {
  const n = exportNumber(value);

  if (n === "") {
    return "";
  }

  const factor =
    10 ** decimals;

  return Math.round(
    (n + Number.EPSILON) *
    factor
  ) / factor;
}


function exportInteger(value) {
  const n = exportNumber(value);

  return n === ""
    ? ""
    : Math.round(n);
}


function exportStockGrowthPeriod() {
  return (
    el("stockGrowthPeriod")?.value ||
    "3M"
  );
}


/* =====================================================
   BUILD EXPORT ROWS
===================================================== */

function buildExportRows() {
  const rows =
    rankStocks(
      allStocks.filter(
        passesFilters
      )
    );

  const growthPeriod =
    exportStockGrowthPeriod();

  return rows.map(row => {
    const volume =
      totalVolume(row);

    const turnover =
      todayTurnoverCr(row);

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

    const rating =
      rsRating(row);

    return {
      "Stock":
        row.name ||
        row.companyName ||
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
        exportRoundedNumber(
          row.price,
          2
        ),

      "Change %":
        exportRoundedNumber(
          row.changePct,
          2
        ),

      "Today Volume":
        exportInteger(
          volume
        ),

      "Today Turnover ₹ Cr":
        exportRoundedNumber(
          turnover,
          2
        ),

      "Today Delivery Vol":
        exportInteger(
          delivery
        ),

      "5D Avg Delivery Vol":
        exportInteger(
          avgDelivery
        ),

      "Delivery Times":
        exportRoundedNumber(
          deliveryRatio,
          2
        ),

      "Delivery %":
        exportRoundedNumber(
          deliveryPct,
          2
        ),

      "5L Vol + 5% Move":
        qualifiesHighVolumeMove(row)
          ? "YES"
          : "NO",

      "RS Rating":
        rating === null
          ? ""
          : exportInteger(rating),

      "RS Label":
        rating === null
          ? "Pending"
          : (
              row.rsLabel ||
              rsRatingLabel(rating)
            ),

      "Sector":
        row.sector ||
        "",

      "Industry":
        row.industry ||
        "",

      "Sector Growth 1M %":
        exportRoundedNumber(
          row.sectorGrowth1M,
          2
        ),

      [`Stock Growth ${growthPeriod} %`]:
        exportRoundedNumber(
          stockGrowth,
          2
        ),

      "T + M + VM":
        exportInteger(
          row.tmvScore
        ),

      "G + F + C":
        exportInteger(
          row.gfcScore
        ),

      "Overall":
        exportInteger(
          row.overallScore
        )
    };
  });
}


/* =====================================================
   EXPORT FILE NAME
===================================================== */

function exportFileBaseName(
  rowCount
) {
  const marketDate =
    metaDataGlobal.marketDate ||
    metaDataGlobal.deliveryDate ||
    metaDataGlobal.lastUpdated ||
    "latest";

  return (
    `MY_MARKET_RESEARCH_` +
    `${marketDate}_` +
    `${rowCount}_stocks`
  );
}


/* =====================================================
   CSV EXPORT
===================================================== */

function csvEscape(value) {
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
    text.includes("\n")
  ) {
    return (
      '"' +
      text.replace(
        /"/g,
        '""'
      ) +
      '"'
    );
  }

  return text;
}


function downloadCSV(rows) {
  if (!rows.length) {
    alert(
      "No matched stocks to download."
    );

    return;
  }

  const headers =
    Object.keys(
      rows[0]
    );

  const csvLines = [
    headers
      .map(csvEscape)
      .join(",")
  ];

  for (const row of rows) {
    csvLines.push(
      headers
        .map(
          header =>
            csvEscape(
              row[header]
            )
        )
        .join(",")
    );
  }

  const csvContent =
    "\uFEFF" +
    csvLines.join("\r\n");

  const blob =
    new Blob(
      [csvContent],
      {
        type:
          "text/csv;charset=utf-8;"
      }
    );

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
    `${exportFileBaseName(
      rows.length
    )}.csv`;

  document.body.appendChild(
    link
  );

  link.click();

  link.remove();

  URL.revokeObjectURL(
    url
  );
}


/* =====================================================
   EXCEL HELPERS
===================================================== */

function findExcelColumnIndex(
  headers,
  headerName
) {
  return headers.indexOf(
    headerName
  );
}


function applyExcelNumberFormat(
  worksheet,
  headers,
  headerName,
  format
) {
  const columnIndex =
    findExcelColumnIndex(
      headers,
      headerName
    );

  if (columnIndex < 0) {
    return;
  }

  const range =
    XLSX.utils.decode_range(
      worksheet["!ref"]
    );

  for (
    let rowIndex =
      range.s.r + 1;
    rowIndex <= range.e.r;
    rowIndex++
  ) {
    const address =
      XLSX.utils.encode_cell(
        {
          r: rowIndex,
          c: columnIndex
        }
      );

    const cell =
      worksheet[address];

    if (!cell) {
      continue;
    }

    if (
      cell.t === "n" &&
      typeof cell.v === "number"
    ) {
      cell.z =
        format;
    }
  }
}


/* =====================================================
   EXCEL EXPORT
===================================================== */

function downloadExcel(rows) {
  if (!rows.length) {
    alert(
      "No matched stocks to download."
    );

    return;
  }

  if (
    typeof XLSX ===
    "undefined"
  ) {
    alert(
      "Excel library not loaded. Please refresh and try again."
    );

    return;
  }

  const worksheet =
    XLSX.utils.json_to_sheet(
      rows
    );

  const headers =
    Object.keys(
      rows[0]
    );


  /* =========================
     COLUMN WIDTHS
  ========================== */

  worksheet["!cols"] =
    headers.map(header => {
      const widths = {
        "Stock": 30,
        "Symbol": 14,
        "Market Cap Category": 20,
        "Market Cap ₹ Cr": 18,
        "Price ₹": 14,
        "Change %": 12,
        "Today Volume": 16,
        "Today Turnover ₹ Cr": 20,
        "Today Delivery Vol": 20,
        "5D Avg Delivery Vol": 22,
        "Delivery Times": 16,
        "Delivery %": 14,
        "5L Vol + 5% Move": 18,
        "RS Rating": 12,
        "RS Label": 14,
        "Sector": 24,
        "Industry": 28,
        "Sector Growth 1M %": 20,
        [`Stock Growth ${
          exportStockGrowthPeriod()
        } %`]: 20,
        "T + M + VM": 14,
        "G + F + C": 14,
        "Overall": 12
      };

      return {
        wch:
          widths[header] ||
          16
      };
    });


  /* =========================
     NUMBER FORMATS
  ========================== */

  applyExcelNumberFormat(
    worksheet,
    headers,
    "Market Cap ₹ Cr",
    "0.00"
  );

  applyExcelNumberFormat(
    worksheet,
    headers,
    "Price ₹",
    "0.00"
  );

  applyExcelNumberFormat(
    worksheet,
    headers,
    "Change %",
    "0.00"
  );

  applyExcelNumberFormat(
    worksheet,
    headers,
    "Today Volume",
    "0"
  );

  applyExcelNumberFormat(
    worksheet,
    headers,
    "Today Turnover ₹ Cr",
    "0.00"
  );

  applyExcelNumberFormat(
    worksheet,
    headers,
    "Today Delivery Vol",
    "0"
  );

  applyExcelNumberFormat(
    worksheet,
    headers,
    "5D Avg Delivery Vol",
    "0"
  );

  applyExcelNumberFormat(
    worksheet,
    headers,
    "Delivery Times",
    "0.00"
  );

  applyExcelNumberFormat(
    worksheet,
    headers,
    "Delivery %",
    "0.00"
  );

  applyExcelNumberFormat(
    worksheet,
    headers,
    "RS Rating",
    "0"
  );

  applyExcelNumberFormat(
    worksheet,
    headers,
    "Sector Growth 1M %",
    "0.00"
  );

  applyExcelNumberFormat(
    worksheet,
    headers,
    `Stock Growth ${
      exportStockGrowthPeriod()
    } %`,
    "0.00"
  );

  applyExcelNumberFormat(
    worksheet,
    headers,
    "T + M + VM",
    "0"
  );

  applyExcelNumberFormat(
    worksheet,
    headers,
    "G + F + C",
    "0"
  );

  applyExcelNumberFormat(
    worksheet,
    headers,
    "Overall",
    "0"
  );


  /* =========================
     FREEZE TOP ROW
  ========================== */

  worksheet["!freeze"] = {
    xSplit: 0,
    ySplit: 1,
    topLeftCell: "A2",
    activePane: "bottomLeft",
    state: "frozen"
  };


  /* =========================
     AUTO FILTER
  ========================== */

  if (worksheet["!ref"]) {
    worksheet["!autofilter"] = {
      ref:
        worksheet["!ref"]
    };
  }


  /* =========================
     WORKBOOK
  ========================== */

  const workbook =
    XLSX.utils.book_new();

  XLSX.utils.book_append_sheet(
    workbook,
    worksheet,
    "Market Research"
  );

  XLSX.writeFile(
    workbook,
    `${exportFileBaseName(
      rows.length
    )}.xlsx`
  );
}


/* =====================================================
   DOWNLOAD HANDLER
===================================================== */

function handleDownload() {
  const rows =
    buildExportRows();

  if (!rows.length) {
    alert(
      "No matched stocks to download."
    );

    return;
  }

  const format =
    el("downloadFormat")?.value ||
    "csv";

  if (format === "xlsx") {
    downloadExcel(rows);
    return;
  }

  downloadCSV(rows);
}


/* =====================================================
   DOWNLOAD SETUP
===================================================== */

function setupDownload() {
  el("downloadData")
    ?.addEventListener(
      "click",
      handleDownload
    );
}


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
