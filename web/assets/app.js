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
  chaebolCodes: null,      // chaebol-codes.json 캐시 — 모달에서 그룹사 정보 lookup
};

// 모달 안의 그룹사 칩(자회사·계열사 등) 클릭 시 호출. 종목코드 → 해당 stock 으로 모달 갈아끼움.
// stocks.json 에 없는 비상장 자회사는 무시 (chip 자체가 .chaebol-chip--unlisted 로 비활성).
function showByCode(code, fallbackName) {
  if (!code) return;
  const s = (state.stocks || []).find((x) => x.code === code);
  if (s) {
    openDetail(s);
  } else if (fallbackName) {
    // stocks.json 에 없으면 임시 stock 객체로 — chart.json 도 없을 수 있어 에러 가능성 있음
    openDetail({ code, name: fallbackName, market: "KOSPI" });
  }
}
window.showByCode = showByCode;

// 종목코드 → {group, affiliates[], subsidiaries[], parent, shareholders[]} 인덱스를 lazy fetch.
// 차트 모달이 처음 열릴 때 1회만 로드. 1MB 정도라 한 번 로드 후 메모리 캐시.
async function loadChaebolCodes() {
  if (state.chaebolCodes !== null) return state.chaebolCodes;
  try {
    const r = await fetch("/data/chaebol-codes.json", { cache: "force-cache" });
    if (!r.ok) {
      state.chaebolCodes = {};
      return state.chaebolCodes;
    }
    state.chaebolCodes = await r.json();
  } catch (_) {
    state.chaebolCodes = {};
  }
  return state.chaebolCodes;
}

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

// KST(Asia/Seoul) 기준 오늘 날짜 YYYY-MM-DD. en-CA locale 이 ISO 포맷을 돌려준다.
function todayKST() {
  return new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Seoul" });
}

// KST 기준 오늘이 거래일(평일)인가. 토/일이면 false.
// 평일 공휴일(설/추석/광복절 등)은 이 함수만으로 잡지 못하지만, 그 경우엔
// 사용자가 보는 게 1거래일 빠른 캔들일 뿐이고 다음 배치에 자동 정리됨.
function isWeekdayKST() {
  // KST 시각의 weekday 를 안전하게 얻는다 — Asia/Seoul 로 포맷팅 후 파싱.
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Seoul",
    weekday: "short",
  }).formatToParts(new Date());
  const wd = (parts.find(p => p.type === "weekday") || {}).value || "";
  return !["Sat", "Sun"].includes(wd);
}

// 지연 시세 프록시 호출. 실패는 무해 — 폴백으로 전일 종가 기반 정상 동작.
// payload.data 에 오늘 잠정 캔들을 붙일지는 merge 단계에서 판단한다.
async function fetchQuote(code) {
  try {
    const r = await fetch(`/api/quote?code=${encodeURIComponent(code)}`, {
      cache: "default",
    });
    if (!r.ok) return null;
    const j = await r.json();
    if (!j || typeof j !== "object") return null;
    // price 없으면 의미 없음. 일반적으로 거래정지/상폐 종목.
    if (j.price == null || Number(j.price) <= 0) return null;
    return j;
  } catch (_) {
    return null;
  }
}

