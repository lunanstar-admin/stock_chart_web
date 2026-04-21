// auth-prerender.js — 동기적으로 #authSlot 을 채워 "로그아웃 flash" 를 막는다.
//
// auth.js 는 `defer` 로드라 HTML 파싱이 끝난 뒤에야 실행되는데,
// 그 사이에 브라우저는 빈 #authSlot 을 한 번 paint 한다. 로그인 상태에서
// 다른 페이지로 이동하면 "유저 칩 → 없음 → 유저 칩" 으로 순간 깜빡인다.
//
// 이 파일은 #authSlot 태그 바로 다음에 **blocking** script 로 배치해
// 파싱 도중에 실행된다. localStorage 의 Supabase 세션 캐시를 peek 해서
// 로그인 상태면 유저 칩을, 아니면 그대로 (auth.js 가 이후에 카카오 버튼
// 을 채운다) 두고 종료한다.
//
// 주의: supabase-js 는 아직 로드되지 않았으므로 여기서는 순수 DOM + localStorage 만 사용.
(function () {
  try {
    if (typeof document === 'undefined' || typeof localStorage === 'undefined') return;
    var slot = document.getElementById('authSlot');
    if (!slot) return;
    // 이미 뭔가 채워져 있으면(중복 실행) 그대로 둔다.
    if (slot.children && slot.children.length > 0) return;

    // localStorage 에서 `sb-<ref>-auth-token` 키 찾기.
    var session = null;
    for (var i = 0; i < localStorage.length; i++) {
      var key = localStorage.key(i);
      if (!key || key.indexOf('sb-') !== 0) continue;
      if (key.lastIndexOf('-auth-token') !== key.length - '-auth-token'.length) continue;
      var raw = localStorage.getItem(key);
      if (!raw) continue;
      var parsed = null;
      try { parsed = JSON.parse(raw); } catch (_) { continue; }
      if (!parsed) continue;
      var s = parsed.currentSession || parsed;
      if (s && s.user) { session = s; break; }
    }
    if (!session || !session.user) return;

    // expires_at 이 이미 만료됐으면 스킵 (auth.js 가 로그아웃 UI 를 그리게 둔다).
    var now = Math.floor(Date.now() / 1000);
    if (session.expires_at && Number(session.expires_at) < now) return;

    var meta = session.user.user_metadata || {};
    var nick = meta.nickname || meta.name || meta.full_name || '회원';
    var avatar = meta.avatar_url || meta.picture || '';

    // 로그인 상태 클래스 선제 부여 — hero 의 signed-in/out 엘리먼트 토글에 사용.
    // auth.js 보다 먼저 실행되므로 FOUC(플래시) 를 막는다.
    try { document.documentElement.classList.add('is-signed-in'); } catch (_) {}
    // 닉네임 주입점이 있으면 즉시 채운다.
    try {
      var nickNodes = document.querySelectorAll('[data-signed-in-nick]');
      for (var n = 0; n < nickNodes.length; n++) nickNodes[n].textContent = nick;
    } catch (_) {}

    function esc(s) {
      return String(s == null ? '' : s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    // auth.js 의 renderAuthChipForUser 와 같은 마크업을 생성한다.
    // 이벤트 바인딩은 일부러 하지 않음 — auth.js 가 로드된 뒤 같은 slot 을
    // 다시 그리면서 이벤트 바인딩까지 처리한다. 그 사이에 사용자가
    // 트리거를 누르면 그냥 무반응 (실질 수백 ms 내 재렌더되므로 실사용 영향 없음).
    slot.innerHTML =
      '<div class="auth-chip-wrap" id="authChipWrap">' +
        '<button type="button" class="user-chip user-chip--btn" id="authTrigger"' +
               ' aria-haspopup="menu" aria-expanded="false" title="' + esc(nick) + ' — 메뉴 열기">' +
          (avatar
            ? '<img class="user-avatar" src="' + esc(avatar) + '" alt="" referrerpolicy="no-referrer">'
            : '<span class="user-avatar user-avatar--fallback" aria-hidden="true">' + esc(nick.slice(0, 1)) + '</span>') +
          '<span class="user-nick">' + esc(nick) + '</span>' +
          '<span class="user-chip-caret" aria-hidden="true">▾</span>' +
        '</button>' +
      '</div>';
  } catch (_) {
    // 어떤 이유로든 실패하면 조용히 무시 — auth.js 의 기존 fallback 이 처리한다.
  }
})();
