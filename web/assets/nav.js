// 햄버거 네비게이션 드로어 + 테마 토글 — 모든 페이지 공통.
(function () {
  // ── 테마 토글 (그레이 → 다크 → 라이트 → 새콤달콤 → 그레이…) ──
  // 그레이가 기본값. 사용자 선택은 localStorage('theme')에 저장.
  // 로그인 상태라면 Supabase `public.members.theme` 에도 동기화(loggingIn side-effect).
  // 버튼은 "다음 전환될 테마"를 암시하는 아이콘을 보여준다.
  //   gray  → 클릭하면 dark  (☾)
  //   dark  → 클릭하면 light (☀)
  //   light → 클릭하면 sweet (🍬)
  //   sweet → 클릭하면 gray  (☁)
  const THEME_CYCLE = ['gray', 'dark', 'light', 'sweet'];
  // 표시용 라벨 (내 정보 > 테마 선택 UI 등에서 재사용)
  const THEME_LABELS = { dark: '다크', light: '크림', sweet: '새콤달콤', gray: '그레이' };
  const THEME_ICONS = { dark: '☾', light: '☀', sweet: '🍬', gray: '☁' };
  function nextTheme(cur) {
    const i = THEME_CYCLE.indexOf(cur);
    return THEME_CYCLE[(i < 0 ? 0 : i + 1) % THEME_CYCLE.length];
  }
  function themeIcon(cur) {
    // 다음 테마를 암시하는 아이콘
    return THEME_ICONS[nextTheme(cur)] || '☁';
  }
  function themeLabel(cur) {
    const nxt = nextTheme(cur);
    return (THEME_LABELS[nxt] || '그레이') + ' 모드로 전환';
  }
  function applyTheme(theme, opts) {
    if (!THEME_CYCLE.includes(theme)) theme = 'gray';
    document.documentElement.setAttribute('data-theme', theme);
    const btn = document.getElementById('themeToggle');
    if (btn) {
      btn.textContent = themeIcon(theme);
      btn.setAttribute('aria-label', themeLabel(theme));
      btn.setAttribute('title', themeLabel(theme));
    }
    try { localStorage.setItem('theme', theme); } catch (_) {}
    // 사용자 액션으로 인한 변경이면 Supabase 에도 동기화 시도.
    // 원격에서 가져와 적용할 때(opts.remote=true)는 저장 루프 방지.
    if (!opts || !opts.remote) {
      syncThemeToSupabase(theme);
    }
  }
  function toggleTheme() {
    const cur = document.documentElement.getAttribute('data-theme') || 'gray';
    applyTheme(nextTheme(cur));
  }
  window.toggleTheme = toggleTheme;
  window.applyTheme = applyTheme;        // 다른 스크립트(auth.js)가 원격 로드 후 호출
  window.THEME_CYCLE = THEME_CYCLE;
  window.THEME_LABELS = THEME_LABELS;
  window.THEME_ICONS = THEME_ICONS;

  // Supabase 동기화: 로그인 상태이면 members.theme 을 upsert.
  // supabase-js 가 아직 로드 전일 수 있으므로 sb 존재 여부만 확인하고 조용히 실패.
  async function syncThemeToSupabase(theme) {
    try {
      const sb = window.sb;
      if (!sb || !sb.auth) return;
      const { data: { session } } = await sb.auth.getSession();
      if (!session || !session.user) return;
      await sb
        .from('members')
        .update({ theme: theme, updated_at: new Date().toISOString() })
        .eq('id', session.user.id);
    } catch (err) {
      // 테이블에 아직 theme 컬럼이 없거나 네트워크 오류 등: localStorage 로 폴백.
      console.debug('[nav] theme sync skipped:', err && err.message);
    }
  }
  window.syncThemeToSupabase = syncThemeToSupabase;

  // 초기 적용 (DOMContentLoaded 전에 실행해 깜빡임 방지)
  // 기존 'gold' 선택은 폐기되었으므로 'gray' 로 자동 이전.
  try {
    let saved = localStorage.getItem('theme');
    if (saved === 'gold') {
      saved = 'gray';
      try { localStorage.setItem('theme', 'gray'); } catch (_) {}
    }
    if (THEME_CYCLE.includes(saved)) {
      document.documentElement.setAttribute('data-theme', saved);
    } else {
      document.documentElement.setAttribute('data-theme', 'gray');
    }
  } catch (_) {
    document.documentElement.setAttribute('data-theme', 'gray');
  }

  // ── 네비 드로어 ──
  function toggleNav() {
    const d = document.getElementById('navDrawer');
    const b = document.getElementById('navBackdrop');
    if (!d || !b) return;
    const open = d.classList.toggle('open');
    b.classList.toggle('show', open);
    document.body.style.overflow = open ? 'hidden' : '';
  }
  window.toggleNav = toggleNav;

  // Escape 키로 닫기
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    const d = document.getElementById('navDrawer');
    if (d && d.classList.contains('open')) toggleNav();
  });

  // 현재 페이지 활성 표시 + 토글 버튼 아이콘 동기화
  document.addEventListener('DOMContentLoaded', function () {
    // 테마 버튼 아이콘 갱신 (이제 버튼이 DOM에 존재)
    applyTheme(document.documentElement.getAttribute('data-theme') || 'gray');

    const path = (location.pathname || '/').replace(/\/+$/, '') || '/';
    document.querySelectorAll('.nav-drawer a').forEach(function (a) {
      const href = (a.getAttribute('href') || '').replace(/\/+$/, '') || '/';
      if (href === path) a.classList.add('active');
    });
  });
})();
