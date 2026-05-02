"""시장 주도주·급등주·인기 종목 분석 블로그 — 매일 1편.

데이터 + 뉴스 결합 분석 글을 자동 생성합니다.

데이터 소스:
  - web/data/stocks.json          : 당일 시세, 등락률, 거래량
  - ~/.../stock_db.sqlite         : 업종(sector), 그룹(group_name)
  - Naver mobile news API         : 종목별 최근 뉴스 (https://m.stock.naver.com/api/news/stock/{code})

출력:
  web/posts/YYYY-MM-DD-market-brief-YYYYMMDD.md
  슬러그가 daily-/batch- 접두어가 아니므로 색인 허용 (AdSense 가치 콘텐츠).

주말은 스킵 (force=True 시 강제 실행).

매일 장마감 후 batch 파이프라인에서 호출되도록 run_batch.py 에 등록 권장.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import sys
import urllib.request
import urllib.error
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "web" / "posts"
DATA_DIR = ROOT / "web" / "data"
KST = timezone(timedelta(hours=9))

DB_CANDIDATES = [
    Path.home() / "Project_AI/stock_db/data/stock_db.sqlite",
    ROOT / "data" / "stock_db.sqlite",
]


# ── 유틸 ──────────────────────────────────────────────
def parse_num(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").strip().rstrip("%")
    try:
        return float(s) if s else 0.0
    except ValueError:
        return 0.0


def fmt_num(v: Any) -> str:
    n = parse_num(v)
    return f"{int(n):,}" if n else "-"


def fmt_mcap(v: Any) -> str:
    n = parse_num(v)
    if not n:
        return "-"
    if n >= 10000:
        return f"{n / 10000:.1f}조"
    return f"{int(n):,}억"


def html_unescape(s: str) -> str:
    import html
    return html.unescape(s or "")


def strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


# ── 데이터 로드 ──────────────────────────────────────────
def load_stocks() -> list[dict]:
    p = DATA_DIR / "stocks.json"
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    return raw.get("stocks") or raw.get("items") or []


def load_db_meta() -> dict[str, dict]:
    """code → {sector, industry, group_name, description}."""
    for cand in DB_CANDIDATES:
        if cand.exists():
            db = cand
            break
    else:
        return {}
    out: dict[str, dict] = {}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        for r in con.execute("SELECT code, sector, industry, group_name, main_products FROM companies"):
            out[r[0]] = {
                "sector": r[1] or None,
                "industry": r[2] or None,
                "group": r[3] or None,
                "products": r[4] or None,
            }
        con.close()
    except Exception as e:
        logger.warning("[market-brief] DB 메타 로드 실패: %s", e)
    return out


# ── 뉴스 fetch ──────────────────────────────────────────
def fetch_news(code: str, n: int = 3, timeout: float = 4.0) -> list[dict]:
    """Naver mobile finance 종목 뉴스. 실패하면 빈 리스트."""
    url = f"https://m.stock.naver.com/api/news/stock/{code}?pageSize={n}&page=1"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; secomdal-bot/1.0)",
            "Referer": f"https://m.stock.naver.com/domestic/stock/{code}/news",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as e:
        logger.debug("[market-brief] news fetch fail %s: %s", code, e)
        return []
    items = []
    for group in data if isinstance(data, list) else []:
        for it in (group.get("items") or [])[:n]:
            title = html_unescape(strip_html(it.get("title") or it.get("titleFull") or ""))
            body = html_unescape(strip_html(it.get("body") or ""))[:120]
            office = it.get("officeName") or ""
            dt = it.get("datetime") or ""
            link = it.get("mobileNewsUrl") or it.get("officialUrl") or ""
            if title:
                items.append({"title": title, "body": body, "office": office, "datetime": dt, "link": link})
        if len(items) >= n:
            break
    return items[:n]


# ── 테마 추출 ──────────────────────────────────────────
KEYWORD_THEMES = [
    # (키워드 패턴, 테마명)
    (r"AI|인공지능|챗GPT|LLM|GPU|NPU", "AI · 반도체"),
    (r"반도체|HBM|D램|낸드|파운드리|TSMC", "반도체"),
    (r"2차전지|이차전지|배터리|양극재|음극재|리튬|전해질|분리막", "2차전지"),
    (r"전기차|EV|테슬라|현대차|기아|충전", "전기차"),
    (r"바이오|신약|임상|FDA|항암|제약|치료제", "바이오 · 헬스케어"),
    (r"방산|무인기|드론|미사일|국방|방위산업", "방산"),
    (r"원전|SMR|원자력", "원전"),
    (r"조선|해운|선박|컨테이너", "조선 · 해운"),
    (r"건설|재건축|시멘트|철강|토목", "건설 · 인프라"),
    (r"태양광|풍력|수소|재생에너지|RE100|친환경", "신재생 에너지"),
    (r"엔터|K팝|아이돌|드라마|콘텐츠|영화", "엔터테인먼트"),
    (r"게임|모바일게임|MMORPG|이스포츠", "게임"),
    (r"화장품|뷰티|코스메틱|K뷰티", "화장품"),
    (r"식품|음식료|유통|편의점", "식품 · 유통"),
    (r"금융|은행|증권|보험", "금융"),
    (r"실적|영업이익|매출|어닝|호실적|컨센서스", "실적 · 어닝"),
    (r"배당|주주환원|자사주|소각", "주주환원"),
    (r"인수|합병|M&A|지분|매각", "M&A · 지분 변동"),
    (r"특허|소송|승소|패소", "특허 · 소송"),
    (r"수주|공급계약|MOU|계약체결", "수주 · 계약"),
]


def detect_themes(text: str) -> list[str]:
    found = []
    for pat, name in KEYWORD_THEMES:
        if re.search(pat, text):
            found.append(name)
    return found


# ── 종목 정보 빌드 ──────────────────────────────────────
def enrich(stock: dict, meta: dict, news_cache: dict) -> dict:
    code = stock["code"]
    m = meta.get(code, {})
    news = news_cache.get(code) or fetch_news(code, n=3)
    news_cache[code] = news
    blob = " ".join(n["title"] + " " + n["body"] for n in news)
    themes = detect_themes(blob)
    return {
        **stock,
        "sector": m.get("sector"),
        "industry": m.get("industry"),
        "group": m.get("group"),
        "products": m.get("products"),
        "news": news,
        "themes": themes,
    }


# ── 마크다운 렌더링 ──────────────────────────────────────
def stock_block(s: dict, rank: int, kind: str) -> str:
    """한 종목에 대한 분석 단락 생성."""
    code = s["code"]
    name = s["name"]
    market = s.get("market") or ""
    price = fmt_num(s.get("price"))
    rate = parse_num(s.get("changeRate"))
    rate_str = f"+{rate:.2f}%" if rate > 0 else f"{rate:.2f}%"
    vol = fmt_num(s.get("volume"))
    mcap = fmt_mcap(s.get("marketCap"))

    lines = []
    title_emoji = {"gainer": "🚀", "volume": "🔥", "leader": "👑"}.get(kind, "📈")
    lines.append(f"### {rank}. {title_emoji} {name} (`{code}`) — {rate_str}")

    sector = s.get("sector") or "-"
    industry = s.get("industry") or sector
    group = s.get("group")
    info = f"- **시장/업종**: {market} · {industry}"
    if group:
        info += f" · {group}"
    info += f"\n- **종가**: {price}원 · **거래량**: {vol}주 · **시가총액**: {mcap}"
    lines.append(info)

    if s.get("products"):
        lines.append(f"- **사업**: {s['products'][:80]}{'…' if len(s['products']) > 80 else ''}")

    themes = s.get("themes") or []
    if themes:
        # dedupe, 상위 3개
        seen = []
        for t in themes:
            if t not in seen:
                seen.append(t)
        lines.append(f"- **추정 테마**: {' · '.join(seen[:3])}")

    news = s.get("news") or []
    if news:
        lines.append("- **주요 뉴스** (네이버 종목 뉴스 발췌):")
        for n in news[:3]:
            t = n["title"][:80]
            office = n.get("office") or ""
            link = n.get("link") or ""
            if link:
                lines.append(f"  - [{t}]({link}) — {office}")
            else:
                lines.append(f"  - {t} — {office}")
    else:
        lines.append("- _최근 뉴스를 가져오지 못했습니다._")

    # 한 줄 해설
    reason = ""
    if rate >= 25:
        reason = "**상한가 인접 급등** — 단기 모멘텀이 매우 강하나 변동성도 함께 큽니다. 진입 시 분할 매수와 손절선 설정이 필수입니다."
    elif rate >= 10:
        reason = "**두자릿수 급등** — 호재성 뉴스 또는 수급 유입이 확인됩니다. 추격보다 눌림 후 재진입을 검토하세요."
    elif kind == "volume":
        reason = "**거래량 급증** — 신규 자금 유입 또는 매물 소화 가능성. 거래량 증가가 가격 상승을 동반했는지 확인이 필요합니다."
    elif kind == "leader":
        reason = "**시장 주도주** — 시가총액·거래대금 상위로 시장 방향을 이끄는 종목. 지수 흐름과 함께 봐야 합니다."
    if reason:
        lines.append(f"- {reason}")

    return "\n".join(lines)


def render_market_brief(stocks: list[dict], date: datetime) -> Optional[str]:
    if not stocks:
        return None
    meta = load_db_meta()
    news_cache: dict[str, list[dict]] = {}

    # 필터: 시총 300억+, 거래량 5만+ (관리종목/저유동성 제외)
    def usable(s: dict) -> bool:
        return parse_num(s.get("marketCap")) >= 300 and parse_num(s.get("volume")) >= 50_000

    filtered = [s for s in stocks if usable(s)]

    # 1) 급등주 Top 5 (등락률 내림차순)
    gainers = sorted(filtered, key=lambda s: -parse_num(s.get("changeRate")))[:5]
    # 2) 거래량 Top 5
    volumes = sorted(filtered, key=lambda s: -parse_num(s.get("volume")))[:5]
    # 3) 시장 주도주 = 시총 상위 10 중 등락률 양수만 5개
    leaders_pool = sorted(filtered, key=lambda s: -parse_num(s.get("marketCap")))[:30]
    leaders = sorted([s for s in leaders_pool if parse_num(s.get("changeRate")) > 0],
                     key=lambda s: -parse_num(s.get("marketCap")))[:5]
    if not leaders:
        # 양수 종목이 없으면 시총 상위 5 (음수여도)
        leaders = leaders_pool[:5]

    # 중복 제거 후 enrich
    all_codes = {s["code"] for s in gainers + volumes + leaders}
    enriched: dict[str, dict] = {}
    for s in stocks:
        if s["code"] in all_codes:
            enriched[s["code"]] = enrich(s, meta, news_cache)

    gainers = [enriched[s["code"]] for s in gainers]
    volumes = [enriched[s["code"]] for s in volumes]
    leaders = [enriched[s["code"]] for s in leaders]

    # 테마 집계 — 등장 빈도
    theme_counter: Counter = Counter()
    for s in list(enriched.values()):
        for t in s.get("themes") or []:
            theme_counter[t] += 1

    date_str = date.strftime("%Y년 %m월 %d일")
    iso = date.strftime("%Y-%m-%d")
    yyyymmdd = date.strftime("%Y%m%d")
    slug = f"market-brief-{yyyymmdd}"

    # 헤드라인 요약 — 상위 3 급등주 이름
    g_names = [s["name"] for s in gainers[:3]]
    g_names_s = " · ".join(g_names) if g_names else "-"

    # 테마 요약
    if theme_counter:
        top_themes = [t for t, _c in theme_counter.most_common(3)]
        theme_summary = " · ".join(top_themes)
    else:
        top_themes = []
        theme_summary = "특정 테마 집중 없음"

    summary = (f"{date_str} 한국 주식시장 시황 분석 — 급등 주도주: {g_names_s}. "
               f"오늘의 부각 테마: {theme_summary}.")

    # 본문 작성
    lines: list[str] = []
    # YAML frontmatter — 콜론(:) 충돌 방지를 위해 따옴표 quote
    def yq(s: str) -> str:
        return '"' + s.replace('"', "'") + '"'

    title_v = f"{date_str} 시장 주도주·급등주 분석 — 테마와 뉴스로 풀어본 오늘의 시황"
    lines.append("---")
    lines.append(f"title: {yq(title_v)}")
    lines.append(f"date: {iso}")
    lines.append(f"slug: {slug}")
    lines.append(f"summary: {yq(summary[:240])}")
    lines.append("tags: [시황, 주도주, 급등주, 테마분석, 인기종목, 뉴스]")
    lines.append("---")
    lines.append("")
    lines.append(f"# {date_str} 한국 주식시장, 누가 시장을 움직였나?")
    lines.append("")
    lines.append(
        f"{date_str} KOSPI · KOSDAQ 종가 기준으로 시장을 움직인 종목들을 정리합니다. "
        f"단순 랭킹을 넘어 — **왜 올랐는지**, **어떤 테마와 연결되는지**, "
        f"그리고 **어떤 뉴스가 함께 있었는지**를 네이버 종목 뉴스와 함께 살펴봅니다. "
        f"본 글의 모든 정보는 참고용이며, 매수·매도 권유가 아닙니다."
    )
    lines.append("")

    if top_themes:
        lines.append("## 🎯 오늘의 핵심 테마")
        lines.append("")
        lines.append(f"분석 대상 {len(enriched)}개 종목의 뉴스 키워드를 추출한 결과, 가장 자주 언급된 테마는 다음과 같습니다.")
        lines.append("")
        for t, c in theme_counter.most_common(5):
            lines.append(f"- **{t}** — {c}개 종목에서 관련 뉴스 포착")
        lines.append("")

    lines.append("## 🚀 오늘의 급등주 Top 5")
    lines.append("")
    lines.append("거래량 5만주 이상 · 시가총액 300억원 이상 필터를 적용해 극소형주를 제외했습니다.")
    lines.append("")
    for i, s in enumerate(gainers, 1):
        lines.append(stock_block(s, i, "gainer"))
        lines.append("")

    lines.append("## 🔥 거래량 폭증 종목 Top 5")
    lines.append("")
    lines.append("거래량은 신규 자금 유입과 시장의 관심을 가늠하는 가장 빠른 지표입니다.")
    lines.append("")
    for i, s in enumerate(volumes, 1):
        lines.append(stock_block(s, i, "volume"))
        lines.append("")

    lines.append("## 👑 시장 주도주 — 시총 상위 대형주 동향")
    lines.append("")
    lines.append("시가총액 상위 30종목 중 오늘 상승한 대표 5종목입니다. 지수의 방향을 직접 결정하는 종목들입니다.")
    lines.append("")
    for i, s in enumerate(leaders, 1):
        lines.append(stock_block(s, i, "leader"))
        lines.append("")

    lines.append("## 💡 시황 종합 코멘트")
    lines.append("")
    if top_themes:
        lines.append(
            f"오늘 시장은 **{top_themes[0]}** 관련 종목이 가장 두드러졌습니다. "
            f"뉴스 흐름과 거래량 증가가 함께 나타난다면 단기 모멘텀이 이어질 가능성이 있으나, "
            f"단순 테마 추격은 변동성에 노출되기 쉽습니다. "
            f"상위 종목의 **시가총액 · 거래대금**과 "
            f"외국인 · 기관 수급을 함께 확인하시기 바랍니다."
        )
    else:
        lines.append(
            "오늘은 특정 테마에 집중된 흐름보다는 개별 호재 · 수급 이슈가 시장을 이끌었습니다. "
            "테마 차원의 큰 흐름은 약했지만, 개별 종목의 거래량 증가와 등락률 상승은 "
            "내일도 이어지는지 확인할 가치가 있습니다."
        )
    lines.append("")
    lines.append(
        "급등 종목 매매 시 점검 항목:"
        "\n- 거래량이 20일 평균 대비 유의미하게 증가했는가"
        "\n- RSI 가 이미 과매수 구간(70+) 인가"
        "\n- 외국인 · 기관 누적이 함께 우상향인가"
        "\n- 동일 업종 내 다른 종목도 같이 움직이는가 (테마 vs 단일 종목)"
        "\n- 상승의 원인이 된 뉴스가 일회성인지 지속 모멘텀인지"
    )
    lines.append("")
    lines.append("> 📚 처음이라면 [기술적 지표 가이드](/guide/technical-indicators) · "
                 "[수급 가이드](/guide/supply-demand) · [용어집](/glossary)을 함께 보시면 좋습니다. "
                 "[전종목 차트](/chart) 에서 위 종목들의 캔들과 수급을 직접 확인할 수 있습니다.")
    lines.append("")
    lines.append("---")
    lines.append(
        "*본 글은 자동 수집된 시세 데이터(FinanceDataReader · pykrx)와 "
        "네이버 종목 뉴스 헤드라인을 결합해 자동 생성된 분석 글입니다. "
        "테마 분류는 뉴스 키워드 매칭에 기반한 자동 추정으로 부정확할 수 있으며, "
        "투자 판단의 참고 자료로만 활용해 주세요. "
        "본 글의 모든 내용은 매수·매도 권유가 아니며, 투자 결과에 대한 책임은 이용자 본인에게 있습니다.*"
    )

    return "\n".join(lines)


# ── 엔트리 ──────────────────────────────────────────
def generate(date: Optional[datetime] = None, force: bool = False) -> Optional[Path]:
    now = date or datetime.now(KST)
    if now.weekday() >= 5 and not force:
        logger.info("[market-brief] weekend skip")
        return None

    stocks = load_stocks()
    if not stocks:
        logger.warning("[market-brief] stocks.json 없음")
        return None

    md = render_market_brief(stocks, now)
    if not md:
        return None

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    yyyymmdd = now.strftime("%Y%m%d")
    path = POSTS_DIR / f"{now.strftime('%Y-%m-%d')}-market-brief-{yyyymmdd}.md"
    path.write_text(md, encoding="utf-8")
    logger.info("[market-brief] wrote %s (%d bytes)", path.relative_to(ROOT), len(md))
    return path


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (기본: 오늘 KST)")
    ap.add_argument("--force", action="store_true")
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
    if p:
        print(p)


if __name__ == "__main__":
    main()
