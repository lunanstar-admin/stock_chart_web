/* 앱 로직: stocks.json 로드, 필터/정렬/페이지네이션, 상세 모달. */

const state = {
  stocks: [],          // stocks.json 의 전체 종목 배열
  filtered: [],        // 필터/정렬 적용 후 배열
  meta: null,          // meta.json
  displayCount: 0,     // 현재 리스트에 그려진 행 개수
  pageSize: 20,
  observer: null,
  loadedCharts: new Set(),
  chartCache: new Map(), // code → {data[], investor{}, meta{}}
};

const els = {};

function $(id) { return document.getElementById(id); }

function formatNum(n) {
  if (n == null || n === "") return "-";
  const num = typeof n === "number" ? n : parseFloat(String(n).replace(/,/g, ""));
  if (isNaN(num)) return "-";
  return num.toLocaleString("ko-KR");
}

function parseNum(v) {
  if (v == null) return 0;
  if (typeof v === "number") return v;
  const n = parseFloat(String(v).replace(/,/g, ""));
  return isNaN(n) ? 0 : n;
}

function formatMcap(val) {
  // Naver marketCap(stocks.json) 단위 = 억원 (숫자 문자열)
  // Naver meta.marketValue 는 "1,262조 7,962억" 같은 사전 포맷 문자열 — 그대로 표시
  if (val == null || val === "") return "-";
  const str = String(val);
  if (/[조억만]/.test(str)) return str; // 이미 포맷된 한글 문자열
  const n = parseNum(val);
  if (!n) return "-";
  if (n >= 10000) return (n / 10000).toFixed(1) + "조";
  return n.toLocaleString() + "억";
}

function formatSupplyBig(n) {
  if (n == null || n === 0) return "0";
  const sign = n > 0 ? "+" : "";
  const abs = Math.abs(n);
  if (abs >= 1e12) return sign + (n / 1e12).toFixed(1) + "조";
  if (abs >= 1e8) return sign + (n / 1e8).toFixed(0) + "억";
  if (abs >= 1e4) return sign + (n / 1e4).toFixed(0) + "만";
  return sign + n;
}

/* ── 데이터 로드 ────────────────────────────────── */

async function loadMeta() {
  try {
    const r = await fetch("/data/meta.json", { cache: "no-cache" });
    if (!r.ok) throw new Error("meta.json 로드 실패");
    state.meta = await r.json();
    const updated = (state.meta.updated || "").replace("T", " ").slice(0, 16);
    const cnt = state.meta.counts?.success ?? state.meta.count ?? 0;
    $("metaInfo").textContent = `업데이트: ${updated} KST · ${cnt}종목`;
  } catch (e) {
    $("metaInfo").textContent = "메타 정보 없음";
  }
}

async function loadStocks() {
  const r = await fetch("/data/stocks.json");
  if (!r.ok) throw new Error("stocks.json 로드 실패");
  const data = await r.json();
  state.stocks = (data.stocks || []).map((s) => ({
    ...s,
    _mcap: parseNum(s.marketCap),
    _vol: parseNum(s.volume),
    _rate: parseNum(s.changeRate),
    _nameLower: (s.name || "").toLowerCase(),
  }));
}

async function loadChartData(code) {
  if (state.chartCache.has(code)) return state.chartCache.get(code);
  try {
    const r = await fetch(`/data/chart/${code}.json`);
    if (!r.ok) throw new Error("not found");
    const d = await r.json();
    state.chartCache.set(code, d);
    return d;
  } catch (e) {
    return null;
  }
}

/* ── 필터/정렬 ─────────────────────────────────── */

function applyFilter() {
  const market = $("fMarket").value;
  const sortKey = $("fSort").value;
  const q = $("fSearch").value.trim().toLowerCase();

  let arr = state.stocks;
  if (market !== "ALL") arr = arr.filter((s) => s.market === market);
  if (q) {
    arr = arr.filter((s) => s._nameLower.includes(q) || s.code.includes(q));
  }

  const cmp = {
    marketCap: (a, b) => b._mcap - a._mcap,
    volume: (a, b) => b._vol - a._vol,
    changeRate: (a, b) => b._rate - a._rate,
  }[sortKey];
  arr = [...arr].sort(cmp);

  state.filtered = arr;
  state.displayCount = 0;
  renderInitial();
}

