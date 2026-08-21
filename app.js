const PAGE = 100;

let all = [];
let meta = {};
let page = 1;

const $ = id => document.getElementById(id);

const scoreVal = x =>
  x === null || x === undefined || x === ''
    ? '<span class="pending">Pending</span>'
    : `<span class="score ${x >= 75 ? 'hi' : x >= 60 ? 'mid' : ''}">${Math.round(x)}</span>`;

const num = x =>
  x === null || x === undefined || x === ''
    ? '—'
    : Number(x).toLocaleString();

const pct = x =>
  x === null || x === undefined || x === ''
    ? '—'
    : `${Number(x).toFixed(2)}%`;

function filters() {
  const q = $('q').value.trim().toLowerCase();
  const ex = $('exchange').value;
  const bd = $('board').value;
  const st = $('status').value;

  return all.filter(s => {
    const matchesQ =
      !q ||
      `${s.symbol} ${s.name} ${s.isin} ${s.sector} ${s.industry}`
        .toLowerCase()
        .includes(q);

    const matchesEx =
      ex === 'ALL' ||
      s.exchange === ex ||
      (s.exchanges || []).includes(ex);

    const matchesBd =
      bd === 'ALL' ||
      s.board === bd;

    const matchesStatus =
      st === 'ALL' ||
      (st === 'READY'
        ? s.dataStatus === 'EOD_READY'
        : s.dataStatus !== 'EOD_READY');

    return matchesQ && matchesEx && matchesBd && matchesStatus;
  });
}

function render() {
  const f = filters();
  const pages = Math.max(1, Math.ceil(f.length / PAGE));

  page = Math.min(page, pages);

  const rows = f.slice(
    (page - 1) * PAGE,
    page * PAGE
  );

  $('resultCount').textContent =
    `${f.length.toLocaleString()} securities matched`;

  $('page').textContent =
    `Page ${page} / ${pages}`;

  $('prev').disabled = page <= 1;
  $('next').disabled = page >= pages;

  $('rows').innerHTML = rows.map(s => `
    <tr>
      <td>
        <div class="name">${s.name}</div>
        <div class="sub">
          ${s.symbol} • ${s.isin || '—'} • ${s.board || ''}
        </div>
      </td>

      <td>
        <span class="tag">${s.exchange || 'NSE'}</span>
      </td>

      <td>
        ${
          s.price == null
            ? '<span class="pending">Pending EOD</span>'
            : `₹${Number(s.price).toFixed(2)}`
        }
      </td>

      <td>${pct(s.changePct)}</td>

      <td>${num(s.volume)}</td>

      <td>
        ${
          s.turnoverCr == null
            ? '—'
            : `₹${Number(s.turnoverCr).toFixed(2)} Cr`
        }
      </td>

      <td>${s.sector || 'Unclassified'}</td>

      <td>${s.industry || 'Unclassified'}</td>

      <td>${scoreVal(s.sectorStrength)}</td>

      <td>${scoreVal(s.macroSupport)}</td>

      <td>${scoreVal(s.valueMigration)}</td>

      <td>${scoreVal(s.futureGrowth)}</td>

      <td>${scoreVal(s.fundamentalQuality)}</td>

      <td>${scoreVal(s.capexScore)}</td>

      <td>${scoreVal(s.overallScore)}</td>
    </tr>
  `).join('');
}

async function init() {
  [all, meta] = await Promise.all([
    fetch('data/stocks.json').then(r => r.json()),
    fetch('data/meta.json').then(r => r.json())
  ]);

  $('mode').textContent =
    `${meta.mode} • Updated ${meta.lastUpdated}`;

  const eodReady =
    all.filter(s => s.dataStatus === 'EOD_READY').length;

  const classified =
    all.filter(
      s =>
        s.sector &&
        s.sector !== 'Unclassified'
    ).length;

  $('stats').innerHTML = `
    <div class="stat">
      <b>${Number(meta.uniqueCount || all.length).toLocaleString()}</b>
      <span>Unique securities</span>
    </div>

    <div class="stat">
      <b>${Number(meta.nseCount || 0).toLocaleString()}</b>
      <span>NSE incl. SME</span>
    </div>

    <div class="stat">
      <b>${eodReady.toLocaleString()}</b>
      <span>EOD price ready</span>
    </div>

    <div class="stat">
      <b>${classified.toLocaleString()}</b>
      <span>Sector classified</span>
    </div>
  `;

  render();
}

['q', 'exchange', 'board', 'status']
  .forEach(id => {
    $(id).addEventListener(
      id === 'q' ? 'input' : 'change',
      () => {
        page = 1;
        render();
      }
    );
  });

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