// payload 의 마지막 일봉 date 가 today(KST) 보다 이전이면, Naver 실시간(20분 지연)
// 값으로 오늘 잠정 캔들을 만들어 data 배열 끝에 붙인다. MA/볼린저/MACD 등 지표 값은
// null 로 두어 선들이 전날에서 끊기게 한다 — 배치 계산 없이 근사하면 오히려 혼란.
// 주봉/월봉(tf) 에는 적용하지 않음 (월요일/다음달 배치가 자연히 반영).
function mergeLiveQuoteIntoPayload(payload, quote, tf) {
  if (tf !== "D" || !payload || !Array.isArray(payload.data) || !payload.data.length) return payload;
  if (!quote || quote.open == null || quote.high == null || quote.low == null || quote.price == null) return payload;
  // 잠정 캔들은 시장이 실제로 OPEN 일 때만 추가한다.
  // (BEFORE/CLOSE/주말/공휴일 모두에서 Naver 는 직전 거래일 종가를 반환 →
  //  그것을 today 캔들로 붙이면 잘못된 정보가 됨)
  if (quote.market !== "OPEN") return payload;
  // 토/일 등 비-거래일 안전망 (이론상 OPEN 이 안 나오지만 이중 방어)
  if (!isWeekdayKST()) return payload;
  const today = todayKST();
  const last = payload.data[payload.data.length - 1];
  if (!last || !last.date) return payload;
  // 배치가 이미 오늘 (또는 그 이후) 데이터를 담고 있다면 중복 방지.
  if (last.date >= today) return payload;
  const tentative = {
    date: today,
    open: Number(quote.open),
    high: Number(quote.high),
    low: Number(quote.low),
    close: Number(quote.price),
    volume: Number(quote.volume || 0),
    // 지표는 의도적으로 null — 이전 거래일에서 선이 자연스럽게 끊긴다.
    ma5: null, ma20: null, ma60: null,
    macd: null, signal: null, hist: null,
    rsi: null, obv: null, mfi: null,
    bb_upper: null, bb_mid: null, bb_lower: null,
    _tentative: true,
  };
  return { ...payload, data: [...payload.data, tentative] };
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
  // 모달 열릴 때 지연 태그 초기화 (데이터 로딩 전이므로 숨김)
  const _delayTag = $("detailDelayTag");
  if (_delayTag) _delayTag.hidden = true;
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

  // 차트 JSON(필수) + 실시간 시세(20분 지연, 선택) + 그룹사 인덱스(선택) 를 병렬 fetch.
  // 시세/그룹사 실패해도 차트는 전일 종가 기준으로 정상 표시된다.
  const [chartRes, quoteRes, chaebolRes] = await Promise.allSettled([
    loadChartData(stock.code),
    fetchQuote(stock.code),
    loadChaebolCodes(),
  ]);
  if (_activeDetailCode !== stock.code) return;

  let payload = chartRes.status === "fulfilled" ? chartRes.value : null;
  const quote = quoteRes.status === "fulfilled" ? quoteRes.value : null;
  const chaebolMap = chaebolRes.status === "fulfilled" ? chaebolRes.value : null;
  const chaebolInfo = chaebolMap && chaebolMap[stock.code] ? chaebolMap[stock.code] : null;

  if (!payload || !payload.data || !payload.data.length) {
    body.innerHTML = '<div class="empty">차트 데이터가 없습니다.</div>';
    return;
  }

  // 오늘 잠정 캔들 append (tf=D 일 때만 의미 있음).
  payload = mergeLiveQuoteIntoPayload(payload, quote, state.timeframe || "D");

  body.innerHTML = buildDetailHTML(stock, payload, quote, chaebolInfo);

  // 종목명 라인 지연 태그 — quote 성공 시 표시
  const delayTag = $("detailDelayTag");
  if (delayTag) delayTag.hidden = !(quote && quote.price != null);

  // 종목명 라인 기준일자 — 잠정 캔들 무시한 마지막 확정 캔들의 date.
  // 장중이면 "오늘 장중", 장 외면 "YYYY-MM-DD 종가" 로 명시해 오해 방지.
  const dateTag = $("detailBaseDate");
  if (dateTag) {
    const lastConfirmed = [...payload.data].reverse().find(d => !d._tentative) || payload.data[payload.data.length - 1];
    const isLive = quote && quote.market === "OPEN";
    const dateStr = isLive ? todayKST() : (lastConfirmed && lastConfirmed.date) || "";
    if (dateStr) {
      dateTag.textContent = isLive ? `📅 ${dateStr} 장중` : `📅 ${dateStr} 종가`;
      dateTag.hidden = false;
    } else {
      dateTag.hidden = true;
    }
  }

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

// 지연 시세 배지 문자열 조합.
//   - 장중(OPEN)  : "⏱ 시세 20분 지연 · 219,000원 +4,500 (+2.10%) · 15:30 기준"
//   - 장마감(CLOSE): "⏱ 시세 20분 지연 · 장마감 · 04-21 종가 기준"
// 잠정 캔들이 실제로 payload 끝에 append 됐는지 여부와 무관하게, quote 만 있으면 노출.
function buildDelayBadge(quote) {
  if (!quote) return "";
  const isOpen = quote.market === "OPEN";
  const price = formatNum(quote.price);
  const chg = quote.change != null ? formatSignedNum(quote.change, quote.changeDir === "up" ? "RISING" : quote.changeDir === "down" ? "FALLING" : "EVEN") : "";
  const rate = quote.changeRate != null ? ((Number(quote.changeRate) > 0 ? "+" : "") + quote.changeRate + "%") : "";
  const chgCls = quote.changeDir === "up" ? "val-up" : quote.changeDir === "down" ? "val-dn" : "";

  // 거래시각: quote.tradedAt 이 Naver tm(HHmmss) 포맷이면 HH:MM 으로, 아니면 fetchedAt(ISO) 에서 추출.
  let timeLabel = "";
  const tm = String(quote.tradedAt || "");
  if (/^\d{6}$/.test(tm)) {
    timeLabel = `${tm.slice(0, 2)}:${tm.slice(2, 4)}`;
  } else if (/^\d{4}$/.test(tm)) {
    timeLabel = `${tm.slice(0, 2)}:${tm.slice(2, 4)}`;
  } else if (quote.fetchedAt) {
    try {
      const d = new Date(quote.fetchedAt);
      timeLabel = d.toLocaleTimeString("ko-KR", { timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", hour12: false });
    } catch (_) {}
  }

  const right = isOpen
    ? (timeLabel ? `${timeLabel} 기준` : "실시간")
    : "장마감";

  return `
    <div class="delay-badge" title="Naver Finance 시세 · 20분 지연">
      <span class="delay-badge-ico" aria-hidden="true">⏱</span>
      <span class="delay-badge-main">시세 20분 지연</span>
      <span class="delay-badge-sep">·</span>
      <span class="delay-badge-price">${price}원</span>
      ${chg ? `<span class="delay-badge-chg ${chgCls}">${chg}${rate ? ` (${rate})` : ""}</span>` : ""}
      <span class="delay-badge-sep">·</span>
      <span class="delay-badge-time">${right}</span>
    </div>`;
}

function buildDetailHTML(stock, payload, quote, chaebolInfo) {
  const latest = payload.data[payload.data.length - 1] || {};
  const meta = payload.meta || {};
  const inv = payload.investor;
  const hasInvestor = !!(inv && inv.data && inv.data.length);
  const tf = state.timeframe || "D";
  const tfLbl = tfLabel(tf);

  // 실시간(20분 지연) 시세가 있으면 스냅샷 우선순위: quote > stocks.json > chart.meta > 일봉 종가.
  // quote.changeDir 은 'up'|'down'|'flat' 이라 서버 스키마 (RISING/FALLING/EVEN) 로 맞춰준다.
  const liveDir = quote && quote.changeDir === "up" ? "RISING"
    : quote && quote.changeDir === "down" ? "FALLING"
    : quote ? "EVEN" : null;

  const priceRaw = (quote && quote.price) || stock.price || meta.price || latest.close;
  const changeRaw = (quote && quote.change != null) ? quote.change : (stock.change || meta.change);
  const dirRaw = liveDir || stock.changeDir || meta.changeDir;
  const rateRaw = (quote && quote.changeRate != null)
    ? String(quote.changeRate)
    : (stock.changeRate || meta.changeRate || "0");
  const rateNum = parseNum(rateRaw);
  const volRaw = (quote && quote.volume != null) ? quote.volume : (stock.volume || meta.volume);
  const mcapRaw = meta.marketValue || stock.marketCap || meta.marketCap;
  // 기준일자 = "마지막 거래일 기준" 의미.
  // 1) 장중(OPEN) 이면 today (오늘 장중 시세 기준)
  // 2) 그 외에는 잠정 캔들(_tentative)을 건너뛴 최근 확정 캔들의 날짜
  // 3) 폴백 — latest 또는 meta.updated 일자
  const lastConfirmed = [...payload.data].reverse().find(d => !d._tentative) || latest;
  const baseDate = (quote && quote.market === "OPEN" ? todayKST() : null)
    || (lastConfirmed && lastConfirmed.date)
    || latest.date
    || (state.meta && state.meta.updated ? String(state.meta.updated).slice(0, 10) : "");

  const changeCls = signClass(changeRaw, dirRaw);
  const rateCls = rateNum > 0 ? "val-up" : rateNum < 0 ? "val-dn" : "";
  const rateStr = (rateNum > 0 ? "+" : "") + (rateRaw || "0") + "%";

  // 지연 시세 배지 — quote 가 있을 때만 표시. 장중이면 거래시각, 장마감이면 '장마감' 라벨.
  const delayBadge = quote ? buildDelayBadge(quote) : "";

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
  // 기업개요 — WiseReport 하단 <ul class="dot_cmp"> 에서 추출한 불릿 리스트
  const overviewBullets = Array.isArray(company.overview) ? company.overview : [];
  const overviewBlock = overviewBullets.length
    ? `
      <div class="cinfo-overview">
        <div class="cinfo-overview-head">
          <span class="cinfo-overview-title">📝 기업개요</span>
          ${company.overviewDate ? `<span class="cinfo-overview-date">[기준 ${escapeHTML(company.overviewDate)}]</span>` : ""}
        </div>
        <ul class="cinfo-overview-list">
          ${overviewBullets.map((t) => `<li>${escapeHTML(t)}</li>`).join("")}
        </ul>
      </div>`
    : "";

  const companySection = companyRows.length || overviewBullets.length
    ? `
    <div class="section cinfo-section">
      <h3>🏢 회사 기본정보</h3>
      ${companyRows.length ? `
      <dl class="cinfo-grid">
        ${companyRows.map((r) => `
          <div class="cinfo-row">
            <dt>${r.label}</dt>
            <dd>${r.value}</dd>
          </div>`).join("")}
      </dl>` : ""}
      ${overviewBlock}
      <div class="cinfo-note">출처: Naver Finance · WiseReport 요약</div>
    </div>`
    : "";

  // ── 그룹사 관계 카드 ────────────────────────────────────
  // chaebol-codes.json 에서 lookup 한 결과를 자회사·계열사·관계사·모회사·주주로 분류 표시
  const chaebolSection = (function () {
    if (!chaebolInfo) return "";
    const code = stock.code;
    const lookupName = (otherCode) => {
      const s = state.stocks.find((x) => x.code === otherCode);
      return s ? s.name : null;
    };
    const codeChip = (c, fallbackName) => {
      const nm = lookupName(c) || fallbackName || c;
      // 같은 페이지 모달 띄우기 — clShowDetail 재사용
      return `<button type="button" class="chaebol-chip" data-code="${c}" onclick="showByCode('${c}', ${JSON.stringify(nm)})">${escapeHTML(nm)} <code>${c}</code></button>`;
    };

    const blocks = [];

    if (chaebolInfo.group) {
      blocks.push(
        `<div class="chaebol-row"><dt>그룹</dt><dd><strong>${escapeHTML(chaebolInfo.group)}</strong></dd></div>`
      );
    }
    if (chaebolInfo.parent && chaebolInfo.parent.code) {
      const p = chaebolInfo.parent;
      const pct = p.pct != null ? ` (${p.pct}%)` : "";
      blocks.push(
        `<div class="chaebol-row"><dt>모회사</dt><dd>${codeChip(p.code, p.name)}${pct}</dd></div>`
      );
    }
    if (Array.isArray(chaebolInfo.subsidiaries) && chaebolInfo.subsidiaries.length) {
      const items = chaebolInfo.subsidiaries.slice(0, 8).map((s) => {
        const pct = s.pct != null ? ` <span class="chaebol-pct">${s.pct}%</span>` : "";
        if (s.code) return codeChip(s.code, s.name) + pct;
        return `<span class="chaebol-chip chaebol-chip--unlisted">${escapeHTML(s.name)}${pct}</span>`;
      });
      blocks.push(
        `<div class="chaebol-row"><dt>자회사</dt><dd class="chaebol-chip-list">${items.join("")}</dd></div>`
      );
    }
    if (Array.isArray(chaebolInfo.affiliates) && chaebolInfo.affiliates.length) {
      const items = chaebolInfo.affiliates.map((c) => codeChip(c));
      blocks.push(
        `<div class="chaebol-row"><dt>계열사</dt><dd class="chaebol-chip-list">${items.join("")}</dd></div>`
      );
    }
    if (Array.isArray(chaebolInfo.shareholders) && chaebolInfo.shareholders.length) {
      const items = chaebolInfo.shareholders.slice(0, 5).map((s) => {
        const rel = s.rel ? ` <span class="chaebol-rel">${escapeHTML(s.rel)}</span>` : "";
        return `<span class="chaebol-chip chaebol-chip--share">${escapeHTML(s.name)}${rel} <span class="chaebol-pct">${s.pct}%</span></span>`;
      });
      blocks.push(
        `<div class="chaebol-row"><dt>주요주주</dt><dd class="chaebol-chip-list">${items.join("")}</dd></div>`
      );
    }

    if (!blocks.length) return "";
    return `
    <div class="section chaebol-section">
      <h3>🏛️ 그룹사 관계</h3>
      <dl class="chaebol-grid">${blocks.join("")}</dl>
      <div class="chaebol-note">
        ⚠️ 인터넷 공개정보(DART 등) 기반 · 매월 1일 업데이트 · 단순 참고자료입니다.
        <a href="/contact" class="chaebol-note-link">오류 제보</a>
      </div>
    </div>`;
  })();

  return `
    <div class="snapshot-section">
      ${quote ? `<p class="snapshot-delay-note">⏱ 현재가·등락률·거래량은 <strong>20분 지연</strong> 시세 기준 · 기준일자·PER·PBR 등은 전일 장마감 후 산출값</p>` : ""}
      <div class="snapshot-grid">
        ${snapshotCells.map((c) => `
          <div class="snapshot-cell">
            <div class="label">${c.label}</div>
            <div class="value${c.cls ? " " + c.cls : ""}">${c.value}</div>
          </div>`).join("")}
      </div>
    </div>

    ${companySection}

    ${chaebolSection}

    <div class="section">
      <div class="section-head">
        <h3>📈 ${tfLbl} 캔들 · 이동평균 · 볼린저 밴드</h3>
        <div class="tf-group tf-group--modal" role="tablist" aria-label="봉 주기">
          ${tfBtn("D", "일봉")}${tfBtn("W", "주봉")}${tfBtn("M", "월봉")}
        </div>
      </div>
      ${delayBadge}
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

  // 공용 렌더 함수 — (clientX, clientY, isTouch) 에 맞춰 해당 캔들 인덱스의
  // 툴팁을 그리고 위치를 잡는다. mouse 와 touch 에서 함께 쓴다.
  const showAt = (clientX, clientY, isTouch) => {
    if (!data || !data.length) return;
    const rect = canvas.getBoundingClientRect();
    const padL = 48;
    const cw = rect.width - padL - 8;
    const barW = cw / data.length;
    const idx = Math.max(0, Math.min(data.length - 1,
      Math.floor((clientX - rect.left - padL) / barW)));
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
    // 기본 위치: 마우스는 커서 우측, 터치는 손가락 위쪽(손가락이 툴팁을 가리지 않도록).
    let x, y;
    if (isTouch) {
      x = clientX - tw / 2;          // 손가락 기준 가로 중앙
      y = clientY - th - 28;          // 손가락 위쪽으로 여유 있게
      if (y < 6) y = clientY + 28;   // 위로 공간이 없으면 아래로
    } else {
      x = clientX + 14;
      y = clientY - 10;
    }
    // 화면 경계 클램프
    if (x + tw + 6 > window.innerWidth) x = window.innerWidth - tw - 6;
    if (x < 6) x = 6;
    if (y + th + 6 > window.innerHeight) y = window.innerHeight - th - 6;
    if (y < 6) y = 6;
    t.style.left = x + "px"; t.style.top = y + "px";
  };
  const hide = () => { if (tip) tip.style.display = "none"; };

  // ── 마우스 ──
  canvas.addEventListener("mousemove", (e) => showAt(e.clientX, e.clientY, false));
  canvas.addEventListener("mouseleave", hide);

  // ── 터치 ──
  // 손가락이 캔버스 안에 있는 동안 인덱스를 실시간으로 따라가게 한다.
  // passive:true 를 유지해서 브라우저의 세로 스크롤은 여전히 동작하도록
  // (CSS touch-action: pan-y 와 짝을 이룸).
  canvas.addEventListener("touchstart", (e) => {
    const t = e.touches[0]; if (!t) return;
    showAt(t.clientX, t.clientY, true);
  }, { passive: true });
  canvas.addEventListener("touchmove", (e) => {
    const t = e.touches[0]; if (!t) return;
    showAt(t.clientX, t.clientY, true);
  }, { passive: true });
  canvas.addEventListener("touchend", hide);
  canvas.addEventListener("touchcancel", hide);
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

// URL 해시에 #code=005930 형태가 있으면 stocks 로드 후 해당 종목 모달 자동 오픈.
// /relations 등 다른 페이지에서 차트로 딥링크할 때 사용.
function _openFromHash() {
  const m = (location.hash || "").match(/code=(\d{6})/);
  if (!m) return;
  const code = m[1];
  const s = state.stocks.find((x) => x.code === code);
  if (s) {
    openDetail(s);
    // 새로고침 시 같은 모달이 또 열리지 않도록 hash 제거
    history.replaceState(null, "", location.pathname);
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
  _openFromHash();
})();
