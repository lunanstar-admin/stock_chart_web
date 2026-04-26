"""
Step 9: 한국 주요 재벌가 가족·혼인 관계 데이터

데이터 원본:
  Obsidian: /Users/kimkihong/Obsidian/Obsidian_Storage/한국 재벌가 가계도 데이터.md

사용법:
  python3 09_chaebol_family.py            # Obsidian 마크다운에서 자동 로드
  python3 09_chaebol_family.py --inline   # 이 파일 안의 INLINE 데이터 사용 (백업)
  python3 09_chaebol_family.py --md PATH  # 다른 마크다운 파일 경로 지정
"""
import sys, os, re, argparse
sys.path.insert(0, os.path.dirname(__file__))
from base import get_conn, now_str, log

# 가계도 마크다운 — 환경변수 CHAEBOL_MD 우선
# 기본: stock_chart_web/data_md/chaebol_family.md (repo 안에 commit)
# 폴백: ~/Obsidian/.../한국 재벌가 가계도 데이터.md (사용자 로컬 작업용)
DEFAULT_MD = os.environ.get(
    'CHAEBOL_MD',
    os.path.join(os.path.dirname(__file__), '..', 'data_md', 'chaebol_family.md'),
)
if not os.path.exists(DEFAULT_MD):
    _fallback = os.path.expanduser('~/Obsidian/Obsidian_Storage/한국 재벌가 가계도 데이터.md')
    if os.path.exists(_fallback):
        DEFAULT_MD = _fallback


def _clean(v):
    """셀 값 정리: '-' 또는 빈 칸은 None"""
    if v is None: return None
    v = str(v).strip()
    if v in ('', '-', '—', 'null', 'None'): return None
    return v


def parse_md_table(md_text, section_title):
    """
    마크다운 섹션의 첫 번째 테이블을 파싱.
    섹션 제목(예: '## 1. 인물 (persons)') 아래의 첫 표만 읽는다.
    Returns: list of dict (헤더 키 사용)
    """
    # 섹션 시작 찾기
    pat = re.compile(r'^##\s+.*' + re.escape(section_title), re.M)
    m = pat.search(md_text)
    if not m:
        log.warning(f"섹션 '{section_title}' 못 찾음")
        return []
    body = md_text[m.end():]

    # 다음 ## 섹션까지 자르기
    next_sec = re.search(r'^##\s', body, re.M)
    if next_sec:
        body = body[:next_sec.start()]

    rows = []
    headers = None
    for line in body.split('\n'):
        line = line.strip()
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        # 구분선 (---|---) 무시
        if all(re.match(r'^:?-+:?$', c) for c in cells if c):
            continue
        if headers is None:
            headers = cells
            continue
        if len(cells) != len(headers):
            continue
        row = dict(zip(headers, cells))
        rows.append(row)
    return rows


def load_from_markdown(md_path):
    """마크다운에서 인물·관계·인물회사 데이터 로드"""
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"마크다운 파일 없음: {md_path}")

    with open(md_path, 'r', encoding='utf-8') as f:
        text = f.read()

    persons_raw = parse_md_table(text, '인물')
    relations_raw = parse_md_table(text, '가족 관계')
    pc_raw = parse_md_table(text, '인물-회사')

    persons = []
    for r in persons_raw:
        if not r.get('id'): continue
        persons.append((
            _clean(r.get('id')),
            _clean(r.get('name')),
            _clean(r.get('name_alt')),
            int(_clean(r.get('birth')) or 0) or None,
            int(_clean(r.get('death')) or 0) or None,
            _clean(r.get('gender')),
            _clean(r.get('group')),
            int(_clean(r.get('gen')) or 0) or None,
            _clean(r.get('role')),
            _clean(r.get('notes')),
        ))

    relations = []
    for r in relations_raw:
        if not r.get('from_id') or not r.get('to_id'): continue
        div = _clean(r.get('divorced'))
        relations.append((
            _clean(r.get('from_id')),
            _clean(r.get('to_id')),
            _clean(r.get('rel_type')),
            int(div) if div and div.isdigit() else 0,
            _clean(r.get('notes')),
        ))

    pc = []
    for r in pc_raw:
        if not r.get('person_id'): continue
        pct = _clean(r.get('ownership_pct'))
        try:
            pct = float(pct) if pct else None
        except ValueError:
            pct = None
        pc.append((
            _clean(r.get('person_id')),
            _clean(r.get('code')),
            _clean(r.get('company')),
            _clean(r.get('role')),
            pct,
        ))

    return persons, relations, pc


