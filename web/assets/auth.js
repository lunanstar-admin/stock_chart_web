// Supabase Auth (Kakao OAuth) — 헤더 우상단의 #authSlot 에 로그인 UI 렌더링.
// 전역 `sb` 로 supabase 클라이언트를 노출해 다른 스크립트에서 재사용.
(function () {
  const SB_URL = 'https://axbbjjpxspvvxbxvuzsz.supabase.co';
  const SB_KEY = 'sb_publishable_fO8T_8oyf5DTQfe_sfazNQ__79zXVDx';

  // supabase-js 가 로드되어 있어야 함. 없으면 헤더는 그대로 두고 조용히 종료.
  if (typeof window === 'undefined' || !window.supabase) {
    console.warn('[auth] supabase-js not loaded; Kakao login disabled.');
    return;
  }

  const sb = window.supabase.createClient(SB_URL, SB_KEY, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      flowType: 'pkce'
    }
  });
  window.sb = sb;

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  async function signInKakao() {
    try {
      console.info('[auth] signInKakao: start', {
        origin: window.location.origin,
        pathname: window.location.pathname,
        redirectTo: window.location.origin + window.location.pathname
      });
      // Supabase gotrue 의 Kakao provider 는 account_email / profile_image /
      // profile_nickname 을 기본 scope 로 하드코딩해 추가로 넘기면 중복 에러가 난다.
      // 따라서 scopes 옵션은 비움 — Kakao 동의항목 설정은 Developers 콘솔에서 관리.
      const { data, error } = await sb.auth.signInWithOAuth({
        provider: 'kakao',
        options: {
          redirectTo: window.location.origin + window.location.pathname
        }
      });
      if (error) throw error;
      // Supabase-js 는 보통 자동으로 window.location.href 를 바꾸지만,
      // 일부 환경(팝업/확장기능/프레임 등)에서는 URL 만 돌려주고 끝날 수 있다.
      // data.url 이 있는데 리다이렉트가 안 일어나면 직접 이동시킨다.
      console.info('[auth] signInKakao: supabase returned', data);
      if (data && data.url) {
        // 이미 브라우저가 이동 중이 아니면 수동 이동
        setTimeout(function () {
          if (document.visibilityState === 'visible') {
            window.location.assign(data.url);
          }
        }, 200);
      } else {
        alert('카카오 로그인 URL 을 받지 못했습니다. (Supabase 응답 비어있음)\n콘솔 로그를 확인해 주세요.');
      }
    } catch (err) {
      console.error('[auth] signInKakao failed:', err);
      var msg = (err && (err.message || err.error_description || err.error)) || String(err);
      alert('카카오 로그인에 실패했습니다.\n\n' + msg +
        '\n\n(원인 예시)\n• Supabase Dashboard → Auth → Providers → Kakao 활성화 및 Client ID/Secret 저장' +
        '\n• Kakao Developers → 카카오 로그인 활성화 ON' +
        '\n• Kakao Developers → Web 플랫폼 도메인에 현재 사이트 주소 등록' +
        '\n• Kakao Developers → Redirect URI 에 https://ipvdnebujnxexibdgfgi.supabase.co/auth/v1/callback 등록');
    }
  }

  async function signOut() {
    try {
      await sb.auth.signOut();
    } catch (err) {
      console.error('[auth] signOut failed:', err);
    } finally {
      // 세션 반영을 확실히 하려면 새로고침.
      location.reload();
    }
  }

  // 아바타 드롭다운 메뉴 열림 상태
  let _menuOpen = false;
  function closeAuthMenu() {
    const menu = document.getElementById('authMenu');
    const trigger = document.getElementById('authTrigger');
    if (menu) menu.hidden = true;
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
    _menuOpen = false;
  }
  function openAuthMenu() {
    const menu = document.getElementById('authMenu');
    const trigger = document.getElementById('authTrigger');
    if (menu) menu.hidden = false;
    if (trigger) trigger.setAttribute('aria-expanded', 'true');
    _menuOpen = true;
  }
  function toggleAuthMenu() { _menuOpen ? closeAuthMenu() : openAuthMenu(); }

  // 문서 어디를 클릭하든 드롭다운 바깥이면 닫기
  document.addEventListener('click', function (ev) {
    if (!_menuOpen) return;
    const wrap = document.getElementById('authChipWrap');
    if (wrap && !wrap.contains(ev.target)) closeAuthMenu();
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && _menuOpen) closeAuthMenu();
  });

  async function renderAuthUI() {
    const slot = document.getElementById('authSlot');
    if (!slot) return;
    const { data: { session } } = await sb.auth.getSession();
    if (session && session.user) {
      const u = session.user;
      const meta = u.user_metadata || {};
      const nick = meta.nickname || meta.name || meta.full_name || '회원';
      const avatar = meta.avatar_url || meta.picture || '';
      // 아바타/닉네임 칩 자체가 버튼 → 탭하면 드롭다운이 열리고 '내 정보'/'로그아웃' 제공
      slot.innerHTML =
        '<div class="auth-chip-wrap" id="authChipWrap">' +
          '<button type="button" class="user-chip user-chip--btn" id="authTrigger"' +
                 ' aria-haspopup="menu" aria-expanded="false" title="' + escapeHtml(nick) + ' — 메뉴 열기">' +
            (avatar
              ? '<img class="user-avatar" src="' + escapeHtml(avatar) + '" alt="" referrerpolicy="no-referrer">'
              : '<span class="user-avatar user-avatar--fallback" aria-hidden="true">' + escapeHtml(nick.slice(0, 1)) + '</span>') +
            '<span class="user-nick">' + escapeHtml(nick) + '</span>' +
            '<span class="user-chip-caret" aria-hidden="true">▾</span>' +
          '</button>' +
          '<div class="auth-menu" id="authMenu" role="menu" hidden>' +
            '<div class="auth-menu-head">' +
              '<div class="auth-menu-nick">' + escapeHtml(nick) + '</div>' +
            '</div>' +
            '<button type="button" class="auth-menu-item" role="menuitem" id="authMyInfo">내 정보</button>' +
            '<button type="button" class="auth-menu-item" role="menuitem" id="authSignOut">로그아웃</button>' +
          '</div>' +
        '</div>';
      const trigger = document.getElementById('authTrigger');
      if (trigger) trigger.addEventListener('click', function (ev) {
        ev.stopPropagation();
        toggleAuthMenu();
      });
      const infoBtn = document.getElementById('authMyInfo');
      if (infoBtn) infoBtn.addEventListener('click', function () {
        closeAuthMenu();
        openMyInfo(session.user);
      });
      const btn = document.getElementById('authSignOut');
      if (btn) btn.addEventListener('click', function () {
        closeAuthMenu();
        signOut();
      });
      // 로그인 상태 확정 직후, 저장된 테마가 있으면 당겨와 적용.
      loadThemeFromSupabase(session.user.id);
    } else {
      closeAuthMenu();
      slot.innerHTML =
        '<button type="button" class="kakao-btn" id="authKakaoSignIn" aria-label="카카오로 로그인">' +
          '<span class="kakao-icon" aria-hidden="true"></span>' +
          '<span class="kakao-btn-label">카카오 로그인</span>' +
        '</button>';
      const btn = document.getElementById('authKakaoSignIn');
      if (btn) btn.addEventListener('click', signInKakao);
    }
  }

  // 로그인 상태라면 members.theme 을 읽어와 UI 에 반영.
  // 없거나 실패하면 localStorage 에 저장된 테마를 유지.
  async function loadThemeFromSupabase(userId) {
    try {
      if (!userId || !window.applyTheme) return;
      const { data, error } = await sb
        .from('members')
        .select('theme')
        .eq('id', userId)
        .maybeSingle();
      if (error) throw error;
      const t = data && data.theme;
      if (t && (!window.THEME_CYCLE || window.THEME_CYCLE.indexOf(t) >= 0)) {
        // remote: true → applyTheme 이 다시 Supabase 로 쓰는 것 방지
        window.applyTheme(t, { remote: true });
      } else if (!t) {
        // 원격 기록이 없으면 현재 로컬 테마를 한 번 저장해 준다 (최초 동기화).
        const cur = document.documentElement.getAttribute('data-theme') || 'dark';
        if (window.syncThemeToSupabase) window.syncThemeToSupabase(cur);
      }
    } catch (err) {
      // members 테이블에 theme 컬럼이 아직 없을 수 있음 — 조용히 무시.
      console.debug('[auth] loadThemeFromSupabase skipped:', err && err.message);
    }
  }

  // 세션 변화 시 헤더 갱신 + 관심종목 동기화 (있을 때만).
  sb.auth.onAuthStateChange(function () {
    renderAuthUI();
    if (window.Watchlist && typeof window.Watchlist.load === 'function') {
      window.Watchlist.load();
    }
  });

  // 카카오 OAuth 실패 시 Supabase 콜백이 #error=... 쿼리를 붙여 복귀시키므로
  // 그걸 직접 읽어 사용자에게 원인을 알려준다.
  function surfaceOAuthError() {
    try {
      var hash = window.location.hash || '';
      if (!hash || hash.indexOf('error') < 0) return;
      var raw = hash.startsWith('#') ? hash.slice(1) : hash;
      var params = new URLSearchParams(raw);
      var err = params.get('error');
      var code = params.get('error_code');
      var desc = params.get('error_description');
      if (err) {
        console.error('[auth] oauth returned error', { err: err, code: code, desc: desc });
        alert('카카오 로그인 실패\n\n' +
          'error: ' + (err || '-') +
          '\ncode : ' + (code || '-') +
          '\ndesc : ' + (desc ? decodeURIComponent(desc) : '-'));
        // 깔끔하게 해시 제거
        history.replaceState(null, '', window.location.pathname + window.location.search);
      }
    } catch (e) { console.error('[auth] surfaceOAuthError failed', e); }
  }

  function onReady() {
    surfaceOAuthError();
    renderAuthUI();
    // 초기 세션 로드 후 관심종목 pull (chart 페이지에서만 동작)
    if (window.Watchlist && typeof window.Watchlist.load === 'function') {
      window.Watchlist.load();
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onReady);
  } else {
    onReady();
  }

  // ── 내 정보 모달 ─────────────────────────────────
  // 드롭다운의 '내 정보' 클릭 시 열리는 모달.
  // 테마 선택(4종) + 회원 탈퇴 진입점을 제공.
  // 모달 DOM 은 lazy 로 body 끝에 주입 (모든 페이지에서 동작).

  function ensureMyInfoModal() {
    if (document.getElementById('myInfoModal')) return;
    var el = document.createElement('div');
    el.id = 'myInfoModal';
    el.className = 'modal-backdrop myinfo-backdrop';
    el.setAttribute('aria-hidden', 'true');
    el.innerHTML =
      '<div class="modal myinfo-modal" role="dialog" aria-labelledby="myInfoTitle">' +
        '<div class="modal-header">' +
          '<h2 id="myInfoTitle">내 정보</h2>' +
          '<button class="close" type="button" data-role="myinfo-close">닫기 (Esc)</button>' +
        '</div>' +
        '<div class="myinfo-body">' +
          // 프로필 블록
          '<section class="myinfo-section">' +
            '<div class="myinfo-profile">' +
              '<div class="myinfo-avatar" id="myInfoAvatar" aria-hidden="true"></div>' +
              '<div class="myinfo-profile-text">' +
                '<div class="myinfo-nick" id="myInfoNick"></div>' +
                '<div class="myinfo-provider">카카오 간편 가입</div>' +
              '</div>' +
            '</div>' +
          '</section>' +
          // 테마 선택
          '<section class="myinfo-section">' +
            '<h3 class="myinfo-heading">테마</h3>' +
            '<p class="myinfo-desc">선택한 테마는 이 브라우저와 로그인 계정 양쪽에 저장됩니다.</p>' +
            '<div class="theme-swatch-grid" id="myInfoThemeGrid" role="radiogroup" aria-label="테마 선택"></div>' +
          '</section>' +
          // 회원 탈퇴
          '<section class="myinfo-section myinfo-danger-zone">' +
            '<h3 class="myinfo-heading">회원 탈퇴</h3>' +
            '<p class="myinfo-desc">탈퇴 시 관심종목·테마 설정·프로필 정보가 <strong>즉시 영구 삭제</strong>되며 복구되지 않습니다.</p>' +
            '<button type="button" class="btn-danger" id="myInfoDeleteBtn">회원 탈퇴 진행</button>' +
          '</section>' +
          // 탈퇴 확인 패널 (초기엔 숨김)
          '<section class="myinfo-section myinfo-confirm-panel" id="myInfoConfirm" hidden>' +
            '<h3 class="myinfo-heading myinfo-heading--danger">⚠️ 정말 탈퇴하시겠어요?</h3>' +
            '<ul class="myinfo-warn-list">' +
              '<li>회원 식별 정보(카카오 연결)가 Supabase 에서 삭제됩니다.</li>' +
              '<li>관심종목 목록이 전부 삭제됩니다.</li>' +
              '<li>저장된 테마 설정이 삭제됩니다.</li>' +
              '<li>이후 다시 가입해도 이전 데이터는 복구할 수 없습니다.</li>' +
            '</ul>' +
            '<label class="myinfo-confirm-label">' +
              '계속하려면 <strong>탈퇴</strong> 를 입력해 주세요' +
              '<input type="text" id="myInfoConfirmInput" autocomplete="off" spellcheck="false" />' +
            '</label>' +
            '<div class="myinfo-confirm-actions">' +
              '<button type="button" class="btn-secondary" id="myInfoCancelBtn">취소</button>' +
              '<button type="button" class="btn-danger" id="myInfoConfirmBtn" disabled>탈퇴하기</button>' +
            '</div>' +
            '<div class="myinfo-error" id="myInfoError" hidden></div>' +
          '</section>' +
        '</div>' +
      '</div>';
    document.body.appendChild(el);

    // 백드롭/닫기 버튼
    el.addEventListener('click', function (ev) {
      if (ev.target === el) closeMyInfo();
    });
    var closeBtn = el.querySelector('[data-role="myinfo-close"]');
    if (closeBtn) closeBtn.addEventListener('click', closeMyInfo);

    // 탈퇴 버튼들
    document.getElementById('myInfoDeleteBtn').addEventListener('click', function () {
      var panel = document.getElementById('myInfoConfirm');
      panel.hidden = false;
      panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      document.getElementById('myInfoConfirmInput').focus();
    });
    document.getElementById('myInfoCancelBtn').addEventListener('click', function () {
      resetConfirmPanel();
    });
    document.getElementById('myInfoConfirmInput').addEventListener('input', function (ev) {
      var ok = ev.target.value.trim() === '탈퇴';
      document.getElementById('myInfoConfirmBtn').disabled = !ok;
    });
    document.getElementById('myInfoConfirmBtn').addEventListener('click', performAccountDeletion);
  }

  function resetConfirmPanel() {
    var panel = document.getElementById('myInfoConfirm');
    if (!panel) return;
    panel.hidden = true;
    var input = document.getElementById('myInfoConfirmInput');
    if (input) input.value = '';
    var btn = document.getElementById('myInfoConfirmBtn');
    if (btn) btn.disabled = true;
    var err = document.getElementById('myInfoError');
    if (err) { err.hidden = true; err.textContent = ''; }
  }

  function openMyInfo(user) {
    ensureMyInfoModal();
    var meta = (user && user.user_metadata) || {};
    var nick = meta.nickname || meta.name || meta.full_name || '회원';
    var avatar = meta.avatar_url || meta.picture || '';

    var avatarEl = document.getElementById('myInfoAvatar');
    if (avatarEl) {
      if (avatar) {
        avatarEl.innerHTML =
          '<img src="' + escapeHtml(avatar) + '" alt="" referrerpolicy="no-referrer" />';
        avatarEl.classList.remove('myinfo-avatar--fallback');
      } else {
        avatarEl.textContent = String(nick).slice(0, 1);
        avatarEl.classList.add('myinfo-avatar--fallback');
      }
    }
    var nickEl = document.getElementById('myInfoNick');
    if (nickEl) nickEl.textContent = nick;

    renderThemeSwatches();
    resetConfirmPanel();

    var el = document.getElementById('myInfoModal');
    el.classList.add('show');
    el.setAttribute('aria-hidden', 'false');
  }

  function closeMyInfo() {
    var el = document.getElementById('myInfoModal');
    if (!el) return;
    el.classList.remove('show');
    el.setAttribute('aria-hidden', 'true');
    resetConfirmPanel();
  }

  function renderThemeSwatches() {
    var grid = document.getElementById('myInfoThemeGrid');
    if (!grid) return;
    var cycle = window.THEME_CYCLE || ['dark', 'light', 'sweet', 'gray'];
    var labels = window.THEME_LABELS || {};
    var icons = window.THEME_ICONS || {};
    var current = document.documentElement.getAttribute('data-theme') || 'dark';
    grid.innerHTML = cycle.map(function (t) {
      var active = t === current;
      return (
        '<button type="button" class="theme-swatch theme-swatch--' + t +
          (active ? ' is-active' : '') + '"' +
          ' data-theme="' + t + '" role="radio" aria-checked="' + (active ? 'true' : 'false') + '">' +
          '<span class="theme-swatch-icon" aria-hidden="true">' + (icons[t] || '') + '</span>' +
          '<span class="theme-swatch-label">' + (labels[t] || t) + '</span>' +
          (active ? '<span class="theme-swatch-badge" aria-hidden="true">✓</span>' : '') +
        '</button>'
      );
    }).join('');
    grid.querySelectorAll('.theme-swatch').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var t = btn.dataset.theme;
        if (!t || !window.applyTheme) return;
        window.applyTheme(t);        // Supabase 동기화 포함
        renderThemeSwatches();       // 활성 표시 갱신
      });
    });
  }

  async function performAccountDeletion() {
    var btn = document.getElementById('myInfoConfirmBtn');
    var err = document.getElementById('myInfoError');
    if (btn) btn.disabled = true;
    if (btn) btn.textContent = '처리 중...';
    try {
      // Supabase RPC: auth.users 삭제 → members / watchlist cascade 삭제
      var res = await sb.rpc('delete_current_user');
      if (res && res.error) throw res.error;
      // 세션 정리 후 홈으로
      try { await sb.auth.signOut(); } catch (_) {}
      try { localStorage.removeItem('theme'); } catch (_) {}
      alert('탈퇴가 완료되었습니다. 이용해 주셔서 감사합니다.');
      window.location.assign('/');
    } catch (e) {
      console.error('[auth] account deletion failed', e);
      if (err) {
        err.hidden = false;
        err.textContent = '탈퇴 처리에 실패했습니다: ' + (e && (e.message || e.hint) || '알 수 없는 오류') +
          '\n잠시 후 다시 시도하거나 관리자에게 문의해 주세요.';
      }
      if (btn) { btn.disabled = false; btn.textContent = '탈퇴하기'; }
    }
  }

  // Escape 로 내 정보 모달 닫기
  document.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Escape') return;
    var el = document.getElementById('myInfoModal');
    if (el && el.classList.contains('show')) closeMyInfo();
  });

  // 외부에서 직접 호출 가능하도록 최소 노출.
  window.signInKakao = signInKakao;
  window.signOut = signOut;
  window.openMyInfo = openMyInfo;
  window.closeMyInfo = closeMyInfo;
})();
