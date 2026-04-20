"""
매일 장마감 배치 끝에 호출되어 테마/주도주 관련 마크다운 글을 한 편 생성한다.

디자인 원칙
----------
1. **순수 데이터 기반** — 숫자·팩트만 사용. LLM/프로즈 자동 생성 없음.
2. **요일 로테이션**:
     월(0)  시가총액 Top 10 대형주 흐름
     화(1)  당일 등락률 상위 10
     수(2)  당일 거래량 상위 10
     목(3)  외국인 누적 순매수 상위 (대형주 200 중)
     금(4)  주간 마켓 랩업 (시장별 상승/하락 수 + Top 3)
     토/일 — no-op
3. **실패는 조용히** — 배치 전체를 깨뜨리지 않는다.
4. **Idempotent** — 같은 날짜로 재실행하면 덮어쓴다.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "web" / "posts"
DATA_DIR = ROOT / "web" / "data"
KST = timezone(timedelta(hours=9))


# ── 유틸 ────────────────────────────────────────────────
def parse_num(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").strip().rstrip("%")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def format_mcap(v: Any) -> str:
    s = str(v or "")
    if re.search(r"[조억만]", s):
        return s
    n = parse_num(v)
    if not n:
        return "-"
    if n >= 10000:
        return f"{n / 10000:.1f}조"
    return f"{int(n):,}억"


def format_num(v: Any) -> str:
    n = parse_num(v)
    if not n:
        return "-"
    return f"{int(n):,}"


def format_supply(n: float) -> str:
    """원 단위 → +1,230억 / -15조 등 사람이 읽기 쉬운 표기"""
    if n == 0 or n is None:
        return "0"
    sign = "+" if n > 0 else "-"
    abs_n = abs(n)
    if abs_n >= 1e12:
        return f"{sign}{abs_n / 1e12:.1f}조"
    if abs_n >= 1e8:
        return f"{sign}{abs_n / 1e8:.0f}억"
    if abs_n >= 1e4:
        return f"{sign}{abs_n / 1e4:.0f}만"
    return f"{sign}{int(abs_n):,}"


def load_stocks() -> list[dict]:
    path = DATA_DIR / "stocks.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("stocks", []) or []
    except Exception as e:
        logger.warning("load_stocks failed: %s", e)
        return []


def load_chart(code: str) -> Optional[dict]:
    p = DATA_DIR / "chart" / f"{code}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ── 공통 템플릿 ─────────────────────────────────────────
CTA = """## 차트로 확인하기

각 종목의 120일 캔들·이평선·볼린저밴드·수급 흐름은
[세콤달.콤 주식차트 →](/chart) 에서 종목명/코드로 검색해 상세 모달로 열 수 있습니다.
일봉 외에 **주봉·월봉** 토글도 지원해 중·장기 흐름까지 한 번에 확인 가능합니다.

> 본 포스트는 매일 장마감 배치가 자동 생성한 데이터 스냅샷입니다.
> 투자 권유가 아니며, 모든 판단과 책임은 이용자 본인에게 있습니다.
"""


def frontmatter(title: str, date_iso: str, slug: str, summary: str, tags: list[str]) -> str:
    tag_list = ", ".join(tags)
    return (
        "---\n"
        f"title: {title}\n"
        f"date: {date_iso}\n"
        f"slug: {slug}\n"
        f"summary: {summary}\n"
        f"tags: [{tag_list}]\n"
        "---\n"
    )


# ── 렌더러 ──────────────────────────────────────────────
def render_top_mcap(stocks: list[dict], date: datetime) -> Optional[str]:
    ranked = [s for s in stocks if parse_num(s.get("marketCap")) > 0]
    ranked.sort(key=lambda s: parse_num(s.get("marketCap")), reverse=True)
    top = ranked[:10]
    if len(top) < 3:
        return None

    date_str = date.strftime("%Y년 %m월 %d일")
    slug = f"daily-mcap-{date.strftime('%Y%m%d')}"

    rows = []
    gainers = losers = 0
    for i, s in enumerate(top, 1):
        rate = parse_num(s.get("changeRate"))
        if rate > 0:
            gainers += 1
        elif rate < 0:
            losers += 1
        sign = "+" if rate > 0 else ""
        rows.append(
            f"| {i} | **{s.get('name', '-')}** | `{s.get('code', '-')}` | {s.get('market', '-')} | "
            f"{format_num(s.get('price'))} | {sign}{rate:.2f}% | {format_mcap(s.get('marketCap'))} |"
        )

    top3 = " · ".join(s.get("name", "-") for s in top[:3])
    summary = (
        f"{date_str} 장마감 기준 KOSPI·KOSDAQ 시가총액 상위 10 종목 스냅샷. "
        f"{top3} 중심으로 대형주 흐름 정리."
    )

    body = f"""
{date_str} 한국 주식 시장(KOSPI · KOSDAQ) 장마감 기준,
시가총액 상위 10 종목의 종가와 등락률을 정리했습니다.
대형주 흐름은 지수 방향의 바로미터이자 외국인·기관 수급이 가장 먼저 반영되는 지표입니다.

