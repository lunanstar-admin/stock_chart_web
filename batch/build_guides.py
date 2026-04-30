"""정적 가이드 페이지 생성 — 기술적 지표, 수급, 캔들, 용어집.

수동 또는 매월 1회 실행:
    python -m batch.build_guides

출력:
    web/guide/technical-indicators.html
    web/guide/supply-demand.html
    web/guide/candle-patterns.html
    web/glossary.html
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")
SITE_URL = "https://secomdal.com"
SITE_NAME = "세콤달.콤 주식맛집"

HOME_SVG = """<svg class="home-ico" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
  <path d="M11.47 2.47a.75.75 0 0 1 1.06 0l9 9a.75.75 0 1 1-1.06 1.06l-.72-.72V20a2 2 0 0 1-2 2h-3.25a.75.75 0 0 1-.75-.75V16a1 1 0 0 0-1-1h-2a1 1 0 0 0-1 1v5.25a.75.75 0 0 1-.75.75H6a2 2 0 0 1-2-2v-8.19l-.72.72a.75.75 0 1 1-1.06-1.06l9-9z"/>
</svg>"""


def page(slug: str, title: str, subtitle: str, description: str, body: str, keywords: str) -> str:
    canonical = f"{SITE_URL}/{slug}"
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<title>{title} — {SITE_NAME}</title>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<meta name="description" content="{description}" />
<meta name="keywords" content="{keywords}" />
<meta name="author" content="세콤달.콤" />
<meta name="robots" content="index, follow, max-image-preview:large" />
<link rel="canonical" href="{canonical}" />
<meta property="og:type" content="article" />
<meta property="og:site_name" content="{SITE_NAME}" />
<meta property="og:title" content="{title}" />
<meta property="og:description" content="{description}" />
<meta property="og:locale" content="ko_KR" />
<meta property="og:image" content="{SITE_URL}/og-image.png" />
<meta property="og:url" content="{canonical}" />
<link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064%2064%22%3E%3Ctext%20y%3D%2252%22%20font-size%3D%2256%22%3E%F0%9F%93%88%3C%2Ftext%3E%3C%2Fsvg%3E" />
<script src="/assets/nav.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
<script defer src="/assets/auth.js"></script>
<link rel="stylesheet" href="/assets/styles.css" />
<style>
.guide-content h2 {{ font-size: 26px; margin: 0 0 8px; }}
.guide-content .lead {{ color: var(--text-secondary); font-size: 15px; margin-bottom: 20px; line-height: 1.7; }}
.guide-content section {{ margin: 24px 0; padding: 16px 18px; background: var(--card,#fff); border: 1px solid var(--border,#e5e7eb); border-radius: 8px; }}
.guide-content section h3 {{ font-size: 18px; margin: 0 0 10px; color: var(--text-primary); }}
.guide-content section h4 {{ font-size: 15px; margin: 14px 0 6px; }}
.guide-content p, .guide-content li {{ line-height: 1.75; font-size: 14px; }}
.guide-content ul, .guide-content ol {{ padding-left: 22px; }}
.guide-content code.formula {{ display: inline-block; background: var(--bg-secondary,#f1f5f9); padding: 2px 6px; border-radius: 4px; font-family: ui-monospace,monospace; font-size: 13px; }}
.guide-content .callout {{ background: rgba(245,158,11,0.08); border-left: 3px solid #f59e0b; padding: 10px 14px; margin: 12px 0; border-radius: 0 6px 6px 0; font-size: 13px; }}
.guide-content .callout strong {{ color: #b45309; }}
.guide-toc {{ background: var(--bg-secondary,#f8fafc); padding: 14px 18px; border-radius: 8px; margin-bottom: 20px; }}
.guide-toc strong {{ display: block; margin-bottom: 6px; font-size: 13px; color: var(--text-secondary); }}
.guide-toc a {{ display: inline-block; margin-right: 12px; font-size: 13px; }}
.guide-related {{ margin-top: 30px; padding: 16px; background: var(--bg-secondary,#f8fafc); border-radius: 8px; }}
.guide-related a {{ display: inline-block; margin-right: 14px; font-size: 13px; }}
</style>
</head>
<body class="page-about">
<div class="topbar">
  <header>
    <div class="nav-left">
      <a href="/" class="home-btn" aria-label="홈으로" title="홈">{HOME_SVG}</a>
      <h1 class="brand-h1"><span class="brand-name"><span class="bc c1">세</span><span class="bc c2">콤</span><span class="bc c3">달</span><span class="bc c4">.</span><span class="bc c1">콤</span></span> <span class="brand-sub">주식<span class="brand-mat">맛</span>집</span></h1>
      <span class="subtitle">{subtitle}</span>
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
  <a href="/relations">그룹사 관계도</a>
  <a href="/guide/technical-indicators">기술적 지표</a>
  <a href="/guide/supply-demand">투자자 수급</a>
  <a href="/guide/candle-patterns">캔들 차트</a>
  <a href="/glossary">용어집</a>
  <a href="/blog">Blog</a>
  <a href="/about">About</a>
  <a href="/contact">Contact Us</a>
</nav>
<div class="nav-backdrop" id="navBackdrop" onclick="toggleNav()"></div>

<main class="static-main">
  <article class="about-content guide-content">
    {body}

    <div class="guide-related">
      <strong>📚 함께 읽기</strong><br>
      <a href="/guide/technical-indicators">기술적 지표 완전 가이드</a>
      <a href="/guide/supply-demand">투자자 수급 읽는 법</a>
      <a href="/guide/candle-patterns">캔들 차트 기초</a>
      <a href="/glossary">주식 용어집</a>
      <a href="/chart">전종목 차트 보기 →</a>
    </div>
  </article>
</main>

<footer>
  데이터 제공: FinanceDataReader · pykrx · Naver Finance &nbsp;|&nbsp;
  <a href="/">Home</a> &middot; <a href="/blog">Blog</a> &middot; <a href="/about">About</a> &middot; <a href="/contact">Contact</a> &middot; <a href="/privacy">Privacy</a>
</footer>
</body>
</html>"""


