const PAGE_SIZE = 100;

/*
=========================================================
PERMANENT MARKET CAP RULE
=========================================================

Known Market Cap below ₹100 Cr:
REMOVE from dashboard.

Pending / unknown Market Cap:
KEEP in dashboard.

When Market Cap filter is Active:
Pending gets excluded because numerical
Market Cap is required.
*/

const MIN_MARKET_CAP_CR = 100;


let allStocks = [];
let filteredStocks = [];
let currentPage = 1;


/*
=========================================================
DEFAULT SORT
=========================================================

Normal:
Change % Highest -> Lowest

If numeric column is ACTIVE:
Active column Highest -> Lowest
*/

let activeSortField = null;


/*
=========================================================
DOM HELPERS
=========================================================
*/

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


/*
=========================================================
PERMANENT DASHBOARD UNIVERSE RULE
=========================================================
*/

function passesPermanentUniverseRule(row) {

  const marketCap =
    num(row.marketCapCr);

  /*
  Pending Market Cap:
  retain the stock.
  */

  if (marketCap === null) {
    return true;
  }

  /*
  Known Market Cap:
  only ₹100 Cr and above.
  */

  return marketCap >= MIN_MARKET_CAP_CR;
}


/*
=========================================================
TOTAL VOLUME
=========================================================
*/

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


/*
=========================================================
TODAY DELIVERY VOLUME
=========================================================
*/

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


/*
=========================================================
5 DAY AVG DELIVERY
=========================================================
*/

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


/*
=========================================================
DELIVERY TIMES
=========================================================
*/

function deliveryTimes(row) {

  const direct = num(
    row.deliveryVolumeRatio ??
    row.deliveryTimes
  );

  if (direct !== null) {
    return direct;
  }

  const today =
    todayDeliveryVolume(row);

  const avg =
    avg5DayDelivery(row);

  if (
    today === null ||
    avg === null ||
    avg <= 0
  ) {
    return null;
  }

  return today / avg;
}


/*
=========================================================
DELIVERY %
=========================================================
*/

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

  const delivery =
    todayDeliveryVolume(row);

  const volume =
    totalVolume(row);

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


/*
=========================================================
5 LAKH VOLUME + 5% MOVE
=========================================================
*/