## 오늘의 대장주 한눈에

- 시가총액 Top 10 중 **상승 {gainers}종 · 하락 {losers}종**
- 선두: **{top[0].get('name')}** ({top[0].get('market')}, 시총 {format_mcap(top[0].get('marketCap'))})

## 시가총액 Top 10

| 순위 | 종목명 | 코드 | 시장 | 종가 | 등락률 | 시가총액 |
|:---:|---|:---:|:---:|---:|---:|---:|
{chr(10).join(rows)}

{CTA}
"""
    return (
        frontmatter(
            title=f"{date_str} 시가총액 상위 10 종목 — 대장주 흐름",
            date_iso=date.strftime("%Y-%m-%d"),
            slug=slug,
            summary=summary,
            tags=["일간", "시가총액", "주도주", "대형주"],
        )
        + body
    )


def render_top_gainer(stocks: list[dict], date: datetime) -> Optional[str]:
    # 최소 거래량/시총 필터로 관리종목·초소형주 노이즈 제거
    filtered = [
        s for s in stocks
        if parse_num(s.get("changeRate")) > 0
        and parse_num(s.get("volume")) >= 50000
        and parse_num(s.get("marketCap")) >= 300  # 300억원 이상
    ]
    filtered.sort(key=lambda s: parse_num(s.get("changeRate")), reverse=True)
    top = filtered[:10]
    if len(top) < 3:
        return None

    date_str = date.strftime("%Y년 %m월 %d일")
    slug = f"daily-gainer-{date.strftime('%Y%m%d')}"

    rows = []
    for i, s in enumerate(top, 1):
        rate = parse_num(s.get("changeRate"))
        rows.append(
            f"| {i} | **{s.get('name', '-')}** | `{s.get('code', '-')}` | {s.get('market', '-')} | "
            f"{format_num(s.get('price'))} | **+{rate:.2f}%** | {format_num(s.get('volume'))} | {format_mcap(s.get('marketCap'))} |"
        )

    top3 = " · ".join(f"{s.get('name')}(+{parse_num(s.get('changeRate')):.1f}%)" for s in top[:3])
    summary = (
        f"{date_str} 종가 기준 상승률 상위 10 종목. 상위 3종목은 {top3}. "
        "거래량 5만주, 시총 300억 이상 필터 적용."
    )

    body = f"""
{date_str} 종가 기준, 한국 주식 시장(KOSPI · KOSDAQ) 에서 상승률이 가장 컸던 10 종목입니다.
**거래량 5만주 이상 · 시가총액 300억원 이상** 필터를 적용해 극소형주/관리종목을 제외했습니다.

## 오늘의 상승 주도주 3선

"""
    for i, s in enumerate(top[:3], 1):
        body += (
            f"{i}. **{s.get('name')}** ({s.get('market')}, `{s.get('code')}`) — "
            f"종가 {format_num(s.get('price'))}원, 등락률 +{parse_num(s.get('changeRate')):.2f}%, "
            f"거래량 {format_num(s.get('volume'))}주\n"
        )

    body += f"""

## 상승률 Top 10

| 순위 | 종목명 | 코드 | 시장 | 종가 | 등락률 | 거래량 | 시가총액 |
|:---:|---|:---:|:---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## 해석 포인트

급등 종목은 단기 모멘텀이 크지만 **변동성**도 함께 커지는 경향이 있습니다.
매수 전 최소한 아래 항목을 함께 점검하는 것이 안전합니다.