# ──────────────────────────────────────────────────────
# 1) 기술적 지표 완전 가이드
# ──────────────────────────────────────────────────────
TECH_BODY = """
<h2>📈 기술적 지표 완전 가이드 — MACD · RSI · 볼린저밴드 · OBV · MFI</h2>
<p class="lead">
  주가 차트 위에 그려지는 보조 지표들은 단순한 그래프가 아니라, 가격과 거래량을 수학적으로 가공해
  <strong>매매 시점의 힌트</strong>를 시각화한 도구입니다. 이 가이드는 세콤달.콤 주식맛집 차트에서 제공하는
  주요 기술적 지표 6가지의 계산 원리, 해석 방법, 그리고 실전에서 자주 빠지는 함정을 한 번에 정리합니다.
  지표는 만능이 아니며, 시장의 모든 움직임을 예측할 수도 없습니다. 다만 <em>가격이 보내는 신호를
  더 명확하게 읽기 위한 보조 도구</em>로 사용한다면 매매 판단에 큰 도움이 됩니다.
</p>

<div class="guide-toc">
  <strong>📑 목차</strong>
  <a href="#sma">이동평균선</a>
  <a href="#macd">MACD</a>
  <a href="#rsi">RSI</a>
  <a href="#bb">볼린저밴드</a>
  <a href="#obv">OBV</a>
  <a href="#mfi">MFI</a>
  <a href="#combo">조합 활용</a>
  <a href="#caveat">한계</a>
</div>

<section id="sma">
  <h3>1. 이동평균선 (Moving Average, MA)</h3>
  <p>
    이동평균선은 일정 기간 동안의 종가 평균을 선으로 이은 것입니다. 단순이동평균(SMA)과
    지수이동평균(EMA)이 가장 흔하며, 세콤달 차트는 5/20/60/120일 SMA를 기본 표시합니다.
    각 기간은 단기 흐름(5·20일), 중기 추세(60일), 장기 흐름(120일)을 의미합니다.
  </p>
  <h4>골든크로스와 데드크로스</h4>
  <ul>
    <li><strong>골든크로스</strong>: 단기 이동평균이 장기 이동평균을 상향 돌파 — 상승 추세 전환 신호로 자주 인용</li>
    <li><strong>데드크로스</strong>: 반대로 단기선이 장기선을 하향 돌파 — 하락 추세 가능성</li>
    <li>다만 횡보장에서는 잦은 가짜 신호(whipsaw)가 발생하므로 거래량·다른 지표와 함께 봐야 합니다.</li>
  </ul>
  <div class="callout"><strong>실전 팁:</strong> 20일선 위에서 횡보하던 종목이 20일선을 깨고 내려오면 단기 추세 약화 신호. 60일선까지 깨면 중기 추세도 위험합니다.</div>
</section>

<section id="macd">
  <h3>2. MACD (Moving Average Convergence Divergence)</h3>
  <p>
    MACD는 단기 EMA(12일)와 장기 EMA(26일)의 차이를 그린 지표입니다. 추세의 방향과 강도를
    동시에 보여주며, 시그널선(MACD의 9일 EMA) 과의 교차로 매매 신호를 읽습니다.
  </p>
  <p><code class="formula">MACD = EMA(12) − EMA(26)</code> · <code class="formula">Signal = EMA(MACD, 9)</code> · <code class="formula">Histogram = MACD − Signal</code></p>
  <h4>해석 포인트</h4>
  <ul>
    <li>MACD가 시그널선을 <strong>상향 돌파</strong> → 매수 신호 후보</li>
    <li>MACD가 시그널선을 <strong>하향 돌파</strong> → 매도 신호 후보</li>
    <li>MACD가 0선 위에 있으면 상승 추세, 아래면 하락 추세</li>
    <li>히스토그램(막대) 길이가 짧아지면 추세 약화, 길어지면 추세 강화</li>
  </ul>
  <h4>다이버전스 (Divergence)</h4>
  <p>
    가격은 신고가를 갱신하는데 MACD는 이전 고점을 못 넘는 경우 → <strong>약세 다이버전스</strong>로,
    상승 추세 둔화의 조기 신호일 수 있습니다. 반대 케이스는 강세 다이버전스로, 하락 종목의 반등 가능성을 시사합니다.
  </p>
</section>

<section id="rsi">
  <h3>3. RSI (Relative Strength Index, 상대강도지수)</h3>
  <p>
    RSI는 일정 기간(보통 14일) 동안의 상승 폭과 하락 폭을 비교해 0~100 사이 값으로 나타낸 지표입니다.
    과매수·과매도 영역을 가늠하는 데 유용합니다.
  </p>
  <p><code class="formula">RSI = 100 − 100 / (1 + RS)</code> · <code class="formula">RS = 14일 평균 상승폭 / 14일 평균 하락폭</code></p>
  <h4>해석 기준 (전통적)</h4>
  <ul>
    <li><strong>RSI &gt; 70</strong>: 과매수 — 단기 조정 가능성</li>
    <li><strong>RSI &lt; 30</strong>: 과매도 — 단기 반등 가능성</li>
    <li>50 부근은 중립, 추세장에서는 50 이상에서 70까지, 50 이하에서 30까지 머무는 경향</li>
  </ul>
  <div class="callout"><strong>주의:</strong> 강한 추세장에서는 RSI가 70 이상에 오래 머물러도 상승이 계속될 수 있습니다. 단순히 70 넘었다고 매도하면 큰 상승을 놓칠 수 있어, MACD·이평선과 함께 봐야 합니다.</div>
</section>

<section id="bb">
  <h3>4. 볼린저밴드 (Bollinger Bands)</h3>
  <p>
    볼린저밴드는 20일 이동평균선을 중심으로, 위·아래 ±2 표준편차 거리에 띠를 그린 지표입니다.
    가격이 밴드 폭의 어디쯤 있는지로 변동성과 상대적 위치를 파악합니다.
  </p>
  <p><code class="formula">Upper = MA(20) + 2σ</code> · <code class="formula">Lower = MA(20) − 2σ</code></p>
  <h4>주요 신호</h4>
  <ul>
    <li><strong>밴드 폭 축소(Squeeze)</strong>: 변동성 잠잠 → 곧 큰 움직임 가능성</li>
    <li><strong>상단 돌파</strong>: 강세 신호이나 상단에 붙어 가는 추세장에서는 매도 신호가 아님</li>
    <li><strong>하단 이탈</strong>: 단기 약세, 다만 강한 하락장에서는 하단 따라 흘러내릴 수 있음</li>
    <li>중심선(20일 MA) 회귀 경향 — 평균 회귀 매매 전략의 기반</li>
  </ul>
</section>

<section id="obv">
  <h3>5. OBV (On Balance Volume, 누적 거래량)</h3>
  <p>
    OBV는 종가가 전일보다 오르면 그날 거래량을 더하고, 내리면 빼서 누적한 지표입니다.
    가격이 횡보해도 OBV가 우상향한다면 <strong>매집(거래량 유입)</strong>이 진행 중일 가능성을 시사합니다.
  </p>
  <h4>활용</h4>
  <ul>
    <li>OBV가 가격보다 먼저 신고가를 만들면 → 강세 다이버전스(상승 압력)</li>
    <li>OBV가 가격을 따라 신고가를 못 만들면 → 약세 다이버전스(상승 추진력 약화)</li>
    <li>거래량 자체가 적은 종목에서는 노이즈가 크므로 신뢰도가 낮음</li>
  </ul>
</section>

<section id="mfi">
  <h3>6. MFI (Money Flow Index, 자금 흐름 지수)</h3>
  <p>
    MFI는 RSI 에 거래량을 가중한 지표로, 거래대금(typical price × volume) 의 유입·유출을
    계산해 0~100 사이로 나타냅니다. RSI 가 가격만 본다면, MFI 는 <strong>"거래대금까지 본 RSI"</strong>입니다.
  </p>
  <ul>
    <li><strong>MFI &gt; 80</strong>: 자금 유입 과열 — 조정 가능성</li>
    <li><strong>MFI &lt; 20</strong>: 자금 유출 과도 — 반등 후보</li>
    <li>RSI와 함께 보면 가격·거래량 모두에서의 매수·매도 압력을 입체적으로 파악 가능</li>
  </ul>
</section>

<section id="combo">
  <h3>7. 지표 조합 활용 — 단일 지표는 위험하다</h3>
  <p>
    어떤 단일 지표도 시장을 100% 설명하지 못합니다. 실전에서는 보통 다음과 같이 <strong>2~3 개 지표를 조합</strong>해
    한 방향의 신호가 동시에 나타날 때 신뢰도를 높입니다.
  </p>
  <h4>예시 조합</h4>
  <ul>
    <li><strong>추세 추종</strong>: 이평선 정배열 + MACD 0선 위 + RSI 50 이상</li>
    <li><strong>역추세 매매</strong>: 볼린저 하단 터치 + RSI 30 이하 + 거래량 급증</li>
    <li><strong>매집 포착</strong>: 가격 횡보 중 OBV 우상향 + MFI 50 이상 유지</li>
    <li><strong>고점 경계</strong>: 가격 신고가 + RSI 다이버전스 + MACD 약세 다이버전스</li>
  </ul>
</section>

<section id="caveat">
  <h3>8. 기술적 지표의 한계 — 반드시 알아야 할 것</h3>
  <ul>
    <li><strong>후행 지표</strong>: 대부분의 지표는 과거 데이터로 계산되므로, 신호가 나오면 이미 움직임의 일부가 진행된 상태일 수 있습니다.</li>
    <li><strong>가짜 신호(whipsaw)</strong>: 횡보장에서는 골든크로스·데드크로스가 빈번히 반복되며 손실을 누적시킵니다.</li>
    <li><strong>이벤트 리스크</strong>: 실적 발표, 정책 변화 같은 펀더멘털 이벤트는 지표로 예측 불가</li>
    <li><strong>과최적화 함정</strong>: 백테스트로 잘 맞은 파라미터가 미래에도 통한다는 보장은 없음</li>
    <li>지표는 <strong>가설을 세우는 도구</strong>일 뿐, 자동 매매 신호가 아니라는 점을 늘 인지해야 합니다.</li>
  </ul>
</section>

<section>
  <h3>마치며</h3>
  <p>
    기술적 지표는 시장의 언어를 읽는 도구입니다. 한두 개를 깊이 이해하고 일관되게 적용하는 것이,
    수십 개를 얕게 보는 것보다 훨씬 효과적입니다. 세콤달.콤 주식맛집의 <a href="/chart">전종목 차트</a>에서
    실제 종목들을 살펴보며 위 지표들을 직접 비교해 보세요. 가설을 세우고, 검증하고, 자신만의 매매 원칙을
    천천히 만들어 가는 과정이 결국 가장 큰 수익률을 만듭니다.
  </p>
</section>
"""

