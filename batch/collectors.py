"""종목 리스트·OHLCV·지표·밸류에이션 수집.

기존 auto_stock_trading 프로젝트의 로직을 참고하여 재구현.
- 전종목 리스트: Naver Finance API (market cap 정렬)
- OHLCV: FinanceDataReader
- 지표: pandas 기반 (MA/MACD/RSI/OBV/VWAP/MFI/Bollinger)
- 밸류에이션/수급 스냅샷: Naver integration API
- 회사 기본정보: Naver Finance → WiseReport iframe(c1010001.aspx) 요약 박스
"""

from __future__ import annotations

import html
import logging
import math
import re
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

_NAVER_HEADERS = {"User-Agent": "Mozilla/5.0 (chart-web batch)"}
_WISEREPORT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (chart-web batch)",
    "Referer": "https://finance.naver.com/",
}


# ─── 종목 리스트 ─────────────────────────────────────────────────────────

def fetch_market_listing(market: str, page_size: int = 100) -> list[dict]:
    """Naver Finance에서 시장 전종목 + 가격/등락/시총 스냅샷 수집.

    Args:
        market: "KOSPI" | "KOSDAQ"
        page_size: 페이지당 종목 수 (Naver 제한 ~100)

    Returns:
        [{code, name, market, price, change, changeRate, changeDir,
          volume, marketCap}, ...]
    """
    assert market in ("KOSPI", "KOSDAQ"), f"unsupported market: {market}"

    stocks: list[dict] = []
    page = 1
    total = None
    while True:
        url = (
            f"https://m.stock.naver.com/api/stocks/marketValue/"
            f"{market}?page={page}&pageSize={page_size}"
        )
        r = requests.get(url, headers=_NAVER_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        raw = data.get("stocks", [])
        total = data.get("totalCount", total)
        if not raw:
            break

        for s in raw:
            code = s.get("itemCode", "")
            if not code:
                continue
            stocks.append({
                "code": code,
                "name": s.get("stockName", code),
                "market": market,
                "price": s.get("closePrice", ""),
                "change": s.get("compareToPreviousClosePrice", ""),
                "changeRate": s.get("fluctuationsRatio", ""),
                "changeDir": (s.get("compareToPreviousPrice") or {}).get("name", ""),
                "volume": s.get("accumulatedTradingVolume", ""),
                "marketCap": s.get("marketValue", ""),
            })

        if total is not None and len(stocks) >= total:
            break
        if len(raw) < page_size:
            break
        page += 1

    logger.info("[%s] listing: %d stocks", market, len(stocks))
    return stocks


# ─── OHLCV + 지표 ────────────────────────────────────────────────────────

def fetch_ohlcv(code: str, days: int = 120) -> pd.DataFrame:
    """FinanceDataReader로 일봉 OHLCV 수집. 지표 계산 여유분(+80일) 포함.

    Args:
        days: 필요한 "결과" 일수. 내부에서 지표 계산용 버퍼를 더 받는다.
              주/월봉 리샘플까지 하려면 호출자가 충분히 큰 값(~3700) 을 넘긴다.

    Returns:
        columns=[date, open, high, low, close, volume] DataFrame (소문자).
        실패 시 빈 DataFrame.
    """
    import FinanceDataReader as fdr  # lazy import for faster test startup

    end = datetime.now()
    start = end - timedelta(days=days + 80)
    try:
        df = fdr.DataReader(code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    except Exception as e:
        logger.debug("fdr error %s: %s", code, e)
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    df = df.reset_index()
    # FDR 컬럼명 정규화
    rename = {c: c.lower() for c in df.columns}
    df = df.rename(columns=rename)
    if "date" not in df.columns and "index" in df.columns:
        df = df.rename(columns={"index": "date"})
    for col in ("open", "high", "low", "close", "volume"):
        if col not in df.columns:
            return pd.DataFrame()
    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """MA/MACD/RSI/OBV/VWAP/MFI/Bollinger를 한 번에 계산해 컬럼 추가.

    auto_stock_trading/strategies/indicators.py 의 로직을 이식.
    """
    if df.empty:
        return df
    out = df.copy()

    # Moving averages
    for p in (5, 20, 60):
        out[f"ma{p}"] = out["close"].rolling(window=p).mean()

    # MACD (12, 26, 9)
    ema_fast = out["close"].ewm(span=12, adjust=False).mean()
    ema_slow = out["close"].ewm(span=26, adjust=False).mean()
    out["macd"] = ema_fast - ema_slow
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]

    # RSI (14)
    delta = out["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["rsi"] = 100 - (100 / (1 + rs))

    # OBV (vectorized)
    direction = np.sign(out["close"].diff().fillna(0))
    out["obv"] = (direction * out["volume"]).cumsum()

    # VWAP (누적)
    tp = (out["high"] + out["low"] + out["close"]) / 3
    out["vwap"] = (tp * out["volume"]).cumsum() / out["volume"].cumsum().replace(0, np.nan)

    # MFI (14)
    mf = tp * out["volume"]
    tp_diff = tp.diff()
    pos = mf.where(tp_diff > 0, 0.0).rolling(window=14).sum()
    neg = mf.where(tp_diff < 0, 0.0).rolling(window=14).sum()
    mr = pos / neg.replace(0, np.nan)
    out["mfi"] = 100 - (100 / (1 + mr))

    # Bollinger Bands (20, 2)
    bb_mid = out["close"].rolling(window=20).mean()
    bb_std = out["close"].rolling(window=20).std()
    out["bb_mid"] = bb_mid
    out["bb_upper"] = bb_mid + 2 * bb_std
    out["bb_lower"] = bb_mid - 2 * bb_std

    return out


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """일봉 → 주/월봉 OHLCV 리샘플.

    rule: pandas offset alias ('W-FRI' = 금요일 종료 주, 'MS' 또는 'ME').
    여기서는 'W'(주 일요일 종료) / 'ME'(월말)을 쓴다.
    """
    if df.empty or "date" not in df.columns:
        return pd.DataFrame()
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.set_index("date").sort_index()
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    res = out.resample(rule).agg(agg).dropna(subset=["open", "close"])
    res = res.reset_index()
    return res


_CHART_COLS = [
    "date", "open", "high", "low", "close", "volume",
    "ma5", "ma20", "ma60",
    "macd", "macd_signal", "macd_hist",
    "rsi", "obv", "vwap", "mfi",
    "bb_upper", "bb_mid", "bb_lower",
]


def chart_records(df: pd.DataFrame, tail: int = 120) -> list[dict]:
    """차트에 필요한 컬럼만 최근 N일 추출 → list[dict]. NaN → None."""
    if df.empty:
        return []
    df = df.tail(tail).copy()
    df = df.where(df.notna(), None)
    if "date" in df.columns:
        df["date"] = df["date"].astype(str).str[:10]
    cols = [c for c in _CHART_COLS if c in df.columns]
    recs = df[cols].to_dict(orient="records")
    for rec in recs:
        for k, v in list(rec.items()):
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                rec[k] = None
            elif hasattr(v, "item"):  # numpy scalar
                rec[k] = v.item()
    return recs


# ─── 메타(밸류에이션/섹터) ──────────────────────────────────────────────

def fetch_meta(code: str) -> dict:
    """Naver integration API → PER/시총/외국인지분율/섹터."""
    meta: dict[str, Any] = {}
    try:
        r = requests.get(
            f"https://m.stock.naver.com/api/stock/{code}/integration",
            headers=_NAVER_HEADERS, timeout=6,
        )
        if r.status_code != 200:
            return meta
        d = r.json()
        for info in d.get("totalInfos", []) or []:
            c = info.get("code")
            if c in ("per", "marketValue", "foreignRate", "eps", "bps", "pbr"):
                meta[c] = info.get("value", "")
        # 섹터 — stockInfo.sectorName 가 있으면 사용 (없는 경우가 대부분)
        items = d.get("stockInfo", {})
        if isinstance(items, dict):
            sector = items.get("sectorName") or items.get("industryName")
            if sector:
                meta["sector"] = sector
    except Exception as e:
        logger.debug("meta fetch error %s: %s", code, e)
    return meta


# ─── 회사 기본정보 (WiseReport 요약 박스 파싱) ───────────────────────────

# Naver Finance `/item/coinfo.naver` 가 embed 하는 WiseReport 요약 페이지에서
# 회사 프로필을 긁어온다. JSON API 가 없고 HTML 만 노출되므로 보수적으로 파싱한다.
_WISEREPORT_URL = "https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={code}"


def _wr_find_title(html_text: str, label: str) -> str | None:
    """title="[label] ..." 패턴에서 값을 뽑아낸다."""
    # title 속성은 "[홈페이지] www.xxx.com" 이거나, "[대표전화] 031-... \r[주식담당] 02-..."
    m = re.search(rf'title="\[{re.escape(label)}\]\s*([^"]+?)"', html_text)
    if not m:
        # 여러 항목이 한 title 에 들어있는 경우 (대표전화 + 주식담당)
        m = re.search(rf'\[{re.escape(label)}\]\s*([^\[<\r\n]+)', html_text)
    if not m:
        return None
    v = html.unescape(m.group(1)).strip()
    return v or None


def _wr_match_dt_after(html_text: str, marker: str) -> str | None:
    """`<dt ...>` 내부 텍스트에 marker 가 포함된 요소의 텍스트를 반환."""
    for m in re.finditer(r"<dt[^>]*>([^<]{1,120})</dt>", html_text):
        t = html.unescape(m.group(1)).strip()
        if marker in t:
            return re.sub(r"\s+", " ", t).strip()
    return None


def fetch_company_info(code: str) -> dict:
    """WiseReport 요약 박스에서 회사 기본정보 추출.

    반환 예:
      {
        "nameKor": "삼성전자",
        "nameEng": "SamsungElec",
        "market": "KOSPI",            # 상위 시장
        "marketSector": "전기·전자",   # 거래소 업종
        "wicsSector": "반도체와반도체장비",  # WICS 업종
        "homepage": "http://www.samsung.com/sec",
        "phone": "031-200-1114",
        "irPhone": "02-2255-9000",
        "fiscalMonth": "12월",
        "industryPer": "24.98",
      }

    네트워크/파싱 실패 시 빈 dict 반환. 배치 전체를 깨트리지 않는다.
    """
    info: dict[str, str] = {}
    try:
        url = _WISEREPORT_URL.format(code=code)
        r = requests.get(url, headers=_WISEREPORT_HEADERS, timeout=8)
        if r.status_code != 200 or not r.text:
            return info
        s = r.text

        # 1) 홈페이지 (href 로 정확히 뽑는 편이 안전)
        m = re.search(r'title="\[홈페이지\][^"]*"\s+href="([^"]+)"', s)
        if m:
            info["homepage"] = html.unescape(m.group(1)).strip()

        # 2) 대표전화 / 주식담당 (하나의 title 에 \r 로 묶여 있을 수 있음)
        m = re.search(r'title="(\[대표전화\][^"]+)"', s)
        if m:
            tel_block = html.unescape(m.group(1))
            m2 = re.search(r'\[대표전화\]\s*([0-9\-\s]+)', tel_block)
            if m2:
                info["phone"] = m2.group(1).strip()
            m2 = re.search(r'\[주식담당\]\s*([0-9\-\s]+)', tel_block)
            if m2:
                info["irPhone"] = m2.group(1).strip()

        # 3) 회사명 (한글) — <span class="name">...</span>
        m = re.search(r'<span class="name">\s*([^<]+?)\s*</span>', s)
        if m:
            info["nameKor"] = html.unescape(m.group(1)).strip()

        # 4) 영문명 / 거래소 업종 / WICS 업종 — 회사명 span 이후의 <dt class="line-left"> 블록들
        head_end = s.find("</table>", s.find("cmp-table")) if "cmp-table" in s else -1
        head = s[:head_end] if head_end > 0 else s[:6000]
        lines = re.findall(r'<dt class="line-left">\s*([^<]+?)\s*</dt>', head)
        for ln in lines:
            t = html.unescape(ln).strip()
            if not t:
                continue
            if ":" in t:
                left, right = [x.strip() for x in t.split(":", 1)]
                if left.upper() == "WICS":
                    info["wicsSector"] = right
                elif left in ("KOSPI", "KOSDAQ", "KONEX"):
                    info["market"] = left
                    # 우측은 "코스피 전기·전자" 처럼 한 번 더 쪼갤 수 있음
                    info["marketSector"] = right
            elif "nameEng" not in info and re.match(r"^[A-Za-z0-9 .,'&\-]+$", t):
                info["nameEng"] = t

        # 5) 결산월 — "12월 결산" 형태
        fm = _wr_match_dt_after(head, "결산")
        if fm:
            m = re.search(r"(\d{1,2})\s*월\s*결산", fm)
            if m:
                info["fiscalMonth"] = f"{int(m.group(1))}월"

        # 6) 업종 PER — "업종PER <b class="num">24.98</b>"
        m = re.search(r"업종PER\s*<b[^>]*>\s*([0-9,.\-]+)", s)
        if m:
            info["industryPer"] = m.group(1).strip()

    except Exception as e:
        logger.debug("company_info fetch error %s: %s", code, e)
    # 빈 문자열은 JSON 을 부풀리므로 제거
    return {k: v for k, v in info.items() if v}