- 거래량이 **20일 평균 대비** 유의미하게 증가했는지
- RSI 가 이미 과매수 구간(70+) 에 진입했는지
- 외국인·기관 수급이 동행하는지, 개인만 몰리는지
- 최근 3~5일 누적 상승률이 과도하지 않은지 (피로도)

{CTA}
"""
    return (
        frontmatter(
            title=f"{date_str} KOSPI·KOSDAQ 상승률 Top 10",
            date_iso=date.strftime("%Y-%m-%d"),
            slug=slug,
            summary=summary,
            tags=["일간", "등락률", "상승주", "특징주"],
        )
        + body
    )


def render_top_volume(stocks: list[dict], date: datetime) -> Optional[str]:
    filtered = [
        s for s in stocks
        if parse_num(s.get("volume")) > 0
        and parse_num(s.get("marketCap")) >= 300
    ]
    filtered.sort(key=lambda s: parse_num(s.get("volume")), reverse=True)
    top = filtered[:10]
    if len(top) < 3:
        return None

    date_str = date.strftime("%Y년 %m월 %d일")
    slug = f"daily-volume-{date.strftime('%Y%m%d')}"

    rows = []
    for i, s in enumerate(top, 1):
        rate = parse_num(s.get("changeRate"))
        sign = "+" if rate > 0 else ""
        rows.append(
            f"| {i} | **{s.get('name', '-')}** | `{s.get('code', '-')}` | {s.get('market', '-')} | "
            f"{format_num(s.get('price'))} | {sign}{rate:.2f}% | **{format_num(s.get('volume'))}** | {format_mcap(s.get('marketCap'))} |"
        )

    top3 = " · ".join(s.get("name", "-") for s in top[:3])
    summary = (
        f"{date_str} KOSPI·KOSDAQ 거래량 상위 10 종목. {top3} 중심으로 관찰된 자금 유입."
    )

    body = f"""
{date_str} 종가 기준, 한국 주식 시장에서 **거래량이 가장 많았던** 10 종목입니다.
거래량 급증은 종종 신규 뉴스 유입·테마주 순환·수급 전환의 신호로 해석됩니다.

## 거래량 Top 10

| 순위 | 종목명 | 코드 | 시장 | 종가 | 등락률 | 거래량(주) | 시가총액 |
|:---:|---|:---:|:---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## 거래량 해석의 기본

단순히 거래량이 많다고 좋은 신호인 것은 아닙니다. **가격 방향성과 함께** 보는 것이 핵심입니다.

- **상승 + 대량 거래** → 신규 매수세 유입, 추세 강화 가능성
- **하락 + 대량 거래** → 투매·차익 실현, 추세 약화 가능성
- **횡보 + 대량 거래** → 수급 교환(매집/분산) 진행 중일 수 있음

세콤달.콤 주식차트 상세 모달의 **OBV / MFI 탭** 에서 거래량-가격 결합 지표를 함께 확인하세요.