# ─── 인라인 백업 데이터 (--inline 옵션) ────────────────────────────────
# 마크다운 파일이 없을 때 비상용
INLINE_PERSONS = [
    ('lee_byungchul', '이병철', 'Lee Byung-chul', 1910, 1987, 'M', '삼성그룹', 1, '창업주', '삼성그룹 창업주'),
    ('lee_kunhee',    '이건희', 'Lee Kun-hee', 1942, 2020, 'M', '삼성그룹', 2, '회장', '삼성 2대 회장'),
    # ... (간략화: Obsidian이 메인 소스)
]
INLINE_RELATIONS = []
INLINE_PERSON_COMPANY = []


def write_db(persons, relations, pc):
    conn = get_conn()
    c = conn.cursor()

    c.execute("DELETE FROM person_company_links")
    c.execute("DELETE FROM family_relations")
    c.execute("DELETE FROM chaebol_persons")

    for p in persons:
        try:
            c.execute("""
                INSERT INTO chaebol_persons
                    (id, name, name_alt, birth_year, death_year, gender, group_name,
                     generation, role, notes, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, p + (now_str(),))
        except Exception as e:
            log.error(f"인물 INSERT 실패 {p[0]}: {e}")

    for r in relations:
        from_id, to_id, rt, div, notes = r
        try:
            c.execute("""
                INSERT OR IGNORE INTO family_relations
                    (from_id, to_id, rel_type, is_divorced, notes, updated_at)
                VALUES (?,?,?,?,?,?)
            """, (from_id, to_id, rt, div, notes, now_str()))
        except Exception as e:
            log.error(f"관계 INSERT 실패 {r}: {e}")

    for pc_row in pc:
        try:
            c.execute("""
                INSERT OR IGNORE INTO person_company_links
                    (person_id, code, company_name, role, ownership_pct, updated_at)
                VALUES (?,?,?,?,?,?)
            """, pc_row + (now_str(),))
        except Exception as e:
            log.error(f"회사링크 INSERT 실패 {pc_row}: {e}")

    conn.commit()

    # 통계
    n_p = c.execute("SELECT COUNT(*) FROM chaebol_persons").fetchone()[0]
    n_r = c.execute("SELECT COUNT(*) FROM family_relations").fetchone()[0]
    n_pc = c.execute("SELECT COUNT(*) FROM person_company_links").fetchone()[0]
    n_groups = c.execute("SELECT COUNT(DISTINCT group_name) FROM chaebol_persons WHERE group_name IS NOT NULL").fetchone()[0]
    log.info(f"✅ 저장 완료: 인물 {n_p}명 / 관계 {n_r}건 / 회사링크 {n_pc}건 / 그룹 {n_groups}개")
    conn.close()


def main():
    p = argparse.ArgumentParser(description='재벌가 가계도 데이터 시드')
    p.add_argument('--md', default=DEFAULT_MD, help='Obsidian 마크다운 경로')
    p.add_argument('--inline', action='store_true', help='파일 내 INLINE 데이터 사용 (비상용)')
    args = p.parse_args()

    if args.inline:
        log.info("📝 INLINE 데이터 사용")
        persons = INLINE_PERSONS
        relations = INLINE_RELATIONS
        pc = INLINE_PERSON_COMPANY
    else:
        log.info(f"📖 마크다운 로드: {args.md}")
        persons, relations, pc = load_from_markdown(args.md)
        log.info(f"   파싱: 인물 {len(persons)}명, 관계 {len(relations)}건, 회사링크 {len(pc)}건")

    write_db(persons, relations, pc)


if __name__ == '__main__':
    main()
