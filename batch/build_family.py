"""Obsidian 마크다운 → secomdal.com 정적 가계도 JSON 변환.

매일 또는 수동 실행:
  python -m batch.build_family

입력:
  ~/Obsidian/Obsidian_Storage/한국 재벌가 가계도 데이터.md

출력:
  web/data/family.json  (인물·관계·인물회사 통합)
"""

from __future__ import annotations
import json, os, re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
MD_PATH = Path.home() / 'Obsidian/Obsidian_Storage/한국 재벌가 가계도 데이터.md'
OUT_PATH = ROOT / 'web/data/family.json'


def _clean(v):
    if v is None: return None
    s = str(v).strip()
    if s in ('', '-', '—', 'null', 'None'): return None
    return s


def parse_md_table(md_text: str, section_keyword: str):
    """## 섹션 제목에 키워드를 포함하는 첫 표 파싱."""
    pat = re.compile(r'^##\s+.*' + re.escape(section_keyword), re.M)
    m = pat.search(md_text)
    if not m:
        return []
    body = md_text[m.end():]
    nx = re.search(r'^##\s', body, re.M)
    if nx:
        body = body[:nx.start()]

    rows, headers = [], None
    for line in body.split('\n'):
        line = line.strip()
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if all(re.match(r'^:?-+:?$', c) for c in cells if c):
            continue
        if headers is None:
            headers = cells
            continue
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def build():
    if not MD_PATH.exists():
        raise SystemExit(f'❌ 마크다운 없음: {MD_PATH}')

    text = MD_PATH.read_text(encoding='utf-8')

    persons_raw = parse_md_table(text, '인물')
    relations_raw = parse_md_table(text, '가족 관계')
    pc_raw = parse_md_table(text, '인물-회사')

    persons = []
    for r in persons_raw:
        if not _clean(r.get('id')): continue
        persons.append({
            'id': _clean(r.get('id')),
            'name': _clean(r.get('name')),
            'name_alt': _clean(r.get('name_alt')),
            'birth': int(_clean(r.get('birth')) or 0) or None,
            'death': int(_clean(r.get('death')) or 0) or None,
            'gender': _clean(r.get('gender')),
            'group': _clean(r.get('group')),
            'gen': int(_clean(r.get('gen')) or 0) or None,
            'role': _clean(r.get('role')),
            'notes': _clean(r.get('notes')),
        })

    relations = []
    for r in relations_raw:
        f, t = _clean(r.get('from_id')), _clean(r.get('to_id'))
        if not f or not t: continue
        div = _clean(r.get('divorced'))
        relations.append({
            'from': f, 'to': t,
            'type': _clean(r.get('rel_type')),
            'divorced': bool(div and div.isdigit() and int(div)),
            'notes': _clean(r.get('notes')),
        })

    pc = []
    for r in pc_raw:
        if not _clean(r.get('person_id')): continue
        pct = _clean(r.get('ownership_pct'))
        try: pct = float(pct) if pct else None
        except ValueError: pct = None
        pc.append({
            'person': _clean(r.get('person_id')),
            'code': _clean(r.get('code')),
            'company': _clean(r.get('company')),
            'role': _clean(r.get('role')),
            'pct': pct,
        })

    out = {
        'updated': datetime.now().isoformat(timespec='seconds'),
        'count_persons': len(persons),
        'count_relations': len(relations),
        'count_companies': len(pc),
        'persons': persons,
        'relations': relations,
        'companies': pc,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'✅ {OUT_PATH} 생성 — 인물 {len(persons)}, 관계 {len(relations)}, 회사 {len(pc)}')


if __name__ == '__main__':
    build()
