"""
Markdown 기반 정적 블로그 빌더.

사용법:
    python -m batch.build_blog

입력: web/posts/*.md  (YAML frontmatter + 본문)
출력:
    web/blog/index.html      글 목록 페이지
    web/blog/{slug}.html     글 본문 페이지
    web/rss.xml              RSS 피드

Frontmatter 예시:
    ---
    title: 2026년 1분기 수급 분석
    date: 2026-04-18
    slug: 2026-q1-supply
    summary: 한 줄 요약
    tags: [삼성전자, 수급]
    cover: /assets/blog/cover.webp   # 선택
    ---

    본문 Markdown...
"""

from __future__ import annotations

import html
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import markdown as md_lib
import yaml

# ── 경로 ────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "web" / "posts"
BLOG_DIR = ROOT / "web" / "blog"
RSS_PATH = ROOT / "web" / "rss.xml"
SITE_URL = "https://secomdal.com"
SITE_NAME = "세콤달.콤 주식맛집"
KST = timezone(timedelta(hours=9))


# ── 데이터 모델 ────────────────────────────────────────
@dataclass
class Post:
    slug: str
    title: str
    date: str                 # YYYY-MM-DD
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    cover: Optional[str] = None
    body_html: str = ""
    source_path: Path | None = None


# ── 파싱 ────────────────────────────────────────────────
FM_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_post(path: Path) -> Post:
    raw = path.read_text(encoding="utf-8")
    m = FM_RE.match(raw)
    if not m:
        raise ValueError(f"{path.name}: YAML frontmatter가 없습니다")
    fm: dict[str, Any] = yaml.safe_load(m.group(1)) or {}
    body_md = m.group(2).strip()

    # 필수 필드
    if not fm.get("title"):
        raise ValueError(f"{path.name}: title 누락")
    date_val = fm.get("date")
    if not date_val:
        raise ValueError(f"{path.name}: date 누락")
    if isinstance(date_val, datetime):
        date_str = date_val.strftime("%Y-%m-%d")
    else:
        date_str = str(date_val)

    slug = fm.get("slug") or path.stem
    slug = re.sub(r"[^a-zA-Z0-9가-힣\-]", "-", slug).strip("-").lower() or path.stem

    body_html = md_lib.markdown(
        body_md,
        extensions=[
            "fenced_code",
            "tables",
            "toc",
            "sane_lists",
            "nl2br",
        ],
        output_format="html5",
    )

    return Post(
        slug=slug,
        title=str(fm["title"]),
        date=date_str,
        summary=str(fm.get("summary") or ""),
        tags=list(fm.get("tags") or []),
        cover=fm.get("cover"),
        body_html=body_html,
        source_path=path,
    )


# ── 템플릿 ─────────────────────────────────────────────
HEAD_COMMON = """<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-3092853375685399"
     crossorigin="anonymous"></script>
<meta name="google-adsense-account" content="ca-pub-3092853375685399">
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064%2064%22%3E%3Ctext%20y%3D%2252%22%20font-size%3D%2256%22%3E%F0%9F%93%88%3C%2Ftext%3E%3C%2Fsvg%3E" />
<script src="/assets/nav.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
<script defer src="/assets/auth.js"></script>
<link rel="stylesheet" href="/assets/styles.css" />"""

HOME_SVG = """<svg class="home-ico" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
  <path d="M11.47 2.47a.75.75 0 0 1 1.06 0l9 9a.75.75 0 1 1-1.06 1.06l-.72-.72V20a2 2 0 0 1-2 2h-3.25a.75.75 0 0 1-.75-.75V16a1 1 0 0 0-1-1h-2a1 1 0 0 0-1 1v5.25a.75.75 0 0 1-.75.75H6a2 2 0 0 1-2-2v-8.19l-.72.72a.75.75 0 1 1-1.06-1.06l9-9z"/>
</svg>"""