function renderInitial() {
  const list = $("stockList");
  list.innerHTML = "";
  if (state.observer) { state.observer.disconnect(); state.observer = null; }
  state.loadedCharts = new Set();

  if (!state.filtered.length) {
    list.innerHTML = '<div class="empty">해당 종목이 없습니다.</div>';
    $("statusLabel").textContent = "";
    return;
  }
  appendNext();
}

function appendNext() {
  const list = $("stockList");
  const existingMore = document.querySelector(".load-more");
  if (existingMore) existingMore.remove();

  const end = Math.min(state.displayCount + state.pageSize, state.filtered.length);
  for (let i = state.displayCount; i < end; i++) {
    list.appendChild(makeRow(state.filtered[i]));
  }
  state.displayCount = end;

  $("statusLabel").textContent =
    `${state.displayCount.toLocaleString()} / ${state.filtered.length.toLocaleString()}종목`;

  if (state.displayCount < state.filtered.length) {
    const more = document.createElement("div");
    more.className = "load-more";
    more.textContent = "더 불러오는 중...";
    list.appendChild(more);
    ensureLoadMoreObserver(more);
  }
  observeVisibleCharts();
}

function ensureLoadMoreObserver(target) {
  if (!state.observerMore) {
    state.observerMore = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          state.observerMore.unobserve(e.target);
          appendNext();
        }
      }
    }, { rootMargin: "200px" });
  }
  state.observerMore.observe(target);
}

/* ── 행 생성 / 차트 lazy load ──────────────────── */

function makeRow(s) {
  const row = document.createElement("div");
  row.className = "cl-row";
  row.dataset.code = s.code;
  row.onclick = () => openDetail(s);

  const rate = parseNum(s.changeRate);
  const rateClass = rate > 0 ? "sup-pos" : rate < 0 ? "sup-neg" : "";
  const rateTxt = s.changeRate
    ? `${rate > 0 ? "+" : ""}${s.changeRate}%`
    : "";

  row.innerHTML = `
    <div class="cl-info">
      <span class="cl-name" title="${s.name}">${s.name}</span>
      <span class="cl-code">${s.code} · ${s.market}</span>
      <span style="font-size:11px;font-weight:600;margin-top:2px">${formatNum(s.price)}</span>
      <span style="font-size:10px" class="${rateClass}">${rateTxt}</span>
    </div>
    <div class="cl-chart"><canvas data-role="mini" data-code="${s.code}"></canvas></div>
    <div class="cl-supply">
      <canvas data-role="supply" data-code="${s.code}"></canvas>
      <div class="sup-summary" data-role="sup-summary" data-code="${s.code}">
        <span style="color:var(--text-secondary)">로딩...</span>
      </div>
    </div>
    <div class="cl-meta" data-role="meta" data-code="${s.code}">
      <span>-</span><span>PER -</span><span>${formatMcap(s.marketCap)}</span>
    </div>
  `;
  return row;
}

function observeVisibleCharts() {
  if (!state.observer) {
    state.observer = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          const code = e.target.dataset.code;
          if (!state.loadedCharts.has(code)) {
            state.loadedCharts.add(code);
            state.observer.unobserve(e.target);
            renderRowData(code);
          }
        }
      }
    }, { rootMargin: "400px" });
  }
  document.querySelectorAll('canvas[data-role="mini"]').forEach((c) => {
    if (!state.loadedCharts.has(c.dataset.code)) state.observer.observe(c);
  });
}

