# 블로그 글 작성 가이드 — AdSense 친화

이 문서는 secomdal.com 의 모든 신규 글(가이드·블로그·테마 분석) 작성에 적용되는
표준입니다. 자동 발행 글(market-brief, daily-, batch-) 은 별도 룰로 noindex 처리되어
이 가이드의 영향 밖이지만, **사람이 직접 쓰는 글은 모두 아래 기준을 따릅니다**.

근거: 한국 AdSense 승인 가이드 영상("애드센스 승인, 이거였구나") + 우리 사이트의 운영 경험.

---

## 1. 핵심 원칙 — "전문성·구조·꾸준함"

AdSense 가 사이트를 평가할 때 보는 것:

1. **광고주 입장에서 가치 있는 사이트인가** — 방문자가 실제로 유익한 정보를 얻는가
2. **전문성 있는 단일 주제 사이트인가** — 잡다한 주제가 섞여 정체성이 흐려지지 않는가
3. **꾸준히 운영되는가** — 일정 간격으로 신뢰할 만한 글이 발행되는가

본 사이트의 단일 주제: **한국 주식 시장 데이터 분석**

이 주제에서 벗어나는 글(예: 일상 일기, 잡학, IT 리뷰)은 작성하지 않습니다.

---

## 2. 글 한 편의 표준 구조

### 슬러그(파일 이름) 규칙

| 슬러그 접두어 | 용도 | 색인 |
|---|---|---|
| `theme-*` | 산업/사이클 분석 칼럼 | ✅ 허용 |
| `guide/*` | 학습용 가이드 (별도 디렉토리) | ✅ 허용 |
| (접두어 없음, 자유 슬러그) | 일반 에디토리얼 글 | ✅ 허용 |
| `market-brief-*` | 자동 시장 분석 (배치 발행) | ❌ noindex |
| `daily-*` | 자동 일일 랭킹 (배치) | ❌ noindex |
| `batch-*` | 운영 회고·장애 기록 등 | ❌ noindex |

**원칙**: 사람이 직접 쓰는 글은 자동 글 접두어를 쓰지 않습니다. 자동 글은 `_is_auto_slug()`
함수에 의해 자동으로 색인 제외 + 블로그 인덱스 숨김 처리됩니다.

### Frontmatter 표준 형식

```yaml
---
title: "제목 — 메인 키워드를 앞쪽에 (15~25자 권장)"
date: YYYY-MM-DD
slug: theme-주제-키워드   # 또는 자유 슬러그
summary: "메타 디스크립션 역할 — 160자 내외, 메인 키워드 1회 포함"
tags: [주제태그1, 주제태그2, 주제태그3]   # 4개 이내 권장
---
```

- **title**: 메인 키워드를 **제목 앞쪽**에 배치. 15~25자 권장.
- **summary**: 160자 내외. 메인 키워드가 띄어쓰기까지 동일하게 한 번 포함되어야
  검색엔진이 키워드 매칭을 인식합니다.
- **tags**: 4개 이내. 사이트 전체에서 일관된 어휘 사용
  (예: `시장분석`, `산업분석`, `기본기`, `테마`, `정책`).

### 본문 구조

```markdown
# (H1) 제목 — frontmatter title 과 동일

*발행일 및 분류 메모 (선택, 이탤릭)*

(도입 단락 — 글의 핵심을 2~4문장으로 요약. 첫 단락이 검색 결과 미리보기에
표시될 수 있으므로 핵심 키워드를 자연스럽게 포함합니다.)

## (H2) 📌 핵심 요약

- 3~4개의 불릿으로 글의 결론을 미리 제시

## (H2) 1. 첫 번째 소제목

본문 단락 (300~500자) — 정보 전달형 문어체. 한 단락은 보통 3~5문장.

## (H2) 2. 두 번째 소제목

본문 단락 (300~500자)

... (H2 4~7개 정도)

## (H2) 마치며

요약 단락 (2~4문장) + 면책 조항

> ⚠️ 본 글은 산업 흐름에 대한 일반적 분석이며, 특정 종목 매수·매도 권유가 아닙니다.

**📚 함께 읽기**

- [관련 글 1](/blog/...)
- [관련 글 2](/blog/...)
- [관련 가이드](/guide/...)
```

### H 태그 규칙

- **H1**: 글의 제목 한 번만 (markdown 의 `# `).
- **H2**: 모든 큰 소제목은 H2 (`## `). 본문 구조의 척추.
- **H3**: 꼭 필요할 때만 H2 아래 세부 항목으로. 남용 금지.
- 영상의 지침: *"H1/H2/H3 를 복잡하게 쓰지 말고 H2 만 잘 써도 충분"*.

