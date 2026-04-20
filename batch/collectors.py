"""종목 리스트·OHLCV·지표·밸류에이션 수집.

기존 auto_stock_trading 프로젝트의 로직을 참고하여 재구현.
- 전종목 리스트: Naver Finance API (market cap 정렬)
- OHLCV: FinanceDataReader
- 지표: pandas 기반 (MA/MACD/RSI/OBV/VWAP/MFI/Bollinger)
- 밸류에이션/수급 스냅샷: Naver integration API
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

_NAVER_HEADERS = {"User-Agent": "Mozilla/5.0 (chart-web batch)"}


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