async function renderRowData(code) {
  const payload = await loadChartData(code);
  if (!payload) {
    const miniC = document.querySelector(`canvas[data-role="mini"][data-code="${code}"]`);
    if (miniC) {
      const ctx = miniC.getContext("2d");
      ctx.fillStyle = "#555"; ctx.font = "11px sans-serif";
      ctx.fillText("데이터 없음", 10, 30);
    }
    return;
  }
  const miniC = document.querySelector(`canvas[data-role="mini"][data-code="${code}"]`);
  if (miniC && payload.data) Chart.drawMini(miniC, payload.data);

  const supC = document.querySelector(`canvas[data-role="supply"][data-code="${code}"]`);
  const sum = document.querySelector(`[data-role="sup-summary"][data-code="${code}"]`);
  const inv = payload.investor;
  if (inv && inv.data && inv.data.length) {
    if (supC) Chart.drawSupplyMini(supC, inv.data);
    const c = inv.cumulative || {};
    const f = c.foreign?.total || 0;
    const i = c.inst?.total || 0;
    const r = c.retail?.total || 0;
    const cls = (v) => (v > 0 ? "sup-pos" : v < 0 ? "sup-neg" : "");
    if (sum) sum.innerHTML =
      `<span class="${cls(f)}">외 ${formatSupplyBig(f)}</span>` +
      `<span class="${cls(i)}">기 ${formatSupplyBig(i)}</span>` +
      `<span class="${cls(r)}">개 ${formatSupplyBig(r)}</span>`;
  } else if (sum) {
    sum.innerHTML = '<span style="color:var(--text-secondary)">수급 없음</span>';
  }

  const metaEl = document.querySelector(`[data-role="meta"][data-code="${code}"]`);
  if (metaEl && payload.meta) {
    const spans = metaEl.querySelectorAll("span");
    if (payload.meta.sector) spans[0].textContent = payload.meta.sector;
    if (payload.meta.per) spans[1].textContent = "PER " + payload.meta.per;
    spans[2].textContent = formatMcap(payload.meta.marketValue || payload.meta.marketCap);
  }
}

/* ── 상세 모달 ────────────────────────────────── */

let _activeDetailCode = null;

async function openDetail(stock) {
  _activeDetailCode = stock.code;
  $("detailTitle").textContent = stock.name;
  $("detailCode").textContent = `${stock.code} · ${stock.market}`;
  const body = $("detailBody");
  body.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  $("detailModal").classList.add("show");

  const payload = await loadChartData(stock.code);
  if (_activeDetailCode !== stock.code) return;

  if (!payload || !payload.data || !payload.data.length) {
    body.innerHTML = '<div class="empty">차트 데이터가 없습니다.</div>';
    return;
  }

  body.innerHTML = buildDetailHTML(stock, payload);

  requestAnimationFrame(() => {
    Chart.drawDetailCandle($("mCandle"), payload.data);
    Chart.drawVolume($("mVolume"), payload.data);
    Chart.drawMACD($("mMACD"), payload.data);
    Chart.drawRSI($("mRSI"), payload.data);
    Chart.drawOBV($("mOBV"), payload.data);
    Chart.drawMFI($("mMFI"), payload.data);

    const inv = payload.investor;
    if (inv && inv.data && inv.data.length) {
      Chart.drawSupplyCumulative($("mSupplyCumul"), inv.data);
      Chart.drawSupplyDaily($("mSupplyDaily"), inv.data);
    }

    attachHoverTooltip($("mCandle"), payload.data);
    wireIndicatorTabs(payload);
  });
}

