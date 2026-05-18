/* 거시 지표 대시보드 렌더링 — /data/macro.json */
(async function () {
  const $ = (id) => document.getElementById(id);

  function dirClass(d) {
    return d === "RISING" ? "macro-up" : d === "FALLING" ? "macro-down" : "macro-flat";
  }
  function dirArrow(d) {
    return d === "RISING" ? "▲" : d === "FALLING" ? "▼" : "—";
  }

  function drawSpark(canvas, points) {
    if (!canvas || !points || !points.length) return;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || 120;
    const h = canvas.clientHeight || 30;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    const xs = points.map((p, i) => i);
    const ys = points.map((p) => p.close);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const rangeY = maxY - minY || 1;
    const stepX = w / Math.max(1, xs.length - 1);

    const first = ys[0];
    const last = ys[ys.length - 1];
    const isUp = last >= first;
    const color = isUp ? "#ef4444" : "#3b82f6"; // 한국 관례: 상승=빨강

    ctx.beginPath();
    points.forEach((p, i) => {
      const x = i * stepX;
      const y = h - ((p.close - minY) / rangeY) * (h - 4) - 2;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.4;
    ctx.stroke();
  }

  function renderFx(data) {
    const list = $("macroFxList");
    if (!list) return;
    const items = [...(data.fx || []), ...(data.commodities || [])];
    if (!items.length) {
      list.innerHTML = '<div class="macro-empty">데이터 없음</div>';
      return;
    }
    list.innerHTML = items.map((it, idx) => `
      <div class="macro-row">
        <div class="macro-row-left">
          <div class="macro-row-name">${it.name}</div>
          <canvas class="macro-spark" data-idx="${idx}" width="120" height="30"></canvas>
        </div>
        <div class="macro-row-right ${dirClass(it.changeDir)}">
          <div class="macro-row-value">${it.value}</div>
          <div class="macro-row-change">${dirArrow(it.changeDir)} ${it.change} (${it.changeRate}%)</div>
        </div>
      </div>
    `).join("");
    list.querySelectorAll("canvas.macro-spark").forEach((c) => {
      const i = parseInt(c.dataset.idx, 10);
      drawSpark(c, items[i].spark);
    });
  }

  function renderSimpleList(elId, rows) {
    const el = $(elId);
    if (!el) return;
    if (!rows || !rows.length) {
      el.innerHTML = '<div class="macro-empty">데이터 없음</div>';
      return;
    }
    el.innerHTML = rows.map((r) => `
      <div class="macro-row macro-row--simple">
        <div class="macro-row-left">
          <div class="macro-row-name">${r.name}</div>
          <div class="macro-row-note">${r.note || ""} · ${r.asof || ""}</div>
        </div>
        <div class="macro-row-right">
          <div class="macro-row-value">${r.value}${r.unit || ""}</div>
        </div>
      </div>
    `).join("");
  }

  function tagLabel(tag) {
    const map = {
      rate: { label: "금리", cls: "tag-rate" },
      cpi: { label: "물가", cls: "tag-cpi" },
      expiry: { label: "만기", cls: "tag-expiry" },
      earnings: { label: "실적", cls: "tag-earnings" },
    };
    return map[tag] || { label: tag || "이벤트", cls: "tag-rate" };
  }

  function fmtDate(iso) {
    if (!iso) return "-";
    const [, m, d] = iso.match(/(\d{4})-(\d{2})-(\d{2})/) || [];
    return m && d ? `${parseInt(m)}/${parseInt(d)}` : iso;
  }

  function daysUntil(iso) {
    if (!iso) return null;
    const now = new Date();
    const target = new Date(iso + "T00:00:00+09:00");
    const ms = target - now;
    return Math.floor(ms / (24 * 3600 * 1000));
  }

  function renderEvents(events) {
    const el = $("macroEventsList");
    if (!el) return;
    if (!events || !events.length) {
      el.innerHTML = '<div class="macro-empty">예정된 이벤트 없음</div>';
      return;
    }
    el.innerHTML = events.slice(0, 8).map((ev) => {
      const t = tagLabel(ev.tag);
      const dleft = daysUntil(ev.date);
      const dlabel =
        dleft === 0 ? "오늘" :
        dleft === 1 ? "내일" :
        dleft > 0 ? `D-${dleft}` :
        dleft < 0 ? `${-dleft}일 전` : "";
      return `
        <div class="macro-row macro-row--event">
          <div class="macro-row-left">
            <div class="macro-row-name">
              <span class="macro-event-tag ${t.cls}">${t.label}</span>
              ${ev.title}
            </div>
            <div class="macro-row-note">${fmtDate(ev.date)} · ${ev.country || ""}</div>
          </div>
          <div class="macro-row-right">
            <div class="macro-row-dleft ${dleft >= 0 ? 'is-future' : 'is-past'}">${dlabel}</div>
          </div>
        </div>
      `;
    }).join("");
  }

  function fmtUpdated(iso) {
    if (!iso) return "";
    const m = iso.match(/(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    return m ? `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]} KST` : iso;
  }

  function setHeaderStamp(cardId, text) {
    const card = document.getElementById(cardId);
    if (!card) return;
    const h3 = card.querySelector("h3");
    if (!h3) return;
    // 기존 스탬프 제거 후 갱신
    const old = h3.querySelector(".macro-stamp");
    if (old) old.remove();
    if (!text) return;
    const span = document.createElement("span");
    span.className = "macro-stamp";
    span.textContent = text;
    h3.appendChild(span);
  }

  try {
    const r = await fetch("/data/macro.json", { cache: "no-cache" });
    if (!r.ok) throw new Error("macro.json 로드 실패");
    const data = await r.json();
    renderFx(data);
    renderSimpleList("macroRatesList", data.rates);
    renderSimpleList("macroCpiList", data.cpi);
    renderSimpleList("macroBondsList", data.bonds);

    // 카드별 데이터 기준일 / 갱신 시각 표시
    if (data.data_date) {
      setHeaderStamp("macroFxCard", `${data.data_date} 종가`);
    }
    // 금리/CPI 는 카드별 row 안에 asof 가 이미 표시됨
    // 푸터에 전체 갱신 시각
    const foot = document.querySelector(".macro-dashboard .macro-foot");
    if (foot && data.updated) {
      foot.innerHTML = `🔄 마지막 갱신: <strong>${fmtUpdated(data.updated)}</strong> &nbsp;·&nbsp; `
        + foot.innerHTML;
    }
    renderEvents(data.events);
  } catch (e) {
    ["macroFxList", "macroRatesList", "macroCpiList", "macroBondsList", "macroEventsList"].forEach((id) => {
      const el = $(id);
      if (el) el.innerHTML = '<div class="macro-empty">불러올 수 없습니다.</div>';
    });
  }
})();
