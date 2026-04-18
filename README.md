# 차트연구 (stock_chart_web)

KOSPI / KOSDAQ 전종목을 전일 종가 기준으로 한 페이지에서 훑어볼 수 있는 무료 공개 웹.
외부 API(pykrx / FinanceDataReader / Naver)는 **매일 1회 배치**로만 호출하고,
결과를 JSON으로 저장해 정적 CDN(Vercel)에서 서빙한다.

```
GitHub Actions (16:45 KST)          Vercel (Static CDN)
─────────────────────────┐          ┌──────────────────────
  python -m batch.run_batch ──commit──▶ web/data/*.json ──▶ 브라우저 fetch
```

## 디렉토리

```
stock_chart_web/
├── web/                    # Vercel 배포 루트
│   ├── index.html
│   ├── assets/             # app.js / chart.js / styles.css
│   └── data/               # 배치 산출물 (git commit)
│       ├── meta.json
│       ├── stocks.json
│       └── chart/{code}.json
├── batch/                  # Python 배치 워커
│   ├── run_batch.py        # 진입점
│   ├── collectors.py       # OHLCV + 지표 + 메타
│   ├── supply.py           # 수급(외국인/기관/개인)
│   └── writers.py          # atomic JSON write
├── .github/workflows/
│   └── daily-batch.yml     # 평일 16:45 KST cron
├── requirements.txt
└── vercel.json
```

## 로컬 실행

```bash
# 1) 배치 소규모 드라이런
python -m batch.run_batch --limit 20 --workers 4

# 2) 프론트엔드 확인 (정적 서버 아무거나)
cd web && python -m http.server 8000
# http://localhost:8000
```

`web/data/` 밑에 `stocks.json`, `meta.json`, `chart/{code}.json` 이 생성되는지 확인한다.

## 배포

1. 이 저장소를 GitHub에 push
2. Vercel에서 GitHub repo 연결 (프레임워크 없음, 루트 그대로)
3. Vercel이 `vercel.json` 을 읽어 `web/` 을 정적 서빙 + `/data/*.json` 캐시 헤더 적용
4. GitHub Actions `daily-batch` 가 평일 16:45 KST 실행 → `web/data/` 커밋 → Vercel 자동 재배포

수동 실행은 GitHub → Actions → `daily-batch` → **Run workflow** (limit/workers 지정 가능).

## 데이터 스키마

### `web/data/stocks.json`
```json
{
  "updated": "2026-04-17T16:45:00+09:00",
  "count": 2589,
  "markets": { "KOSPI": 951, "KOSDAQ": 1638 },
  "stocks": [
    {
      "code": "005930", "name": "삼성전자", "market": "KOSPI",
      "price": "78,200", "change": "+400", "changeRate": "+0.51",
      "changeDir": "up", "volume": 12345678, "marketCap": 467000000000000
    }
  ]
}
```

### `web/data/chart/{code}.json`
```json
{
  "code": "005930", "name": "삼성전자",
  "updated": "2026-04-17T16:45:00+09:00",
  "data": [
    { "date": "2026-01-02", "open": 77000, "high": 78500, "low": 76800,
      "close": 78200, "volume": 12345678,
      "ma5": 77900, "ma20": 76500, "ma60": 73200,
      "macd": 120.5, "macd_signal": 95.1, "macd_hist": 25.4,
      "rsi": 58.2, "obv": 1.23e9, "vwap": 77600,
      "mfi": 61.3, "bb_upper": 80100, "bb_mid": 76500, "bb_lower": 72900 }
  ],
  "investor": {
    "data": [
      { "date": "2026-01-02", "foreign": 12300, "inst": -4500, "retail": -7800,
        "securities": 0, "insurance": 0, "pension": 0, "corp": 0 }
    ],
    "cumulative": {
      "foreign": { "total": 123000, "cumulative": [12300, 24600] },
      "inst":    { "total": -45000, "cumulative": [-4500, -9000] },
      "retail":  { "total": -78000, "cumulative": [-7800, -15600] }
    },
    "_source": "pykrx"
  },
  "meta": {
    "sector": "반도체", "per": 14.2, "pbr": 1.3, "eps": 5500,
    "marketValue": 467000000000000, "foreignRate": 52.1,
    "name": "삼성전자", "market": "KOSPI", "price": "78,200", "..."
  }
}
```

### `web/data/meta.json`
```json
{
  "updated": "2026-04-17T16:45:00+09:00",
  "elapsed_sec": 1243.5,
  "counts": { "total": 2589, "success": 2570, "failed": 19 },
  "markets": { "KOSPI": 951, "KOSDAQ": 1638 },
  "failed_samples": [["123456", "empty_ohlcv"], ["234567", "timeout"]]
}
```

## 기술 스택

- **Batch**: Python 3.11 · pykrx · FinanceDataReader · pandas · numpy · requests
- **Frontend**: Vanilla JS + HTML5 Canvas (의존성 없음)
- **Hosting**: Vercel 정적 배포 (Edge CDN)
- **Scheduler**: GitHub Actions cron (평일 16:45 KST)

## 왜 GitHub Actions + 정적 JSON인가

- pykrx / FinanceDataReader 는 Python 패키지라 Vercel Functions(Node/Edge)에서 직접 못 돌림.
- 외부 API는 일일 1회만 호출하면 충분(전일 종가 기준).
- 정적 JSON은 Vercel 무료 tier(1GB)에 충분히 들어가고, Edge CDN 캐시로 응답 수 ms.
- 추후 Supabase + Auth 도입 시 배치 결과를 DB에 밀어넣는 식으로 자연스럽게 확장 가능.

## 향후 확장

- Supabase 마이그레이션 + 회원 인증
- 로그인 사용자용 실시간 API (Vercel Functions + KIS WebSocket 프록시)
- 관심종목 (Supabase `watchlist` 테이블)
- 스캐너 기능 재도입 (별도 배치 워커)

## 라이선스

MIT