# ──────────────────────────────────────────────────────
# 2) 투자자 수급 읽는 법
# ──────────────────────────────────────────────────────
SUPPLY_BODY = """
<h2>🏦 외국인·기관·개인 수급 읽는 법 — 누가 사고 누가 파는가</h2>
<p class="lead">
  주식시장에서 가격은 결국 매수와 매도의 균형으로 결정됩니다. 그 균형을 만드는 주체는 크게
  <strong>외국인·기관·개인</strong> 셋으로 분류되며, 각 주체의 매매 패턴은 시장의 단·중기 흐름을
  이해하는 데 결정적인 단서를 제공합니다. 본 가이드는 세콤달.콤 주식맛집이 매일 제공하는
  60일 누적 수급 데이터를 어떻게 읽고 해석할지 정리합니다.
</p>

<section>
  <h3>1. 세 주체의 정체와 성향</h3>
  <h4>외국인 (Foreign)</h4>
  <p>
    외국 국적의 기관·개인 투자자입니다. 한국 시장에서는 보통 글로벌 자산운용사·헤지펀드·국부펀드 등이 큰 비중을 차지하며,
    <strong>달러 환율, 글로벌 매크로 환경, MSCI 한국 지수 변경</strong>에 민감하게 반응합니다.
    중장기 매매 비중이 높아, 외국인이 일관되게 매수/매도하는 종목은 추세가 길게 이어지는 경향이 있습니다.
  </p>
  <h4>기관 (Institutional)</h4>
  <p>
    국내 자산운용사·연기금·보험사·은행 등의 매매를 통칭합니다. 펀드 환매 흐름·연기금 자산 배분 정책이 영향을 주며,
    분기 말·연말의 윈도우 드레싱(평가 효과를 위한 매수)도 종종 나타납니다.
    외국인보다 단기적·테크니컬한 매매 비중이 높은 편입니다.
  </p>
  <h4>개인 (Retail)</h4>
  <p>
    일반 개인 투자자입니다. 흔히 외국인·기관과 반대 방향으로 움직이는 경향이 있다고 알려져 있으며,
    이를 두고 "개미는 항상 늦다" 는 표현이 자주 쓰이지만 — 사실은 단순히 <em>외국인+기관 = 100% − 개인</em>
    이라는 회계적 항등식의 결과이기도 합니다. 즉, 누군가 사면 누군가는 팔아야 하기 때문입니다.
  </p>
</section>

<section>
  <h3>2. 누적 순매수 그래프 읽기</h3>
  <p>
    세콤달.콤 차트는 60일 동안의 외국인·기관 순매수를 누적해 라인 그래프로 표시합니다.
    하루의 매매보다 누적 흐름을 보는 이유는 다음과 같습니다.
  </p>
  <ul>
    <li><strong>일별 노이즈 제거</strong> — 하루 매도가 컸어도 며칠간 매수가 더 컸다면 추세는 유지</li>
    <li><strong>방향성 파악</strong> — 우상향이면 매수 우위, 우하향이면 매도 우위</li>
    <li><strong>가격과의 교차 검증</strong> — 가격은 횡보인데 외국인 누적이 우상향이면 매집 가능성</li>
  </ul>
  <h4>실전 패턴</h4>
  <ul>
    <li><strong>외국인+기관 동시 매수</strong>: 가장 강한 매수 신호. 추세가 길게 이어질 가능성.</li>
    <li><strong>외국인 매수, 기관 매도</strong>: 시각이 엇갈림 — 외국인이 옳으면 추세 지속, 기관이 옳으면 단기 조정.</li>
    <li><strong>외국인 매도, 기관 매수</strong>: 일반적으로 가격 변동성이 큼. 환율 이슈로 외국인이 빠질 때 자주 발생.</li>
    <li><strong>둘 다 매도</strong>: 약세 시나리오. 개인의 단기 반등 매수만으로는 추세를 돌리기 어려움.</li>
  </ul>
</section>

<section>
  <h3>3. 수급과 가격의 관계 — 4가지 케이스</h3>
  <ol>
    <li><strong>가격↑ + 외인·기관 매수↑</strong>: 추세 강화. 이상적인 상승.</li>
    <li><strong>가격↑ + 외인·기관 매도↑</strong>: 의심스러운 상승. 단기 차익실현 매물 출회 가능.</li>
    <li><strong>가격↓ + 외인·기관 매수↑</strong>: 매집 가능성. 가격이 눌려 있어도 큰손이 사 모으는 신호.</li>
    <li><strong>가격↓ + 외인·기관 매도↑</strong>: 명확한 약세. 추세 반전까지는 시간이 필요.</li>
  </ol>
</section>

<section>
  <h3>4. 흔히 빠지는 함정</h3>
  <ul>
    <li><strong>"외국인이 사면 무조건 오른다"</strong> — 외국인도 손실을 보고 빠집니다. 외국인 매수 = 정답이 아님.</li>
    <li><strong>한 종목 수급으로 시장 전체를 보지 마세요</strong> — 종목 수급은 종목 이슈에 좌우되며, 시장 전체 수급(KOSPI 외국인 누적)과 다를 수 있습니다.</li>
    <li><strong>프로그램 매매 분류 차이</strong> — 차익·비차익 분류 기준이 거래소마다 다를 수 있고, "외국인" 안에도 단기·장기가 섞여 있습니다.</li>
    <li><strong>지연 데이터</strong> — 일반에 공개되는 수급은 장 마감 후 집계로, 실시간 흐름과는 차이가 있습니다.</li>
  </ul>
</section>

<section>
  <h3>5. 수급 + 다른 데이터 조합</h3>
  <p>수급만 보지 말고 다음 정보와 함께 보는 것을 권장합니다.</p>
  <ul>
    <li><strong>거래량</strong>: 같은 매수 1억 원이라도 거래량이 적은 종목에서는 영향이 큽니다.</li>
    <li><strong>공매도 잔고</strong>: 외국인 매도가 공매도 비중 증가와 겹치면 약세 강도가 더 큼.</li>
    <li><strong>업종 수급</strong>: 같은 업종 내 다른 종목도 비슷한 수급 흐름인지 (섹터 매수인지 종목 매수인지)</li>
    <li><strong>실적·뉴스</strong>: 펀더멘털 이슈가 수급 변화의 원인일 수 있음</li>
  </ul>
</section>

<section>
  <h3>마치며</h3>
  <p>
    수급 데이터는 가격 차트만 보는 것보다 훨씬 입체적인 정보를 줍니다. 다만 만능은 아니며,
    "누가 사는가" 못지않게 "왜 사는가" 를 함께 추정할 줄 알아야 의사결정의 질이 올라갑니다.
    세콤달.콤의 <a href="/chart">전종목 차트</a>에서 외국인·기관 누적 라인을 가격과 비교하며
    여러 종목을 살펴보세요. 패턴이 눈에 익으면 수급은 강력한 보조 도구가 됩니다.
  </p>
</section>
"""