function qualifiesHighVolumeMove(row) {

  const volume =
    totalVolume(row);

  const change =
    num(row.changePct);

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


/*
=========================================================
STOCK GROWTH
=========================================================
*/

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


/*
=========================================================
FORMATTERS
=========================================================
*/

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


/*
=========================================================
MARKET CAP DISPLAY
=========================================================
*/

function marketCapVal(row) {

  const category =
    row.marketCapCategory;

  const marketCap =
    num(row.marketCapCr);

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


/*
=========================================================
5L + 5% STATUS
=========================================================
*/

function highVolumeMoveVal(row) {

  const volume =
    totalVolume(row);

  const change =
    num(row.changePct);

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

  if (
    qualifiesHighVolumeMove(row)
  ) {

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


/*
=========================================================
RESEARCH REASON DETAILS
=========================================================
*/

function normalizeDetailItem(
  title,
  item
) {

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

  if (
    Array.isArray(details)
  ) {

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

      tailwind:
        "Tailwind",

      macro:
        "Macro",

      macroSupport:
        "Macro",

      valueMigration:
        "Value Migration",

      futureGrowth:
        "Future Growth",

      fundamental:
        "Fundamental",

      fundamentalQuality:
        "Fundamental",

      capex:
        "CAPEX",

      capexScore:
        "CAPEX"
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


function openReasonModal(
  title,
  score,
  details
) {

  const modal =
    el("reasonModal");

  if (!modal) {
    return;
  }


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

  const modal =
    el("reasonModal");

  if (!modal) {
    return;
  }

  modal.classList.remove("open");

  modal.setAttribute(
    "aria-hidden",
    "true"
  );
}


/*
=========================================================
SCORE BUTTON
=========================================================
*/

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


/*
=========================================================
FILTER HELPERS
=========================================================
*/

function inputNumber(id) {

  const element =
    el(id);

  if (!element) {
    return null;
  }

  if (
    element.value === ""
  ) {
    return null;
  }

  return num(element.value);
}


function checked(id) {

  return Boolean(
    el(id)?.checked
  );
}


/*
=========================================================
FILTERING
=========================================================
*/

function passesFilters(row) {

  /*
  PERMANENT MARKET CAP RULE
  */

  if (
    !passesPermanentUniverseRule(row)
  ) {
    return false;
  }


  /*
  SEARCH
  */

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


    if (
      !haystack.includes(q)
    ) {
      return false;
    }
  }


  /*
  =====================================================
  MARKET CAP
  =====================================================

  When Active:

  1. Pending market cap removed.
  2. Minimum threshold cannot go below ₹100 Cr.
  3. User value e.g. 500 means >= ₹500 Cr.
  */

  if (
    checked("activeMarketCap")
  ) {

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


    if (
      value === null
    ) {
      return false;
    }


    if (
      value < threshold
    ) {
      return false;
    }
  }


  /*
  PRICE
  */

  if (
    checked("activePrice")
  ) {

    const threshold =
      inputNumber(
        "abovePrice"
      );

    const value =
      num(row.price);

    if (
      value === null
    ) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  /*
  CHANGE %
  */

  if (
    checked("activeChange")
  ) {

    const threshold =
      inputNumber(
        "aboveChange"
      );

    const value =
      num(row.changePct);

    if (
      value === null
    ) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  /*
  TODAY VOLUME
  */

  if (
    checked("activeTodayVolume")
  ) {

    const threshold =
      inputNumber(
        "aboveTodayVolume"
      );

    const value =
      totalVolume(row);

    if (
      value === null
    ) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  /*
  TODAY DELIVERY
  */

  if (
    checked("activeTodayDelivery")
  ) {

    const threshold =
      inputNumber(
        "aboveTodayDelivery"
      );

    const value =
      todayDeliveryVolume(row);

    if (
      value === null
    ) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  /*
  5 DAY AVG DELIVERY
  */

  if (
    checked("active5DDelivery")
  ) {

    const threshold =
      inputNumber(
        "above5DDelivery"
      );

    const value =
      avg5DayDelivery(row);

    if (
      value === null
    ) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  /*
  DELIVERY TIMES
  */

  if (
    checked("activeDeliveryRatio")
  ) {

    const threshold =
      inputNumber(
        "aboveDeliveryRatio"
      );

    const value =
      deliveryTimes(row);

    if (
      value === null
    ) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  /*
  DELIVERY %
  */

  if (
    checked("activeDeliveryPct")
  ) {

    const threshold =
      inputNumber(
        "aboveDeliveryPct"
      );

    const value =
      deliveryPercentage(row);

    if (
      value === null
    ) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  /*
  5L VOL + 5% MOVE
  */

  if (
    checked("activeHighVolMove") &&
    !qualifiesHighVolumeMove(row)
  ) {
    return false;
  }


  /*
  SECTOR
  */

  if (
    checked("activeSector")
  ) {

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


  /*
  INDUSTRY
  */

  if (
    checked("activeIndustry")
  ) {

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


  /*
  SECTOR GROWTH
  */

  if (
    checked("activeSectorGrowth")
  ) {

    const threshold =
      inputNumber(
        "aboveSectorGrowth"
      );

    const value =
      num(row.sectorGrowth1M);

    if (
      value === null
    ) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  /*
  STOCK GROWTH
  */

  if (
    checked("activeStockGrowth")
  ) {

    const threshold =
      inputNumber(
        "aboveStockGrowth"
      );

    const value =
      selectedStockGrowth(row);

    if (
      value === null
    ) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  /*
  TMV
  */

  if (
    checked("activeTMV")
  ) {

    const threshold =
      inputNumber(
        "aboveTMV"
      );

    const value =
      num(row.tmvScore);

    if (
      value === null
    ) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  /*
  GFC
  */

  if (
    checked("activeGFC")
  ) {

    const threshold =
      inputNumber(
        "aboveGFC"
      );

    const value =
      num(row.gfcScore);

    if (
      value === null
    ) {
      return false;
    }

    if (
      threshold !== null &&
      value < threshold
    ) {
      return false;
    }
  }


  /*
  OVERALL
  */

  if (
    checked("activeOverall")
  ) {

    const threshold =
      inputNumber(
        "aboveOverall"
      );

    const value =
      num(row.overallScore);

    if (
      value === null
    ) {
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


/*
=========================================================
SORT VALUE
=========================================================
*/

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


/*
=========================================================
NUMERIC DESCENDING SORT
=========================================================
*/

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


  if (
    av === null &&
    bv === null
  ) {
    return 0;
  }


  if (
    av === null
  ) {
    return 1;
  }


  if (
    bv === null
  ) {
    return -1;
  }


  if (
    bv !== av
  ) {
    return bv - av;
  }


  return 0;
}


/*
=========================================================
RANK STOCKS
=========================================================
*/

function rankStocks(rows) {

  return [...rows]
    .sort(
      (
        a,
        b
      ) => {


        /*
        PRIMARY SORT:
        ACTIVE NUMERIC COLUMN
        */

        if (
          activeSortField
        ) {

          const primary =
            compareNumericDesc(
              a,
              b,
              activeSortField
            );

          if (
            primary !== 0
          ) {
            return primary;
          }
        }


        /*
        NORMAL / SECONDARY:
        CHANGE % HIGH -> LOW
        */

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

          if (
            changeSort !== 0
          ) {
            return changeSort;
          }
        }


        /*
        NAME TIE BREAK
        */

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


/*
=========================================================
ACTIVE SORT MAPPING
=========================================================
*/

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


  if (
    checkbox.checked
  ) {

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


/*
=========================================================
SECTOR / INDUSTRY OPTIONS
=========================================================
*/

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
      (
        a,
        b
      ) =>
        a.localeCompare(b)
    );


  select.innerHTML =
    `
      <option value="">
        All
      </option>
    `;


  for (
    const value
    of unique
  ) {

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


  if (
    unique.includes(current)
  ) {

    select.value =
      current;
  }
}


function populateDropdowns() {

  fillSelectOptions(
    "sectorFilter",
    allStocks.map(
      row =>
        row.sector
    )
  );


  fillSelectOptions(
    "industryFilter",
    allStocks.map(
      row =>
        row.industry
    )
  );
}


/*
=========================================================
RENDER TABLE
=========================================================
*/

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
    currentPage = totalPages;
  }


  if (
    currentPage < 1
  ) {
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


  if (
    el("resultCount")
  ) {

    el("resultCount").textContent =
      `${total.toLocaleString(
        "en-IN"
      )} matched`;
  }


  if (
    el("page")
  ) {

    el("page").textContent =
      `Page ${currentPage} of ${totalPages}`;
  }


  if (
    el("prev")
  ) {

    el("prev").disabled =
      currentPage <= 1;
  }


  if (
    el("next")
  ) {

    el("next").disabled =
      currentPage >= totalPages;
  }


  syncTopScrollbar();

  setupReasonButtons();
}


/*
=========================================================
REASON BUTTON EVENTS
=========================================================
*/

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


            if (
              type === "tmv"
            ) {

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


            if (
              type === "gfc"
            ) {

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


/*
=========================================================
FILTER EVENTS
=========================================================
*/

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


  /*
  ACTIVE NUMERIC FILTERS
  */

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


  /*
  FILTER INPUTS
  */

  const numericInputs = [

    "aboveMarketCap",
    "abovePrice",
    "aboveChange",

    "aboveTodayVolume",
    "aboveTodayDelivery",
    "above5DDelivery",

    "aboveDeliveryRatio",
    "aboveDeliveryPct",

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


  /*
  SECTOR
  */

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


  /*
  INDUSTRY
  */

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


  /*
  STOCK GROWTH PERIOD
  */

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


/*
=========================================================
RESET FILTERS
=========================================================
*/

function resetFilters() {

  if (
    el("q")
  ) {
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


  if (
    el("sectorFilter")
  ) {

    el("sectorFilter").value =
      "";
  }


  if (
    el("industryFilter")
  ) {

    el("industryFilter").value =
      "";
  }


  if (
    el("stockGrowthPeriod")
  ) {

    el("stockGrowthPeriod").value =
      "3M";
  }


  /*
  NORMAL SORT
  */

  activeSortField =
    null;


  currentPage =
    1;


  renderRows();
}


/*
=========================================================
PAGINATION
=========================================================
*/

function setupPagination() {

  el("prev")
    ?.addEventListener(
      "click",
      () => {

        if (
          currentPage > 1
        ) {

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


/*
=========================================================
TOP SCROLLBAR
=========================================================
*/

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


/*
=========================================================
STATS
=========================================================
*/

function updateStats(
  stocks,
  meta
) {

  /*
  Stocks passed here are already
  permanent-universe filtered.
  */

  if (
    el("totalStocks")
  ) {

    el("totalStocks").textContent =
      stocks.length.toLocaleString(
        "en-IN"
      );
  }


  const eodReady =
    stocks.filter(
      row =>
        num(row.price) !== null
    )
    .length;


  if (
    el("eodReady")
  ) {

    el("eodReady").textContent =
      eodReady.toLocaleString(
        "en-IN"
      );
  }


  const marketCapReady =
    stocks.filter(
      row =>
        num(row.marketCapCr) !== null
    )
    .length;


  if (
    el("marketCapReady")
  ) {

    el("marketCapReady").textContent =
      marketCapReady.toLocaleString(
        "en-IN"
      );
  }


  const fullyScored =
    stocks.filter(
      row =>
        num(row.overallScore) !== null
    )
    .length;


  if (
    el("fullyScored")
  ) {

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


  for (
    const value
    of dateCandidates
  ) {

    if (value) {

      marketDate =
        value;

      break;
    }
  }


  if (
    el("marketDate")
  ) {

    el("marketDate").textContent =
      marketDate ||
      "—";
  }
}


/*
=========================================================
MODAL EVENTS
=========================================================
*/

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

      if (
        event.key ===
        "Escape"
      ) {

        closeReasonModal();
      }
    }
  );
}


/*
=========================================================
LOAD JSON
=========================================================
*/

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


  if (
    !response.ok
  ) {

    throw new Error(
      `Unable to load ${path}: ${response.status}`
    );
  }


  return response.json();
}


/*
=========================================================
INITIALIZE
=========================================================
*/

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


    /*
    =====================================================
    PERMANENT MARKET CAP SCREEN
    =====================================================

    Known < ₹100 Cr:
    removed.

    Pending Market Cap:
    retained.
    */

    allStocks =
      loadedStocks.filter(
        passesPermanentUniverseRule
      );


    populateDropdowns();


    updateStats(
      allStocks,
      metaData
    );


    setupFilterEvents();

    setupPagination();

    setupScrollSync();

    setupModalEvents();


    el("resetScores")
      ?.addEventListener(
        "click",
        resetFilters
      );


    /*
    NORMAL:
    CHANGE % HIGH -> LOW
    */

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


  } catch (error) {

    console.error(
      "Dashboard load error:",
      error
    );


    if (
      el("rows")
    ) {

      el("rows").innerHTML =
        `
          <tr>

            <td
              colspan="17"
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


/*
=========================================================
START
=========================================================
*/

document.addEventListener(
  "DOMContentLoaded",
  init
);
