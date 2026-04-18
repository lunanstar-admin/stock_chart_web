// Contact Us 페이지 — Supabase feedback 테이블에 의견 INSERT.
// Supabase 공개 publishable key (anon) — RLS가 걸려 있어 INSERT만 허용.
(function () {
  const SUPABASE_URL = 'https://ipvdnebujnxexibdgfgi.supabase.co';
  const SUPABASE_KEY = 'sb_publishable_bfy0VK7S3lgLV3Q34fp4UA_0UJRQ_M8';
  const ENDPOINT = SUPABASE_URL + '/rest/v1/feedback';

  function $(id) { return document.getElementById(id); }

  document.addEventListener('DOMContentLoaded', function () {
    const ta = $('fbMessage');
    const count = $('fbCount');
    if (ta && count) {
      const update = function () { count.textContent = String(ta.value.length); };
      ta.addEventListener('input', update);
      update();
    }
  });

  async function submitFeedback(ev) {
    ev.preventDefault();
    const email = ($('fbEmail').value || '').trim();
    const message = ($('fbMessage').value || '').trim();
    const status = $('fbStatus');
    const submit = $('fbSubmit');

    status.className = 'status';
    status.textContent = '';

    if (message.length < 5) {
      status.className = 'status err';
      status.textContent = '메시지는 최소 5자 이상 입력해 주세요.';
      return false;
    }
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      status.className = 'status err';
      status.textContent = '이메일 형식이 올바르지 않습니다.';
      return false;
    }

    submit.disabled = true;
    status.className = 'status';
    status.textContent = '보내는 중...';

    const payload = {
      message: message,
      email: email || null,
      user_agent: (navigator.userAgent || '').slice(0, 500),
      page: location.pathname
    };

    try {
      const res = await fetch(ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'apikey': SUPABASE_KEY,
          'Authorization': 'Bearer ' + SUPABASE_KEY,
          'Prefer': 'return=minimal'
        },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const text = await res.text().catch(function () { return ''; });
        throw new Error('HTTP ' + res.status + ' — ' + text.slice(0, 200));
      }
      status.className = 'status ok';
      status.textContent = '✓ 의견이 전달되었습니다. 감사합니다!';
      $('feedbackForm').reset();
      const count = $('fbCount'); if (count) count.textContent = '0';
    } catch (err) {
      console.error(err);
      status.className = 'status err';
      status.textContent = '전송 실패. 잠시 후 다시 시도하거나 이메일로 문의해 주세요.';
    } finally {
      submit.disabled = false;
    }
    return false;
  }

  window.submitFeedback = submitFeedback;
})();
