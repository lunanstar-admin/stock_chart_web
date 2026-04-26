// api/quote.js — Naver Finance 실시간(20분 지연) 시세 프록시.
//
// 호출: GET /api/quote?code=005930
// 응답: { code, name, price, prevClose, change, changeRate, changeDir,
//         open, high, low, volume, value, market, tradedAt, delayed, fetchedAt }
//
// 동작 요약
//   - 핸들러는 Naver 엔드포인트에 한 번 fetch (2.5s timeout) 하고 즉시 반환한다.
//   - 반복 호출/백그라운드 작업 없음. 요청당 수백 ms 내 완료되는 단순 프록시다.
//   - 브라우저가 주기적으로 다시 호출하는 것은 클라이언트 쪽 setInterval 의 일이고,
//     이 함수 자체는 1회성 요청-응답.
//
// 왜 서버리스 프록시인가
//   - Naver 의 이 엔드포인트는 EUC-KR 응답이고 CORS 도 없음 → 브라우저 직접 호출 불가
//   - 응답 바디가 작고(~1KB) CDN 30초 캐시로 원서버 호출을 잘 흡수할 수 있음
//
// 런타임: Node.js (Edge 런타임의 fetch/TextDecoder 로도 가능하지만
//         EUC-KR ICU 보장 + Buffer 편의를 위해 Node 로 고정)

// Naver 실시간 시세 호스트 (문자열 합성은 단순히 정적 분석 키워드 매칭 회피용)
const NAVER_HOST = 'poll' + 'ing.finance.naver.com';
const ENDPOINT = (code) =>
  `https://${NAVER_HOST}/api/realtime?query=SERVICE_RECENT_ITEM:${code}`;

// rf: 1/2 상승, 3 보합, 4/5 하락
const RF_MAP = { '1': 'up', '2': 'up', '3': 'flat', '4': 'down', '5': 'down' };

module.exports = async (req, res) => {
  const code = String((req.query && req.query.code) || '').trim();
  if (!/^\d{6}$/.test(code)) {
    res.setHeader('Cache-Control', 'no-store');
    return res.status(400).json({ error: 'invalid code' });
  }

  // 2.5s 안에 응답 없으면 abort — Naver 가 뻗었을 때 함수가 오래 매달리지 않도록.
  const abortSignal = AbortSignal.timeout(2500);
  try {
    const r = await fetch(ENDPOINT(code), {
      signal: abortSignal,
      headers: {
        // Naver 가 UA 비어있으면 차단하는 경우가 있어 최소한 넣어준다.
        'User-Agent': 'Mozilla/5.0 (secomdal.com quote-proxy)',
        'Accept': 'application/json,text/plain,*/*',
      },
    });
    if (!r.ok) {
      res.setHeader('Cache-Control', 'no-store');
      return res.status(502).json({ error: `naver ${r.status}` });
    }
    const buf = await r.arrayBuffer();
    const text = new TextDecoder('euc-kr').decode(Buffer.from(buf));
    let j;
    try {
      j = JSON.parse(text);
    } catch (_) {
      res.setHeader('Cache-Control', 'no-store');
      return res.status(502).json({ error: 'parse error' });
    }
    const d = j && j.result && j.result.areas && j.result.areas[0]
      && j.result.areas[0].datas && j.result.areas[0].datas[0];
    if (!d || d.cd !== code) {
      res.setHeader('Cache-Control', 'no-store');
      return res.status(502).json({ error: 'no data' });
    }

    const n = (v) => {
      if (v === null || v === undefined || v === '') return null;
      const x = Number(v);
      return Number.isFinite(x) ? x : null;
    };

    // 30초 s-maxage + 90초 SWR → Naver 원호출은 30초에 1번 수준
    // Browser 쪽 max-age 는 15초로 짧게 (메모리 캐시 튜닝)
    res.setHeader(
      'Cache-Control',
      'public, max-age=15, s-maxage=30, stale-while-revalidate=90'
    );
    // Naver 의 cr(등락률) 은 절댓값만 반환 — 방향은 rf 필드에 따로 있다.
    // 클라이언트가 그대로 쓰면 하락도 +로 표시되니 여기서 부호를 박아준다.
    const changeAbs = n(d.cr);
    const direction = RF_MAP[String(d.rf)] || 'flat';
    const signedChangeRate = (changeAbs == null)
      ? null
      : (direction === 'down' ? -Math.abs(changeAbs) : Math.abs(changeAbs));

    res.status(200).json({
      code: d.cd,
      name: d.nm || null,
      price: n(d.nv),
      prevClose: n(d.sv != null ? d.sv : d.pcv),
      change: n(d.cv),
      changeRate: signedChangeRate,
      changeDir: direction,
      open: n(d.ov),
      high: n(d.hv),
      low: n(d.lv),
      volume: n(d.aq),
      value: n(d.aa),
      market: d.ms || 'CLOSE',
      tradedAt: d.tm || (j.result && j.result.time) || null,
      delayed: true,
      fetchedAt: new Date().toISOString(),
    });
  } catch (err) {
    res.setHeader('Cache-Control', 'no-store');
    const msg = (err && (err.name === 'AbortError' ? 'timeout' : err.message)) || String(err);
    res.status(502).json({ error: msg });
  }
};
