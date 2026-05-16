"""거시 지표 대시보드 데이터 수집.

출력: web/data/macro.json
{
  "updated":   ISO8601 KST,
  "data_date": "YYYY-MM-DD",
  "fx": [
    { "code": "USD/KRW", "name": "원/달러", "value": "1,489.84",
      "change": "+5.20", "changeRate": "+0.35", "changeDir": "RISING",
      "spark": [{"date":"...","close":1480.1}, ...] }
  ],
  "commodities": [...],            # WTI, 금
  "rates": [...],                  # 한국 기준금리, 미국 Fed, KOSPI200 옵션 등
  "cpi":   [...],                  # 한국 CPI, 미국 CPI (월간 발표값)
  "short_total": {                 # 시장 전체 공매도 잔고 추이
    "latest": "...", "trend30": [{"date":"...","value":...}, ...]
  },
  "events": [                      # 향후 30일 이벤트 (수동 관리 events.json 머지)
    { "date":"2026-05-22","title":"한국은행 금통위","tag":"rate" }
  ]
}

데이터 소스:
- 환율/원자재: FinanceDataReader (USD/KRW, EUR/KRW, JPY/KRW, CL=F WTI, GC=F 금)
- 금리/CPI: web/data/macro_static.json (수동 관리, 사용자가 월 1회 업데이트)
- 이벤트: web/data/events.json (수동 큐레이션)
- 공매도 합계: web/data/shorting.json 이 있으면 합산, 없으면 빈값
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")

# (FDR 코드, 표시명, 단위 소수자리)
FX_DEFS = [
    ("USD/KRW", "원/달러", 2),
    ("EUR/KRW", "원/유로", 2),
    ("JPY/KRW", "원/엔(100엔 환산)", 2),
]

COMMODITY_DEFS = [
    ("CL=F", "WTI 원유 (USD/배럴)", 2),
    ("GC=F", "금 (USD/oz)", 1),
]


def _fmt(v: float, dec: int) -> str:
    if v is None:
        return "-"
    return f"{v:,.{dec}f}"


def _build_series(code: str, name: str, dec: int, days: int = 35) -> dict | None:
    import FinanceDataReader as fdr

    end = datetime.now(KST)
    start = end - timedelta(days=days + 10)  # 영업일 손실 대비
    try:
        df = fdr.DataReader(code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    except Exception as e:
        logger.warning("FDR %s 실패: %s", code, e)
        return None
    if df.empty:
        return None

    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    if "date" not in df.columns and "index" in df.columns:
        df = df.rename(columns={"index": "date"})

    # JPY/KRW 는 100엔 환산
    multiplier = 100.0 if code == "JPY/KRW" else 1.0
    df["close"] = df["close"] * multiplier

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last
    cur = float(last["close"])
    prev_close = float(prev["close"])
    chg = cur - prev_close
    rate = (chg / prev_close * 100.0) if prev_close else 0.0
    direction = "RISING" if chg > 0 else ("FALLING" if chg < 0 else "FLAT")

    spark = []
    tail = df.tail(30)
    for _, row in tail.iterrows():
        d = str(row["date"])[:10]
        try:
            v = float(row["close"])
        except Exception:
            continue
        spark.append({"date": d, "close": round(v, max(2, dec))})

    return {
        "code": code,
        "name": name,
        "value": _fmt(cur, dec),
        "change": ("+" if chg > 0 else "") + _fmt(chg, dec),
        "changeRate": f"{rate:+.2f}",
        "changeDir": direction,
        "spark": spark,
    }


def _load_static(path: Path) -> dict:
    """금리/CPI 정적 데이터. 파일 없으면 기본 시드 반환."""
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # 기본 시드 (사용자가 매월 dashboard 설정에서 수정 예정)
    return {
        "rates": [
            {"name": "한국 기준금리", "value": "3.00", "unit": "%",
             "asof": "2026-04-11", "note": "한국은행 금통위"},
            {"name": "미국 Fed 금리", "value": "4.50", "unit": "%",
             "asof": "2026-05-01", "note": "FOMC 상단"},
        ],
        "cpi": [
            {"name": "한국 CPI (YoY)", "value": "2.4", "unit": "%",
             "asof": "2026-04", "note": "통계청 발표"},
            {"name": "미국 CPI (YoY)", "value": "3.1", "unit": "%",
             "asof": "2026-04", "note": "BLS 발표"},
        ],
    }


def _load_events(path: Path) -> list[dict]:
    """이벤트 캘린더. 파일 없으면 기본 시드."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            return data.get("events", [])
        except Exception:
            pass
    # 기본 시드 (다음 30일 주요 이벤트)
    today = datetime.now(KST).date()
    return [
        {"date": str(today + timedelta(days=6)),
         "title": "한국은행 금통위", "tag": "rate", "country": "KR"},
        {"date": str(today + timedelta(days=14)),
         "title": "미국 FOMC", "tag": "rate", "country": "US"},
        {"date": str(today + timedelta(days=15)),
         "title": "한국 5월 CPI 발표", "tag": "cpi", "country": "KR"},
        {"date": str(today + timedelta(days=19)),
         "title": "미국 5월 CPI 발표", "tag": "cpi", "country": "US"},
        {"date": str(today + timedelta(days=21)),
         "title": "KOSPI200 옵션·선물 동시만기", "tag": "expiry", "country": "KR"},
    ]


def _aggregate_short_total(output_dir: Path) -> dict | None:
    """web/data/shorting.json 이 있으면 시장 전체 합산."""
    p = output_dir / "shorting.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    # shorting.json 구조에 따라 처리 — 일단 latest 메시지만
    latest = data.get("updated") or data.get("data_date")
    return {"latest": latest, "trend30": []}


def build_macro(output_dir: Path) -> bool:
    fx = []
    for code, name, dec in FX_DEFS:
        item = _build_series(code, name, dec)
        if item:
            fx.append(item)
            logger.info("fx ok: %s value=%s rate=%s", name, item["value"], item["changeRate"])

    commodities = []
    for code, name, dec in COMMODITY_DEFS:
        item = _build_series(code, name, dec)
        if item:
            commodities.append(item)
            logger.info("commodity ok: %s value=%s", name, item["value"])

    static = _load_static(output_dir / "macro_static.json")
    events = _load_events(output_dir / "events.json")
    short_total = _aggregate_short_total(output_dir)

    # data_date: 환율의 마지막 날짜
    data_date = None
    if fx and fx[0].get("spark"):
        data_date = fx[0]["spark"][-1]["date"]

    payload = {
        "updated": datetime.now(KST).replace(microsecond=0).isoformat(),
        "data_date": data_date,
        "fx": fx,
        "commodities": commodities,
        "rates": static.get("rates", []),
        "cpi": static.get("cpi", []),
        "short_total": short_total,
        "events": sorted(events, key=lambda e: e.get("date", ""))[:20],
    }
    out = output_dir / "macro.json"
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.info("wrote %s (fx=%d, commod=%d, events=%d)",
                out, len(fx), len(commodities), len(events))
    return True


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="web/data")
    args = parser.parse_args()
    build_macro(Path(args.output))