function buildDetailHTML(stock, payload) {
  const latest = payload.data[payload.data.length - 1] || {};
  const meta = payload.meta || {};
  const inv = payload.investor;
  const hasInvestor = !!(inv && inv.data && inv.data.length);
  const snapshotCells = [
    { label: "현재가", value: formatNum(stock.price || latest.close) },
    { label: "등락률", value: (parseNum(stock.changeRate) > 0 ? "+" : "") + (stock.changeRate || "0") + "%" },
    { label: "거래량", value: formatNum(stock.volume) },
    { label: "시가총액", value: formatMcap(stock.marketCap) },
    { label: "PER", value: meta.per || "-" },
    { label: "외국인비율", value: meta.foreignRate ? String(meta.foreignRate).replace(/%$/, "") + "%" : "-" },
    { label: "섹터", value: meta.sector || "-" },
  ];

  return `
    <div class="snapshot-grid">
      ${snapshotCells.map((c) => `
        <div class="snapshot-cell">
          <div class="label">${c.label}</div>
          <div class="value">${c.value}</div>
        </div>`).join("")}
    </div>

    <div class="section">
      <h3>📈 일봉 캔들 · 이동평균 · 볼린저 밴드</h3>
      <div class="chart-wrap"><canvas id="mCandle"></canvas></div>
      <div class="chart-legend">
        <span><span class="dot" style="background:#ef4444"></span>양봉</span>
        <span><span class="dot" style="background:#4f8cff"></span>음봉</span>
        <span><span class="dot" style="background:rgba(255,210,0,0.85)"></span>MA5</span>
        <span><span class="dot" style="background:rgba(255,120,50,0.85)"></span>MA20</span>
        <span><span class="dot" style="background:rgba(140,120,255,0.85)"></span>MA60</span>
        <span><span class="dot" style="background:rgba(168,85,247,0.6)"></span>BB(20,2)</span>
      </div>
      <div class="chart-wrap" style="margin-top:4px"><canvas id="mVolume"></canvas></div>
    </div>

    <div class="section">
      <div class="chart-tabs">
        <div class="chart-tab active" data-tab="macd">MACD</div>
        <div class="chart-tab" data-tab="rsi">RSI</div>
        <div class="chart-tab" data-tab="obv">OBV</div>
        <div class="chart-tab" data-tab="mfi">MFI</div>
      </div>
      <div class="chart-pane active" data-pane="macd">
        <div class="chart-wrap"><canvas id="mMACD"></canvas></div>
        <div class="chart-legend">
          <span><span class="dot" style="background:#4f8cff"></span>MACD</span>
          <span><span class="dot" style="background:#f59e0b"></span>Signal</span>
          <span>히스토그램</span>
        </div>
      </div>
      <div class="chart-pane" data-pane="rsi">
        <div class="chart-wrap"><canvas id="mRSI"></canvas></div>
        <div class="chart-legend"><span>과매수 70 / 과매도 30</span></div>
      </div>
      <div class="chart-pane" data-pane="obv">
        <div class="chart-wrap"><canvas id="mOBV"></canvas></div>
        <div class="chart-legend"><span><span class="dot" style="background:#22c55e"></span>OBV</span></div>
      </div>
      <div class="chart-pane" data-pane="mfi">
        <div class="chart-wrap"><canvas id="mMFI"></canvas></div>
        <div class="chart-legend"><span>과매수 80 / 과매도 20</span></div>
      </div>
    </div>

    ${hasInvestor ? `
    <div class="section">
      <h3>💰 투자자별 누적 순매수 (60일)</h3>
      <div class="chart-wrap"><canvas id="mSupplyCumul"></canvas></div>
      <div class="chart-legend">
        <span><span class="dot" style="background:rgba(79,140,255,0.9)"></span>외국인</span>
        <span><span class="dot" style="background:rgba(239,68,68,0.9)"></span>기관</span>
        <span><span class="dot" style="background:rgba(245,158,11,0.9)"></span>개인</span>
      </div>
      <h3 style="margin-top:12px">📊 일별 순매수 (3주체)</h3>
      <div class="chart-wrap"><canvas id="mSupplyDaily"></canvas></div>
    </div>
    ` : `
    <div class="section" style="color:var(--text-secondary);font-size:12px">
      수급 데이터가 아직 수집되지 않았습니다.
    </div>
    `}
  `;
}

function wireIndicatorTabs(payload) {
  const drawForTab = (tab) => {
    const data = payload.data;
    if (tab === "macd") Chart.drawMACD($("mMACD"), data);
    else if (tab === "rsi") Chart.drawRSI($("mRSI"), data);
    else if (tab === "obv") Chart.drawOBV($("mOBV"), data);
    else if (tab === "mfi") Chart.drawMFI($("mMFI"), data);
  };
  document.querySelectorAll(".chart-tab").forEach((t) => {
    t.onclick = () => {
      document.querySelectorAll(".chart-tab").forEach((x) => x.classList.remove("active"));
      document.querySelectorAll(".chart-pane").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      document.querySelector(`.chart-pane[data-pane="${t.dataset.tab}"]`).classList.add("active");
      // pane 이 display:none 상태일 때 draw 가 width 0 으로 그려졌을 수 있으므로 재렌더
      requestAnimationFrame(() => drawForTab(t.dataset.tab));
    };
  });
}