# ──────────────────────────────────────────────────────
# 3) 캔들 차트 기초
# ──────────────────────────────────────────────────────
CANDLE_BODY = """
<h2>🕯️ 캔들 차트 기초 — 봉 하나가 알려주는 4가지 가격</h2>
<p class="lead">
  캔들 차트(봉 차트)는 일정 기간의 시가·종가·고가·저가 4가지 가격을 하나의 막대로 시각화한 차트입니다.
  17세기 일본 쌀 거래상이었던 혼마 무네히사가 고안한 형식이 현재까지 전 세계에서 표준으로 쓰이고 있습니다.
  이 가이드는 캔들의 구조부터 자주 등장하는 패턴, 그리고 패턴 매매의 한계까지 차근차근 정리합니다.
</p>

<section>
  <h3>1. 캔들 한 개의 구조</h3>
  <ul>
    <li><strong>몸통(body)</strong>: 시가와 종가 사이의 굵은 사각형</li>
    <li><strong>꼬리(wick, shadow)</strong>: 몸통 위·아래로 뻗은 가는 선 — 고가와 저가를 표시</li>
    <li><strong>양봉(빨강 또는 파랑)</strong>: 종가가 시가보다 높음 — 그날 매수가 우세</li>
    <li><strong>음봉(파랑 또는 빨강)</strong>: 종가가 시가보다 낮음 — 그날 매도가 우세</li>
  </ul>
  <div class="callout"><strong>색상은 지역별 관습</strong>이며, 한국·일본은 보통 양봉 빨강 / 음봉 파랑이지만, 미국·유럽은 양봉 초록 / 음봉 빨강을 더 많이 씁니다. 색만 보고 헷갈리지 말고 시가·종가의 관계로 판단하세요.</div>
</section>

<section>
  <h3>2. 일봉·주봉·월봉의 차이</h3>
  <ul>
    <li><strong>일봉</strong>: 하루의 시가·고가·저가·종가. 단기 매매 시그널 포착에 적합.</li>
    <li><strong>주봉</strong>: 5거래일을 묶은 봉. 중기 추세 파악에 유리. 일봉의 잡음을 걸러줌.</li>
    <li><strong>월봉</strong>: 한 달치 봉. 장기 사이클(상승·하락 국면) 분석용.</li>
  </ul>
  <p>
    같은 종목이라도 봉 주기에 따라 그림이 완전히 달라 보일 수 있습니다.
    단기 매매라면 일봉, 장기 보유라면 주봉·월봉을 기본으로 보는 것이 좋습니다.
    세콤달 차트는 좌상단 토글로 일봉·주봉·월봉을 즉시 전환할 수 있습니다.
  </p>
</section>

<section>
  <h3>3. 자주 등장하는 단일 캔들 패턴</h3>
  <h4>장대양봉 / 장대음봉</h4>
  <p>
    몸통이 길고 꼬리가 거의 없는 캔들. 그날 매수(또는 매도) 한 방향이 압도적이었음을 의미하며,
    추세의 시작이나 가속을 시사합니다. 특히 거래량이 평소보다 2배 이상 늘어난 장대봉은 의미가 큽니다.
  </p>
  <h4>도지(Doji)</h4>
  <p>
    시가와 종가가 거의 같아 십자가 형태인 캔들. 매수와 매도가 균형을 이뤘음을 뜻하며,
    상승·하락 추세의 끝에 나타나면 <strong>추세 반전 가능성</strong>의 신호로 자주 인용됩니다.
  </p>
  <h4>망치형 (Hammer) / 역망치형</h4>
  <p>
    몸통이 작고 한쪽 꼬리가 매우 긴 캔들. 하락 후 등장한 망치형(아래 꼬리 김)은 저가에서의 매수 진입을,
    상승 후 등장한 역망치형(위 꼬리 김)은 고가에서의 매도 압력을 시사합니다.
  </p>
</section>

<section>
  <h3>4. 자주 등장하는 복수 캔들 패턴</h3>
  <h4>장악형 (Engulfing)</h4>
  <p>
    전일 캔들의 몸통을 다음날 캔들이 완전히 덮어버리는 패턴. 하락 후 양봉 장악형이 나오면 반전 신호,
    상승 후 음봉 장악형은 약세 반전 신호로 해석됩니다.
  </p>
  <h4>샛별형 (Morning Star) / 석별형 (Evening Star)</h4>
  <p>
    3개의 캔들로 이뤄진 패턴입니다. 하락 → 작은 몸통 → 강한 양봉 흐름이면 샛별형(매수 신호 후보),
    상승 → 작은 몸통 → 강한 음봉 흐름이면 석별형(매도 신호 후보) 입니다.
  </p>
  <h4>갭(Gap)</h4>
  <p>
    전일 종가와 당일 시가 사이에 가격 공백이 생긴 상태. 강한 호재·악재로 형성되며,
    <strong>상승 갭</strong>은 매수 압력의 증거지만 단기 차익매물의 표적이 되기도 합니다.
    대부분의 갭은 일정 시간 안에 채워진다는 통계적 경향이 있습니다.
  </p>
</section>

<section>
  <h3>5. 캔들 패턴 매매의 한계</h3>
  <ul>
    <li><strong>단독 신호의 신뢰도는 낮음</strong> — 망치형 하나만 보고 매수하기보다는, 지지선·이평선·거래량과 겹칠 때 의미가 커집니다.</li>
    <li><strong>거래량을 함께 봐야 함</strong> — 거래량 없는 패턴은 가짜 신호일 확률이 높음.</li>
    <li><strong>시장 전체 흐름이 우선</strong> — 약세장에서 망치형이 나와도 시장이 더 빠지면 무력화될 수 있음.</li>
    <li><strong>패턴 인식 편향</strong> — 사람은 무작위 차트에서도 패턴을 만들어 보는 경향이 있어, 통계적 검증 없이 맹신하면 위험합니다.</li>
  </ul>
</section>

<section>
  <h3>마치며</h3>
  <p>
    캔들은 가격 데이터의 시각화 도구일 뿐, 그 자체로 미래를 예측하지 않습니다.
    중요한 것은 캔들이 <strong>어디에서</strong>(지지선·저항선·이평선 위/아래에서) 나타났고,
    <strong>어떤 거래량</strong>과 함께였는지, 그리고 <strong>전반적인 추세</strong>가 어떤 상태인지를 함께 보는 것입니다.
    세콤달 차트에서 다양한 종목의 일봉·주봉을 보며 위에서 설명한 패턴을 직접 찾아보세요.
    눈에 익을수록 차트 읽기가 빨라집니다.
  </p>
</section>
"""

