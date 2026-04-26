"""
Step 4: 주요 주주 + 배당 정보 수집
- DART API: 최대주주·특수관계인 지분
- 네이버 금융: 배당 이력
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from base import get_conn, now_str, safe_int, safe_float, log, DART_API_KEY, rate_limit

import requests
from datetime import datetime

CURRENT_YEAR = datetime.now().year

def fetch_major_shareholders(corp_code: str, year: int) -> list:
    """DART: 최대주주 및 특수관계인 보유현황"""
    results = []
    try:
        r = requests.get(
            'https://opendart.fss.or.kr/api/hyslrSttus.json',
            params={
                'crtfc_key': DART_API_KEY,
                'corp_code': corp_code,
                'bsns_year': str(year),
                'reprt_code': '11011',  # 사업보고서
            },
            timeout=10
        )
        d = r.json()
        if d.get('status') != '000':
            return results
        for item in d.get('list', []):
            results.append({
                'shareholder_name': item.get('nm', ''),
                'relation':         item.get('relate', ''),
                'shares':           safe_int(item.get('trmend_posesn_stock_co')),
                'ownership_pct':    safe_float(item.get('trmend_posesn_stock_qota_rt')),
            })
    except Exception as e:
        log.debug(f"DART 주주 오류 ({corp_code}/{year}): {e}")
    return results

def fetch_dividend_naver(code: str) -> list:
    """네이버 금융 배당 이력 (새 API 형식)"""
    results = []
    try:
        url = f'https://m.stock.naver.com/api/stock/{code}/finance/annual'
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        data = r.json()
        fi = data.get('financeInfo', {})
        if not isinstance(fi, dict):
            return results

        # 비컨센서스 연도 목록
        year_entries = [(t['key'], int(t['key'][:4]))
                        for t in fi.get('trTitleList', [])
                        if t.get('isConsensus') == 'N']

        title_map = {row['title']: row.get('columns', {}) for row in fi.get('rowList', [])}

        def _val(title, key):
            v = title_map.get(title, {}).get(key, {}).get('value')
            return v if v and v != '-' else None

        for key, year in year_entries:
            dps = safe_int(_val('주당배당금', key))
            # 배당수익률은 별도 행 없으면 None
            if dps is not None:
                results.append({
                    'year':              year,
                    'dividend_per_share': dps,
                    'dividend_yield':     None,
                    'payout_ratio':       None,
                })
    except Exception as e:
        log.debug(f"네이버 배당 오류 ({code}): {e}")
    return results

def fetch_dividend_dart(corp_code: str, year: int) -> dict:
    """DART: 배당에 관한 사항"""
    try:
        r = requests.get(
            'https://opendart.fss.or.kr/api/alotMatter.json',
            params={
                'crtfc_key': DART_API_KEY,
                'corp_code': corp_code,
                'bsns_year': str(year),
                'reprt_code': '11011',
            },
            timeout=10
        )
        d = r.json()
        if d.get('status') != '000':
            return {}
        for item in d.get('list', []):
            stkKnd = item.get('stck_knd', '')
            if '보통주' in stkKnd or '우선주' not in stkKnd:
                return {
                    'dividend_per_share': safe_int(item.get('per_sto_divi_amt')),
                    'dividend_yield':     safe_float(item.get('divi_rt')),
                    'payout_ratio':       safe_float(item.get('tot_divi_amt')),
                }
    except Exception as e:
        log.debug(f"DART 배당 오류: {e}")
    return {}

def main(limit=None, market_filter=None):
    conn = get_conn()
    c = conn.cursor()

    query = """
        SELECT co.code, co.corp_code, co.market, co.market_cap_rank
        FROM companies co
        ORDER BY co.market_cap_rank ASC
    """
    params = []
    if market_filter:
        query = query.replace("ORDER BY", "WHERE co.market = ? ORDER BY")
        params.append(market_filter)
    if limit:
        query += f" LIMIT {limit}"

    rows = c.execute(query, params).fetchall()
    log.info(f"주주·배당 수집 대상: {len(rows)}개")

    for i, row in enumerate(rows):
        code      = row['code']
        corp_code = row['corp_code'] or ''
        rank      = row['market_cap_rank']

        log.info(f"[{i+1}/{len(rows)}] {code} rank#{rank}")

        # 주주 정보 (DART, 최근 2년)
        if corp_code:
            for year in [CURRENT_YEAR - 1, CURRENT_YEAR - 2]:
                shareholders = fetch_major_shareholders(corp_code, year)
                rate_limit(0.4)
                for sh in shareholders:
                    c.execute("""
                        INSERT INTO shareholders
                            (code, report_year, shareholder_name, relation, shares, ownership_pct, collected_at)
                        VALUES (?,?,?,?,?,?,?)
                        ON CONFLICT DO NOTHING
                    """, (
                        code, year,
                        sh['shareholder_name'], sh['relation'],
                        sh['shares'], sh['ownership_pct'],
                        now_str()
                    ))
                if shareholders:
                    log.info(f"  {year} 주주 {len(shareholders)}명")
                    break  # 최신연도 있으면 OK

        # 배당 정보 (네이버 우선, DART 보완)
        dividends = fetch_dividend_naver(code)
        rate_limit(0.3)

        for dv in dividends:
            year = dv['year']
            if year < CURRENT_YEAR - 4:
                continue
            # DART로 보완
            if corp_code and not dv.get('dividend_per_share'):
                dart_dv = fetch_dividend_dart(corp_code, year)
                rate_limit(0.4)
                dv.update({k: v for k, v in dart_dv.items() if v is not None})

            c.execute("""
                INSERT INTO dividends
                    (code, year, dividend_per_share, dividend_yield, payout_ratio, collected_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(code, year) DO UPDATE SET
                    dividend_per_share=excluded.dividend_per_share,
                    dividend_yield=excluded.dividend_yield,
                    payout_ratio=excluded.payout_ratio,
                    collected_at=excluded.collected_at
            """, (
                code, year,
                dv.get('dividend_per_share'),
                dv.get('dividend_yield'),
                dv.get('payout_ratio'),
                now_str()
            ))

        conn.commit()

    conn.close()
    log.info("=== 주주·배당 수집 완료 ===")

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=None)
    p.add_argument('--market', default=None)
    args = p.parse_args()
    main(limit=args.limit, market_filter=args.market)
