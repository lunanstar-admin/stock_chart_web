// 햄버거 네비게이션 드로어 + 테마 토글 — 모든 페이지 공통.
(function () {
  // ── 테마 토글 (라이트 / 다크) ──
  // 다크가 기본값. 사용자 선택은 localStorage('theme')에 저장.
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const btn = document.getElementById('themeToggle');
    if (btn) {
      // 현재 다크라면 "라이트로 전환" 아이콘(☀)을, 라이트라면 "다크로 전환" 아이콘(☾)을 표시.
      btn.textContent = theme === 'light' ? '☾' : '☀';
      btn.setAttribute('aria-label', theme === 'light' ? '다크 모드로 전환' : '라이트 모드로 전환');
    }
    try { localStorage.setItem('theme', theme); } catch (_) {}
  }
  function toggleTheme() {
    const cur = document.documentElement.getAttribute('data-theme') || 'dark';
    applyTheme(cur === 'light' ? 'dark' : 'light');
  }
  window.toggleTheme = toggleTheme;

  // 초기 적용 (DOMContentLoaded 전에 실행해 깜빡임 방지)
  try {
    const saved = localStorage.getItem('theme');
    if (saved === 'light' || saved === 'dark') {
      document.documentElement.setAttribute('data-theme', saved);
    } else {
      document.documentElement.setAttribute('data-theme', 'dark');
    }
  } catch (_) {
    document.documentElement.setAttribute('data-theme', 'dark');
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
    applyTheme(document.documentElement.getAttribute('data-theme') || 'dark');

    const path = (location.pathname || '/').replace(/\/+$/, '') || '/';
    document.querySelectorAll('.nav-drawer a').forEach(function (a) {
      const href = (a.getAttribute('href') || '').replace(/\/+$/, '') || '/';
      if (href === path) a.classList.add('active');
    });
  });
})();
