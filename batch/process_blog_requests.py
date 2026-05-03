"""관리자 블로그 요청 큐 처리 — Supabase 의 blog_requests 테이블을 polling 해
Claude Haiku 로 글을 작성하고 web/posts/ 에 저장.

매 30분 GitHub Actions cron 이 호출.

환경변수:
  SUPABASE_URL              : 프로젝트 URL
  SUPABASE_SERVICE_KEY      : service_role 키 (RLS 우회용, GitHub Secret)
  ANTHROPIC_API_KEY         : Claude API 키
  ANTHROPIC_MODEL           : 모델명 (기본 claude-haiku-4-5)
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

# build_market_brief 의 헬퍼 재사용
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from batch.build_market_brief import (
    fetch_news, fetch_article_body, extract_relevant_sentences,
    detect_themes, parse_num, fmt_num, fmt_mcap, has_jongseong,
    call_anthropic, ANTHROPIC_API_KEY, load_db_meta,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "web" / "posts"
DATA_DIR = ROOT / "web" / "data"
KST = timezone(timedelta(hours=9))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


# ── Supabase REST helpers ────────────────────────────────
def _sb_request(method: str, path: str, *, params: Optional[dict] = None,
                body: Any = None, prefer: str = "") -> tuple[int, Any]:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY 환경변수 미설정")
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, safe=",.()")
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            txt = r.read().decode("utf-8")
            return r.status, (json.loads(txt) if txt else None)
    except urllib.error.HTTPError as e:
        body_txt = ""
        try:
            body_txt = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        logger.warning("[blog-req] SB %s %s → %s: %s", method, path, e.code, body_txt[:300])
        return e.code, body_txt


def fetch_pending_requests() -> list[dict]:
    """status='pending' AND due_at<=now() 인 요청 가져옴."""
    now_iso = datetime.now(timezone.utc).isoformat()
    status, data = _sb_request("GET", "blog_requests", params={
        "select": "*",
        "status": "eq.pending",
        "due_at": f"lte.{now_iso}",
        "order": "due_at.asc",
        "limit": "10",
    })
    if status != 200 or not isinstance(data, list):
        return []
    return data


def update_request(req_id: str, **fields) -> bool:
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    status, _ = _sb_request(
        "PATCH",
        "blog_requests",
        params={"id": f"eq.{req_id}"},
        body=fields,
        prefer="return=minimal",
    )
    return 200 <= status < 300


# ── 차트 데이터 로드 ────────────────────────────────
def load_chart(code: str) -> Optional[dict]:
    p = DATA_DIR / "chart" / f"{code}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def summarize_price_action(code: str, name: str) -> str:
    """최근 10거래일 OHLCV + 60일 외국인·기관 누적을 짧은 사실 텍스트로."""
    c = load_chart(code)
    if not c:
        return ""
    # chart.json 구조 파악 — 일반적으로 candles[] 또는 ohlcv[]
    candles = c.get("candles") or c.get("ohlcv") or c.get("D") or []
    if not candles:
        return ""
    last10 = candles[-10:]
    if not last10:
        return ""

    # 종가/거래량 추출
    def _g(x, *keys):
        for k in keys:
            if isinstance(x, dict) and k in x and x[k] is not None:
                return x[k]
        return None

    closes = [parse_num(_g(x, "close", "c", 4)) for x in last10]
    vols = [parse_num(_g(x, "volume", "v", 5)) for x in last10]
    dates = [_g(x, "date", "d", 0) or "" for x in last10]
    if not closes or not closes[-1]:
        return ""

    first_close = closes[0]
    last_close = closes[-1]
    period_chg = (last_close - first_close) / first_close * 100 if first_close else 0.0
    avg_vol = sum(vols) / len(vols) if vols else 0
    today_vol = vols[-1] if vols else 0
    vol_ratio = today_vol / avg_vol if avg_vol else 0

    # 외국인/기관 (있으면)
    flow = c.get("supply") or c.get("flow") or {}
    foreign_60 = parse_num(flow.get("foreign60") or flow.get("foreign") or 0)
    inst_60 = parse_num(flow.get("inst60") or flow.get("institution") or 0)

    parts = []
    parts.append(f"최근 10거래일 종가 변화 {period_chg:+.2f}%")
    if avg_vol > 0:
        parts.append(f"오늘 거래량은 10일 평균 대비 {vol_ratio:.1f}배")
    if foreign_60:
        sign = "순매수" if foreign_60 > 0 else "순매도"
        parts.append(f"외국인 60일 누적 {sign} {abs(int(foreign_60)):,}주")
    if inst_60:
        sign = "순매수" if inst_60 > 0 else "순매도"
        parts.append(f"기관 60일 누적 {sign} {abs(int(inst_60)):,}주")
    return ". ".join(parts) + "."


# ── 글 생성 프롬프트 ──────────────────────────────────
TONE_HINTS = {
    "analysis": "분석형: 인과·맥락·전망을 5~7문장으로. 매크로 배경 → 산업 영향 → 종목 이벤트 → 시장 반응.",
    "brief":    "속보형: 핵심 사실 위주 3~4문장. 짧고 명확하게.",
    "explainer":"해설형: 초보자가 이해할 수 있게 7~9문장. 용어 풀이 포함.",
}


def build_prompt(req: dict, news_list: list[dict], price_summary: str, meta: dict) -> str:
    name = req["stock_name"]
    code = req["stock_code"]
    topic = req["topic"]
    notes = req.get("notes") or ""
    tone = req.get("tone") or "analysis"
    industry = meta.get("industry") or meta.get("sector") or ""
    products = (meta.get("products") or "").strip()[:160]

    # 기사 본문 묶음 (top 3)
    articles = []
    for i, n in enumerate(news_list[:3]):
        body = (n.get("fullBody") or "").strip()
        if not body:
            continue
        # 본문 너무 길면 종목명/주제 키워드 근처만 ±1100자
        idx = max(body.find(name), -1)
        if idx < 0:
            for kw in topic.split():
                if len(kw) >= 2:
                    idx = body.find(kw)
                    if idx >= 0:
                        break
        if idx >= 0 and len(body) > 2400:
            start = max(0, idx - 1100)
            end = min(len(body), idx + 1100)
            body = ("…" if start > 0 else "") + body[start:end] + ("…" if end < len(body) else "")
        elif len(body) > 2400:
            body = body[:2400] + "…"
        # 종목명 강조
        for needle in {name, name.replace(" ", "")}:
            if needle:
                body = body.replace(needle, f"[[{needle}]]")
        articles.append(f"[기사 #{i+1}] {n.get('title','')} ({n.get('office','')})\n{body}")

    article_str = "\n\n---\n\n".join(articles) or "(본문을 가져오지 못했습니다)"
    headlines_str = "\n".join(f"- {n.get('title','')}" for n in news_list[:5] if n.get('title'))

    return f"""당신은 한국 주식시장 데이터를 객관적으로 분석하는 금융 데이터 작가입니다.
