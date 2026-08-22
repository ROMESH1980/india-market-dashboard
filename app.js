const PAGE = 100;

let all = [];
let meta = {};
let page = 1;

const $ = id => document.getElementById(id);

const scoreVal = x =>
  x === null || x === undefined || x === ''
    ? '<span class="pending">Pending</span>'
    : `<span class="score ${x >= 75 ? 'hi' : x >= 60 ? 'mid' : ''}">${Number(x).toFixed(0)}</span>`;

const pct = x =>
  x === null || x === undefined || x === ''
    ? '—'
    : `${Number(x).toFixed(2)}%`;

const volumeVal = x =>
  x === null || x === undefined || x === ''
    ? '—'
    : Number(x).toLocaleString();

const ratioVal = x =>
  x === null || x === undefined || x === ''
    ? '<span class="pending">—</span>'
    : `<strong>${Number(x).toFixed(2)}×</strong>`;

function getMin(id) {
  const el = $(id);

  if (!el || el.value === '') {
    return null;
  }

  const n = Number(el.value);

  return Number.isFinite(n) ? n : null;
}

function scorePass(value, min) {
  if (min === null) return true;

  if (
    value === null ||
    value === undefined ||
    value === ''
  ) {
    return false;
  }

  return Number(value) >= min;
}

function filters() {
  const q = $('q').value.trim().toLowerCase();
  const ex = $('exchange').value;
  const bd = $('board').value;
  const st = $('status').value;

  const minOverall = getMin('minOverall');
  const minMacro = getMin('minMacro');
  const minVM = getMin('minVM');
  const minGrowth = getMin('minGrowth');
  const minFundamental = getMin('minFundamental');
  const minCapex = getMin('minCapex');
  const minSectorStrength = getMin('minSectorStrength');

  return all.filter(s => {
    const text =
      `${s.symbol} ${s.name} ${s.isin} ${s.sector} ${s.industry}`
        .toLowerCase();

    const matchesQ =
      !q || text.includes(q);

    const matchesEx =
      ex === 'ALL' ||
      s.exchange === ex;

    const matchesBd =
      bd === 'ALL' ||
      s.board === bd;

    const matchesStatus =
      st === 'ALL' ||
      (
        st === 'READY'
          ? s.overallScore !== null &&
            s.overallScore !== undefined
          : s.overallScore === null ||
            s.overallScore === undefined
      );

    return (
      matchesQ &&
      matchesEx &&
      matchesBd &&
      matchesStatus &&
      scorePass(s.overallScore, minOverall) &&
      scorePass(s.macroSupport, minMacro) &&
      scorePass(s.valueMigration, minVM) &&
      scorePass(s.futureGrowth, minGrowth) &&
      scorePass(s.fundamentalQuality, minFundamental) &&
      scorePass(s.capexScore, minCapex) &&
      scorePass(s.sectorStrength, minSectorStrength)
    );
  });
}

function rankStocks(rows) {
  return [...rows].sort((a, b) => {
    const ao = a.overallScore;
    const bo = b.overallScore;

    if (ao != null && bo == null) return -1;
    if (ao == null && bo != null) return 1;

    if (ao != null && bo != null) {
      if (Number(bo) !== Number(ao)) {
        return Number(bo) - Number(ao);
      }

      if (
        a.valueMigration != null &&
        b.valueMigration != null &&
        Number(b.valueMigration) !==
        Number(a.valueMigration)
      ) {
        return (
          Number(b.valueMigration) -
          Number(a.valueMigration)
        );
      }

      if (
        a.futureGrowth != null &&
        b.futureGrowth != null &&
        Number(b.futureGrowth) !==
        Number(a.futureGrowth)
      ) {
        return (
          Number(b.futureGrowth) -
          Number(a.futureGrowth)
        );
      }
    }

    return (
      a.name || ''
    ).localeCompare(
      b.name || ''
    );
  });
}

