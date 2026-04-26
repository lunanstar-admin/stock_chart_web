/**
 * relations.js — 그룹사 관계도 페이지 로직
 *
 * 데이터 소스
 *   /data/chaebol.json        — 그룹·회원사 메타
 *   /data/chaebol-codes.json  — 종목코드별 자회사·모회사·주주 인덱스 (그래프 edge 추출용)
 */

(function () {
  "use strict";

  const state = {
    view: "graph",           // 'graph' | 'tree' | 'table'
    listedOnly: true,
    chaebol: null,           // chaebol.json
    codes: null,             // chaebol-codes.json
    selectedGroup: null,     // 현재 그룹명
    network: null,           // vis-network 인스턴스
  };

  // ─── 유틸 ──────────────────────────────────────────────
  const $ = (id) => document.getElementById(id);

  function escapeHTML(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function setStatus(msg) {
    const el = $("relStatus");
    if (el) {
      el.textContent = msg || "";
      el.style.display = msg ? "block" : "none";
    }
  }

  function showCanvas(which) {
    // which: 'graph' | 'tree' | 'table'
    $("relCanvas").hidden = which !== "graph";
    $("relTree").hidden = which !== "tree";
    $("relTable").hidden = which !== "table";
  }

  // ─── 데이터 로드 ────────────────────────────────────────
  async function loadData() {
    setStatus("데이터 로드 중…");
    try {
      const [c1, c2] = await Promise.all([
        fetch("/data/chaebol.json", { cache: "default" }).then((r) => r.json()),
        fetch("/data/chaebol-codes.json", { cache: "default" }).then((r) => r.json()),
      ]);
      state.chaebol = c1;
      state.codes = c2;
      setStatus("");
      return true;
    } catch (e) {
      setStatus("⚠️ 데이터 로드 실패: " + (e && e.message ? e.message : e));
      return false;
    }
  }

  // ─── vis-network 동적 대기 ───────────────────────────────
  function waitForVis(timeoutMs = 5000) {
    return new Promise((resolve, reject) => {
      const t0 = Date.now();
      (function poll() {
        if (typeof vis !== "undefined" && vis.Network) return resolve(vis);
        if (Date.now() - t0 > timeoutMs) return reject(new Error("vis-network 로드 실패"));
        setTimeout(poll, 60);
      })();
    });
  }

  // ─── 그룹 셀렉트 채우기 ─────────────────────────────────
  function populateGroupSelects() {
    const owSel = $("relGroupSelect");
    if (!state.chaebol) return;

    const memberGroups = new Set((state.chaebol.groupMembers || []).map((m) => m.group));
    const groups = (state.chaebol.groups || [])
      .filter((g) => memberGroups.has(g.name))
      .slice()
      .sort((a, b) => {
        const ra = a.rank == null ? 9999 : a.rank;
        const rb = b.rank == null ? 9999 : b.rank;
        return ra - rb;
      });
    // groups 메타에 없는 그룹도 멤버가 있으면 추가
    const known = new Set(groups.map((g) => g.name));
    [...memberGroups].forEach((gn) => {
      if (!known.has(gn)) groups.push({ name: gn, rank: null });
    });

    owSel.innerHTML = groups.map((g) => {
      const label = g.rank ? `${g.rank}위. ${g.name}` : g.name;
      return `<option value="${escapeHTML(g.name)}">${escapeHTML(label)}</option>`;
    }).join("");

    if (groups.length) {
      const samsung = groups.find((g) => g.name === "삼성그룹") || groups.find((g) => g.name === "삼성") || groups[0];
      owSel.value = samsung.name;
      state.selectedGroup = samsung.name;
    }
  }

  // ─── 그룹사 관계도 — 데이터 변환 ────────────────────────
  function buildOwnershipGraph(groupName) {
    if (!state.chaebol || !state.codes) return { nodes: [], edges: [] };
    const members = (state.chaebol.groupMembers || []).filter((m) => m.group === groupName);
    if (!members.length) return { nodes: [], edges: [] };

    const nodes = members.map((m) => ({
      id: m.code || `__${groupName}_${m.name}`,
      code: m.code || null,
      name: m.name,
      listed: !!m.listed,
      rep: !!m.rep,
    }));
    if (state.listedOnly) {
      const filtered = nodes.filter((n) => n.listed);
      return makeEdges(groupName, filtered);
    }
    return makeEdges(groupName, nodes);
  }

  function makeEdges(groupName, nodes) {
    const codeSet = new Set(nodes.map((n) => n.code).filter(Boolean));
    const edges = [];
    nodes.forEach((n) => {
      if (!n.code) return;
      const info = state.codes[n.code];
      if (!info) return;
      // parent (다중 가능)
      const parents = info.parents || (info.parent ? [info.parent] : []);
      parents.forEach((p) => {
        if (p && p.code && codeSet.has(p.code)) {
          edges.push({ from: p.code, to: n.code, pct: p.pct });
        }
      });
      // subsidiaries
      (info.subsidiaries || []).forEach((s) => {
        if (s.code && codeSet.has(s.code)) {
          edges.push({ from: n.code, to: s.code, pct: s.pct });
        }
      });
    });
    // dedup
    const seen = new Set();
    const uniq = [];
    edges.forEach((e) => {
      const k = e.from + "→" + e.to;
      if (seen.has(k)) return;
      seen.add(k);
      uniq.push(e);
    });
    return { nodes, edges: uniq };
  }

  function classify(n, edges) {
    const hasOut = edges.some((e) => e.from === n.id);
    const hasIn = edges.some((e) => e.to === n.id);
    if (n.rep) return "rep";
    if (hasOut && !hasIn) return "parent";
    if (hasIn && !hasOut) return n.listed ? "sub_listed" : "sub_unlisted";
    return n.listed ? "mid_listed" : "mid_unlisted";
  }

  // ─── 노드 그래프 ─────────────────────────────────────
  async function renderOwnershipGraph(groupName) {
    if (state.network) { try { state.network.destroy(); } catch (_) {} state.network = null; }
    const { nodes, edges } = buildOwnershipGraph(groupName);
    if (!nodes.length) {
      $("relCanvas").innerHTML = `<div class="rel-empty">표시할 회사가 없습니다.</div>`;
      return;
    }
    setStatus("그래프 렌더링 중…");
    let visLib;
    try { visLib = await waitForVis(5000); } catch (e) {
      setStatus("⚠️ 그래프 라이브러리 로드 실패. 트리/테이블 뷰는 사용 가능합니다.");
      return;
    }
    setStatus("");

    const fmtCap = (v) => v ? (v >= 1e12 ? (v/1e12).toFixed(1)+"조" : v >= 1e8 ? (v/1e8).toFixed(0)+"억" : v) : "-";

    const visNodes = nodes.map((n) => {
      const role = classify(n, edges);
      const styles = {
        rep:           { bg: "#fff7ed", border: "#f59e0b", fontColor: "#92400e" },
        parent:        { bg: "#fef2f2", border: "#dc2626", fontColor: "#991b1b" },
        sub_listed:    { bg: "#f8fafc", border: "#3b82f6", fontColor: "#1e40af" },
        sub_unlisted:  { bg: "#f1f5f9", border: "#94a3b8", fontColor: "#475569" },
        mid_listed:    { bg: "#f0f9ff", border: "#0ea5e9", fontColor: "#0c4a6e" },
        mid_unlisted:  { bg: "#f8fafc", border: "#cbd5e1", fontColor: "#64748b" },
      }[role];
      return {
        id: n.id,
        label: n.name,
        shape: "box",
        color: { background: styles.bg, border: styles.border, highlight: { background: "#fef3c7", border: styles.border } },
        font: { color: styles.fontColor, size: 12, face: "Pretendard, system-ui, sans-serif" },
        borderWidth: n.rep ? 3 : 1.5,
        margin: 6,
        title: `${n.name}${n.code ? " ("+n.code+")":""}\n${n.listed ? "상장" : "비상장"}${n.rep ? " · 대표" : ""}`,
      };
    });

    const visEdges = edges.map((e, i) => {
      const pct = e.pct;
      let color = "#0d9488", width = 1.4;
      if (pct >= 50) { color = "#dc2626"; width = 2.8; }
      else if (pct >= 20) { color = "#ea580c"; width = 2.0; }
      return {
        id: "e" + i,
        from: e.from, to: e.to,
        arrows: "to",
        color: { color, opacity: 0.85 },
        width,
        label: pct != null ? pct + "%" : "",
        font: { size: 9, color: "#475569", strokeWidth: 0, align: "middle" },
        smooth: { type: "cubicBezier", forceDirection: "vertical", roundness: 0.4 },
      };
    });

    const container = $("relCanvas");
    container.innerHTML = "";
    const data = { nodes: new visLib.DataSet(visNodes), edges: new visLib.DataSet(visEdges) };
    const options = {
      layout: { hierarchical: { enabled: true, direction: "UD", sortMethod: "directed", levelSeparation: 130, nodeSpacing: 160 } },
      physics: { enabled: false },
      interaction: { hover: true, tooltipDelay: 150, navigationButtons: true, keyboard: false },
      edges: { smooth: { type: "cubicBezier" } },
    };
    state.network = new visLib.Network(container, data, options);
    state.network.on("doubleClick", (params) => {
      if (params.nodes.length) {
        const id = params.nodes[0];
        const n = nodes.find((x) => x.id === id);
        if (n && n.code) location.href = `/chart#code=${n.code}`;
      }
    });
    renderLegend();
  }

  // ─── 트리 뷰 ────────────────────────────────────────
  function renderOwnershipTree(groupName) {
    const { nodes, edges } = buildOwnershipGraph(groupName);
    if (!nodes.length) {
      $("relTree").innerHTML = `<div class="rel-empty">표시할 회사가 없습니다.</div>`;
      return;
    }
    const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
    const childrenOf = {};
    edges.forEach((e) => {
      childrenOf[e.from] = childrenOf[e.from] || [];
      childrenOf[e.from].push({ to: e.to, pct: e.pct });
    });
    const targetSet = new Set(edges.map((e) => e.to));
    const roots = nodes.filter((n) => !targetSet.has(n.id));
    const renderNode = (n, depth, pct) => {
      if (!n) return "";
      const childrenHTML = (childrenOf[n.id] || [])
        .map((c) => renderNode(byId[c.to], depth + 1, c.pct)).join("");
      const pctTxt = pct != null ? ` <span class="rel-tree-pct">${pct}%</span>` : "";
      const star = n.rep ? " ⭐" : "";
      return `
        <li>
          <span class="rel-tree-node ${n.listed ? "is-listed" : "is-unlisted"}">
            ${n.code ? `<a href="/chart#code=${n.code}">${escapeHTML(n.name)}</a>` : escapeHTML(n.name)}${star}${pctTxt}
          </span>
          ${childrenHTML ? `<ul class="rel-tree-children">${childrenHTML}</ul>` : ""}
        </li>`;
    };
    const html = `<ul class="rel-tree-root">${roots.map((r) => renderNode(byId[r.id], 0, null)).join("")}</ul>`;
    $("relTree").innerHTML = html;
  }

  // ─── 테이블 뷰 ────────────────────────────────────────
  function renderOwnershipTable(groupName) {
    const { nodes } = buildOwnershipGraph(groupName);
    if (!nodes.length) {
      $("relTable").innerHTML = `<div class="rel-empty">표시할 회사가 없습니다.</div>`;
      return;
    }
    const rows = nodes.map((n) => {
      let parents = [];
      let subs = [];
      if (n.code && state.codes[n.code]) {
        const info = state.codes[n.code];
        parents = info.parents || (info.parent ? [info.parent] : []);
        subs = (info.subsidiaries || []).filter((s) => s.code && nodes.some((x) => x.code === s.code));
      }
      return { ...n, parents, subs };
    });
    const tableHTML = `
      <table class="rel-table">
        <thead>
          <tr>
            <th>회사명</th>
            <th>종목코드</th>
            <th>상장</th>
            <th>모회사 (지분율)</th>
            <th>주요 자회사 (지분율)</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((r) => `
            <tr>
              <td>${r.rep ? "<strong>" : ""}${escapeHTML(r.name)}${r.rep ? " ⭐</strong>" : ""}</td>
              <td>${r.code ? `<a href="/chart#code=${r.code}">${r.code}</a>` : "-"}</td>
              <td>${r.listed ? "✓" : "-"}</td>
              <td>${r.parents.length
                ? r.parents.map((p) => `${escapeHTML(p.name)} (${p.pct ?? "-"}%)`).join("<br>")
                : "-"}</td>
              <td>${r.subs.length
                ? r.subs.slice(0, 8).map((s) => `${escapeHTML(s.name)} (${s.pct ?? "-"}%)`).join("<br>")
                : "-"}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>`;
    $("relTable").innerHTML = tableHTML;
  }

  // ─── 범례 ───────────────────────────────────────────
  function renderLegend() {
    const el = $("relLegend");
    if (!el) return;
    el.innerHTML = `
      <span><span class="leg-box" style="background:#fff7ed;border:2px solid #f59e0b"></span>대표 회사</span>
      <span><span class="leg-box" style="background:#f8fafc;border:1px solid #3b82f6"></span>상장사</span>
      <span><span class="leg-box" style="background:#f1f5f9;border:1px solid #94a3b8"></span>비상장</span>
      <span><span class="leg-arrow">→</span> 출자관계 (지분%)</span>
      <span class="leg-hint">노드 더블클릭 → 종목 차트로 이동</span>
    `;
  }

  // ─── 뷰 전환 ────────────────────────────────────
  function switchView(view) {
    state.view = view;
    document.querySelectorAll(".rel-view-btn").forEach((b) => {
      b.classList.toggle("is-active", b.dataset.view === view);
    });
    showCanvas(view);
    renderCurrent();
  }

  function renderCurrent() {
    const g = state.selectedGroup;
    if (!g) return;
    if (state.view === "graph") renderOwnershipGraph(g);
    else if (state.view === "tree") renderOwnershipTree(g);
    else if (state.view === "table") renderOwnershipTable(g);
  }

  // ─── 초기화 ─────────────────────────────────────────
  async function init() {
    const ok = await loadData();
    if (!ok) return;
    populateGroupSelects();

    document.querySelectorAll(".rel-view-btn").forEach((b) => {
      b.addEventListener("click", () => switchView(b.dataset.view));
    });
    $("relGroupSelect").addEventListener("change", (e) => {
      state.selectedGroup = e.target.value;
      renderCurrent();
    });
    const lo = $("relListedOnly");
    if (lo) lo.addEventListener("change", (e) => {
      state.listedOnly = !!e.target.checked;
      renderCurrent();
    });

    showCanvas(state.view);
    renderCurrent();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
