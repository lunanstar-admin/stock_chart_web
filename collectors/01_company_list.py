"""
Step 1: 시총순위 기준 종목 목록 수집
- KOSPI200 → KOSPI 전체 → KOSDAQ 전체 순서로 수집
- pykrx + FinanceDataReader + DART 코드 매핑
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from base import get_conn, now_str, safe_int, safe_float, log, DART_API_KEY

import requests
import time
from datetime import datetime, timedelta

def get_kospi200_codes():
    """pykrx에서 KOSPI200 구성종목 조회"""
    try:
        from pykrx import stock
        today = datetime.now().strftime('%Y%m%d')
        # 최근 영업일 기준
        for days_back in range(0, 10):
            d = (datetime.now() - timedelta(days=days_back)).strftime('%Y%m%d')
            try:
                df = stock.get_index_portfolio_deposit_file('1028', d)  # 1028=KOSPI200
                if df is not None and len(df) > 0:
                    log.info(f"KOSPI200 구성종목 {len(df)}개 조회 ({d})")
                    return list(df)
            except:
                continue
    except Exception as e:
        log.warning(f"pykrx KOSPI200 조회 실패: {e}")
    return []

def get_market_stocks_naver(market='KOSPI'):
    """네이버 금융 API로 전체 종목 시총순 조회"""
    stocks = []
    page = 1
    while True:
        try:
            url = f'https://m.stock.naver.com/api/stocks/marketValue/{market}?page={page}&pageSize=100'
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            data = r.json()
            batch = data.get('stocks', [])
            if not batch:
                break
            for s in batch:
                stocks.append({
                    'code':       s.get('itemCode', ''),
                    'name':       s.get('stockName', ''),
                    'market':     market,
                    'market_cap': s.get('marketValue', 0),
                    'close_price': safe_int(s.get('closePrice', '').replace(',', '') if s.get('closePrice') else 0),
                })
            log.info(f"  {market} page {page}: {len(batch)}개 (누적 {len(stocks)})")
            if len(batch) < 100:
                break
            page += 1
            time.sleep(0.3)
        except Exception as e:
            log.error(f"네이버 {market} page {page} 오류: {e}")
            break
    return stocks

def get_dart_corp_codes():
    """DART 전체 기업 고유번호 다운로드 (ZIP → XML 파싱)"""
    import zipfile, io, xml.etree.ElementTree as ET
    corp_map = {}  # stock_code → corp_code
    try:
        url = f'https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={DART_API_KEY}'
        r = requests.get(url, timeout=30)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            with z.open('CORPCODE.xml') as f:
                tree = ET.parse(f)
                root = tree.getroot()
                for corp in root.findall('list'):
                    stock_code = corp.findtext('stock_code', '').strip()
                    corp_code  = corp.findtext('corp_code', '').strip()
                    corp_cls   = corp.findtext('corp_cls', '').strip()
                    if stock_code and corp_code:
                        corp_map[stock_code] = {'corp_code': corp_code, 'corp_cls': corp_cls}
        log.info(f"DART 기업코드 매핑: {len(corp_map)}개")
    except Exception as e:
        log.error(f"DART 기업코드 다운로드 실패: {e}")
    return corp_map

def get_company_basic_dart(corp_code):
    """DART API: 기업 기본정보"""
    try:
        url = 'https://opendart.fss.or.kr/api/company.json'
        r = requests.get(url, params={'crtfc_key': DART_API_KEY, 'corp_code': corp_code}, timeout=10)
        d = r.json()
        if d.get('status') == '000':
            return d
    except Exception as e:
        log.debug(f"DART 기업정보 오류 ({corp_code}): {e}")
    return {}

def main():
    conn = get_conn()
    c = conn.cursor()

    # ── STEP 1: DART 기업코드 매핑 ──────────────────────────────────
    log.info("=== DART 기업코드 매핑 다운로드 ===")
    dart_map = get_dart_corp_codes()

    # ── STEP 2: KOSPI 시총 전체 조회 ────────────────────────────────
    log.info("=== KOSPI 전체 종목 조회 (시총순) ===")
    kospi_stocks = get_market_stocks_naver('KOSPI')

    # ── STEP 3: KOSDAQ 시총 전체 조회 ───────────────────────────────
    log.info("=== KOSDAQ 전체 종목 조회 (시총순) ===")
    kosdaq_stocks = get_market_stocks_naver('KOSDAQ')

    # ── STEP 4: KOSPI200 마킹 ────────────────────────────────────────
    log.info("=== KOSPI200 구성종목 조회 ===")
    kospi200_codes = set(get_kospi200_codes())
    log.info(f"KOSPI200: {len(kospi200_codes)}개")

    # ── STEP 5: DB 저장 ─────────────────────────────────────────────
    all_stocks = []
    # KOSPI: 시총순 rank 부여
    for rank, s in enumerate(kospi_stocks, 1):
        s['market_cap_rank'] = rank
        s['is_kospi200'] = s['code'] in kospi200_codes
        all_stocks.append(s)
    # KOSDAQ: rank는 KOSPI 이후부터
    kospi_len = len(kospi_stocks)
    for rank, s in enumerate(kosdaq_stocks, 1):
        s['market_cap_rank'] = kospi_len + rank
        s['is_kospi200'] = False
        all_stocks.append(s)

    inserted = 0
    for s in all_stocks:
        code = s['code']
        if not code:
            continue
        dart_info = dart_map.get(code, {})
        corp_code = dart_info.get('corp_code', '')
        corp_cls  = dart_info.get('corp_cls', '')

        # 시총 문자열 → 정수
        mc = s.get('market_cap', 0)
        if isinstance(mc, str):
            mc = safe_int(mc.replace(',', '')) or 0
        try:
            mc = int(float(str(mc).replace(',', ''))) if mc else 0
        except:
            mc = 0

        c.execute("""
            INSERT INTO companies (code, name, market, market_cap, market_cap_rank,
                                   close_price, corp_code, corp_cls, is_kospi200,
                                   collected_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                name=excluded.name,
                market=excluded.market,
                market_cap=excluded.market_cap,
                market_cap_rank=excluded.market_cap_rank,
                close_price=excluded.close_price,
                corp_code=COALESCE(excluded.corp_code, corp_code),
                corp_cls=COALESCE(excluded.corp_cls, corp_cls),
                is_kospi200=excluded.is_kospi200,
                updated_at=excluded.updated_at
        """, (
            code, s['name'], s['market'],
            mc, s['market_cap_rank'],
            s.get('close_price', 0),
            corp_code, corp_cls,
            1 if s.get('is_kospi200') else 0,
            now_str(), now_str()
        ))

        # collection_status 초기화
        c.execute("""
            INSERT OR IGNORE INTO collection_status (code, market, market_cap_rank, status)
            VALUES (?, ?, ?, 'pending')
        """, (code, s['market'], s['market_cap_rank']))

        inserted += 1

    conn.commit()
    conn.close()

    log.info(f"=== 완료: KOSPI {len(kospi_stocks)}개 / KOSDAQ {len(kosdaq_stocks)}개 / 총 {inserted}개 저장 ===")
    log.info(f"KOSPI200 포함: {len(kospi200_codes)}개")

if __name__ == '__main__':
    main()
