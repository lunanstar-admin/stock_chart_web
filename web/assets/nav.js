// 햄버거 네비게이션 드로어 — 모든 페이지 공통.
(function () {
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

  // 현재 페이지 활성 표시
  document.addEventListener('DOMContentLoaded', function () {
    const path = (location.pathname || '/').replace(/\/+$/, '') || '/';
    document.querySelectorAll('.nav-drawer a').forEach(function (a) {
      const href = (a.getAttribute('href') || '').replace(/\/+$/, '') || '/';
      if (href === path) a.classList.add('active');
    });
  });
})();