세콤달.콤 주식맛집의 자동 발행 블로그를 위해 **관리자가 지정한 종목·주제** 에 대한 분석 글을 작성하세요.

# 작업 흐름
1) 관리자가 지정한 [주제] 와 [추가 메모] 를 글의 핵심 축으로 잡는다.
2) [기사 본문] 에서 해당 종목 관련 사실·인과를 추출 (다른 종목 이야기·일반 시황은 제외).
3) [최근 시세 흐름] 의 가격·거래량·수급 데이터를 결합한다.
4) 매크로 배경 → 산업 영향 → 종목 고유 이벤트 → 시장 반응(가격·거래량) 의 인과를 한 글로.

# 절대 규칙
1. [기사 본문], [데이터], [최근 시세] 만 사용. 그 밖의 추측·창작 금지.
2. **원문 카피 금지**. paraphrase 필수. 직접 인용은 ≤15자 따옴표 한 번만.
3. 매수/매도 권유 금지. 구체적 목표가/손절가 제시 금지.
4. 환각 방지: 자료에 없는 인물·기업명·계약·실적 수치 만들지 않기.
5. 한국어 평이체 ('~합니다' 톤). 마크다운 헤더 없음. 종목명은 **굵게** 한 번만.
6. 다른 종목 이름이 자료에 등장해도 분석 대상은 오직 [[{name}]]. 다른 종목은 "동일 테마 종목들도 동반…" 정도로만.
7. 자료가 부족하면 "구체적 호재가 보도에서 명확히 드러나지 않아…" 식 보수적 처리.
8. {TONE_HINTS.get(tone, TONE_HINTS['analysis'])}

# 출력 형식
다음 4개 섹션을 마크다운으로 작성:

## 📌 핵심 요약
3~4문장으로 무슨 일이고 왜 중요한지.

## 📰 뉴스로 본 배경
[기사 본문] 의 인과를 paraphrase. 매크로 → 산업 → 종목 흐름.

## 📈 최근 주가·거래 흐름
[최근 시세] 의 숫자를 활용해 가격·거래량·수급 변화를 자체 서술.

## 🔍 종합 코멘트
관리자 [주제] 관점에서 짧게 마무리 (2~3문장). 추세 지속 여부의 가늠 포인트 한 줄 포함 가능.

# 종목 데이터
- 종목명: {name}
- 종목코드: {code}
- 업종: {industry or "(미상)"}
- 사업: {products or "(미상)"}

# 관리자 지정 주제
{topic}

# 추가 메모
{notes or "(없음)"}

# 최근 시세 흐름 (자동 집계)
{price_summary or "(시세 데이터 부족)"}

# 기사 본문 (네이버 종목 뉴스 — [[{name}]] 으로 강조)
{article_str}

# 참고 헤드라인
{headlines_str or "(없음)"}

# 출력 (위 4개 섹션의 마크다운 본문만):"""


