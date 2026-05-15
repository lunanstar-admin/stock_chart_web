"""Unsplash 무료 스톡 사진을 블로그 글의 hero image 로 자동 첨부.

매일 또는 신규 글 발행 시 1회 실행. 멱등 — cover 가 이미 있는 글은 건너뜀.

환경변수:
    UNSPLASH_ACCESS_KEY  : Unsplash Developer 사이트에서 발급 (무료)

처리 흐름:
    1) web/posts/*.md 순회
    2) frontmatter 에 cover 가 없는 글만 처리
    3) tags + 제목 키워드로 Unsplash 검색
    4) 첫 결과 이미지 다운로드 → web/blog/img/{slug}.jpg
    5) frontmatter 에 cover / cover_alt / cover_credit / cover_credit_url 추가
    6) Unsplash 의 download trigger 엔드포인트 호출 (analytics 의무 요건)

Unsplash 약관:
    - 다운로드 시 GET /photos/{id}/download endpoint trigger 필요 (analytics)
    - 사진 표시 시 photographer + "on Unsplash" attribution 필수
    - UTM source/medium 파라미터 부착 권장
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
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "web" / "posts"
IMG_DIR = ROOT / "web" / "blog" / "img"

UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
UTM = "?utm_source=secomdal&utm_medium=referral"

# 처리 대상 슬러그 (자동 데이터 글 포함 — 모든 글에 이미지 추가)
# 다만 daily-/batch-/market-brief- 의 경우 짧은 글이라 이미지가 더 중요.
AUTO_PREFIXES = ("daily-", "batch-", "market-brief-")


# ── Unsplash API 호출 ────────────────────────────────────
def _search_photo(query: str, timeout: float = 15.0) -> Optional[dict]:
    """검색 결과 첫 번째 사진의 메타데이터 반환."""
    if not UNSPLASH_KEY:
        return None
    q = urllib.parse.quote(query)
    url = (
        "https://api.unsplash.com/search/photos"
        f"?query={q}&per_page=5&orientation=landscape&content_filter=high"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Client-ID {UNSPLASH_KEY}",
            "Accept-Version": "v1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")[:200]
        except Exception:
            pass
        logger.warning("[unsplash] search HTTP %s for %r: %s", e.code, query, body)
        return None
    except (urllib.error.URLError, TimeoutError) as e:
        logger.warning("[unsplash] search failed for %r: %s", query, e)
        return None
    results = data.get("results") or []
    if not results:
        logger.info("[unsplash] no results for %r", query)
        return None
    return results[0]


def _trigger_download(photo: dict, timeout: float = 8.0) -> None:
    """Unsplash analytics 의무 endpoint. 응답은 무시해도 됨."""
    dl_url = (photo.get("links") or {}).get("download_location")
    if not dl_url:
        return
    if "client_id" not in dl_url:
        sep = "&" if "?" in dl_url else "?"
        dl_url = f"{dl_url}{sep}client_id={UNSPLASH_KEY}"
    req = urllib.request.Request(dl_url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
    except Exception:
        pass  # analytics 트리거 실패는 무시


def _download_image(photo: dict, dest: Path, timeout: float = 30.0) -> bool:
    """사진의 regular(1080px) 버전 다운로드. 성공 시 True."""
    urls = photo.get("urls") or {}
    img_url = urls.get("regular") or urls.get("small")
    if not img_url:
        return False
    try:
        req = urllib.request.Request(img_url, headers={"User-Agent": "secomdal-bot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
    except Exception as e:
        logger.warning("[unsplash] download failed %s: %s", img_url, e)
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


# ── frontmatter 다루기 ────────────────────────────────────
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _has_cover(text: str) -> bool:
    m = FM_RE.match(text)
    if not m:
        return False
    return bool(re.search(r"^cover:\s*\S", m.group(1), re.MULTILINE))


def _parse_frontmatter(text: str) -> tuple[str, str, str]:
    """text → (head, fm_body, body). fm_body 는 --- 사이 raw text."""
    m = FM_RE.match(text)
    if not m:
        return "", "", text
    return "---\n", m.group(1), "\n---\n" + m.group(2)


def _add_cover_to_frontmatter(text: str, cover: str, alt: str,
                              credit_name: str, credit_url: str) -> str:
    """frontmatter 의 끝에 cover 필드들 추가."""
    head, fm, rest = _parse_frontmatter(text)
    if not head:
        return text
    addition = (
        f"\ncover: {json.dumps(cover, ensure_ascii=False)}"
        f"\ncover_alt: {json.dumps(alt, ensure_ascii=False)}"
        f"\ncover_credit: {json.dumps(credit_name, ensure_ascii=False)}"
        f"\ncover_credit_url: {json.dumps(credit_url, ensure_ascii=False)}"
    )
    return head + fm.rstrip() + addition + rest


# ── 검색 쿼리 만들기 ────────────────────────────────────
# 한국어 글 → 영문 키워드로 매핑 (Unsplash 는 영어 결과가 압도적으로 많음)
KEYWORD_MAP = {
    "AI": "artificial intelligence",
    "반도체": "semiconductor",
    "전력": "power infrastructure",
    "데이터센터": "data center",
    "자율주행": "self driving car",
    "로봇": "robot",
    "휴머노이드": "humanoid robot",
    "전기차": "electric vehicle",
    "배터리": "battery",
    "통신": "telecommunication network",
    "SMR": "small modular reactor",
    "원자력": "nuclear power",
    "양자": "quantum computing",
    "우주": "space rocket",
    "바이오": "biotech laboratory",
    "헬스케어": "healthcare technology",
    "중동": "middle east",
    "방산": "defense industry",
    "건설": "construction site",
    "조선": "shipbuilding",
    "해운": "container ship",
    "정유": "oil refinery",
    "금융": "financial market",
    "은행": "bank building",
    "보험": "insurance office",
    "차트": "stock chart",
    "주식": "stock market",
    "코스피": "korean stock market",
    "환율": "currency exchange",
    "수급": "trading",
    "거래량": "stock trading",
    "PER": "stock valuation",
    "기술적지표": "stock chart analysis",
    "캔들": "candlestick chart",
    "휴장일": "calendar schedule",
    "용어집": "dictionary book",
    "관계도": "business network",
    "지주회사": "holding company",
    "운영": "server operations",
    "인프라": "infrastructure",
    "GitHub Actions": "ci cd pipeline",
    "장애대응": "server monitoring",
    # 자동 글 (시장 분석·일일 랭킹) 태그 매핑
    "시장분석": "financial market analysis",
    "마감시황": "stock market closing",
    "시황": "stock market closing",
    "주도주": "market leaders trading",
    "급등주": "stock rising chart",
    "테마분석": "industry sector analysis",
    "인기종목": "popular stocks",
    "뉴스": "financial news",
    "외국인": "foreign investor",
    "기관": "institutional investor",
    "개인": "retail investor trading",
    "랭킹": "stock ranking chart",
    "TOP10": "stock ranking chart",
    "시가총액": "stock market capitalization",
    "수익률": "investment returns",
    "거래대금": "stock trading volume",
}

# 슬러그 접두어 → fallback 검색어. KEYWORD_MAP 으로 매핑이 안 됐을 때 사용.
SLUG_PREFIX_FALLBACK = {
    "daily-wrap-": "stock market closing",
    "daily-mcap-": "stock market capitalization",
    "daily-gainer-": "stock rising chart",
    "daily-volume-": "stock trading volume",
    "daily-foreign-": "foreign investor trading",
    "daily-": "financial market analysis",
    "market-brief-": "stock market analysis",
    "batch-": "server operations",
    "theme-": "industry analysis",
    "custom-": "stock chart trading",
}


def _build_query(title: str, tags: list[str], slug: str) -> str:
    """제목·태그를 영문 키워드 1~3개로 변환해 query 구성."""
    candidates: list[str] = []

    # 태그에서 매핑 시도
    for t in (tags or [])[:5]:
        t_clean = t.strip()
        if t_clean in KEYWORD_MAP:
            candidates.append(KEYWORD_MAP[t_clean])
        else:
            # 한글이 아닌 영문 태그면 그대로
            if t_clean and not re.search(r"[가-힣]", t_clean):
                candidates.append(t_clean.lower())

    # 제목에서도 매핑 시도
    for ko, en in KEYWORD_MAP.items():
        if ko in title and en not in candidates:
            candidates.append(en)
            if len(candidates) >= 3:
                break

    # 슬러그 접두어 fallback — 자동 글에 특히 중요
    if not candidates:
        for prefix, fallback in SLUG_PREFIX_FALLBACK.items():
            if slug.startswith(prefix):
                candidates.append(fallback)
                break

    # 그래도 비어있으면 일반 기본값
    if not candidates:
        if "ai" in slug:
            candidates.append("artificial intelligence")
        elif "market" in slug or "stock" in slug:
            candidates.append("stock market")
        else:
            candidates.append("finance technology")

    return " ".join(candidates[:3])


def _extract_meta(text: str) -> dict:
    """frontmatter 에서 title/slug/tags 추출."""
    m = FM_RE.match(text)
    if not m:
        return {}
    fm = m.group(1)
    out: dict = {}
    title_m = re.search(r'^title:\s*"?([^"\n]+)"?', fm, re.MULTILINE)
    if title_m:
        out["title"] = title_m.group(1).strip()
    slug_m = re.search(r'^slug:\s*"?([^"\n]+)"?', fm, re.MULTILINE)
    if slug_m:
        out["slug"] = slug_m.group(1).strip()
    tags_m = re.search(r'^tags:\s*\[(.*?)\]', fm, re.MULTILINE)
    if tags_m:
        raw = tags_m.group(1)
        out["tags"] = [t.strip().strip('"').strip("'") for t in raw.split(",") if t.strip()]
    return out


# ── 메인 ────────────────────────────────────────────────
def enrich_one(path: Path, sleep_after: float = 1.5) -> bool:
    """한 글에 cover 추가. 성공 시 True."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("[unsplash] read fail %s: %s", path.name, e)
        return False

    if _has_cover(text):
        return False  # 이미 처리됨

    meta = _extract_meta(text)
    title = meta.get("title", "")
    tags = meta.get("tags", [])
    slug = meta.get("slug") or path.stem

    query = _build_query(title, tags, slug)
    logger.info("[unsplash] %s — query=%r", slug, query)

    photo = _search_photo(query)

    # 1차 검색 실패 시 generic fallback 으로 재시도
    if not photo:
        fallback_query = "stock market chart"
        if slug.startswith("batch-"):
            fallback_query = "server operations"
        elif slug.startswith("guide/") or "guide" in slug:
            fallback_query = "finance education"
        logger.info("[unsplash] %s — retry with %r", slug, fallback_query)
        photo = _search_photo(fallback_query)

    if not photo:
        logger.info("[unsplash] %s — no photo even with fallback, skip", slug)
        return False

    # 다운로드
    img_filename = f"{slug}.jpg"
    img_path = IMG_DIR / img_filename
    if not _download_image(photo, img_path):
        return False

    # analytics 트리거
    _trigger_download(photo)

    # 메타 추출
    user = photo.get("user") or {}
    user_name = user.get("name") or user.get("username") or "Unsplash"
    user_url = (user.get("links") or {}).get("html") or "https://unsplash.com"
    user_url_attr = f"{user_url}{UTM}"
    alt = photo.get("alt_description") or photo.get("description") or title

    # frontmatter 업데이트
    cover_url = f"/blog/img/{img_filename}"
    new_text = _add_cover_to_frontmatter(text, cover_url, alt, user_name, user_url_attr)
    path.write_text(new_text, encoding="utf-8")

    logger.info("[unsplash] %s — cover added: %s by %s", slug, cover_url, user_name)

    # rate limit 보호 (Demo tier: 50 req/hour ≈ 1.2/min)
    time.sleep(sleep_after)
    return True


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10, help="이번 실행에서 처리할 최대 글 수")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not UNSPLASH_KEY:
        logger.warning("[unsplash] UNSPLASH_ACCESS_KEY 미설정 — 스킵")
        return 0

    # 최신순으로 정렬해 최근 글부터 우선 처리
    paths = sorted(POSTS_DIR.glob("*.md"), reverse=True)
    processed = 0
    for p in paths:
        if processed >= args.limit:
            break
        if enrich_one(p):
            processed += 1

    logger.info("[unsplash] 완료: %d 글에 cover 추가", processed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