function attachHoverTooltip(canvas, data) {
  let tip;
  const ensureTip = () => {
    if (tip) return tip;
    tip = document.createElement("div");
    tip.className = "cl-tooltip";
    tip.style.display = "none";
    document.body.appendChild(tip);
    return tip;
  };
  canvas.addEventListener("mousemove", (e) => {
    if (!data || !data.length) return;
    const rect = canvas.getBoundingClientRect();
    const padL = 48;
    const cw = rect.width - padL - 8;
    const barW = cw / data.length;
    const idx = Math.max(0, Math.min(data.length - 1,
      Math.floor((e.clientX - rect.left - padL) / barW)));
    const d = data[idx];
    if (!d) return;
    const up = d.close >= d.open;
    const cls = up ? "tt-up" : "tt-dn";
    const t = ensureTip();
    t.innerHTML = `
      <div style="font-weight:600;margin-bottom:2px">${d.date || ""}</div>
      <span class="tt-label">시가</span><span class="${cls}">${formatNum(d.open)}</span>
      <span class="tt-label" style="margin-left:8px">고가</span><span class="tt-up">${formatNum(d.high)}</span><br>
      <span class="tt-label">저가</span><span class="tt-dn">${formatNum(d.low)}</span>
      <span class="tt-label" style="margin-left:8px">종가</span><span class="${cls}">${formatNum(d.close)}</span><br>
      <span class="tt-label">거래량</span>${formatNum(d.volume)}<br>
      <span class="tt-label">MA5</span>${d.ma5 ? formatNum(Math.round(d.ma5)) : "-"}
      <span class="tt-label" style="margin-left:6px">MA20</span>${d.ma20 ? formatNum(Math.round(d.ma20)) : "-"}
      <span class="tt-label" style="margin-left:6px">MA60</span>${d.ma60 ? formatNum(Math.round(d.ma60)) : "-"}
    `;
    t.style.display = "block";
    t.style.visibility = "hidden";
    const tw = t.offsetWidth, th = t.offsetHeight;
    t.style.visibility = "";
    let x = e.clientX + 14, y = e.clientY - 10;
    if (x + tw + 6 > window.innerWidth) x = e.clientX - tw - 14;
    if (y + th + 6 > window.innerHeight) y = window.innerHeight - th - 6;
    if (y < 6) y = 6;
    t.style.left = x + "px"; t.style.top = y + "px";
  });
  canvas.addEventListener("mouseleave", () => { if (tip) tip.style.display = "none"; });
}

function closeDetail() {
  _activeDetailCode = null;
  $("detailModal").classList.remove("show");
}

function onBackdropClick(e) {
  if (e.target.id === "detailModal") closeDetail();
}

/* ── 초기화 ───────────────────────────────────── */

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeDetail();
});

let _searchDebounce;
let _resizeDebounce;
function bindInputs() {
  $("fMarket").addEventListener("change", applyFilter);
  $("fSort").addEventListener("change", applyFilter);
  $("fSearch").addEventListener("input", () => {
    clearTimeout(_searchDebounce);
    _searchDebounce = setTimeout(applyFilter, 200);
  });
  window.addEventListener("resize", () => {
    clearTimeout(_resizeDebounce);
    _resizeDebounce = setTimeout(() => {
      if (Chart.redrawAll) Chart.redrawAll(document.getElementById("stockList"));
    }, 150);
  });
}

(async function init() {
  bindInputs();
  await loadMeta();
  try {
    await loadStocks();
  } catch (e) {
    $("stockList").innerHTML =
      '<div class="empty">데이터를 불러올 수 없습니다. 배치 실행이 필요합니다.</div>';
    return;
  }
  applyFilter();
})();