# ── 요청 1건 처리 ────────────────────────────────
def slugify(text: str, max_len: int = 40) -> str:
    """슬러그 — 안정적인 URL 을 위해 ASCII 만 허용. 한글은 제거됨."""
    s = re.sub(r"[^\w\-]+", "-", text or "", flags=re.ASCII).strip("-").lower()
    s = re.sub(r"-+", "-", s)
    return s[:max_len] or "post"


def process_one(req: dict) -> Optional[Path]:
    rid = req["id"]
    code = req["stock_code"]
    name = req["stock_name"]
    topic = req["topic"]
    logger.info("[blog-req] processing %s — %s (%s) topic=%r", rid[:8], name, code, topic[:30])

    # processing 으로 락 — race condition 방지
    if not update_request(rid, status="processing"):
        logger.warning("[blog-req] %s 락 실패", rid[:8])
        return None

    try:
        # 1) 뉴스 수집 + 본문 fetch
        news = fetch_news(code, n=6)
        for it in news[:3]:
            link = it.get("link")
            if link:
                it["fullBody"] = fetch_article_body(link)

        # 2) 시세 요약
        price_summary = summarize_price_action(code, name)

        # 3) 메타
        meta_all = load_db_meta()
        meta = meta_all.get(code, {})

        # 4) Claude 호출
        prompt = build_prompt(req, news, price_summary, meta)
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY 미설정")
        body = call_anthropic(prompt, max_tokens=1500, temperature=0.5)
        if not body or len(body) < 200:
            raise RuntimeError(f"LLM 응답 부족 (길이 {len(body)})")
        body = re.sub(r"^\s*```.*?\n|```\s*$", "", body, flags=re.MULTILINE).strip()

        # 5) 마크다운 파일 작성 — slug 는 ASCII (code + timestamp + 요청 ID 짧은 prefix).
        # 같은 분에 같은 종목 여러 요청 들어와도 충돌 안 나도록 request id 8자 포함.
        date = datetime.now(KST).strftime("%Y-%m-%d")
        ts = datetime.now(KST).strftime('%y%m%d%H%M')
        topic_ascii = slugify(topic, 20)
        rid_short = rid.replace("-", "")[:8]
        slug_parts = ["custom", code]
        if topic_ascii:
            slug_parts.append(topic_ascii)
        slug_parts.append(ts)
        slug_parts.append(rid_short)
        slug = "-".join(slug_parts)
        title = f"{name} — {topic[:60]}"
        summary = (
            f"{name}({code}) 분석 — {topic[:140]}"
        )

        def yq(s):
            return '"' + s.replace('"', "'") + '"'

        md = "\n".join([
            "---",
            f"title: {yq(title)}",
            f"date: {date}",
            f"slug: {slug}",
            f"summary: {yq(summary)}",
            "tags: [관리자, 종목분석, " + (meta.get("industry") or "테마") + "]",
            "---",
            "",
            f"# {title}",
            "",
            f"*{datetime.now(KST).strftime('%Y년 %m월 %d일 %H:%M KST')} 발행 — 관리자 요청 분석 글*",
            "",
            body.strip(),
            "",
            "---",
            "",
            "**📰 참고한 뉴스 (네이버 종목 뉴스)**",
            "",
        ])
        for n in news[:5]:
            t = (n.get("title") or "")[:90]
            office = n.get("office") or ""
            link = n.get("link") or ""
            dt = (n.get("datetime") or "")[:8]
            dt_fmt = f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}" if len(dt) >= 8 else ""
            byline = " · ".join(x for x in [office, dt_fmt] if x)
            if link:
                md += f"\n- [{t}]({link}) — _{byline}_"
            else:
                md += f"\n- {t} — _{byline}_"

        md += (
            "\n\n---\n\n"
            "*본 글은 관리자가 지정한 종목과 주제를 바탕으로 자동 수집된 데이터(시세 + 네이버 종목 뉴스 + Claude Haiku 분석) 를 결합해 자동 생성되었습니다. "
            "투자 판단의 참고 자료로만 활용해 주시고, 매수·매도 권유가 아닙니다.*\n"
        )

        POSTS_DIR.mkdir(parents=True, exist_ok=True)
        path = POSTS_DIR / f"{date}-{slug}.md"
        path.write_text(md, encoding="utf-8")

        # 6) DB 갱신
        update_request(rid, status="done", result_slug=slug, error=None)
        logger.info("[blog-req] %s done → %s", rid[:8], slug)
        return path
    except Exception as e:
        logger.exception("[blog-req] %s 실패", rid[:8])
        update_request(rid, status="failed", error=str(e)[:500])
        return None


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.warning("[blog-req] SUPABASE 환경변수 없음 — 스킵")
        return 0

    pending = fetch_pending_requests()
    if not pending:
        logger.info("[blog-req] pending 요청 없음")
        return 0

    logger.info("[blog-req] %d 건 처리 시작", len(pending))
    written = []
    for req in pending:
        p = process_one(req)
        if p:
            written.append(p)

    logger.info("[blog-req] 처리 완료: %d 건 글 생성", len(written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