# ──────────────────────────────────────────────────────
# 4) 주식 용어집
# ──────────────────────────────────────────────────────
GLOSSARY_BODY = """
<h2>📖 주식 용어집 — 가장 자주 쓰는 30개 용어 정리</h2>
<p class="lead">
  주식 차트와 뉴스에서 자주 마주치지만 정확한 의미가 모호한 용어들을 한 페이지에 정리했습니다.
  세콤달.콤 주식맛집의 차트와 데이터를 더 깊이 이해할 수 있도록, 가장 빈번하게 쓰이는
  30개 용어의 뜻과 활용 맥락을 함께 담았습니다.
</p>

<section>
  <h3>📊 가격·거래 용어</h3>
  <h4>시가 (Open)</h4>
  <p>장이 시작될 때 첫 체결가. 한국 주식시장은 9시 정규장 시작 시 단일가로 결정됩니다.</p>
  <h4>종가 (Close)</h4>
  <p>그날 장이 마감될 때 마지막 체결가. 보통 차트의 캔들 색깔·이동평균선 계산의 기준이 됩니다.</p>
  <h4>고가·저가 (High/Low)</h4>
  <p>그 기간 동안 거래된 최고가·최저가. 캔들 꼬리 끝이 이 가격을 표시합니다.</p>
  <h4>거래량 (Volume)</h4>
  <p>해당 기간 동안 거래된 주식 수. 가격 변화의 신뢰도를 가늠하는 핵심 지표입니다.</p>
  <h4>거래대금</h4>
  <p>거래량 × 평균 거래가격. 시가총액이 큰 종목 비교에 더 적합합니다.</p>
  <h4>등락률</h4>
  <p>전일 종가 대비 오늘 종가의 변동 비율. <code class="formula">(오늘종가 − 전일종가) / 전일종가 × 100</code></p>
  <h4>호가</h4>
  <p>매수·매도 주문 가격 단위. 한국은 가격대별로 호가 단위가 다릅니다(예: 5만원 미만 100원, 5~10만원 500원 등).</p>
</section>

<section>
  <h3>💰 가치 평가 지표</h3>
  <h4>시가총액 (Market Cap)</h4>
  <p>발행주식수 × 현재 주가. 회사의 시장가치를 단순화한 지표로, 보통 회사 규모를 비교할 때 씁니다.</p>
  <h4>PER (Price Earnings Ratio, 주가수익비율)</h4>
  <p>주가 / 주당순이익(EPS). 1주당 이익 대비 몇 배에 거래되고 있는지 — 보통 낮으면 저평가, 높으면 고평가로 해석되나 산업·성장률에 따라 적정 수준이 다릅니다.</p>
  <h4>PBR (Price Book-value Ratio, 주가순자산비율)</h4>
  <p>주가 / 주당순자산(BPS). 회사의 청산가치 대비 시장가치 비교. 1배 미만이면 장부상 자산보다 싸게 거래되는 셈.</p>
  <h4>EPS (Earnings Per Share, 주당순이익)</h4>
  <p>당기순이익 / 발행주식수. 1주가 1년간 벌어들인 이익.</p>
  <h4>BPS (Book-value Per Share, 주당순자산)</h4>
  <p>자기자본 / 발행주식수. 1주에 해당하는 회사 순자산.</p>
  <h4>ROE (Return on Equity, 자기자본이익률)</h4>
  <p>당기순이익 / 자기자본. 주주 자본을 얼마나 효율적으로 쓰고 있는지 — 워런 버핏이 가장 중시한다고 알려진 지표.</p>
  <h4>ROA (Return on Assets, 총자산이익률)</h4>
  <p>당기순이익 / 총자산. 부채까지 포함한 자산 전체의 수익률.</p>
  <h4>배당수익률</h4>
  <p>주당 배당금 / 현재 주가. 주가에 대한 배당의 매력도를 보여줍니다.</p>
</section>

<section>
  <h3>🏦 시장 구조 용어</h3>
  <h4>KOSPI (코스피)</h4>
  <p>한국 종합주가지수. 한국거래소 유가증권시장에 상장된 대형주 중심. 1980년 1월 4일 = 100.</p>
  <h4>KOSDAQ (코스닥)</h4>
  <p>코스닥시장 종합지수. 중·소형주, 벤처·IT기업 비중이 높음. 1996년 7월 1일 = 1000.</p>
  <h4>KOSPI200</h4>
  <p>코스피 시가총액 상위 200종목으로 구성된 지수. 선물·옵션·ETF의 기초 지수로 사용.</p>
  <h4>지주회사 (Holding Company)</h4>
  <p>다른 회사 주식을 보유해 그 회사를 지배하는 것을 본업으로 하는 회사. 예: SK, LG, 한화 등 그룹 지주사.</p>
  <h4>관계회사·자회사</h4>
  <p>지분율로 구분 — 자회사는 50% 초과 보유(연결 대상), 관계회사는 20~50% 보유(지분법 적용).</p>
  <h4>액면가</h4>
  <p>주식 발행 시 정한 명목 가격(보통 5,000원·500원·100원). 시장 가격과 무관.</p>
  <h4>액면분할</h4>
  <p>1주를 N주로 쪼개는 것. 주가가 명목상 낮아져 거래가 활발해지는 효과를 노림(가치 변화는 없음).</p>
  <h4>우선주</h4>
  <p>의결권은 없지만 배당·잔여재산 분배에 우선권이 있는 주식. 종목코드가 일반적으로 5/7/9/K로 끝납니다(예: 005935 삼성전자우).</p>
  <h4>보통주</h4>
  <p>일반적으로 거래되는 주식. 의결권 있음.</p>
</section>

<section>
  <h3>📈 매매·수급 용어</h3>
  <h4>외국인 순매수</h4>
  <p>외국인의 매수 금액 − 매도 금액. 양수면 외국인 자금이 유입, 음수면 유출.</p>
  <h4>기관 순매수</h4>
  <p>국내 기관(연기금·운용사·보험·은행 등)의 매매 차이. 같은 방식으로 산출.</p>
  <h4>개인 순매수</h4>
  <p>개인 투자자의 순매수. 외국인+기관과의 항등식 관계로 자주 반대 방향으로 보임.</p>
  <h4>공매도</h4>
  <p>주식을 빌려서 먼저 팔고, 가격이 내려가면 다시 사서 갚는 거래. 하락에 베팅하는 매매.</p>
  <h4>대차거래</h4>
  <p>주식을 빌려주고 빌리는 거래. 공매도의 사전 단계로 활용되기도 합니다.</p>
  <h4>프로그램 매매</h4>
  <p>컴퓨터 알고리즘으로 일정 조건에 따라 자동 발주되는 매매. 차익거래·비차익거래로 분류됩니다.</p>
  <h4>상한가·하한가</h4>
  <p>한국 주식은 하루 ±30% 가격 변동 제한이 있으며, 그 한도까지 오르거나 내린 가격을 말합니다.</p>
  <h4>VI (Volatility Interruption)</h4>
  <p>변동성 완화장치. 단기간에 가격이 급변할 때 2분간 단일가매매로 전환되는 제도.</p>
</section>

<section>
  <h3>마치며</h3>
  <p>
    용어를 정확히 알면 차트와 뉴스가 훨씬 또렷이 보입니다. 헷갈리는 용어가 있을 때마다
    이 페이지를 북마크해 두고 참고하세요. 세콤달.콤 주식맛집은 가능한 모든 데이터를
    원본 그대로 제공하되, 사용자가 의미를 이해하는 데 도움이 되는 가이드를 함께 발행하고 있습니다.
    질문이나 제안은 <a href="/contact">Contact</a> 로 자유롭게 남겨주세요.
  </p>
</section>
"""

