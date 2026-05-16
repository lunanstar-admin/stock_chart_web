"""거시 지표 대시보드 — 100% 자동 수집.

데이터 소스 (모두 API 키 등록 불필요):
- 환율/원자재: FinanceDataReader (Yahoo Finance 백엔드)
- 한국 CPI/기준금리: 한국은행 ECOS sample 키
- 미국 CPI/Fed 금리: FRED 공개 CSV (https://fred.stlouisfed.org/graph/fredgraph.csv)

출력: web/data/macro.json
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")

ECOS_BASE = "https://ecos.bok.or.kr/api"
ECOS_KEY = "sample"   # 무료 sample 키 (월간 5,000건/일 제한, 충분)

# 환율 — FDR
FX_DEFS = [
    ("USD/KRW", "원/달러", 2),
    ("EUR/KRW", "원/유로", 2),
    ("JPY/KRW", "원/엔(100엔)", 2),
]
COMMODITY_DEFS = [
    ("CL=F", "WTI 원유 (USD/배럴)", 2),
    ("GC=F", "금 (USD/oz)", 1),
]


# ─── FDR 시계열 (환율/원자재) ──────────────────────────────

def _build_series(code: str, name: str, dec: int, days: int = 35) -> dict | None:
    import FinanceDataReader as fdr

    end = datetime.now(KST)
    start = end - timedelta(days=days + 10)
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
    for _, row in df.tail(30).iterrows():
        d = str(row["date"])[:10]
        try:
            v = float(row["close"])
        except Exception:
            continue
        spark.append({"date": d, "close": round(v, max(2, dec))})

    return {
        "code": code,
        "name": name,
        "value": f"{cur:,.{dec}f}",
        "change": ("+" if chg > 0 else "") + f"{chg:,.{dec}f}",
        "changeRate": f"{rate:+.2f}",
        "changeDir": direction,
        "spark": spark,
    }


# ─── 한국은행 ECOS ──────────────────────────────

def _ecos_keystat() -> dict[str, dict]:
    """ECOS KeyStatisticList 101건 페이지네이션 수집 → {name: row} 맵."""
    out: dict[str, dict] = {}
    for start in range(1, 102, 10):
        end = min(start + 9, 101)
        url = f"{ECOS_BASE}/KeyStatisticList/{ECOS_KEY}/json/kr/{start}/{end}"
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
        except Exception as e:
            logger.warning("ECOS KeyStat %d-%d 실패: %s", start, end, e)
            continue
        rows = data.get("KeyStatisticList", {}).get("row", [])
        for row in rows:
            out[row.get("KEYSTAT_NAME", "")] = row
    return out


def _ecos_cpi_yoy() -> tuple[float | None, str | None]:
    """ECOS 소비자물가지수(901Y009) 24개월치 시계열로 YoY 계산.

    sample 키는 단일 호출당 10건이 max 라 페이지네이션으로 수집.
    """
    end = datetime.now(KST)
    start = (end - timedelta(days=400)).strftime("%Y%m")
    end_s = end.strftime("%Y%m")

    rows: list[dict] = []
    for page_start in range(1, 31, 10):
        page_end = page_start + 9
        url = (f"{ECOS_BASE}/StatisticSearch/{ECOS_KEY}/json/kr"
               f"/{page_start}/{page_end}/901Y009/M/{start}/{end_s}/0")
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
        except Exception as e:
            logger.warning("ECOS CPI page %d 실패: %s", page_start, e)
            continue
        page_rows = data.get("StatisticSearch", {}).get("row", [])
        if not page_rows:
            break
        rows.extend(page_rows)
        # total_count 보다 많이 받았으면 중단
        total = data.get("StatisticSearch", {}).get("list_total_count", 0)
        if len(rows) >= total:
            break

    if len(rows) < 13:
        return None, None
    # TIME=YYYYMM 정렬
    rows = sorted(rows, key=lambda r: r.get("TIME", ""))
    last = rows[-1]
    last_time = last.get("TIME", "")
    try:
        last_val = float(last["DATA_VALUE"])
    except Exception:
        return None, None
    # 12개월 전 값 찾기
    target_time = str(int(last_time) - 100)  # YYYYMM 산술
    base = next((r for r in rows if r.get("TIME") == target_time), None)
    if not base:
        return None, last_time
    try:
        base_val = float(base["DATA_VALUE"])
    except Exception:
        return None, last_time
    yoy = (last_val - base_val) / base_val * 100.0
    return yoy, last_time


# ─── FRED 공개 CSV ──────────────────────────────

def _fred_csv(series_id: str, since: str = "2024-01-01") -> dict[str, float]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={since}"
    try:
        r = requests.get(url, timeout=12)
        if r.status_code != 200:
            return {}
        out: dict[str, float] = {}
        for row in list(csv.reader(io.StringIO(r.text)))[1:]:
            if len(row) >= 2 and row[1] and row[1] != ".":
                try:
                    out[row[0]] = float(row[1])
                except ValueError:
                    continue
        return out
    except Exception as e:
        logger.warning("FRED %s 실패: %s", series_id, e)
        return {}


def _fred_us_cpi_yoy() -> tuple[float | None, str | None]:
    """CPIAUCSL 최근/12개월전 YoY 계산."""
    series = _fred_csv("CPIAUCSL", since="2024-01-01")
    if not series:
        return None, None
    dates = sorted(series.keys())
    last_date = dates[-1]
    last_val = series[last_date]
    last_dt = datetime.strptime(last_date, "%Y-%m-%d")
    yoy_target = last_dt.replace(year=last_dt.year - 1).strftime("%Y-%m-%d")
    if yoy_target not in series:
        return None, last_date
    yoy = (last_val - series[yoy_target]) / series[yoy_target] * 100.0
    return yoy, last_date


def _fred_us_fed_rate() -> tuple[float | None, str | None]:
    """미국 Fed funds target upper bound 최신값."""
    series = _fred_csv("DFEDTARU", since="2025-01-01")
    if not series:
        return None, None
    dates = sorted(series.keys())
    last_date = dates[-1]
    return series[last_date], last_date


# ─── 이벤트 캘린더 — events_builder.py 가 자동 생성 ──────────────────

def _build_events(output_dir: Path) -> list[dict]:
    """events_builder 모듈 사용. 모듈 import 실패 시 빈 리스트."""
    try:
        from batch import events_builder
        return events_builder.build_events(output_dir, horizon_days=60)
    except Exception as e:
        logger.warning("events_builder 실패(폴백 사용): %s", e)
        today = datetime.now(KST).date()
        return [
            {"date": str(today + timedelta(days=6)),  "title": "한국은행 금통위", "tag": "rate", "country": "KR"},
            {"date": str(today + timedelta(days=14)), "title": "미국 FOMC", "tag": "rate", "country": "US"},
        ]


# ─── 통합 빌더 ──────────────────────────────

def build_macro(output_dir: Path) -> bool:
    # 환율 + 원자재 — FDR
    fx = [it for it in (_build_series(c, n, d) for c, n, d in FX_DEFS) if it]
    commodities = [it for it in (_build_series(c, n, d) for c, n, d in COMMODITY_DEFS) if it]
    for it in fx:
        logger.info("fx: %s = %s (%s%%)", it["name"], it["value"], it["changeRate"])
    for it in commodities:
        logger.info("commodity: %s = %s", it["name"], it["value"])

    # 금리 + CPI — ECOS + FRED 자동 수집
    rates: list[dict] = []
    cpi: list[dict] = []

    # 한국 통계 (ECOS KeyStat)
    ks = _ecos_keystat()
    kr_rate = ks.get("한국은행 기준금리")
    if kr_rate:
        cycle = kr_rate.get("CYCLE", "")
        # YYYYMMDD → YYYY-MM-DD
        asof = f"{cycle[:4]}-{cycle[4:6]}-{cycle[6:8]}" if len(cycle) == 8 else cycle
        rates.append({
            "name": "한국 기준금리",
            "value": kr_rate.get("DATA_VALUE", "-"),
            "unit": "%",
            "asof": asof,
            "note": "한국은행 ECOS",
        })
        logger.info("KR base rate: %s%% (%s)", kr_rate["DATA_VALUE"], asof)

    # 한국 CPI — 지수 자체 + YoY 계산
    kr_cpi_yoy, kr_cpi_time = _ecos_cpi_yoy()
    if kr_cpi_yoy is not None:
        yyyy_mm = f"{kr_cpi_time[:4]}-{kr_cpi_time[4:6]}" if kr_cpi_time and len(kr_cpi_time) >= 6 else kr_cpi_time
        cpi.append({
            "name": "한국 CPI (YoY)",
            "value": f"{kr_cpi_yoy:.1f}",
            "unit": "%",
            "asof": yyyy_mm,
            "note": "한국은행 ECOS",
        })
        logger.info("KR CPI YoY: %.2f%% (%s)", kr_cpi_yoy, yyyy_mm)

    # 미국 Fed 금리 — FRED
    us_rate_val, us_rate_date = _fred_us_fed_rate()
    if us_rate_val is not None:
        rates.append({
            "name": "미국 Fed 금리 (상단)",
            "value": f"{us_rate_val:.2f}",
            "unit": "%",
            "asof": us_rate_date,
            "note": "FRED DFEDTARU",
        })
        logger.info("US Fed rate: %s%% (%s)", us_rate_val, us_rate_date)

    # 미국 CPI YoY — FRED
    us_cpi_yoy, us_cpi_date = _fred_us_cpi_yoy()
    if us_cpi_yoy is not None:
        yyyy_mm = us_cpi_date[:7] if us_cpi_date else "-"
        cpi.append({
            "name": "미국 CPI (YoY)",
            "value": f"{us_cpi_yoy:.1f}",
            "unit": "%",
            "asof": yyyy_mm,
            "note": "FRED CPIAUCSL",
        })
        logger.info("US CPI YoY: %.2f%% (%s)", us_cpi_yoy, yyyy_mm)

    events = _build_events(output_dir)

    data_date = fx[0]["spark"][-1]["date"] if fx and fx[0].get("spark") else None
    payload = {
        "updated": datetime.now(KST).replace(microsecond=0).isoformat(),
        "data_date": data_date,
        "fx": fx,
        "commodities": commodities,
        "rates": rates,
        "cpi": cpi,
        "events": sorted(events, key=lambda e: e.get("date", ""))[:20],
    }
    out = output_dir / "macro.json"
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.info("wrote %s (fx=%d commod=%d rates=%d cpi=%d events=%d)",
                out, len(fx), len(commodities), len(rates), len(cpi), len(events))
    return True


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="web/data")
    args = parser.parse_args()
    build_macro(Path(args.output))
