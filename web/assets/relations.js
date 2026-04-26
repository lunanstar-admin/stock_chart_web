/**
 * relations.js — 재벌 가계도 + 그룹사 관계도 페이지 로직
 *
 * 데이터 소스
 *   /data/chaebol.json        — 인물·가계·그룹·회원사 메타
 *   /data/chaebol-codes.json  — 종목코드별 자회사·모회사·주주 인덱스 (그래프 edge 추출용)
 *
 * 모드
 *   ownership — 그룹사 관계도 (그룹 선택 + 노드/트리/테이블 뷰 + 상장사 필터)
 *   family    — 재벌 가계도 (가문 선택, vis-network hierarchical layout)
 */

(function () {
  "use strict";

  const state = {
    mode: "ownership",       // 'ownership' | 'family'
    view: "graph",           // 'graph' | 'tree' | 'table'
    listedOnly: true,
    chaebol: null,           // chaebol.json
    codes: null,             // chaebol-codes.json
    selectedGroup: null,     // 현재 그룹명
    selectedFamilyGroup: null,
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
    const fmSel = $("relFamilyGroup");
    if (!state.chaebol) return;

    // ownership: 모든 business_groups (rank 순), members 가 있는 것만
    const memberGroups = new Set((state.chaebol.groupMembers || []).map((m) => m.group));
    const groups = (state.chaebol.groups || [])
      .filter((g) => memberGroups.has(g.name))
      .slice()
      .sort((a, b) => {
        const ra = a.rank == null ? 9999 : a.rank;
        const rb = b.rank == null ? 9999 : b.rank;
        return ra - rb;
      });
    owSel.innerHTML = groups.map((g) => {
      const label = g.rank ? `${g.rank}위. ${g.name}` : g.name;
      return `<option value="${escapeHTML(g.name)}">${escapeHTML(label)}</option>`;
    }).join("");

    // family: chaebol_persons 의 group_name distinct
    const famGroups = [...new Set((state.chaebol.persons || []).map((p) => p.group).filter(Boolean))].sort();
    fmSel.innerHTML = `<option value="">전체 가문</option>` +
      famGroups.map((g) => `<option value="${escapeHTML(g)}">${escapeHTML(g)}</option>`).join("");

    // 기본 선택
    if (groups.length) {
      const samsung = groups.find((g) => g.name === "삼성") || groups[0];
      owSel.value = samsung.name;
      state.selectedGroup = samsung.name;
    }
  }

  // ─── 그룹사 관계도 — 데이터 변환 ────────────────────────
  // 그룹 → { nodes:[{code, name, listed, isParent, isSub}], edges:[{from, to, pct}] }
  function buildOwnershipGraph(groupName) {
    if (!state.chaebol || !state.codes) return { nodes: [], edges: [] };
    const members = (state.chaebol.groupMembers || []).filter((m) => m.group === groupName);
    if (!members.length) return { nodes: [], edges: [] };

    // 노드 후보: 그룹 멤버 회사들. 코드 있는 것만 lookup 가능.
    const nodes = members.map((m) => ({
      id: m.code || `__${groupName}_${m.name}`,
      code: m.code || null,
      name: m.name,
      listed: !!m.listed,
      rep: !!m.rep,
    }));
    if (state.listedOnly) {
      const filtered = nodes.filter((n) => n.listed);
      // 상장사가 1개 이하면 필터 해제 안내
      if (filtered.length < 2) {
        return { nodes: [], edges: [], note: "상장사 필터를 끄면 비상장 회원사가 보입니다." };
      }
      nodes.length = 0;
      filtered.forEach((n) => nodes.push(n));
    }

    // edges: chaebol-codes 의 parent/subsidiaries 정보 활용
    const edges = [];
    const nodeIds = new Set(nodes.map((n) => n.id));
    nodes.forEach((n) => {
      if (!n.code) return;
      const info = state.codes[n.code];
      if (!info) return;
      // 자회사 — n → sub
      (info.subsidiaries || []).forEach((s) => {
        if (s.code && nodeIds.has(s.code)) {
          edges.push({ from: n.code, to: s.code, pct: s.pct });
        }
      });
    });
    return { nodes, edges };
  }

  // ─── 관계도: vis-network 노드 뷰 ──────────────────────────
  async function renderOwnershipGraph(groupName) {
    if (state.network) {
      try { state.network.destroy(); } catch (_) {}
      state.network = null;
    }
    const { nodes, edges, note } = buildOwnershipGraph(groupName);
    if (!nodes.length) {
      $("relCanvas").innerHTML = `<div class="rel-empty">표시할 회사가 없습니다.${note ? "<br>" + escapeHTML(note) : ""}</div>`;
      renderLegend();
      return;
    }

    setStatus("그래프 렌더링 중…");
    let visLib;
    try { visLib = await waitForVis(5000); } catch (e) {
      setStatus("⚠️ 그래프 라이브러리 로드 실패. 트리/테이블 뷰는 사용 가능합니다.");
      return;
    }

    // vis 데이터셋 변환
    const visNodes = nodes.map((n) => ({
      id: n.id,
      label: n.name + (n.code ? `\n${n.code}` : ""),
      code: n.code,
      shape: "box",
      borderWidth: n.rep ? 3 : 1,
      color: {
        background: n.rep ? "#fff7ed" : (n.listed ? "#f8fafc" : "#f1f5f9"),
        border: n.rep ? "#f59e0b" : (n.listed ? "#3b82f6" : "#94a3b8"),
        highlight: { background: "#fef3c7", border: "#f59e0b" },
      },
      font: { size: 13, face: "Pretendard, system-ui, sans-serif", color: "#1f2328" },
      margin: 8,
    }));

    const visEdges = edges.map((e, i) => ({
      id: "e" + i,
      from: e.from,
      to: e.to,
      label: e.pct != null ? e.pct + "%" : "",
      arrows: "to",
      color: { color: "#94a3b8", highlight: "#3b82f6" },
      font: { size: 11, color: "#64748b", strokeWidth: 0, align: "middle" },
      smooth: { type: "continuous", roundness: 0.2 },
    }));

    setStatus("");
    const container = $("relCanvas");
    container.innerHTML = "";
    const data = { nodes: new visLib.DataSet(visNodes), edges: new visLib.DataSet(visEdges) };
    const options = {
      layout: { improvedLayout: true },
      physics: {
        stabilization: { iterations: 200 },
        barnesHut: { gravitationalConstant: -8000, springLength: 140, springConstant: 0.04, avoidOverlap: 0.4 },
      },
      interaction: { hover: true, tooltipDelay: 200, navigationButtons: true, keyboard: false },
      nodes: { borderWidth: 1, shadow: false },
      edges: { width: 1 },
    };
    state.network = new visLib.Network(container, data, options);

    // 노드 클릭 → 차트 모달 열기 (chart 페이지로 이동 후 모달)
    state.network.on("doubleClick", (params) => {
      if (!params.nodes.length) return;
      const id = params.nodes[0];
      const n = nodes.find((x) => x.id === id);
      if (n && n.code) {
        // 다른 페이지에서 모달 직접 열 수 없으니 차트 페이지로 이동 + URL hash 로 코드 전달
        window.location.href = `/chart#code=${n.code}`;
      }
    });

    renderLegend();
  }

  // ─── 트리 뷰 ──────────────────────────────────────────
  function renderOwnershipTree(groupName) {
    const { nodes, edges } = buildOwnershipGraph(groupName);
    if (!nodes.length) {
      $("relTree").innerHTML = `<div class="rel-empty">표시할 회사가 없습니다.</div>`;
      return;
    }
    const byId = {};
    nodes.forEach((n) => (byId[n.id] = { ...n, children: [] }));
    const incoming = new Set(); // 부모를 가진 노드 id
    edges.forEach((e) => {
      if (byId[e.from] && byId[e.to]) {
        byId[e.from].children.push({ ...byId[e.to], pct: e.pct });
        incoming.add(e.to);
      }
    });
    const roots = nodes.filter((n) => !incoming.has(n.id));

    const renderNode = (n, depth, pct) => {
      const codeBadge = n.code
        ? `<a class="rel-tree-code" href="/chart#code=${n.code}">${n.code}</a>`
        : "";
      const listedBadge = n.listed ? `<span class="rel-tree-badge">상장</span>` : "";
      const repBadge = n.rep ? `<span class="rel-tree-badge rel-tree-badge--rep">대표</span>` : "";
      const pctTxt = pct != null ? `<span class="rel-tree-pct">${pct}%</span>` : "";
      const childrenHTML = (n.children || [])
        .map((c) => renderNode(c, depth + 1, c.pct))
        .join("");
      return `
        <li class="rel-tree-node">
          <div class="rel-tree-card">
            ${pctTxt}
            <span class="rel-tree-name">${escapeHTML(n.name)}</span>
            ${codeBadge}
            ${repBadge}${listedBadge}
          </div>
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
    // 각 회사의 모회사·자회사 매핑
    const rows = nodes.map((n) => {
      let parent = null;
      let subs = [];
      if (n.code && state.codes[n.code]) {
        const info = state.codes[n.code];
        parent = info.parent || null;
        subs = (info.subsidiaries || []).filter((s) => s.code && nodes.some((x) => x.code === s.code));
      }
      return { ...n, parent, subs };
    });
    const tableHTML = `
      <table class="rel-table">
        <thead>
          <tr>
            <th>회사명</th>
            <th>종목코드</th>
            <th>상장</th>
            <th>모회사</th>
            <th>주요 자회사 (지분율)</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((r) => `
            <tr>
              <td>${r.rep ? "<strong>" : ""}${escapeHTML(r.name)}${r.rep ? " ⭐</strong>" : ""}</td>
              <td>${r.code ? `<a href="/chart#code=${r.code}">${r.code}</a>` : "-"}</td>
              <td>${r.listed ? "✓" : "-"}</td>
              <td>${r.parent ? `${escapeHTML(r.parent.name)} (${r.parent.pct ?? "-"}%)` : "-"}</td>
              <td>${r.subs.length
                ? r.subs.slice(0, 5).map((s) => `${escapeHTML(s.name)} (${s.pct ?? "-"}%)`).join(", ")
                : "-"}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>`;
    $("relTable").innerHTML = tableHTML;
  }

  // ─── 가계도 ─────────────────────────────────────────
  // vis-network hierarchical layout 으로 단순화 — dashboard 의 커스텀 SVG 대신.
  async function renderFamilyGraph(filterGroup) {
    if (state.network) { try { state.network.destroy(); } catch (_) {} state.network = null; }
    if (!state.chaebol) return;

    const allPersons = state.chaebol.persons || [];
    const persons = filterGroup
      ? allPersons.filter((p) => p.group === filterGroup)
      : allPersons;
    if (!persons.length) {
      $("relCanvas").innerHTML = `<div class="rel-empty">데이터 없음</div>`;
      renderLegend();
      return;
    }
    const personSet = new Set(persons.map((p) => p.id));
    const relations = (state.chaebol.family || []).filter(
      (r) => personSet.has(r.from) && personSet.has(r.to)
    );

    setStatus("가계도 렌더링 중…");
    let visLib;
    try { visLib = await waitForVis(5000); } catch (e) {
      setStatus("⚠️ 그래프 라이브러리 로드 실패");
      return;
    }
    setStatus("");

    // 그룹별 컬러 팔레트
    const palette = ["#10b981", "#f59e0b", "#3b82f6", "#ec4899", "#8b5cf6", "#ef4444", "#06b6d4", "#84cc16", "#f97316", "#6366f1"];
    const groupColors = {};
    [...new Set(persons.map((p) => p.group).filter(Boolean))].forEach((g, i) => {
      groupColors[g] = palette[i % palette.length];
    });

    const visNodes = persons.map((p) => {
      const color = groupColors[p.group] || "#94a3b8";
      const labelLines = [
        p.name + (p.gender === "F" ? " ♀" : p.gender === "M" ? " ♂" : ""),
        p.role || "",
        p.birth ? `${p.birth}${p.death ? "~" + p.death : "~"}` : "",
      ].filter(Boolean);
      return {
        id: p.id,
        label: labelLines.join("\n"),
        shape: "box",
        color: {
          background: p.death ? "#f1f5f9" : "#fff",
          border: color,
          highlight: { background: "#fef3c7", border: color },
        },
        borderWidth: 2,
        font: { size: 12, color: "#1f2328", face: "Pretendard, system-ui, sans-serif" },
        margin: 6,
        title: p.notes || "",
      };
    });
    const visEdges = [];
    relations.forEach((r, i) => {
      if (r.type === "parent") {
        visEdges.push({
          id: "p" + i,
          from: r.from, to: r.to,
          arrows: "to",
          color: { color: "#64748b" },
          width: 1.2,
        });
      } else if (r.type === "spouse") {
        visEdges.push({
          id: "s" + i,
          from: r.from, to: r.to,
          color: { color: r.divorced ? "#ef4444" : "#ec4899" },
          dashes: r.divorced,
          width: 1.5,
          arrows: "",
        });
      }
    });

    const container = $("relCanvas");
    container.innerHTML = "";
    const data = { nodes: new visLib.DataSet(visNodes), edges: new visLib.DataSet(visEdges) };
    const options = {
      layout: {
        hierarchical: {
          enabled: true,
          direction: "UD",
          sortMethod: "directed",
          nodeSpacing: 140,
          levelSeparation: 130,
        },
      },
      physics: { enabled: false },
      interaction: { hover: true, tooltipDelay: 200, navigationButtons: true, keyboard: false },
      edges: { smooth: { type: "cubicBezier" } },
    };
    state.network = new visLib.Network(container, data, options);
    renderLegend();
  }

  // ─── 범례 ───────────────────────────────────────────
  function renderLegend() {
    const el = $("relLegend");
    if (!el) return;
    if (state.mode === "ownership") {
      el.innerHTML = `
        <span><span class="leg-box" style="background:#fff7ed;border:2px solid #f59e0b"></span>대표 회사</span>
        <span><span class="leg-box" style="background:#f8fafc;border:1px solid #3b82f6"></span>상장사</span>
        <span><span class="leg-box" style="background:#f1f5f9;border:1px solid #94a3b8"></span>비상장</span>
        <span><span class="leg-arrow">→</span> 출자관계 (지분%)</span>
        <span class="leg-hint">노드 더블클릭 → 종목 차트로 이동</span>
      `;
    } else {
      el.innerHTML = `
        <span><span class="leg-line" style="background:#64748b"></span>↓ 부모-자식</span>
        <span><span class="leg-line" style="background:#ec4899"></span> 부부</span>
        <span><span class="leg-line leg-line--dashed" style="border-color:#ef4444"></span> 이혼</span>
        <span class="leg-hint">색깔 = 그룹</span>
      `;
    }
  }

  // ─── 모드/뷰 전환 ────────────────────────────────────
  function switchMode(mode) {
    state.mode = mode;
    document.querySelectorAll(".rel-mode-btn").forEach((b) => {
      b.classList.toggle("is-active", b.dataset.mode === mode);
    });
    $("relControlsOwnership").hidden = mode !== "ownership";
    $("relControlsFamily").hidden = mode !== "family";
    if (mode === "ownership") {
      showCanvas(state.view);
      renderCurrent();
    } else {
      showCanvas("graph");  // 가계도는 항상 graph
      state.view = "graph";
      renderFamilyGraph($("relFamilyGroup").value || null);
    }
  }

  function switchView(view) {
    state.view = view;
    document.querySelectorAll(".rel-view-btn").forEach((b) => {
      b.classList.toggle("is-active", b.dataset.view === view);
    });
    showCanvas(view);
    renderCurrent();
  }

  function renderCurrent() {
    if (state.mode !== "ownership") return;
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

    // 이벤트 바인딩
    document.querySelectorAll(".rel-mode-btn").forEach((b) => {
      b.addEventListener("click", () => switchMode(b.dataset.mode));
    });
    document.querySelectorAll(".rel-view-btn").forEach((b) => {
      b.addEventListener("click", () => switchView(b.dataset.view));
    });
    $("relGroupSelect").addEventListener("change", (e) => {
      state.selectedGroup = e.target.value;
      renderCurrent();
    });
    $("relFamilyGroup").addEventListener("change", (e) => {
      state.selectedFamilyGroup = e.target.value || null;
      if (state.mode === "family") renderFamilyGraph(state.selectedFamilyGroup);
    });
    $("relListedOnly").addEventListener("change", (e) => {
      state.listedOnly = !!e.target.checked;
      renderCurrent();
    });

    // 첫 렌더
    switchMode("ownership");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