def layout(title: str, subtitle: str, body: str, description: str = "", canonical: str = "") -> str:
    desc_tag = f'<meta name="description" content="{html.escape(description)}" />' if description else ""
    canon_tag = f'<link rel="canonical" href="{canonical}" />' if canonical else ""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<title>{html.escape(title)} — {SITE_NAME}</title>
{desc_tag}
{canon_tag}
{HEAD_COMMON}
</head>
<body class="page-about">
<div class="topbar">
  <header>
    <div class="nav-left">
      <a href="/" class="home-btn" aria-label="홈으로" title="홈">{HOME_SVG}</a>
      <h1 class="brand-h1"><span class="brand-name"><span class="bc c1">세</span><span class="bc c2">콤</span><span class="bc c3">달</span><span class="bc c4">.</span><span class="bc c1">콤</span></span> <span class="brand-sub">주식<span class="brand-mat">맛</span>집</span></h1>
      <span class="subtitle">{html.escape(subtitle)}</span>
    </div>
    <div class="nav-right">
      <div id="authSlot" class="auth-slot" aria-live="polite"></div><script src="/assets/auth-prerender.js"></script>
      <button class="theme-toggle" id="themeToggle" aria-label="테마 전환" onclick="toggleTheme()">☀</button>
      <button class="nav-toggle" aria-label="메뉴" onclick="toggleNav()">
        <span></span><span></span><span></span>
      </button>
    </div>
  </header>
</div>

<nav class="nav-drawer" id="navDrawer">
  <a href="/">Home</a>
  <a href="/chart">Stock Chart</a>
  <a href="/blog">Blog</a>
  <a href="/about">About</a>
  <a href="/contact">Contact Us</a>
</nav>
<div class="nav-backdrop" id="navBackdrop" onclick="toggleNav()"></div>

{body}

<footer>
  데이터 제공: FinanceDataReader · pykrx · Naver Finance &nbsp;|&nbsp;
  <a href="/">Home</a> &middot; <a href="/blog">Blog</a> &middot;
  <a href="/about">About</a> &middot; <a href="/contact">Contact</a> &middot;
  <a href="/privacy">Privacy</a>
</footer>

</body>
</html>
"""


def render_post(post: Post, all_posts: list[Post]) -> str:
    idx = next((i for i, p in enumerate(all_posts) if p.slug == post.slug), -1)
    prev_p = all_posts[idx + 1] if idx + 1 < len(all_posts) else None  # 최신→과거 정렬 기준
    next_p = all_posts[idx - 1] if idx > 0 else None

    tags_html = ""
    if post.tags:
        chips = "".join(f'<span class="blog-tag">#{html.escape(t)}</span>' for t in post.tags)
        tags_html = f'<div class="blog-tags">{chips}</div>'

    cover_html = ""
    if post.cover:
        cover_html = f'<img class="blog-cover" src="{html.escape(post.cover)}" alt="" loading="lazy" />'

    nav_html = '<nav class="blog-nav">'
    if next_p:
        nav_html += f'<a class="blog-nav-prev" href="/blog/{next_p.slug}">← {html.escape(next_p.title)}</a>'
    else:
        nav_html += '<span></span>'
    if prev_p:
        nav_html += f'<a class="blog-nav-next" href="/blog/{prev_p.slug}">{html.escape(prev_p.title)} →</a>'
    else:
        nav_html += '<span></span>'
    nav_html += '</nav>'

    body = f"""
<main class="static-main">
  <article class="blog-article">
    <header class="blog-article-head">
      <div class="blog-breadcrumb"><a href="/blog">← 블로그 목록</a></div>
      <h2>{html.escape(post.title)}</h2>
      <div class="blog-meta">
        <time datetime="{post.date}">{post.date}</time>
        {tags_html}
      </div>
      {cover_html}
    </header>

    <div class="blog-body">
      {post.body_html}
    </div>

    {nav_html}

    <div class="blog-cta">
      <p>관련 종목 차트가 궁금하다면?</p>
      <a class="cta" href="/chart">세콤달.콤 주식맛집 열기 →</a>
    </div>
  </article>

  <div class="ad-slot ad-bottom" aria-label="광고">
    <span class="ad-placeholder">광고</span>
  </div>
</main>
"""
    return layout(
        title=post.title,
        subtitle="Blog",
        body=body,
        description=post.summary or post.title,
        canonical=f"{SITE_URL}/blog/{post.slug}",
    )


def render_index(posts: list[Post]) -> str:
    if not posts:
        cards = '<div class="empty">아직 작성된 글이 없습니다.</div>'
    else:
        items = []
        for p in posts:
            tag_chips = "".join(
                f'<span class="blog-tag">#{html.escape(t)}</span>' for t in p.tags
            )
            cover = (
                f'<img class="blog-card-cover" src="{html.escape(p.cover)}" alt="" loading="lazy" />'
                if p.cover else ""
            )
            items.append(f"""
