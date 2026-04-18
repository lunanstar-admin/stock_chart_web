"""투자자별 수급 데이터 수집 (외국인/기관/개인).

우선순위:
  1차: pykrx — 장마감 직후 데이터, 기관 세부 포함 (KRX 차단 시 실패)
  2차: Naver Finance frgn.naver — 외국인/기관 순매매 + 보유비율 (~60일)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

import requests

logger = logging.getLogger(__name__)

_NAVER_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}


def _sanitize_record(rec: dict) -> dict:
    import math
    clean = {}
    for k, v in rec.items():
        if v is None:
            clean[k] = None
            continue
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            clean[k] = None
            continue
        if hasattr(v, "item"):
            clean[k] = v.item()
            continue
        clean[k] = v
    return clean


def _parse_int(s: str) -> int | None:
    """Naver 문자열 (+1,234 / -1,234 / 1,234) → int."""
    if s is None:
        return None
    s = s.strip().replace(",", "").replace("+", "")
    if not s or s == "-":
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _parse_float(s: str) -> float | None:
    if s is None:
        return None
    s = s.strip().replace(",", "").replace("%", "").replace("+", "")
    if not s or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _fetch_naver_frgn(code: str, days: int) -> list[dict]:
    """Naver Finance frgn.naver 페이지 스크레이핑.

    테이블 컬럼: 날짜 | 종가 | 전일비 | 등락률 | 거래량 | 기관순매매 | 외국인순매매 | 보유주수 | 보유율
    페이지당 20행, days/20+1 페이지 조회 (최대 3페이지).
    """
    pages = min(4, max(1, days // 20 + 1))
    records: list[dict] = []
    for p in range(1, pages + 1):
        try:
            r = requests.get(
                "https://finance.naver.com/item/frgn.naver",
                params={"code": code, "page": str(p)},
                headers=_NAVER_UA,
                timeout=10,
            )
            if r.status_code != 200 or not r.text:
                continue
            html = r.text
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
            for row in rows:
                if 'class="num"' not in row:
                    continue
                if not re.search(r"\d{4}\.\d{2}\.\d{2}", row):
                    continue
                cells_raw = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
                cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells_raw]
                if len(cells) < 9:
                    continue
                date_str = cells[0].replace(".", "-")
                inst_val = _parse_int(cells[5])
                foreign_val = _parse_int(cells[6])
                foreign_ratio = _parse_float(cells[8])
                if inst_val is None and foreign_val is None:
                    continue
                # 개인 = -(기관 + 외국인)  (근사; 기타법인 제외됨)
                retail_val = None
                if inst_val is not None and foreign_val is not None:
                    retail_val = -(inst_val + foreign_val)
                records.append({
                    "date": date_str,
                    "inst": inst_val,
                    "foreign": foreign_val,
                    "retail": retail_val,
                    "foreign_ratio": foreign_ratio,
                })
        except Exception as e:
            logger.debug("naver frgn page %d failed for %s: %s", p, code, e)
    # 중복 제거 + 날짜 오름차순
    seen = set()
    unique = []
    for r in records:
        if r["date"] in seen:
            continue
        seen.add(r["date"])
        unique.append(r)
    unique.sort(key=lambda x: x["date"])
    return unique[-days:]


def fetch_investor(code: str, days: int = 60) -> dict:
    """투자자별 일별 순매수 데이터 수집.

    Returns:
        {"data": list[dict], "cumulative": {col: {total, cumulative[]}}, "_source": str}
        데이터가 없으면 {"data": [], "cumulative": {}, "_source": ""}
    """
    records: list[dict] = []
    source = ""

    # 1차: pykrx (KRX Akamai 차단 시 실패)
    try:
        from pykrx import stock as pykrx_stock

        end = datetime.now()
        start = end - timedelta(days=days + 5)
        df = pykrx_stock.get_market_trading_value_by_date(
            start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), code, detail=True,
        )
        if df is not None and not df.empty:
            df = df.reset_index()
            col_map = {
                "날짜": "date",
                "금융투자": "securities",
                "보험": "insurance",
                "투신": "investment_trust",
                "사모": "private_equity",
                "은행": "bank",
                "기타금융": "other_finance",
                "연기금등": "pension",
                "기관합계": "inst",
                "기타법인": "corp",
                "개인": "retail",
                "외국인": "foreign",
                "기타외국인": "other_foreign",
            }
            df = df.rename(columns=col_map)
            if "date" in df.columns:
                df["date"] = df["date"].astype(str).str[:10]
            df = df.tail(days)
            df = df.where(df.notna(), None)
            records = [_sanitize_record(r) for r in df.to_dict(orient="records")]
            source = "pykrx"
    except Exception as e:
        logger.debug("pykrx investor %s failed: %s", code, e)

    # 2차: Naver frgn.naver 폴백
    if not records:
        try:
            records = _fetch_naver_frgn(code, days)
            if records:
                source = "naver"
        except Exception as e:
            logger.debug("naver investor %s failed: %s", code, e)

    if not records:
        return {"data": [], "cumulative": {}, "_source": ""}

    cumulative: dict[str, Any] = {}
    for col in (
        "inst", "retail", "foreign", "corp",
        "securities", "insurance", "investment_trust",
        "private_equity", "bank", "other_finance", "pension",
        "other_foreign",
    ):
        vals = [r.get(col) for r in records if r.get(col) is not None]
        if not vals:
            continue
        cum = 0
        cum_list = []
        for v in vals:
            cum += v
            cum_list.append(cum)
        cumulative[col] = {
            "total": int(sum(vals)),
            "cumulative": [int(c) for c in cum_list],
        }

    return {"data": records, "cumulative": cumulative, "_source": source}