---

## 3. 문체 가이드

### 사용하는 표현

- `~입니다 / ~합니다` 체. 정보 전달형 문어체.
- 사실 진술 + 가능성 진술 + 한계 진술의 3박자.
  - 예: "전력 인프라 종목이 부각되고 있습니다. 다만 모든 종목이 동등 수혜를 받는 것은 아닙니다."

### 피하는 표현

- ❌ `~했어요 ~예요 ~더라고요` 같은 구어체
- ❌ `ㅎㅎ ㅋㅋ ㅠㅠ` 같은 이모티콘
- ❌ `진짜 좋더라` `대박이다` 같은 감탄사
- ❌ `~인 것 같습니다` 같은 모호한 추정 (다른 명확한 표현으로 대체)
- ❌ 1인칭 `저는 ~` (1인 운영 글이라도 사이트 톤은 객관)

### 환각·과장 방지 가드

- 학습 데이터·도구가 확신할 수 없는 *특정 시점의 사실*은 인용하지 않습니다.
  (예: "X 종목이 어제 30% 올랐다" 같은 단정 — 자동 글 외에는 피함)
- **프레임워크·구조 중심**의 글 — 닷컴 비교, 산업 사이클, 지정학 채널 같은
  시점 무관 분석을 선호.
- 데이터·인용이 필요할 때는 *공개 출처* 명기 (DART, Naver Finance 등).

---

## 4. 분량 가이드

| 글 종류 | 권장 분량 |
|---|---|
| 일반 에디토리얼 글 | **1,500~2,500자** (A4 1~1.5장) |
| 산업 분석 칼럼(theme-*) | **2,500~4,000자** |
| 학습 가이드(guide/) | **3,000~6,000자** |
| 용어집 페이지 | 길이 제한 없음 (검색 친화 항목 누적) |

**너무 짧은 글**(800자 이하)은 *thin content* 로 분류돼 사이트 전체 평가를 깎습니다.
짧은 메모는 글로 발행하지 말고 트위터·SNS 에 올리세요.

**너무 긴 글**(7,000자 이상)은 두 편으로 나누세요. 한 페이지의 평균 체류시간이
오히려 짧아질 수 있습니다.

---

## 5. 발행 리듬

- **하루 2~3편 이내** 권장. 한꺼번에 5편 이상 동시 push 는 *기계적 발행*
  시그널이 될 수 있습니다.
- **글 사이 1시간 이상 간격** — 여러 글을 작성해 두었다면 예약 발행으로 분산.
- **승인 심사 중에도 발행 지속** — 정지 상태는 *유령 사이트* 시그널.
- 자동 발행 글(market-brief-) 는 위 규칙과 *별개*. 색인 제외이므로 발행 빈도에
  영향이 없습니다.

---

## 6. 사진·미디어

### 자동 cover 이미지 (Unsplash)

신규 글이 발행되면 GitHub Actions 의 `batch/enrich_images.py` 가 자동으로
**Unsplash** 무료 사진을 검색해 `web/blog/img/{slug}.jpg` 로 저장하고
frontmatter 에 다음 4개 필드를 추가합니다.

```yaml
cover: /blog/img/theme-ai-cycle-flow.jpg
cover_alt: "AI 데이터센터 서버랙"
cover_credit: "Photographer Name"
cover_credit_url: "https://unsplash.com/@photographer?utm_source=secomdal..."
```

`build_blog.py` 는 cover 가 있으면 글 상단(제목 아래)에 이미지 + photographer 크레딧을
자동 렌더링합니다. Unsplash 라이선스 의무 (사진작가 표시, "on Unsplash" 링크,
download analytics 트리거) 모두 자동 처리됩니다.

### 검색 키워드 매핑

`enrich_images.py` 의 `KEYWORD_MAP` 딕셔너리가 한국어 태그·제목 키워드를 영문
검색어로 변환합니다 (예: `반도체` → `semiconductor`, `자율주행` → `self driving car`).
새 주제를 자주 쓰게 되면 이 매핑을 추가하세요.

### 수동으로 사진 넣기 — 단계별 가이드

자동 Unsplash 가 마음에 안 드는 결과를 줄 때, 또는 *내가 직접 고른 사진* 또는
*ChatGPT 로 만든 이미지*를 쓰고 싶을 때의 절차입니다.

#### 1단계: 이미지 파일 준비

