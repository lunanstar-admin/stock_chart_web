"""
한국 주식 기업정보 DB 스키마 생성
"""
import sqlite3
import os

DB_PATH = os.environ.get(
    'STOCK_DB',
    os.path.join(os.path.dirname(__file__), '..', 'data', 'stock_db.sqlite'),
)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def create_database():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── 1. 기업 기본정보 ─────────────────────────────────────────────
    c.executescript("""
    CREATE TABLE IF NOT EXISTS companies (
        code            TEXT PRIMARY KEY,   -- 종목코드 (6자리)
        name            TEXT NOT NULL,       -- 종목명
        market          TEXT,               -- KOSPI | KOSDAQ
        sector          TEXT,               -- GICS 업종
        industry        TEXT,               -- 세부업종
        listing_date    TEXT,               -- 상장일
        settlement_month INTEGER,           -- 결산월
        par_value       INTEGER,            -- 액면가
        shares_total    INTEGER,            -- 상장주식수
        corp_code       TEXT,               -- DART 고유번호
        corp_cls        TEXT,               -- Y:유가증권 K:코스닥 N:코넥스 E:기타
        ceo             TEXT,               -- 대표이사
        address         TEXT,               -- 본사주소
        homepage        TEXT,               -- 홈페이지
        phone           TEXT,               -- 전화번호
        employee_count  INTEGER,            -- 직원수
        founded_year    INTEGER,            -- 설립연도
        description     TEXT,               -- 사업내용 요약
        main_products   TEXT,               -- 주요제품/서비스
        group_name      TEXT,               -- 계열그룹명
        -- 지수 구성 여부
        is_kospi200     INTEGER DEFAULT 0,  -- KOSPI200 편입여부
        -- 시장 데이터 (스냅샷)
        market_cap      INTEGER,            -- 시가총액 (원)
        market_cap_rank INTEGER,            -- 시총순위
        close_price     INTEGER,            -- 현재가
        per             REAL,               -- PER
        pbr             REAL,               -- PBR
        eps             INTEGER,            -- EPS
        bps             INTEGER,            -- BPS
        roe             REAL,               -- ROE(%)
        -- 메타
        collected_at    TEXT,               -- 수집일시
        updated_at      TEXT                -- 갱신일시
    );

    -- ── 2. 재무제표 (연간) ──────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS financials_annual (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        code            TEXT NOT NULL,
        year            INTEGER NOT NULL,   -- 회계연도 (2022, 2023, 2024)
        fs_type         TEXT DEFAULT 'CFS', -- CFS:연결 OFS:별도
        -- 손익계산서
        revenue         INTEGER,            -- 매출액
        operating_profit INTEGER,           -- 영업이익
        net_income      INTEGER,            -- 당기순이익
        ebitda          INTEGER,            -- EBITDA
        gross_profit    INTEGER,            -- 매출총이익
        -- 재무상태표
        total_assets    INTEGER,            -- 자산총계
        total_equity    INTEGER,            -- 자본총계
        total_debt      INTEGER,            -- 부채총계
        cash            INTEGER,            -- 현금및현금성자산
        short_term_debt INTEGER,            -- 단기차입금
        long_term_debt  INTEGER,            -- 장기차입금
        -- 현금흐름표
        cfo             INTEGER,            -- 영업활동현금흐름
        cfi             INTEGER,            -- 투자활동현금흐름
        cff             INTEGER,            -- 재무활동현금흐름
        capex           INTEGER,            -- 설비투자(CAPEX)
        fcf             INTEGER,            -- 잉여현금흐름
        -- 수익성 지표
        op_margin       REAL,               -- 영업이익률(%)
        net_margin      REAL,               -- 순이익률(%)
        roe             REAL,               -- ROE(%)
        roa             REAL,               -- ROA(%)
        debt_ratio      REAL,               -- 부채비율(%)
        -- 메타
        collected_at    TEXT,
        UNIQUE(code, year, fs_type)
    );

    -- ── 3. 배당 이력 ───────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS dividends (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        code            TEXT NOT NULL,
        year            INTEGER NOT NULL,
        dividend_per_share INTEGER,         -- 주당배당금
        dividend_yield  REAL,               -- 배당수익률(%)
        payout_ratio    REAL,               -- 배당성향(%)
        ex_dividend_date TEXT,              -- 배당락일
        payment_date    TEXT,               -- 배당지급일
        collected_at    TEXT,
        UNIQUE(code, year)
    );

    -- ── 4. 주요 주주 ───────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS shareholders (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        code            TEXT NOT NULL,
        report_year     INTEGER NOT NULL,   -- 기준연도
        shareholder_name TEXT NOT NULL,     -- 주주명
        relation        TEXT,               -- 관계 (최대주주, 특수관계인 등)
        shares          INTEGER,            -- 보유주식수
        ownership_pct   REAL,               -- 지분율(%)
        collected_at    TEXT
    );

    -- ── 5. 사업부문별 매출 ─────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS business_segments (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        code            TEXT NOT NULL,
        year            INTEGER NOT NULL,
        segment_name    TEXT NOT NULL,      -- 사업부문명
        revenue         INTEGER,            -- 부문 매출
        revenue_pct     REAL,               -- 전체 대비 비중(%)
        collected_at    TEXT
    );

    -- ── 6. 계열그룹·지분관계 ───────────────────────────────────────
    CREATE TABLE IF NOT EXISTS group_affiliations (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name      TEXT NOT NULL,      -- 계열그룹명
        code            TEXT NOT NULL,      -- 계열사 종목코드
        parent_code     TEXT,               -- 모회사 코드
        ownership_pct   REAL,               -- 모회사 지분율
        is_listed       INTEGER DEFAULT 1,  -- 상장여부
        updated_at      TEXT,
        UNIQUE(group_name, code)
    );

    -- ── 7. 분기 실적 ───────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS financials_quarterly (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        code            TEXT NOT NULL,
        year            INTEGER NOT NULL,
        quarter         INTEGER NOT NULL,   -- 1,2,3,4
        fs_type         TEXT DEFAULT 'CFS',
        revenue         INTEGER,
        operating_profit INTEGER,
        net_income      INTEGER,
        op_margin       REAL,
        collected_at    TEXT,
        UNIQUE(code, year, quarter, fs_type)
    );

    -- ── 8. 수집 진행 상태 ──────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS collection_status (
        code            TEXT PRIMARY KEY,
        market          TEXT,
        market_cap_rank INTEGER,
        status          TEXT DEFAULT 'pending',  -- pending|done|error
        error_msg       TEXT,
        started_at      TEXT,
        finished_at     TEXT
    );

    -- 인덱스
    CREATE INDEX IF NOT EXISTS idx_companies_market ON companies(market);
    CREATE INDEX IF NOT EXISTS idx_companies_rank ON companies(market_cap_rank);
    CREATE INDEX IF NOT EXISTS idx_financials_code ON financials_annual(code);
    CREATE INDEX IF NOT EXISTS idx_dividends_code ON dividends(code);
    CREATE INDEX IF NOT EXISTS idx_shareholders_code ON shareholders(code);
    """)

    conn.commit()
    conn.close()
    print(f"DB 생성 완료: {os.path.abspath(DB_PATH)}")

if __name__ == '__main__':
    create_database()