function render() {
  const filtered =
    rankStocks(
      filters()
    );

  const pages =
    Math.max(
      1,
      Math.ceil(
        filtered.length /
        PAGE
      )
    );

  page =
    Math.min(
      page,
      pages
    );

  const rows =
    filtered.slice(
      (page - 1) * PAGE,
      page * PAGE
    );

  $('resultCount').textContent =
    `${filtered.length.toLocaleString()} securities matched`;

  $('page').textContent =
    `Page ${page} / ${pages}`;

  $('prev').disabled =
    page <= 1;

  $('next').disabled =
    page >= pages;

  $('rows').innerHTML =
    rows.map(s => `
      <tr>

        <td>
          <div class="name">
            ${s.name}
          </div>

          <div class="sub">
            ${s.symbol}
            • ${s.isin || '—'}
            • ${s.board || ''}
          </div>
        </td>

        <td>
          <span class="tag">
            ${s.exchange || 'NSE'}
          </span>
        </td>

        <td>
          ${
            s.price == null
              ? '<span class="pending">Pending EOD</span>'
              : `₹${Number(s.price).toFixed(2)}`
          }
        </td>

        <td>
          ${pct(s.changePct)}
        </td>

        <td>
          ${
            s.turnoverCr == null
              ? '—'
              : `₹${Number(s.turnoverCr).toFixed(2)} Cr`
          }
        </td>

        <td>
          ${volumeVal(
            s.todayDeliveryVolume
          )}
        </td>

        <td>
          ${volumeVal(
            s.avg5DayDeliveryVolume
          )}
        </td>

        <td>
          ${ratioVal(
            s.deliveryVolumeRatio
          )}
        </td>

        <td>
          ${s.sector || 'Unclassified'}
        </td>

        <td>
          ${s.industry || 'Unclassified'}
        </td>

        <td>
          ${scoreVal(
            s.sectorStrength
          )}
        </td>

        <td>
          ${scoreVal(
            s.macroSupport
          )}
        </td>

        <td>
          ${scoreVal(
            s.valueMigration
          )}
        </td>

        <td>
          ${scoreVal(
            s.futureGrowth
          )}
        </td>

        <td>
          ${scoreVal(
            s.fundamentalQuality
          )}
        </td>

        <td>
          ${scoreVal(
            s.capexScore
          )}
        </td>

        <td>
          ${scoreVal(
            s.overallScore
          )}
        </td>

      </tr>
    `).join('');
}

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

async function init() {
  [all, meta] =
    await Promise.all([
      fetchJSON(
        'data/stocks.json'
      ),
      fetchJSON(
        'data/meta.json'
      )
    ]);

  $('mode').textContent =
    `${meta.mode} • Updated ${meta.lastUpdated}`;

  const scored =
    all.filter(
      s =>
        s.overallScore !== null &&
        s.overallScore !== undefined
    ).length;

  const classified =
    all.filter(
      s =>
        s.sector &&
        s.sector !==
        'Unclassified'
    ).length;

  $('stats').innerHTML = `
    <div class="stat">
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

    <div class="stat">
      <b>
        ${Number(
          meta.matchedPriceCount ||
          0
        ).toLocaleString()}
      </b>
      <span>
        EOD price ready
      </span>
    </div>

    <div class="stat">
      <b>
        ${classified.toLocaleString()}
      </b>
      <span>
        Sector classified
      </span>
    </div>

    <div class="stat">
      <b>
        ${scored.toLocaleString()}
      </b>
      <span>
        Fully scored
      </span>
    </div>
  `;

  render();
}

[
  'q',
  'exchange',
  'board',
  'status',
  'minOverall',
  'minMacro',
  'minVM',
  'minGrowth',
  'minFundamental',
  'minCapex',
  'minSectorStrength'
].forEach(id => {

  const el = $(id);

  if (!el) {
    return;
  }

  el.addEventListener(
    id === 'q'
      ? 'input'
      : 'change',
    () => {
      page = 1;
      render();
    }
  );
});

const strongBtn =
  $('strongSetup');

if (strongBtn) {
  strongBtn.onclick = () => {

    $('minOverall').value = 70;
    $('minMacro').value = 70;
    $('minVM').value = 70;
    $('minGrowth').value = 70;
    $('minFundamental').value = 60;
    $('minCapex').value = 60;
    $('minSectorStrength').value = 60;

    page = 1;
    render();
  };
}

const resetBtn =
  $('resetScores');

if (resetBtn) {
  resetBtn.onclick = () => {

    [
      'minOverall',
      'minMacro',
      'minVM',
      'minGrowth',
      'minFundamental',
      'minCapex',
      'minSectorStrength'
    ].forEach(id => {
      $(id).value = '';
    });

    page = 1;
    render();
  };
}

$('prev').onclick = () => {
  page--;
  render();

  scrollTo({
    top: 360,
    behavior: 'smooth'
  });
};

$('next').onclick = () => {
  page++;
  render();

  scrollTo({
    top: 360,
    behavior: 'smooth'
  });
};

init();