<a class="blog-card" href="/blog/{p.slug}">
  {cover}
  <div class="blog-card-body">
    <div class="blog-card-date">{p.date}</div>
    <h3 class="blog-card-title">{html.escape(p.title)}</h3>
    {f'<p class="blog-card-summary">{html.escape(p.summary)}</p>' if p.summary else ''}
    {f'<div class="blog-tags">{tag_chips}</div>' if tag_chips else ''}
  </div>
</a>""")
        cards = '<div class="blog-grid">' + "".join(items) + "</div>"

    body = f"""
<main class="static-main">
  <section class="blog-hero">
    <h2>📝 세콤달.콤 주식맛집 블로그</h2>
    <p class="lead">종목 분석·수급 인사이트·시장 동향을 기록합니다.</p>
  </section>

  {cards}

  <div class="ad-slot ad-bottom" aria-label="광고">
    <span class="ad-placeholder">광고</span>
  </div>
</main>
"""
    return layout(
        title="블로그",
        subtitle="Blog",
        body=body,
        description="세콤달.콤 주식맛집의 종목 분석 및 시장 인사이트 블로그",
        canonical=f"{SITE_URL}/blog",
    )


def render_rss(posts: list[Post]) -> str:
    now = datetime.now(KST).strftime("%a, %d %b %Y %H:%M:%S +0900")
    items = []
    for p in posts[:20]:  # 최신 20개만
        pub = f"{p.date} 09:00:00 +0900"
        try:
            pub_dt = datetime.strptime(p.date, "%Y-%m-%d").replace(tzinfo=KST)
            pub = pub_dt.strftime("%a, %d %b %Y %H:%M:%S +0900")
        except ValueError:
            pass
        items.append(f"""    <item>
      <title>{html.escape(p.title)}</title>
      <link>{SITE_URL}/blog/{p.slug}</link>
      <guid isPermaLink="true">{SITE_URL}/blog/{p.slug}</guid>
      <pubDate>{pub}</pubDate>
      <description>{html.escape(p.summary or p.title)}</description>
    </item>""")
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{SITE_NAME} Blog</title>
    <link>{SITE_URL}/blog</link>
    <description>KOSPI·KOSDAQ 종목 분석과 시장 인사이트</description>
    <language>ko-kr</language>
    <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>
"""
    return rss


# ── 빌드 ────────────────────────────────────────────────
def build() -> int:
    if not POSTS_DIR.exists():
        POSTS_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[blog] {POSTS_DIR} 생성됨")

    md_files = sorted(POSTS_DIR.glob("*.md"))
    if not md_files:
        print("[blog] 작성된 글이 없습니다. web/posts/*.md 에 글을 추가하세요.")

    posts: list[Post] = []
    for f in md_files:
        try:
            posts.append(parse_post(f))
        except Exception as e:
            print(f"[blog] {f.name} 파싱 실패: {e}", file=sys.stderr)

    # 최신순 정렬
    posts.sort(key=lambda p: (p.date, p.slug), reverse=True)

    # 출력 디렉토리 초기화
    if BLOG_DIR.exists():
        for item in BLOG_DIR.iterdir():
            if item.is_file():
                item.unlink()
    else:
        BLOG_DIR.mkdir(parents=True, exist_ok=True)

    # 개별 글
    for p in posts:
        out = BLOG_DIR / f"{p.slug}.html"
        out.write_text(render_post(p, posts), encoding="utf-8")
        print(f"[blog] {out.relative_to(ROOT)}")

    # 목록 페이지
    index_html = render_index(posts)
    (BLOG_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print(f"[blog] web/blog/index.html")

    # RSS
    RSS_PATH.write_text(render_rss(posts), encoding="utf-8")
    print(f"[blog] web/rss.xml")

    print(f"[blog] 완료: {len(posts)} 글 생성")
    return 0


if __name__ == "__main__":
    sys.exit(build())
