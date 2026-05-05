"""공매도 잔고 비중 수집 + 분류.

매일 장마감 후 KRX 의 공매도 잔고 비중을 종목별로 수집하여
6단계 분류 + 시장 백분위와 함께 web/data/shorting.json 으로 출력.

분류 임계값(잔고 비중 %):
  매우 좋음 < 0.5
  양호      < 1.5
  보통      < 3.0
  다소 높음 < 5.0
  매우 높음 < 10.0
  경고      ≥ 10.0

백분위(pct): 잔고 비중 오름차순 — 0 = 시장 최저(가장 안전), 100 = 시장 최고(가장 위험).
UI 에서는 100-pct 를 '상위 X%' 로 표시.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
OUT_PATH = ROOT / "web" / "data" / "shorting.json"

# (upper_bound, class_code, korean_label)
THRESHOLDS: list[tuple[float, str, str]] = [
    (0.5, "good_strong", "매우 좋음"),
    (1.5, "good",        "양호"),
    (3.0, "neutral",     "보통"),
    (5.0, "warn",        "다소 높음"),
    (10.0, "high",       "매우 높음"),
    (float("inf"), "alert", "경고"),
]


def classify(ratio: float) -> tuple[str, str]:
    for upper, code, label in THRESHOLDS:
        if ratio < upper:
            return code, label
    return "alert", "경고"


def find_latest_trading_date(start: datetime, max_back: int = 14) -> Optional[str]:
    """잔고 데이터가 있는 가장 최근 거래일을 KOSPI 로 탐색."""
    from pykrx import stock as pykrx_stock
    for delta in range(0, max_back):
        d = (start - timedelta(days=delta)).strftime("%Y%m%d")
        try:
            df = pykrx_stock.get_shorting_balance_by_ticker(d, market="KOSPI")
            if df is not None and len(df) > 0:
                return d
        except Exception as e:
            logger.debug("[short] probe %s: %s", d, type(e).__name__)
            continue
    return None


def _ratio_column(df) -> Optional[str]:
    """pykrx 반환 DF 에서 '비중' 컬럼명 찾기 (버전별 미세 차이)."""
    for c in df.columns:
        cl = str(c)
        if "비중" in cl:
            return cl
    return None


def fetch_all_balance(date: str) -> dict[str, float]:
    """KOSPI + KOSDAQ 전 종목의 공매도 잔고 비중(%) 반환."""
    from pykrx import stock as pykrx_stock
    out: dict[str, float] = {}
    for market in ("KOSPI", "KOSDAQ"):
        try:
            df = pykrx_stock.get_shorting_balance_by_ticker(date, market=market)
        except Exception as e:
            logger.warning("[short] %s fetch fail: %s", market, e)
            continue
        if df is None or df.empty:
            continue
        col = _ratio_column(df)
        if col is None:
            logger.warning("[short] %s 비중 컬럼 못 찾음 (cols=%s)", market, list(df.columns))
            continue
        for ticker, row in df.iterrows():
            try:
                v = float(row[col])
            except Exception:
                continue
            if v < 0 or v > 100:
                continue
            out[str(ticker).zfill(6)] = round(v, 4)
    return out


def compute_percentiles(items: dict[str, float]) -> dict[str, int]:
    """잔고 비중 오름차순 백분위. 0 = 가장 낮음(좋음), 100 = 가장 높음(위험)."""
    if not items:
        return {}
    sorted_codes = sorted(items.keys(), key=lambda c: items[c])
    n = len(sorted_codes)
    return {
        code: round(rank / max(1, n - 1) * 100)
        for rank, code in enumerate(sorted_codes)
    }


def collect() -> Optional[Path]:
    """전체 파이프라인 실행 — 실패 시 None 반환 (배치는 계속 진행)."""
    try:
        latest = find_latest_trading_date(datetime.now(KST))
    except ImportError:
        logger.warning("[short] pykrx 미설치 — 스킵")
        return None
    if not latest:
        logger.warning("[short] 최근 거래일 데이터 없음 (KRX 차단 가능)")
        return None

    items = fetch_all_balance(latest)
    if not items:
        logger.warning("[short] 데이터 0건")
        return None

    pct = compute_percentiles(items)
    out = {
        "updated": datetime.now(KST).isoformat(timespec="seconds"),
        "trade_date": latest,
        "count": len(items),
        # UI 가 임계값을 같이 그리고 싶을 때 사용
        "thresholds": [
            {"upper": t[0] if t[0] != float("inf") else None, "class": t[1], "label": t[2]}
            for t in THRESHOLDS
        ],
        "items": {
            code: {
                "ratio": ratio,
                "class": classify(ratio)[0],
                "label": classify(ratio)[1],
                "pct": pct.get(code, 50),
            }
            for code, ratio in items.items()
        },
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    sz_kb = OUT_PATH.stat().st_size / 1024
    logger.info(
        "[short] %s 생성 — date=%s items=%d (%.1f KB)",
        OUT_PATH.name, latest, len(items), sz_kb
    )
    return OUT_PATH


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    collect()


if __name__ == "__main__":
    main()