PAGES = [
    {
        "out": "web/guide/technical-indicators.html",
        "slug": "guide/technical-indicators",
        "title": "기술적 지표 완전 가이드 — MACD · RSI · 볼린저밴드",
        "subtitle": "Guide · 기술적 지표",
        "description": "주식 차트의 기술적 지표(이동평균선·MACD·RSI·볼린저밴드·OBV·MFI) 의 계산 원리, 해석 방법, 한계와 조합 활용법을 한 번에 정리한 완전 가이드.",
        "keywords": "기술적지표, MACD, RSI, 볼린저밴드, 이동평균선, OBV, MFI, 주식차트, 보조지표, 골든크로스, 데드크로스",
        "body": TECH_BODY,
    },
    {
        "out": "web/guide/supply-demand.html",
        "slug": "guide/supply-demand",
        "title": "외국인·기관·개인 수급 읽는 법",
        "subtitle": "Guide · 수급",
        "description": "외국인·기관·개인 누적 순매수의 의미와 가격과의 관계, 실전 패턴 4가지, 수급 매매에서 흔히 빠지는 함정까지 정리한 투자자 수급 가이드.",
        "keywords": "외국인수급, 기관수급, 개인수급, 누적순매수, 외국인매매, 기관매매, 프로그램매매, 공매도, 매집",
        "body": SUPPLY_BODY,
    },
    {
        "out": "web/guide/candle-patterns.html",
        "slug": "guide/candle-patterns",
        "title": "캔들 차트 기초 — 봉의 구조와 주요 패턴",
        "subtitle": "Guide · 캔들",
        "description": "캔들 차트의 기본 구조(시가·종가·고가·저가)부터 일봉·주봉·월봉의 차이, 망치형·도지·장악형·샛별형 등 주요 패턴과 한계를 정리한 캔들 가이드.",
        "keywords": "캔들차트, 봉차트, 망치형, 도지, 장악형, 샛별형, 갭, 일봉, 주봉, 월봉, 캔들패턴",
        "body": CANDLE_BODY,
    },
    {
        "out": "web/glossary.html",
        "slug": "glossary",
        "title": "주식 용어집 — 시가총액 · PER · ROE · 외국인 순매수",
        "subtitle": "Glossary · 용어집",
        "description": "주식 투자에서 자주 쓰는 30개 용어의 정확한 정의 — 가격·거래, 가치 평가(PER·PBR·EPS·ROE), 시장 구조(KOSPI·지주회사·우선주), 매매·수급(공매도·VI) 정리.",
        "keywords": "주식용어, 시가총액, PER, PBR, EPS, ROE, KOSPI, KOSDAQ, 지주회사, 우선주, 공매도, 외국인순매수",
        "body": GLOSSARY_BODY,
    },
]


def main() -> None:
    for spec in PAGES:
        out = ROOT / spec["out"]
        out.parent.mkdir(parents=True, exist_ok=True)
        html = page(spec["slug"], spec["title"], spec["subtitle"],
                    spec["description"], spec["body"], spec["keywords"])
        out.write_text(html, encoding="utf-8")
        kb = out.stat().st_size / 1024
        print(f"✅ {out}  ({kb:.1f} KB)")


if __name__ == "__main__":
    main()