{CTA}
"""
    return (
        frontmatter(
            title=f"{date_str} 거래량 상위 10 종목 — 자금이 몰린 주식",
            date_iso=date.strftime("%Y-%m-%d"),
            slug=slug,
            summary=summary,
            tags=["일간", "거래량", "수급", "특징주"],
        )
        + body
    )


def render_top_foreign(stocks: list[dict], date: datetime) -> Optional[str]:
    """대형주 200 종목 중 외국인 60일 누적 순매수 상위 10."""
    # 시총 상위 후보군 제한 (성능)
    candidates = [s for s in stocks if parse_num(s.get("marketCap")) > 0]
    candidates.sort(key=lambda s: parse_num(s.get("marketCap")), reverse=True)
    pool = candidates[:200]

    enriched: list[tuple[dict, float, float]] = []  # (stock, foreign_cum, price_change_rate)
    for s in pool:
        chart = load_chart(s.get("code", ""))
        if not chart:
            continue
        inv = chart.get("investor") or {}
        cum = (inv.get("cumulative") or {}).get("foreign") or {}
        total = parse_num(cum.get("total"))
        if total == 0:
            continue
        enriched.append((s, total, parse_num(s.get("changeRate"))))

    if len(enriched) < 3:
        return None

    enriched.sort(key=lambda t: t[1], reverse=True)
    top = enriched[:10]

    date_str = date.strftime("%Y년 %m월 %d일")
    slug = f"daily-foreign-{date.strftime('%Y%m%d')}"

    rows = []
    for i, (s, fcum, rate) in enumerate(top, 1):
        sign = "+" if rate > 0 else ""
        rows.append(
            f"| {i} | **{s.get('name', '-')}** | `{s.get('code', '-')}` | {s.get('market', '-')} | "
            f"{format_num(s.get('price'))} | {sign}{rate:.2f}% | **{format_supply(fcum)}** | {format_mcap(s.get('marketCap'))} |"
        )

    top3 = " · ".join(s.get("name", "-") for s, _, _ in top[:3])
    summary = (
        f"{date_str} 기준 최근 60거래일 외국인 누적 순매수 상위 10 종목 (대형주 200 대상). "
        f"{top3} 중심 유입."
    )

    body = f"""
{date_str} 장마감 기준, 시가총액 상위 200 종목 중 **최근 60거래일 외국인 누적 순매수**가
가장 컸던 10 종목을 정리했습니다. 외국인은 거시 요인(환율·미국 금리·지정학)에 민감하며
중·장기 포지션을 구축하는 경향이 있어, 누적 흐름은 주도주 판별의 중요한 단서가 됩니다.

## 외국인 누적 매수 Top 10 (60일)

| 순위 | 종목명 | 코드 | 시장 | 종가 | 당일 등락률 | 외국인 누적 | 시가총액 |
|:---:|---|:---:|:---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## 함께 보면 좋은 지표

외국인 단독 매수만으로 판단하기보다는 아래 요소를 함께 보세요.

- **기관 수급** 방향이 외국인과 같은지 (쌍끌이인지)
- **개인** 매매 방향이 반대인지 (지속성 시사)
- 가격이 누적 매수 금액과 **비례해 상승**하고 있는지

세콤달.콤 주식차트 상세 모달의 **수급 탭**에서 누적·일별 차트를 함께 확인할 수 있습니다.

{CTA}
"""
    return (
        frontmatter(
            title=f"{date_str} 외국인 누적 순매수 Top 10 — 주도 매수주",
            date_iso=date.strftime("%Y-%m-%d"),
            slug=slug,
            summary=summary,
            tags=["일간", "외국인", "수급", "주도주"],
        )
        + body
    )


def render_market_wrap(stocks: list[dict], date: datetime) -> Optional[str]:
    if not stocks:
        return None

    def split_by_market(market: str):
        arr = [s for s in stocks if s.get("market") == market]
        up = [s for s in arr if parse_num(s.get("changeRate")) > 0]
        dn = [s for s in arr if parse_num(s.get("changeRate")) < 0]
        flat = len(arr) - len(up) - len(dn)
        return arr, up, dn, flat

    kospi_all, kospi_up, kospi_dn, kospi_flat = split_by_market("KOSPI")
    kosdaq_all, kosdaq_up, kosdaq_dn, kosdaq_flat = split_by_market("KOSDAQ")

    if not kospi_all and not kosdaq_all:
        return None

    def top_movers(arr: list[dict], n: int = 5, reverse: bool = True):
        f = [
            s for s in arr
            if parse_num(s.get("volume")) >= 50000
            and parse_num(s.get("marketCap")) >= 300
        ]
        f.sort(key=lambda s: parse_num(s.get("changeRate")), reverse=reverse)
        return f[:n]

    kospi_gainers = top_movers(kospi_all)
    kospi_losers = top_movers(kospi_all, reverse=False)
    kosdaq_gainers = top_movers(kosdaq_all)
    kosdaq_losers = top_movers(kosdaq_all, reverse=False)

    # 거래량 Top 5 (전종목)
    vol = [s for s in stocks if parse_num(s.get("volume")) > 0 and parse_num(s.get("marketCap")) >= 300]
    vol.sort(key=lambda s: parse_num(s.get("volume")), reverse=True)
    vol_top = vol[:5]

    date_str = date.strftime("%Y년 %m월 %d일")
    week_str = date.strftime("%Y년 %m월 %d일")
    slug = f"daily-wrap-{date.strftime('%Y%m%d')}"

    def row(s: dict) -> str:
        rate = parse_num(s.get("changeRate"))
        sign = "+" if rate > 0 else ""
        return (
            f"| **{s.get('name', '-')}** | `{s.get('code', '-')}` | "
            f"{format_num(s.get('price'))} | {sign}{rate:.2f}% | {format_num(s.get('volume'))} |"
        )

    def tbl(rows_arr: list[dict]) -> str:
        header = "| 종목명 | 코드 | 종가 | 등락률 | 거래량 |\n|---|:---:|---:|---:|---:|"
        body_rows = "\n".join(row(s) for s in rows_arr) if rows_arr else "| - | - | - | - | - |"
        return f"{header}\n{body_rows}"

    summary = (
        f"{date_str} 장마감 마켓 랩업. "
        f"KOSPI 상승 {len(kospi_up)}·하락 {len(kospi_dn)}, "
        f"KOSDAQ 상승 {len(kosdaq_up)}·하락 {len(kosdaq_dn)}."
    )

    body = f"""
{date_str} 한국 주식 시장(KOSPI · KOSDAQ) 장마감 마켓 랩업입니다.

