/* Canvas 기반 캔들/지표/수급 렌더러. 외부 라이브러리 없음. */

const Chart = (() => {
  const COL = {
    up: "#ef4444",
    down: "#4f8cff",
    ma5: "rgba(255,210,0,0.85)",
    ma20: "rgba(255,120,50,0.85)",
    ma60: "rgba(140,120,255,0.85)",
    grid: "rgba(255,255,255,0.06)",
    text: "#888",
    bbUpper: "rgba(168,85,247,0.35)",
    bbLower: "rgba(168,85,247,0.35)",
    bbFill: "rgba(168,85,247,0.05)",
    signal: "#f59e0b",
    macd: "#4f8cff",
    obv: "#22c55e",
    rsi: "#a855f7",
    mfi: "#ec4899",
    foreign: "rgba(79,140,255,0.9)",
    inst: "rgba(239,68,68,0.9)",
    retail: "rgba(245,158,11,0.9)",
  };

  function setupCanvas(canvas, height) {
    // 캔버스 자체의 style 을 일단 리셋해서 CSS width:100% 가 다시 적용되도록
    canvas.style.width = "";
    canvas.style.height = "";
    const parent = canvas.parentElement;
    const parentW = parent ? (parent.clientWidth || parent.getBoundingClientRect().width) : 0;
    const dpr = window.devicePixelRatio || 1;
    const w = Math.max(1, Math.floor(parentW));
    const h = height;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    return { ctx, w, h };
  }

  // 부모 레이아웃이 확정된 후 draw 를 재시도하는 헬퍼
  // 부모 너비가 너무 작으면 (< 60px) 한 번 requestAnimationFrame 으로 재시도.
  function safeDraw(canvas, fn) {
    const parent = canvas.parentElement;
    const w = parent ? (parent.clientWidth || parent.getBoundingClientRect().width) : 0;
    if (w < 60) {
      requestAnimationFrame(() => {
        const w2 = parent ? (parent.clientWidth || parent.getBoundingClientRect().width) : 0;
        if (w2 < 60) {
          // 한 번 더 기다린다 (초기 레이아웃 race 대비)
          requestAnimationFrame(fn);
        } else {
          fn();
        }
      });
    } else {
      fn();
    }
  }

  /* ── 미니차트 (리스트 행용) ────────────────────────────── */
  function drawMini(canvas, data) {
    if (!data || !data.length) return;
    // 리스트 행의 초기 레이아웃 race 방지
    canvas.__chartData = data;
    canvas.__chartKind = "mini";
    return safeDraw(canvas, () => _drawMiniImpl(canvas, data));
  }

  function _drawMiniImpl(canvas, data) {
    const { ctx, w, h } = setupCanvas(canvas, 180);

    const dateH = 12;
    const chartH = Math.floor((h - dateH) * 0.72);
    const volH = Math.floor((h - dateH) * 0.23);
    const volY = chartH + 2;

    const lows = data.map((d) => d.low);
    const highs = data.map((d) => d.high);
    const opens = data.map((d) => d.open);
    const closes = data.map((d) => d.close);
    const vols = data.map((d) => d.volume || 0);

    const minP = Math.min(...lows);
    const maxP = Math.max(...highs);
    const maxV = Math.max(...vols, 1);
    const pr = maxP - minP || 1;
    const n = data.length;
    const barW = Math.max(1, (w - 4) / n);
    const toY = (p) => chartH - ((p - minP) / pr) * (chartH - 4) - 2;

    for (let i = 0; i < n; i++) {
      const x = 2 + i * barW;
      const o = opens[i], c = closes[i], hg = highs[i], lw = lows[i];
      const up = c >= o;
      const color = up ? COL.up : COL.down;
      const yTop = toY(Math.max(o, c));
      const yBot = toY(Math.min(o, c));
      ctx.strokeStyle = color;
      ctx.lineWidth = 0.8;
      ctx.beginPath();
      ctx.moveTo(x + barW / 2, toY(hg));
      ctx.lineTo(x + barW / 2, toY(lw));
      ctx.stroke();
      ctx.fillStyle = color;
      const bh = Math.max(1, yBot - yTop);
      if (barW > 2) ctx.fillRect(x + 0.5, yTop, barW - 1, bh);
      else ctx.fillRect(x, yTop, barW, bh);
    }

    const mas = [
      { key: "ma5", color: COL.ma5 },
      { key: "ma20", color: COL.ma20 },
      { key: "ma60", color: COL.ma60 },
    ];
    for (const m of mas) {
      ctx.strokeStyle = m.color;
      ctx.lineWidth = 0.8;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < n; i++) {
        const v = data[i][m.key];
        if (v == null) continue;
        const x = 2 + i * barW + barW / 2;
        const y = toY(v);
        if (!started) { ctx.moveTo(x, y); started = true; }
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    for (let i = 0; i < n; i++) {
      const x = 2 + i * barW;
      const vH = (vols[i] / maxV) * volH;
      const up = closes[i] >= opens[i];
      ctx.fillStyle = up ? "rgba(239,68,68,0.35)" : "rgba(79,140,255,0.35)";
      ctx.fillRect(x, volY + volH - vH, Math.max(1, barW - 0.5), vH);
    }

    ctx.fillStyle = COL.text;
    ctx.font = "8px sans-serif";
    ctx.textAlign = "center";
    let lastMonth = "";
    for (let i = 0; i < n; i++) {
      const d = data[i].date;
      if (!d) continue;
      const m = d.slice(5, 7);
      if (m !== lastMonth) {
        lastMonth = m;
        const x = 2 + i * barW + barW / 2;
        ctx.fillText(d.slice(2, 4) + "/" + m, x, h - 2);
      }
    }
  }

  /* ── 수급 누적 미니차트 (3주체) ──────────────────────── */
  function drawSupplyMini(canvas, records) {
    if (!records || !records.length) return;
    canvas.__chartData = records;
    canvas.__chartKind = "supplyMini";
    return safeDraw(canvas, () => _drawSupplyMiniImpl(canvas, records));
  }

  function _drawSupplyMiniImpl(canvas, records) {
    const { ctx, w, h } = setupCanvas(canvas, 100);

    let cf = 0, ci = 0, cr = 0;
    const F = [], I = [], R = [];
    for (const rec of records) {
      cf += rec.foreign || 0; F.push(cf);
      ci += rec.inst || 0; I.push(ci);
      cr += rec.retail || 0; R.push(cr);
    }

    const all = F.concat(I).concat(R);
    let mn = Math.min(...all);
    let mx = Math.max(...all);
    if (mn === mx) { mn -= 1; mx += 1; }
    const rng = mx - mn;

    const padL = 2, padR = 2, padT = 6, padB = 14;
    const cw = w - padL - padR;
    const ch = h - padT - padB;
    const toY = (v) => padT + ch - ((v - mn) / rng) * ch;

    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.setLineDash([2, 2]);
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    const zy = toY(0);
    ctx.moveTo(padL, zy); ctx.lineTo(w - padR, zy);
    ctx.stroke();
    ctx.setLineDash([]);

    const series = [
      { data: F, color: COL.foreign },
      { data: I, color: COL.inst },
      { data: R, color: "rgba(150,150,150,0.5)" },
    ];
    const n = records.length;
    for (const s of series) {
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const x = padL + (n > 1 ? (i / (n - 1)) * cw : 0);
        const y = toY(s.data[i]);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    ctx.font = "8px sans-serif";
    ctx.textAlign = "center";
    const legs = [
      { label: "외", color: COL.foreign, x: w * 0.2 },
      { label: "기", color: COL.inst, x: w * 0.5 },
      { label: "개", color: "rgba(150,150,150,0.7)", x: w * 0.8 },
    ];
    for (const lg of legs) {
      ctx.fillStyle = lg.color;
      ctx.fillRect(lg.x - 12, h - 10, 8, 2);
      ctx.fillStyle = "#888";
      ctx.fillText(lg.label, lg.x + 6, h - 6);
    }
  }

  /* ── 상세 모달용: 메인 캔들 + 볼린저 + MA ────────────── */
  function drawDetailCandle(canvas, data) {
    if (!data || !data.length) return;
    const { ctx, w, h } = setupCanvas(canvas, 300);
    const padL = 48, padR = 8, padT = 10, padB = 20;
    const cw = w - padL - padR;
    const ch = h - padT - padB;

    const lows = data.map((d) => d.low);
    const highs = data.map((d) => d.high);
    let minP = Math.min(...lows);
    let maxP = Math.max(...highs);
    for (const d of data) {
      if (d.bb_lower != null) minP = Math.min(minP, d.bb_lower);
      if (d.bb_upper != null) maxP = Math.max(maxP, d.bb_upper);
    }
    const pr = maxP - minP || 1;
    const n = data.length;
    const barW = Math.max(1, cw / n);
    const toY = (p) => padT + ch - ((p - minP) / pr) * ch;

    // 가로 그리드
    ctx.strokeStyle = COL.grid;
    ctx.lineWidth = 0.5;
    ctx.fillStyle = COL.text;
    ctx.font = "10px sans-serif";
    ctx.textAlign = "right";
    for (let i = 0; i <= 4; i++) {
      const p = minP + (pr * i) / 4;
      const y = toY(p);
      ctx.beginPath();
      ctx.moveTo(padL, y); ctx.lineTo(w - padR, y);
      ctx.stroke();
      ctx.fillText(Math.round(p).toLocaleString(), padL - 4, y + 3);
    }

    // Bollinger fill
    ctx.fillStyle = COL.bbFill;
    ctx.beginPath();
    let first = true;
    for (let i = 0; i < n; i++) {
      const v = data[i].bb_upper; if (v == null) continue;
      const x = padL + i * barW + barW / 2;
      const y = toY(v);
      if (first) { ctx.moveTo(x, y); first = false; }
      else ctx.lineTo(x, y);
    }
    for (let i = n - 1; i >= 0; i--) {
      const v = data[i].bb_lower; if (v == null) continue;
      const x = padL + i * barW + barW / 2;
      ctx.lineTo(x, toY(v));
    }
    ctx.closePath(); ctx.fill();

    // Bollinger lines
    for (const key of ["bb_upper", "bb_lower"]) {
      ctx.strokeStyle = COL.bbUpper;
      ctx.lineWidth = 0.8;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < n; i++) {
        const v = data[i][key]; if (v == null) continue;
        const x = padL + i * barW + barW / 2;
        const y = toY(v);
        if (!started) { ctx.moveTo(x, y); started = true; }
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // 캔들
    for (let i = 0; i < n; i++) {
      const d = data[i];
      const x = padL + i * barW;
      const up = d.close >= d.open;
      const color = up ? COL.up : COL.down;
      const yTop = toY(Math.max(d.open, d.close));
      const yBot = toY(Math.min(d.open, d.close));
      ctx.strokeStyle = color; ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x + barW / 2, toY(d.high));
      ctx.lineTo(x + barW / 2, toY(d.low));
      ctx.stroke();
      ctx.fillStyle = color;
      ctx.fillRect(x + 0.5, yTop, Math.max(1, barW - 1), Math.max(1, yBot - yTop));
    }

    // MA 선
    const mas = [
      { k: "ma5", c: COL.ma5 },
      { k: "ma20", c: COL.ma20 },
      { k: "ma60", c: COL.ma60 },
    ];
    for (const m of mas) {
      ctx.strokeStyle = m.c; ctx.lineWidth = 1.2;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < n; i++) {
        const v = data[i][m.k]; if (v == null) continue;
        const x = padL + i * barW + barW / 2;
        const y = toY(v);
        if (!started) { ctx.moveTo(x, y); started = true; }
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // x축 날짜
    ctx.fillStyle = COL.text; ctx.textAlign = "center";
    let lastMonth = "";
    for (let i = 0; i < n; i++) {
      const d = data[i].date; if (!d) continue;
      const m = d.slice(5, 7);
      if (m !== lastMonth) {
        lastMonth = m;
        const x = padL + i * barW + barW / 2;
        ctx.fillText(d.slice(0, 4) === new Date().getFullYear().toString() ? m + "월" : d.slice(2, 7), x, h - 4);
      }
    }
  }

  function drawVolume(canvas, data) {
    if (!data || !data.length) return;
    const { ctx, w, h } = setupCanvas(canvas, 70);
    const padL = 48, padR = 8, padT = 6, padB = 14;
    const cw = w - padL - padR;
    const ch = h - padT - padB;
    const vols = data.map((d) => d.volume || 0);
    const maxV = Math.max(...vols, 1);
    const n = data.length;
    const barW = Math.max(1, cw / n);
    for (let i = 0; i < n; i++) {
      const d = data[i];
      const up = d.close >= d.open;
      const x = padL + i * barW;
      const vH = (vols[i] / maxV) * ch;
      ctx.fillStyle = up ? "rgba(239,68,68,0.45)" : "rgba(79,140,255,0.45)";
      ctx.fillRect(x, padT + ch - vH, Math.max(1, barW - 0.5), vH);
    }
    ctx.fillStyle = COL.text; ctx.font = "10px sans-serif"; ctx.textAlign = "right";
    ctx.fillText(maxV.toLocaleString(), padL - 4, padT + 8);
  }

  /* ── 지표 패널들 (MACD, RSI, OBV, MFI) ──────────── */
  function drawLinePanel(canvas, data, opts) {
    if (!data || !data.length) return;
    const { ctx, w, h } = setupCanvas(canvas, 120);
    const padL = 48, padR = 8, padT = 10, padB = 16;
    const cw = w - padL - padR;
    const ch = h - padT - padB;
    const n = data.length;
    const barW = Math.max(1, cw / n);

    // 범위 계산
    const allVals = [];
    for (const s of opts.series) {
      for (const d of data) if (d[s.key] != null) allVals.push(d[s.key]);
    }
    if (opts.bars) {
      for (const d of data) if (d[opts.bars.key] != null) allVals.push(d[opts.bars.key]);
    }
    let mn = Math.min(...allVals, opts.yMin != null ? opts.yMin : Infinity);
    let mx = Math.max(...allVals, opts.yMax != null ? opts.yMax : -Infinity);
    if (opts.yMin != null) mn = opts.yMin;
    if (opts.yMax != null) mx = opts.yMax;
    if (mn === mx) { mn -= 1; mx += 1; }
    const rng = mx - mn;
    const toY = (v) => padT + ch - ((v - mn) / rng) * ch;

    // 가이드라인
    ctx.strokeStyle = COL.grid; ctx.lineWidth = 0.5;
    ctx.fillStyle = COL.text; ctx.font = "10px sans-serif"; ctx.textAlign = "right";
    const guides = opts.guides || [];
    for (const g of guides) {
      const y = toY(g);
      ctx.beginPath();
      ctx.moveTo(padL, y); ctx.lineTo(w - padR, y);
      ctx.stroke();
      ctx.fillText(g.toString(), padL - 4, y + 3);
    }

    if (opts.bars) {
      for (let i = 0; i < n; i++) {
        const v = data[i][opts.bars.key]; if (v == null) continue;
        const x = padL + i * barW;
        const y0 = toY(0);
        const y = toY(v);
        ctx.fillStyle = v >= 0 ? opts.bars.colorPos : opts.bars.colorNeg;
        ctx.fillRect(x, Math.min(y, y0), Math.max(1, barW - 0.5), Math.abs(y - y0));
      }
    }

    for (const s of opts.series) {
      ctx.strokeStyle = s.color; ctx.lineWidth = 1.2;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < n; i++) {
        const v = data[i][s.key]; if (v == null) continue;
        const x = padL + i * barW + barW / 2;
        const y = toY(v);
        if (!started) { ctx.moveTo(x, y); started = true; }
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  }

  function drawMACD(canvas, data) {
    drawLinePanel(canvas, data, {
      guides: [0],
      series: [
        { key: "macd", color: COL.macd },
        { key: "macd_signal", color: COL.signal },
      ],
      bars: {
        key: "macd_hist",
        colorPos: "rgba(239,68,68,0.5)",
        colorNeg: "rgba(79,140,255,0.5)",
      },
    });
  }
  function drawRSI(canvas, data) {
    drawLinePanel(canvas, data, {
      yMin: 0, yMax: 100,
      guides: [30, 50, 70],
      series: [{ key: "rsi", color: COL.rsi }],
    });
  }
  function drawOBV(canvas, data) {
    drawLinePanel(canvas, data, {
      series: [{ key: "obv", color: COL.obv }],
    });
  }
  function drawMFI(canvas, data) {
    drawLinePanel(canvas, data, {
      yMin: 0, yMax: 100,
      guides: [20, 50, 80],
      series: [{ key: "mfi", color: COL.mfi }],
    });
  }

  /* ── 상세 수급 누적 ───────────────────────────── */
  function drawSupplyCumulative(canvas, records) {
    if (!records || !records.length) return;
    const { ctx, w, h } = setupCanvas(canvas, 180);
    const padL = 48, padR = 8, padT = 10, padB = 24;
    const cw = w - padL - padR;
    const ch = h - padT - padB;

    let cf = 0, ci = 0, cr = 0;
    const F = [], I = [], R = [];
    for (const rec of records) {
      cf += rec.foreign || 0; F.push(cf);
      ci += rec.inst || 0; I.push(ci);
      cr += rec.retail || 0; R.push(cr);
    }
    const all = F.concat(I).concat(R);
    let mn = Math.min(...all), mx = Math.max(...all);
    if (mn === mx) { mn -= 1; mx += 1; }
    const rng = mx - mn;
    const n = records.length;
    const toY = (v) => padT + ch - ((v - mn) / rng) * ch;
    const toX = (i) => padL + (n > 1 ? (i / (n - 1)) * cw : 0);

    ctx.strokeStyle = COL.grid; ctx.lineWidth = 0.5;
    ctx.beginPath();
    const zy = toY(0);
    ctx.moveTo(padL, zy); ctx.lineTo(w - padR, zy);
    ctx.stroke();

    ctx.fillStyle = COL.text; ctx.font = "10px sans-serif"; ctx.textAlign = "right";
    ctx.fillText((mx / 1e8).toFixed(0) + "억", padL - 4, padT + 8);
    ctx.fillText((mn / 1e8).toFixed(0) + "억", padL - 4, padT + ch - 2);

    const series = [
      { data: F, color: COL.foreign, label: "외국인" },
      { data: I, color: COL.inst, label: "기관" },
      { data: R, color: COL.retail, label: "개인" },
    ];
    for (const s of series) {
      ctx.strokeStyle = s.color; ctx.lineWidth = 1.4;
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const x = toX(i), y = toY(s.data[i]);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // 날짜 x축
    ctx.fillStyle = COL.text; ctx.textAlign = "center";
    const firstD = records[0]?.date || "";
    const lastD = records[n - 1]?.date || "";
    ctx.fillText(firstD, padL + 40, h - 6);
    ctx.fillText(lastD, w - padR - 40, h - 6);
  }

  function drawSupplyDaily(canvas, records) {
    if (!records || !records.length) return;
    const { ctx, w, h } = setupCanvas(canvas, 140);
    const padL = 48, padR = 8, padT = 10, padB = 20;
    const cw = w - padL - padR;
    const ch = h - padT - padB;
    const n = records.length;
    const groupW = cw / n;
    const barW = Math.max(1, (groupW - 1) / 3);

    const all = [];
    for (const r of records) {
      all.push(r.foreign || 0, r.inst || 0, r.retail || 0);
    }
    const amx = Math.max(...all.map(Math.abs), 1);
    const zy = padT + ch / 2;
    const toY = (v) => zy - (v / amx) * (ch / 2);

    ctx.strokeStyle = COL.grid; ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(padL, zy); ctx.lineTo(w - padR, zy);
    ctx.stroke();

    for (let i = 0; i < n; i++) {
      const base = padL + i * groupW;
      const r = records[i];
      const vs = [r.foreign || 0, r.inst || 0, r.retail || 0];
      const cs = [COL.foreign, COL.inst, COL.retail];
      for (let k = 0; k < 3; k++) {
        const x = base + k * barW + 0.5;
        const y = toY(vs[k]);
        const yTop = Math.min(zy, y);
        const bh = Math.abs(y - zy);
        ctx.fillStyle = cs[k];
        ctx.fillRect(x, yTop, Math.max(0.5, barW - 0.5), Math.max(0.5, bh));
      }
    }

    ctx.fillStyle = COL.text; ctx.font = "10px sans-serif"; ctx.textAlign = "center";
    if (records[0]) ctx.fillText(records[0].date, padL + 30, h - 4);
    if (records[n - 1]) ctx.fillText(records[n - 1].date, w - padR - 30, h - 4);
  }

  // 윈도우 리사이즈 시 캔버스 재렌더 (미니차트용)
  function redrawAll(root) {
    const canvases = (root || document).querySelectorAll("canvas[data-role='mini'], canvas[data-role='supply']");
    canvases.forEach((c) => {
      const kind = c.__chartKind, data = c.__chartData;
      if (!kind || !data) return;
      if (kind === "mini") _drawMiniImpl(c, data);
      else if (kind === "supplyMini") _drawSupplyMiniImpl(c, data);
    });
  }

  return {
    drawMini,
    drawSupplyMini,
    drawDetailCandle,
    drawVolume,
    drawMACD,
    drawRSI,
    drawOBV,
    drawMFI,
    drawSupplyCumulative,
    drawSupplyDaily,
    redrawAll,
  };
})();
