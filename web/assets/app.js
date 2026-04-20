/* 앱 로직: stocks.json 로드, 필터/정렬/페이지네이션, 상세 모달. */

const state = {
  stocks: [],          // stocks.json 의 전체 종목 배열
  filtered: [],        // 필터/정렬 적용 후 배열
  meta: null,          // meta.json
  displayCount: 0,     // 현재 리스트에 그려진 행 개수
  pageSize: 20,
  observer: null,
  loadedCharts: new Set(),
  chartCache: new Map(),   // code → raw {data[], investor{}, meta{}}  (일봉 원본)
  chartCacheTF: new Map(), // `${code}:${tf}` → 리샘플 + 지표 재계산된 {data[], investor, meta}
  timeframe: "D",          // 'D' | 'W' | 'M'
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

// 전일 대비 금액 (예: 스냅샷의 change 필드)를 "+1,500" / "-1,500" 형태로.
// Naver 스냅샷에선 이미 "-1,500" 형태로 들어올 수 있으나, 숫자만 올 때도 대비해
// changeDir ("RISING" / "FALLING" / "EVEN") 를 부호 힌트로 사용.
function formatSignedNum(v, dir) {
  if (v == null || v === "") return "-";
  const str = String(v).trim();
  if (/^[+-]/.test(str)) return str;              // 이미 부호가 붙어 있음
  const n = parseNum(str);
  if (!n) return "0";
  if (dir === "FALLING") return "-" + n.toLocaleString("ko-KR");
  if (dir === "RISING") return "+" + n.toLocaleString("ko-KR");
  return n.toLocaleString("ko-KR");
}

// 값의 부호 색상 클래스 (한국 증시 관행: 양수=빨강, 음수=파랑).
function signClass(v, dir) {
  if (dir === "RISING") return "val-up";
  if (dir === "FALLING") return "val-dn";
  const n = parseNum(v);
  return n > 0 ? "val-up" : n < 0 ? "val-dn" : "";
}

// HTML 본문에 안전하게 박히는 텍스트로 변환.
function escapeHTML(v) {
  if (v == null) return "";
  return String(v)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// HTML 속성값(href, title 등)에 들어갈 문자열을 안전하게 변환.
function escapeAttr(v) {
  return escapeHTML(v);
}

/* ── 데이터 로드 ────────────────────────────────── */

async function loadMeta() {
  try {
    const r = await fetch("/data/meta.json", { cache: "no-cache" });
    if (!r.ok) throw new Error("meta.json 로드 실패");
    state.meta = await r.json();
    const updated = (state.meta.updated || "").replace("T", " ").slice(0, 16);
    const cnt = state.meta.counts?.success ?? state.meta.count ?? 0;
    const metaEl = $("metaInfo");
    if (metaEl) metaEl.textContent = `업데이트: ${updated} KST · ${cnt}종목`;
    // 헤더 우측 '마지막 데이터 날짜 기준' 라벨 (chart.html)
    const dataDateEl = $("dataDate");
    if (dataDateEl) {
      const ymd = (state.meta.updated || "").slice(0, 10);
      dataDateEl.textContent = ymd
        ? `${ymd} 종가 기준`
        : "마지막 데이터 날짜 기준";
    }
  } catch (e) {
    const metaEl = $("metaInfo");
    if (metaEl) metaEl.textContent = "메타 정보 없음";
    const dataDateEl = $("dataDate");
    if (dataDateEl) dataDateEl.textContent = "마지막 데이터 날짜 기준";
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
  // 현재 timeframe 에 맞는 payload (리샘플/지표 포함) 반환. 원본은 state.chartCache.
  const tf = state.timeframe || "D";
  const cacheKey = `${code}:${tf}`;
  if (state.chartCacheTF.has(cacheKey)) return state.chartCacheTF.get(cacheKey);

  let raw = state.chartCache.get(code);
  if (!raw) {
    try {
      const r = await fetch(`/data/chart/${code}.json`);
      if (!r.ok) throw new Error("not found");
      raw = await r.json();
      state.chartCache.set(code, raw);
    } catch (e) {
      return null;
    }
  }
  const out = transformPayload(raw, tf);
  state.chartCacheTF.set(cacheKey, out);
  return out;
}

/* ── 봉 주기 변환 (일/주/월) ───────────────────── */

// payload 를 주어진 timeframe 으로 변환하여 동일한 shape 의 새 payload 반환.
// 일봉이면 원본을 그대로 반환.
// 배치가 dataW / dataM 을 미리 계산해 넣어주면 그걸 그대로 쓰고,
// 없으면 클라이언트에서 raw.data 를 리샘플+지표 재계산 (폴백).
function transformPayload(raw, tf) {
  if (!raw || tf === "D") return raw;
  const preKey = tf === "W" ? "dataW" : "dataM";
  if (Array.isArray(raw[preKey]) && raw[preKey].length) {
    return { ...raw, data: raw[preKey] };
  }
  const resampled = resampleOHLCV(raw.data || [], tf);
  const withIndicators = addIndicators(resampled);
  return {
    ...raw,
    data: withIndicators,
  };
}

function resampleOHLCV(daily, tf) {
  if (!daily || !daily.length) return [];
  const groups = new Map(); // key → {open, high, low, close, volume, date}
  const order = [];
  for (const d of daily) {
    if (!d || !d.date) continue;
    const key = bucketKey(d.date, tf);
    let b = groups.get(key);
    if (!b) {
      b = { key, open: d.open, high: d.high, low: d.low, close: d.close, volume: 0, date: d.date };
      groups.set(key, b);
      order.push(key);
    }
    if (d.high != null && d.high > b.high) b.high = d.high;
    if (d.low != null && d.low < b.low) b.low = d.low;
    b.close = d.close;          // 버킷 내 마지막 종가
    b.date = d.date;            // 버킷 내 마지막 날짜로 표시
    b.volume = (b.volume || 0) + (d.volume || 0);
  }
  return order.map((k) => {
    const b = groups.get(k);
    return {
      date: b.date,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
      volume: b.volume,
    };
  });
}

function bucketKey(dateStr, tf) {
  if (tf === "M") return dateStr.slice(0, 7);          // YYYY-MM
  // 주봉: 월요일 기준 주 키
  const d = new Date(dateStr + "T00:00:00");
  const day = d.getDay();                               // 0=일, 1=월...
  const diff = day === 0 ? -6 : 1 - day;
  const mon = new Date(d);
  mon.setDate(d.getDate() + diff);
  const y = mon.getFullYear();
  const m = String(mon.getMonth() + 1).padStart(2, "0");
  const dd = String(mon.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

/* ── 지표 재계산 (주/월봉 리샘플 이후) ─────────── */
function addIndicators(series) {
  if (!series.length) return series;
  const out = series.map((d) => ({ ...d }));
  const close = out.map((d) => d.close);
  const high = out.map((d) => d.high);
  const low = out.map((d) => d.low);
  const vol = out.map((d) => d.volume || 0);

  // MA
  attachSMA(out, close, 5, "ma5");
  attachSMA(out, close, 20, "ma20");
  attachSMA(out, close, 60, "ma60");

  // Bollinger(20, 2)
  const bbPeriod = 20;
  const bbK = 2;
  for (let i = 0; i < out.length; i++) {
    if (i < bbPeriod - 1) continue;
    let sum = 0;
    for (let j = i - bbPeriod + 1; j <= i; j++) sum += close[j];
    const mean = sum / bbPeriod;
    let sq = 0;
    for (let j = i - bbPeriod + 1; j <= i; j++) sq += (close[j] - mean) ** 2;
    const sd = Math.sqrt(sq / bbPeriod);
    out[i].bb_middle = mean;
    out[i].bb_upper = mean + bbK * sd;
    out[i].bb_lower = mean - bbK * sd;
  }

  // MACD (12, 26, 9)
  const ema12 = emaArray(close, 12);
  const ema26 = emaArray(close, 26);
  const macd = close.map((_, i) =>
    ema12[i] != null && ema26[i] != null ? ema12[i] - ema26[i] : null
  );
  const macdSignal = emaArray(macd, 9);
  for (let i = 0; i < out.length; i++) {
    out[i].macd = macd[i];
    out[i].macd_signal = macdSignal[i];
    out[i].macd_hist =
      macd[i] != null && macdSignal[i] != null ? macd[i] - macdSignal[i] : null;
  }

  // RSI(14), Wilder's smoothing
  const rsiPeriod = 14;
  if (out.length > rsiPeriod) {
    let gainSum = 0, lossSum = 0;
    for (let i = 1; i <= rsiPeriod; i++) {
      const diff = close[i] - close[i - 1];
      if (diff >= 0) gainSum += diff;
      else lossSum -= diff;
    }
    let avgG = gainSum / rsiPeriod;
    let avgL = lossSum / rsiPeriod;
    out[rsiPeriod].rsi = avgL === 0 ? 100 : 100 - 100 / (1 + avgG / avgL);
    for (let i = rsiPeriod + 1; i < out.length; i++) {
      const diff = close[i] - close[i - 1];
      const g = diff > 0 ? diff : 0;
      const l = diff < 0 ? -diff : 0;
      avgG = (avgG * (rsiPeriod - 1) + g) / rsiPeriod;
      avgL = (avgL * (rsiPeriod - 1) + l) / rsiPeriod;
      out[i].rsi = avgL === 0 ? 100 : 100 - 100 / (1 + avgG / avgL);
    }
  }

  // OBV (cumulative)
  let obv = 0;
  out[0].obv = 0;
  for (let i = 1; i < out.length; i++) {
    if (close[i] > close[i - 1]) obv += vol[i];
    else if (close[i] < close[i - 1]) obv -= vol[i];
    out[i].obv = obv;
  }

  // MFI(14)
  const mfiPeriod = 14;
  if (out.length > mfiPeriod) {
    const tp = close.map((_, i) => (high[i] + low[i] + close[i]) / 3);
    for (let i = mfiPeriod; i < out.length; i++) {
      let pos = 0, neg = 0;
      for (let j = i - mfiPeriod + 1; j <= i; j++) {
        const mf = tp[j] * (vol[j] || 0);
        if (j > 0) {
          if (tp[j] > tp[j - 1]) pos += mf;
          else if (tp[j] < tp[j - 1]) neg += mf;
        }
      }
      out[i].mfi = neg === 0 ? 100 : 100 - 100 / (1 + pos / neg);
    }
  }

  return out;
}

function attachSMA(out, arr, period, key) {
  if (arr.length < period) return;
  let sum = 0;
  for (let i = 0; i < arr.length; i++) {
    sum += arr[i];
    if (i >= period) sum -= arr[i - period];
    if (i >= period - 1) out[i][key] = sum / period;
  }
}

function emaArray(arr, period) {
  const out = new Array(arr.length).fill(null);
  if (arr.length < period) return out;
  const k = 2 / (period + 1);
  // SMA 로 seed
  let sum = 0, count = 0;
  for (let i = 0; i < arr.length; i++) {
    if (arr[i] == null) continue;
    count++;
    sum += arr[i];
    if (count === period) {
      out[i] = sum / period;
      let prev = out[i];
      for (let j = i + 1; j < arr.length; j++) {
        if (arr[j] == null) { out[j] = prev; continue; }
        prev = arr[j] * k + prev * (1 - k);
        out[j] = prev;
      }
      break;
    }
  }
  return out;
}

/* ── 필터/정렬 ─────────────────────────────────── */

function applyFilter() {
  const market = $("fMarket").value;
  const sortKey = $("fSort").value;
  const q = $("fSearch").value.trim().toLowerCase();
  const watchOnly = !!($("fWatchlistOnly") && $("fWatchlistOnly").checked);

  let arr = state.stocks;
  if (market !== "ALL") arr = arr.filter((s) => s.market === market);
  if (q) {
    arr = arr.filter((s) => s._nameLower.includes(q) || s.code.includes(q));
  }
  if (watchOnly && window.Watchlist) {
    arr = arr.filter((s) => Watchlist.has(s.code));
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
  const rateClass = rate > 0 ? "val-up" : rate < 0 ? "val-dn" : "";
  const rateTxt = s.changeRate
    ? `${rate > 0 ? "+" : ""}${s.changeRate}%`
    : "";

  const starOn = !!(window.Watchlist && Watchlist.has(s.code));
  const starLabel = starOn ? "★ 담김" : "☆ 관심종목 추가";
  const starTitle = starOn ? "관심종목에서 빼기" : "관심종목에 추가";
  const starCls = starOn ? "star-btn star-btn--pill star-btn--on" : "star-btn star-btn--pill";

  row.innerHTML = `
    <div class="cl-info">
      <button type="button" class="${starCls}" data-role="star" data-code="${s.code}"
        aria-pressed="${starOn}" title="${starTitle}">${starLabel}</button>
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
  // 별 버튼은 row 클릭(상세 모달)로 전파되지 않도록 별도 핸들러
  const starBtn = row.querySelector('[data-role="star"]');
  if (starBtn) {
    starBtn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (window.Watchlist) Watchlist.toggle(s.code);
    });
  }
  return row;
}

// 관심종목 상태가 바뀔 때 이미 렌더된 행/모달의 별 모양만 갱신 (행 재생성 X)
function refreshStars() {
  document.querySelectorAll('[data-role="star"]').forEach((btn) => {
    const on = !!(window.Watchlist && Watchlist.has(btn.dataset.code));
    applyStarState(btn, on, { isModal: false });
  });
  const dStar = $("detailStar");
  if (dStar && _activeDetailCode) {
    const on = !!(window.Watchlist && Watchlist.has(_activeDetailCode));
    applyStarState(dStar, on, { isModal: true });
  }
}

// star 버튼(행/모달 공용) 의 텍스트·aria·클래스를 on/off 상태에 맞춰 세팅.
function applyStarState(btn, on, opts) {
  const isModal = !!(opts && opts.isModal);
  btn.textContent = on
    ? (isModal ? "★ 관심 담김" : "★ 담김")
    : (isModal ? "☆ 관심종목 추가" : "☆ 관심종목 추가");
  btn.setAttribute("aria-pressed", on ? "true" : "false");
  btn.setAttribute("title", on ? "관심종목에서 빼기" : "관심종목에 추가");
  btn.classList.toggle("star-btn--on", on);
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
  // 모달 헤더의 별 — 현재 상태 반영 + 클릭 핸들러 재바인딩
  const dStar = $("detailStar");
  if (dStar) {
    const on = !!(window.Watchlist && Watchlist.has(stock.code));
    // 모달용 pill 스타일 보장 (HTML 에 하드코딩된 기본 class 덮어쓰기)
    dStar.classList.add("star-btn", "star-btn--pill");
    dStar.classList.remove("star-btn--lg");
    applyStarState(dStar, on, { isModal: true });
    dStar.onclick = (ev) => {
      ev.stopPropagation();
      if (window.Watchlist) Watchlist.toggle(stock.code);
    };
  }
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

function tfLabel(tf) {
  return tf === "W" ? "주봉" : tf === "M" ? "월봉" : "일봉";
}

function buildDetailHTML(stock, payload) {
  const latest = payload.data[payload.data.length - 1] || {};
  const meta = payload.meta || {};
  const inv = payload.investor;
  const hasInvestor = !!(inv && inv.data && inv.data.length);
  const tf = state.timeframe || "D";
  const tfLbl = tfLabel(tf);

  // 스냅샷 원본 값 — stocks.json 우선, 없으면 chart/{code}.json 의 meta 로 폴백
  const priceRaw = stock.price || meta.price || latest.close;
  const changeRaw = stock.change || meta.change;
  const dirRaw = stock.changeDir || meta.changeDir;
  const rateRaw = stock.changeRate || meta.changeRate || "0";
  const rateNum = parseNum(rateRaw);
  const volRaw = stock.volume || meta.volume;
  const mcapRaw = meta.marketValue || stock.marketCap || meta.marketCap;
  const baseDate =
    latest.date ||
    (state.meta && state.meta.updated ? String(state.meta.updated).slice(0, 10) : "");

  const changeCls = signClass(changeRaw, dirRaw);
  const rateCls = rateNum > 0 ? "val-up" : rateNum < 0 ? "val-dn" : "";
  const rateStr = (rateNum > 0 ? "+" : "") + (rateRaw || "0") + "%";

  const snapshotCells = [
    { label: "현재가", value: formatNum(priceRaw) },
    { label: "전일대비", value: formatSignedNum(changeRaw, dirRaw), cls: changeCls },
    { label: "등락률", value: rateStr, cls: rateCls },
    { label: "거래량", value: formatNum(volRaw) },
    { label: "시가총액", value: formatMcap(mcapRaw) },
    { label: "PER", value: meta.per || "-" },
    { label: "PBR", value: meta.pbr || "-" },
    { label: "EPS", value: meta.eps || "-" },
    { label: "BPS", value: meta.bps || "-" },
    { label: "외국인비율", value: meta.foreignRate ? String(meta.foreignRate).replace(/%$/, "") + "%" : "-" },
    { label: "섹터", value: meta.sector || "-" },
    { label: "기준일자", value: baseDate || "-" },
  ];

  const tfBtn = (v, label) =>
    `<button type="button" class="tf-btn${v === tf ? " is-active" : ""}" data-tf="${v}">${label}</button>`;

  // 회사 기본정보 — meta.company 가 존재하고 최소 한 필드라도 있으면 렌더
  const company = (meta && meta.company) || {};
  const companyRows = [];
  if (company.nameKor || company.nameEng) {
    const en = company.nameEng ? ` <span class="cinfo-sub">${escapeHTML(company.nameEng)}</span>` : "";
    companyRows.push({ label: "회사명", value: escapeHTML(company.nameKor || stock.name) + en });
  }
  if (company.market || company.marketSector) {
    const mk = [company.market, company.marketSector].filter(Boolean).join(" · ");
    companyRows.push({ label: "시장·업종", value: escapeHTML(mk) });
  }
  if (company.wicsSector) {
    companyRows.push({ label: "WICS 업종", value: escapeHTML(company.wicsSector) });
  }
  if (company.industryPer) {
    companyRows.push({ label: "업종 PER", value: escapeHTML(company.industryPer) + "배" });
  }
  if (company.fiscalMonth) {
    companyRows.push({ label: "결산월", value: escapeHTML(company.fiscalMonth) });
  }
  if (company.phone) {
    companyRows.push({ label: "대표전화", value: escapeHTML(company.phone) });
  }
  if (company.irPhone && company.irPhone !== company.phone) {
    companyRows.push({ label: "주식담당", value: escapeHTML(company.irPhone) });
  }
  if (company.homepage) {
    const safe = escapeAttr(company.homepage);
    const display = escapeHTML(company.homepage.replace(/^https?:\/\//, "").replace(/\/$/, ""));
    companyRows.push({
      label: "홈페이지",
      value: `<a class="cinfo-link" href="${safe}" target="_blank" rel="noopener noreferrer">${display} ↗</a>`,
    });
  }
  const companySection = companyRows.length
    ? `
    <div class="section cinfo-section">
      <h3>🏢 회사 기본정보</h3>
      <dl class="cinfo-grid">
        ${companyRows.map((r) => `
          <div class="cinfo-row">
            <dt>${r.label}</dt>
            <dd>${r.value}</dd>
          </div>`).join("")}
      </dl>
      <div class="cinfo-note">출처: Naver Finance · WiseReport 요약</div>
    </div>`
    : "";

  return `
    <div class="snapshot-grid">
      ${snapshotCells.map((c) => `
        <div class="snapshot-cell">
          <div class="label">${c.label}</div>
          <div class="value${c.cls ? " " + c.cls : ""}">${c.value}</div>
        </div>`).join("")}
    </div>

    ${companySection}

    <div class="section">
      <div class="section-head">
        <h3>📈 ${tfLbl} 캔들 · 이동평균 · 볼린저 밴드</h3>
        <div class="tf-group tf-group--modal" role="tablist" aria-label="봉 주기">
          ${tfBtn("D", "일봉")}${tfBtn("W", "주봉")}${tfBtn("M", "월봉")}
        </div>
      </div>
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

// 필터바 / 상세 모달에 공존하는 .tf-btn 의 활성 상태를 state.timeframe 에 맞춰 동기화.
function syncTFButtons() {
  document.querySelectorAll(".tf-btn").forEach((x) => {
    x.classList.toggle("is-active", x.dataset.tf === state.timeframe);
  });
}

// 봉 주기 변경 시: 이미 로드된 행의 차트/모달 전부 재렌더.
// 원본 chartCache 는 그대로 두고, 새 timeframe 의 리샘플 결과만 계산됨.
async function onTimeframeChange() {
  // 현재 리스트에 그려진 행들 중 이미 차트가 로드된(또는 대기 중) 것들을
  // 모두 새 timeframe 으로 다시 그린다.
  const codes = Array.from(state.loadedCharts);
  for (const code of codes) {
    renderRowData(code);   // loadChartData 내부에서 새 TF payload 가져옴
  }
  // 상세 모달이 열려 있으면 재렌더
  if (_activeDetailCode) {
    const stock = state.stocks.find((s) => s.code === _activeDetailCode);
    if (stock) await redrawDetail(stock);
  }
}

async function redrawDetail(stock) {
  const payload = await loadChartData(stock.code);
  if (_activeDetailCode !== stock.code) return;
  if (!payload || !payload.data || !payload.data.length) return;
  const body = $("detailBody");
  // 활성 지표 탭 유지
  const activeTab =
    document.querySelector(".chart-tab.active")?.dataset.tab || "macd";
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
    if (activeTab && activeTab !== "macd") {
      const t = document.querySelector(`.chart-tab[data-tab="${activeTab}"]`);
      if (t) t.click();
    }
  });
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

  // 일봉 / 주봉 / 월봉 토글 — 필터바 + 모달 내부 버튼 둘 다 동작하도록 이벤트 위임
  document.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".tf-btn");
    if (!btn) return;
    const tf = btn.dataset.tf;
    if (!tf || tf === state.timeframe) return;
    state.timeframe = tf;
    syncTFButtons();
    onTimeframeChange();
  });
  if ($("fWatchlistOnly")) {
    $("fWatchlistOnly").addEventListener("change", () => {
      // 비로그인 사용자가 체크하면 안내 후 해제
      if ($("fWatchlistOnly").checked && window.Watchlist && !Watchlist.isSignedIn()) {
        alert("관심종목은 카카오 로그인 후 이용할 수 있습니다.");
        $("fWatchlistOnly").checked = false;
        return;
      }
      applyFilter();
    });
  }
  window.addEventListener("resize", () => {
    clearTimeout(_resizeDebounce);
    _resizeDebounce = setTimeout(() => {
      if (Chart.redrawAll) Chart.redrawAll(document.getElementById("stockList"));
    }, 150);
  });

  // 관심종목 변화 시: 별 모양 갱신. '관심종목만' 활성 상태면 리스트 재필터.
  if (window.Watchlist) {
    Watchlist.onChange(() => {
      refreshStars();
      if ($("fWatchlistOnly") && $("fWatchlistOnly").checked) applyFilter();
    });
  }
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
