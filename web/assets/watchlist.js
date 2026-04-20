// 관심종목 스토어 — 로그인한 사용자의 Supabase `public.watchlist` 테이블을
// 메모리 Set 과 동기화한다. 비로그인 상태에서는 빈 Set 으로 동작.
// app.js 가 `window.Watchlist.has(code)` / `.toggle(code)` / `.onChange(fn)` 을 호출해 UI 에 반영.
(function () {
  if (typeof window === 'undefined') return;

  const codes = new Set();
  let loaded = false;
  let currentUserId = null;
  const listeners = new Set();

  function emit() {
    for (const fn of listeners) {
      try { fn(codes); } catch (e) { console.error('[watchlist] listener error', e); }
    }
  }

  async function getSession() {
    if (!window.sb || !window.sb.auth) return null;
    try {
      const { data } = await window.sb.auth.getSession();
      return data && data.session ? data.session : null;
    } catch (e) {
      console.error('[watchlist] getSession failed', e);
      return null;
    }
  }

  // 로그인/로그아웃 시 호출. 세션이 있으면 서버에서 pull, 없으면 clear.
  async function load() {
    const session = await getSession();
    codes.clear();
    currentUserId = session ? session.user.id : null;
    if (session && window.sb) {
      try {
        const { data, error } = await window.sb
          .from('watchlist')
          .select('code')
          .eq('user_id', session.user.id);
        if (error) throw error;
        (data || []).forEach(r => codes.add(r.code));
      } catch (e) {
        console.error('[watchlist] load failed', e);
      }
    }
    loaded = true;
    emit();
  }

  // 하나의 종목을 on/off 토글. 로그인 필요.
  async function toggle(code) {
    if (!code) return null;
    const session = await getSession();
    if (!session) {
      alert('관심종목은 카카오 로그인 후 저장됩니다.\n우상단의 카카오 버튼을 눌러 로그인해 주세요.');
      return null;
    }
    if (!window.sb) return null;

    // 낙관적 업데이트 — 서버 실패 시 롤백
    const wasOn = codes.has(code);
    if (wasOn) codes.delete(code); else codes.add(code);
    emit();

    try {
      if (wasOn) {
        const { error } = await window.sb
          .from('watchlist')
          .delete()
          .eq('user_id', session.user.id)
          .eq('code', code);
        if (error) throw error;
      } else {
        const { error } = await window.sb
          .from('watchlist')
          .insert({ user_id: session.user.id, code: code });
        if (error) throw error;
      }
      return !wasOn;
    } catch (e) {
      // 롤백
      if (wasOn) codes.add(code); else codes.delete(code);
      emit();
      console.error('[watchlist] toggle failed', e);
      alert('관심종목 저장에 실패했습니다. 잠시 후 다시 시도해 주세요.');
      return wasOn;
    }
  }

  function has(code) { return codes.has(code); }
  function size() { return codes.size; }
  function isLoaded() { return loaded; }
  function isSignedIn() { return currentUserId != null; }
  function onChange(fn) {
    listeners.add(fn);
    return function unsubscribe() { listeners.delete(fn); };
  }

  window.Watchlist = { load, toggle, has, size, onChange, isLoaded, isSignedIn };
})();
