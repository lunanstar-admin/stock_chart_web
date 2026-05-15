"""주요 지수(KOSPI/KOSDAQ/KOSPI200) 일봉 + 주봉 + 월봉 수집.

개별종목 collectors 의 fetch_ohlcv/compute_indicators/resample/chart_records 를
그대로 재사용. 출력 파일: web/data/indices.json

스키마:
{
  "updated":   ISO8601 KST,
  "data_date": "YYYY-MM-DD" — 마지막 확정 캔들 날짜,
  "indices": [
    {
      "code":       "KS11" | "KQ11" | "KS200",
      "name":       "KOSPI" | "KOSDAQ" | "KOSPI200",
      "value":      "2,543.21",
      "change":     "-23.45",
      "changeRate": "-0.91",
      "changeDir":  "RISING" | "FALLING" | "FLAT",
      "data":       [{date, open, high, low, close, volume, ma5, ma20, macd, rsi14, ...}],
      "dataW":      [...] (주봉),
      "dataM":      [...] (월봉)
    }
  ]
}
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from batch.collectors import (
    chart_records,
    compute_indicators,
    fetch_ohlcv,
    resample_ohlcv,
)

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")

# (FDR 코드, 화면 표시명)
INDEX_DEFS = [
    ("KS11", "KOSPI"),
    ("KQ11", "KOSDAQ"),
    ("KS200", "KOSPI200"),
]


def _fmt_number(n: float, dec: int = 2) -> str:
    """1234.56 -> '1,234.56'."""
    return f"{n:,.{dec}f}"


def _build_index(code: str, name: str) -> dict | None:
    # 일봉 ~3700일 → 주/월 리샘플 충분
    df = fetch_ohlcv(code, days=3700)
    if df.empty:
        logger.warning("index %s (%s) empty", code, name)
        return None
    df = compute_indicators(df)

    # 최신값
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last
    cur = float(last["close"])
    prev_close = float(prev["close"])
    chg = cur - prev_close
    rate = (chg / prev_close * 100.0) if prev_close else 0.0
    direction = "RISING" if chg > 0 else ("FALLING" if chg < 0 else "FLAT")

    dfW = resample_ohlcv(df, "W")
    dfM = resample_ohlcv(df, "M")

    return {
        "code": code,
        "name": name,
        "value": _fmt_number(cur),
        "change": _fmt_number(chg),
        "changeRate": f"{rate:+.2f}",
        "changeDir": direction,
        "data": chart_records(df, tail=120),
        "dataW": chart_records(dfW, tail=120),
        "dataM": chart_records(dfM, tail=120),
    }


def build_indices(output_dir: Path) -> bool:
    """전체 지수 데이터 수집 → indices.json 작성."""
    indices: list[dict] = []
    for code, name in INDEX_DEFS:
        try:
            entry = _build_index(code, name)
            if entry:
                indices.append(entry)
                logger.info("index ok: %s (%s) value=%s rate=%s",
                            name, code, entry["value"], entry["changeRate"])
        except Exception as e:
            logger.exception("index %s failed: %s", code, e)

    if not indices:
        logger.error("no indices collected, skipping write")
        return False

    # data_date: 첫 지수의 마지막 캔들 날짜
    data_date = None
    if indices and indices[0].get("data"):
        data_date = indices[0]["data"][-1].get("date")

    payload = {
        "updated": datetime.now(KST).replace(microsecond=0).isoformat(),
        "data_date": data_date,
        "indices": indices,
    }
    out_path = output_dir / "indices.json"
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("wrote %s (%d indices, data_date=%s)",
                out_path, len(indices), data_date)
    return True


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="web/data")
    args = parser.parse_args()
    build_indices(Path(args.output))
