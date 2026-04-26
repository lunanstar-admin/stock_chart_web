"""
Step 7: 종속/관계회사 정보 (DART 타법인 출자현황 API)
- API: otrCprInvstmntSttus.json
- 병렬 처리 (ThreadPoolExecutor) - 10 workers
- 지분율, 장부가액, 자회사 자산/순이익 등 수집
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from base import get_conn, now_str, safe_int, safe_float, log, DART_API_KEY

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import threading

CURRENT_YEAR = datetime.now().year
DEFAULT_YEAR = CURRENT_YEAR - 1   # 직전 사업연도

_db_lock = threading.Lock()


def fetch_subsidiaries_dart(corp_code: str, year: int) -> list:
    """DART 타법인 출자현황 API"""
    try:
        r = requests.get(
            'https://opendart.fss.or.kr/api/otrCprInvstmntSttus.json',
            params={
                'crtfc_key': DART_API_KEY,
                'corp_code': corp_code,
                'bsns_year': str(year),
                'reprt_code': '11011',  # 사업보고서
            },
            timeout=15
        )
        d = r.json()
        if d.get('status') != '000':
            return []
        return d.get('list', [])
    except Exception as e:
        log.debug(f"DART 자회사 오류 ({corp_code}/{year}): {e}")
        return []


def parse_subsidiary(parent_code, parent_corp_code, parent_name, item, bsns_year):
    """타법인 출자 항목 → DB 레코드"""
    return (
        parent_code,
        parent_corp_code,
        parent_name,
        item.get('inv_prm', ''),                                    # 출자대상회사
        None,                                                        # sub_corp_code (later resolve)
        None,                                                        # sub_code (later resolve)
        item.get('invstmnt_purps', ''),                             # 출자목적
        safe_float(item.get('trmend_blce_qota_rt')),                # 기말 지분율
        safe_int(item.get('trmend_blce_acntbk_amount')),            # 기말 장부가액
        safe_int(item.get('recent_bsns_year_fnnr_sttus_tot_assets')),
        safe_int(item.get('recent_bsns_year_fnnr_sttus_thstrm_ntpf')),
        item.get('frst_acqs_de', ''),
        item.get('stlm_dt', ''),
        bsns_year,
        now_str(),
    )


def process_company(row, year: int):
    """단일 모회사 처리 → 자회사 리스트"""
    code, corp_code, name = row
    items = fetch_subsidiaries_dart(corp_code, year)
    if not items:
        return code, []
    records = [parse_subsidiary(code, corp_code, name, it, year) for it in items if it.get('inv_prm')]
    return code, records


def main(limit=None, market_filter=None, year=DEFAULT_YEAR, workers=10):
    conn = get_conn()
    c = conn.cursor()

    query = """
        SELECT code, corp_code, name
        FROM companies
        WHERE corp_code IS NOT NULL AND corp_code != ''
    """
    params = []
    if market_filter:
        query += " AND market = ?"
        params.append(market_filter)
    query += " ORDER BY market_cap_rank ASC"
    if limit:
        query += f" LIMIT {limit}"

    rows = c.execute(query, params).fetchall()
    rows = [(r[0], r[1], r[2]) for r in rows]
    log.info(f"종속회사 수집 대상: {len(rows)}개 ({year}년 사업보고서, workers={workers})")

    total_subs = 0
    processed = 0

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(process_company, row, year): row for row in rows}

        for fut in as_completed(futures):
            try:
                code, records = fut.result()
            except Exception as e:
                log.error(f"처리 오류: {e}")
                continue

            processed += 1

            if records:
                with _db_lock:
                    cc = conn.cursor()
                    for rec in records:
                        try:
                            cc.execute("""
                                INSERT INTO subsidiaries
                                    (parent_code, parent_corp_code, parent_name, sub_name,
                                     sub_corp_code, sub_code, investment_purpose, ownership_pct,
                                     book_value, sub_total_assets, sub_net_income,
                                     first_acq_date, report_date, bsns_year, collected_at)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                                ON CONFLICT(parent_corp_code, sub_name, bsns_year) DO UPDATE SET
                                    ownership_pct=excluded.ownership_pct,
                                    book_value=excluded.book_value,
                                    sub_total_assets=excluded.sub_total_assets,
                                    sub_net_income=excluded.sub_net_income,
                                    collected_at=excluded.collected_at
                            """, rec)
                        except Exception as e:
                            log.debug(f"INSERT 오류: {e}")
                    conn.commit()
                total_subs += len(records)

            if processed % 50 == 0:
                log.info(f"  진행: {processed}/{len(rows)} (자회사 누적 {total_subs})")

    log.info(f"=== 종속회사 수집 완료: {processed}/{len(rows)} 모회사, {total_subs}건 ===")

    # 상장 자회사 매칭 (sub_name → companies.code)
    log.info("상장 자회사 매칭...")
    matched = c.execute("""
        UPDATE subsidiaries
        SET sub_code = (
            SELECT code FROM companies
            WHERE TRIM(REPLACE(REPLACE(REPLACE(companies.name, '㈜', ''), '(주)', ''), ' ', ''))
                = TRIM(REPLACE(REPLACE(REPLACE(subsidiaries.sub_name, '㈜', ''), '(주)', ''), ' ', ''))
            LIMIT 1
        )
        WHERE sub_code IS NULL
    """).rowcount
    conn.commit()
    log.info(f"  상장사 매칭: {matched}건")

    conn.close()


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=None)
    p.add_argument('--market', default=None)
    p.add_argument('--year', type=int, default=DEFAULT_YEAR)
    p.add_argument('--workers', type=int, default=10)
    p.add_argument('--reset', action='store_true')
    args = p.parse_args()
    main(limit=args.limit, market_filter=args.market, year=args.year, workers=args.workers)