- **권장 크기**: 가로 1200~1920px, 세로 600~1080px (16:9 정도 가로 비율)
- **권장 형식**: `.jpg` (사진), `.png` (일러스트·다이어그램), `.webp` (둘 다 가능)
- **권장 용량**: 한 장당 **500KB 이하**. 너무 크면 페이지 속도가 나빠짐
- **압축 도구**:
  - 온라인 무료: [Squoosh](https://squoosh.app) (Google 제공, 드래그앤드롭)
  - 또는 `web/blog/img/` 에 넣은 뒤 압축

#### 2단계: 파일을 저장소에 추가

파일명은 글의 슬러그와 같게 짓는 것이 관리하기 좋습니다.

```
web/blog/img/{슬러그}.jpg
```

예시:
```
web/posts/2026-05-20-my-article.md
web/blog/img/my-article.jpg            ← 슬러그가 my-article 인 경우
```

여러 장 쓸 때는 접미사:
```
web/blog/img/my-article.jpg            (cover)
web/blog/img/my-article-1.png          (본문용)
web/blog/img/my-article-2.png          (본문용)
```

#### 3단계: frontmatter 에 cover 필드 추가

글의 markdown 파일 최상단 `---` 사이에 다음 필드를 추가합니다.

##### A) 본인이 직접 찍거나 ChatGPT 등으로 만든 이미지 (저작권 본인 소유)

```yaml
---
title: "글 제목"
date: 2026-05-20
slug: my-article
summary: "..."
tags: [태그1, 태그2]
cover: /blog/img/my-article.jpg
cover_alt: "이미지에 대한 설명 (시각장애인용 + SEO)"
---
```

`cover_credit` 과 `cover_credit_url` 은 *생략* 하면 됩니다. 그러면 사이트는
이미지만 보여주고 photographer 크레딧 라인을 표시하지 않습니다.

##### B) Unsplash 사이트에서 직접 골라온 이미지

```yaml
cover: /blog/img/my-article.jpg
cover_alt: "이미지 설명"
cover_credit: "Photographer Name"
cover_credit_url: "https://unsplash.com/@photographer?utm_source=secomdal&utm_medium=referral"
```

photographer 이름과 프로필 URL 은 Unsplash 사진 페이지에서 복사. URL 끝에
**`?utm_source=secomdal&utm_medium=referral`** 를 반드시 붙이세요 (라이선스 요건).

##### C) Pexels / Pixabay 등 다른 무료 스톡 사이트

```yaml
cover: /blog/img/my-article.jpg
cover_alt: "이미지 설명"
cover_credit: "Photographer Name on Pexels"
cover_credit_url: "https://www.pexels.com/photo/..."
```

##### D) 공공기관·언론·보도자료 이미지 (라이선스 명시)

```yaml
cover: /blog/img/my-article.jpg
cover_alt: "이미지 설명"
cover_credit: "출처: 공공누리"
cover_credit_url: "https://www.kogl.or.kr/..."
```

#### 4단계: 자동 처리 막기

frontmatter 에 `cover` 필드가 *있으면* `enrich_images.py` 는 그 글을 *자동으로*
건너뜁니다 (멱등). 즉 수동 cover 설정을 한 글은 영구히 보존됩니다.

#### 5단계: 커밋·푸시

```bash
git add web/blog/img/my-article.jpg web/posts/2026-05-20-my-article.md
git commit -m "post(my-article): 수동 cover 이미지 추가"
git push
```

`build_blog.py` 가 다음 배치 또는 수동 실행 시 새 frontmatter 를 읽고
HTML 의 `<figure class="blog-cover-wrap">` 블록에 이미지 + 크레딧을 자동 렌더링.

### 본문 내 추가 이미지

본문 안에 이미지를 추가하고 싶을 때 (예: 비교 다이어그램, 스크린샷):

```markdown
![대체 텍스트](/blog/img/my-article-diagram.png)
*캡션: 이 도표는 ... 을 보여줍니다. 출처: 한국거래소*
```

또는 HTML 직접 사용 (캡션 + 출처를 더 깔끔하게):

```markdown
<figure class="inline-figure">
  <img src="/blog/img/my-article-diagram.png" alt="설명" loading="lazy" />
  <figcaption>도표: ... <a href="출처URL">출처</a></figcaption>
</figure>
```

원칙:
- 본문 이미지는 1~2장 이내 (너무 많으면 글이 가벼워 보임)
- 정보 전달에 *반드시 필요한* 경우에만
- 차트·그래프는 정적 이미지보다 *사이트 내부 차트 페이지로 링크* 가 좋음
- 모든 이미지에 `alt` 텍스트 필수 (SEO + 접근성)
- 첫 이미지(cover) 외에는 `loading="lazy"`

### ChatGPT 로 이미지 만들 때 팁

ChatGPT.com (Plus 구독) 에서 이미지를 생성한 경우:

1. **다운로드 → 압축**: 원본은 보통 1024×1024 PNG. Squoosh 로 600~800KB 이하로
2. **저작권**: OpenAI 정책상 사용자가 권리 보유. `cover_credit` 생략 가능
3. **alt 텍스트**: 이미지가 무엇을 *보여주는지* 한 문장으로
4. **글 주제와의 매칭**: 너무 추상적이거나 일반적인 이미지는 피하고,
   해당 글의 *핵심 비유*를 시각화한 것을 선택

생성 프롬프트 예시 (theme-ai-power-infra 글이라면):
```
A photorealistic image of a modern data center server room with
electrical infrastructure visible in the background, dramatic lighting,
clean professional style, wide aspect ratio 16:9, no text or watermarks
```

생성 후 사이트 톤(차분한 다크/베이지)과 맞는지 확인 후 사용.

---

## 7. 내부 링크

모든 글은 **마지막에 "함께 읽기"** 섹션으로 같은 주제의 다른 글 3~5개를 링크합니다.
이는 검색엔진의 *주제 응집도* 평가에 도움이 됩니다.

링크 대상 예시:
- 같은 시리즈의 다른 분석 글
- 관련 가이드 페이지
- 용어집 항목

---

## 8. AI 도구 사용 시 규칙

AI 도구로 초안을 만드는 것은 *허용*되지만, 다음을 반드시 지킵니다.

1. **그대로 복붙 금지** — 모든 문장을 사람이 한 번 읽고 다듬습니다.
2. **AI 흔적 표현 제거** — `Claude`, `GPT`, `LLM`, `자동 생성`, `AI 작성`
   같은 표현은 본문에서 절대 사용 금지.
3. **AI 가 만든 단정적 사실은 의심** — 분석·논리 구조는 유지하되 *특정 회사·수치*는
   공식 출처로 재확인.
4. **AI 가 만든 환각성 단정** ("X 가 Y 를 인수했다") 은 *모든 글*에서 제거.

---

## 9. 면책 조항 (모든 분석·시황 글 필수)

글 끝부분에 다음 형식의 면책 인용 박스를 포함합니다.

```markdown
> ⚠️ 본 글은 산업 흐름에 대한 일반적 분석이며, 특정 종목 매수·매도 권유가
> 아닙니다. 투자 판단의 모든 책임은 이용자 본인에게 있으며, 매매 결정 전
> 공식 출처(한국거래소·DART·증권사 리포트)에서 사실 관계를 재확인하시기 바랍니다.
```

가이드·용어집·정책 페이지는 면책 조항이 없어도 됩니다.

---

## 10. 발행 후 체크리스트

새 글을 push 하기 전 다음을 확인합니다.

- [ ] frontmatter `title`, `date`, `slug`, `summary`, `tags` 모두 입력됨
- [ ] 글자 수가 권장 범위 안인가
- [ ] H1 한 번 + H2 4~7개 구조인가
- [ ] 도입 단락에 메인 키워드가 자연스럽게 포함되었나
- [ ] `~입니다 ~합니다` 톤이 일관되는가
- [ ] 이모티콘·구어체·1인칭 1인칭이 없는가
- [ ] 면책 조항이 포함되어 있는가 (분석·시황 글의 경우)
- [ ] 내부 링크 3~5개가 마지막에 있는가
- [ ] AI 흔적 단어가 모두 제거되었는가
- [ ] 자동 글 접두어(`market-brief-`, `daily-`, `batch-`) 를 사용하지 않았는가
- [ ] 맞춤법 검사 1회

---

## 11. 자동 글의 처리 (참고)

자동 발행되는 글들은 *이미* 다음 처리가 되어 있습니다 (코드 자동).

- 슬러그가 `market-brief-` / `daily-` / `batch-` 로 시작
- `<meta name="robots" content="noindex,nofollow">` 자동 삽입
- `sitemap.xml` 에서 제외
- `web/blog/index.html` (블로그 인덱스 페이지) 에서 숨김
- `web/data/recent-posts.json` (메인 카드) 에서 제외

따라서 자동 글의 분량·품질이 사이트 전체 평가에 영향을 *주지 않습니다*.

만약 새 자동 발행 카테고리를 추가하게 되면, `batch/build_blog.py` 의
`_is_auto_slug()` 함수에 새 접두어를 추가해 주세요.

---

## 변경 이력

- 2026-05-14 — 최초 작성. AdSense 거절(가치 낮은 콘텐츠) 회피 가이드 영상 적용.