## 시장 요약

| 시장 | 전체 | 상승 | 하락 | 보합 |
|---|---:|---:|---:|---:|
| **KOSPI** | {len(kospi_all)} | {len(kospi_up)} | {len(kospi_dn)} | {kospi_flat} |
| **KOSDAQ** | {len(kosdaq_all)} | {len(kosdaq_up)} | {len(kosdaq_dn)} | {kosdaq_flat} |

## KOSPI 상승률 Top 5

{tbl(kospi_gainers)}

## KOSPI 하락률 Top 5

{tbl(kospi_losers)}

## KOSDAQ 상승률 Top 5

{tbl(kosdaq_gainers)}

## KOSDAQ 하락률 Top 5

{tbl(kosdaq_losers)}

## 거래량 Top 5 (전종목)

{tbl(vol_top)}

{CTA}
"""
    return (
        frontmatter(
            title=f"{date_str} 마켓 랩업 — KOSPI·KOSDAQ 상승/하락 Top 5",
            date_iso=date.strftime("%Y-%m-%d"),
            slug=slug,
            summary=summary,
            tags=["일간", "마켓랩업", "KOSPI", "KOSDAQ"],
        )
        + body
    )


RENDERERS = {
    0: render_top_mcap,
    1: render_top_gainer,
    2: render_top_volume,
    3: render_top_foreign,
    4: render_market_wrap,
}


# ── 엔트리 ──────────────────────────────────────────────
def generate(date: Optional[datetime] = None, force: bool = False) -> Optional[Path]:
    """오늘자(또는 지정한 날짜) 글 1편 생성. 주말은 스킵."""
    now = date or datetime.now(KST)
    wd = now.weekday()
    if wd >= 5 and not force:
        logger.info("[daily-post] weekend (%s) 스킵", now.strftime("%a"))
        return None

    renderer = RENDERERS.get(wd) or RENDERERS[0]
    stocks = load_stocks()
    if not stocks:
        logger.warning("[daily-post] stocks.json 없음 또는 비어있음. 스킵.")
        return None

    try:
        md = renderer(stocks, now)
    except Exception as e:
        logger.exception("[daily-post] renderer 실패: %s", e)
        return None

    if not md:
        logger.warning("[daily-post] renderer 가 빈 결과 반환. 스킵.")
        return None

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    # 파일명: YYYY-MM-DD-daily-{theme}.md
    m = re.search(r"slug:\s*(\S+)", md)
    slug = m.group(1) if m else f"daily-{now.strftime('%Y%m%d')}"
    path = POSTS_DIR / f"{now.strftime('%Y-%m-%d')}-{slug}.md"
    path.write_text(md, encoding="utf-8")
    logger.info("[daily-post] wrote %s (%d bytes)", path.relative_to(ROOT), len(md))
    return path


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (기본: 오늘 KST)")
    ap.add_argument("--force", action="store_true", help="주말에도 강제 실행")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    d = None
    if args.date:
        d = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=KST)

    p = generate(date=d, force=args.force)
    if p is None:
        sys.exit(0)
    print(p)


if __name__ == "__main__":
    main()
