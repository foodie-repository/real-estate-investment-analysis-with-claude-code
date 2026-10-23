"""7장에서 전달한 정확한 주소·단지·평형대만 SQL로 조회한다."""
from contextlib import contextmanager
from pathlib import Path

import duckdb

from src.preprocessing.complex_trades import normalize_trades
from src.utils.dashboard_link import validate_selection


@contextmanager
def _connection(path, direct=False):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise ValueError('가격·거래량 대시보드의 DB를 찾을 수 없습니다.')
    con = duckdb.connect(':memory:')
    try:
        con.execute("SET memory_limit='1GB'")
        con.execute('SET threads=4')
        con.execute("ATTACH '"+str(path).replace("'", "''")+"' AS source (READ_ONLY)")
        use_lot = all({'번지', '지번'} & {r[0] for r in con.execute(f'DESCRIBE source.main.{t}').fetchall()}
                      for t in ('매매', '전월세'))
        normalize_trades(con, '매매', 'sale', use_lot, detail=True, direct=direct)
        normalize_trades(con, '전월세', 'lease', use_lot, detail=True)
        yield con
    finally:
        con.close()


def _select_targets(con, targets):
    targets = validate_selection(dict(v=1, targets=targets))['targets']
    con.execute('CREATE TEMP TABLE selected_targets (시도 VARCHAR, 시군구 VARCHAR, 읍면동 VARCHAR, 단지명 VARCHAR, 주소 VARCHAR, 평형대 VARCHAR)')
    con.executemany('INSERT INTO selected_targets VALUES (?, ?, ?, ?, ?, ?)', targets)
    keys = '시도,시군구,읍면동,단지명,주소,평형대'
    for kind in ('sale', 'lease'):
        con.execute(f'CREATE TEMP TABLE selected_{kind} AS SELECT p.* FROM pg_{kind} p JOIN selected_targets USING ({keys})')
    return targets


def linked_bounds(path, targets):
    with _connection(path) as con:
        _select_targets(con, targets)
        row = con.execute('''SELECT min(계약년월),max(계약년월),min(전용면적),max(전용면적)
            FROM (SELECT 계약년월,전용면적 FROM selected_sale UNION ALL SELECT 계약년월,전용면적 FROM selected_lease)''').fetchone()
    return row


def load_linked_data(path, targets, area, period, trade_type, direct=False):
    """원자료는 SQL에서 제한하며, 기존 9장 차트가 요구하는 최종 자료만 DataFrame으로 넘긴다."""
    validated = validate_selection(dict(v=1, targets=targets, area=area, period=period))
    area, period = validated['area'], validated['period']
    if trade_type not in ('매매+전세', '매매만', '전세만'):
        raise ValueError('거래유형을 확인하세요.')
    with _connection(path, direct) as con:
        targets = _select_targets(con, validated['targets'])
        clauses, args = ['계약년월 BETWEEN ? AND ?'], list(period)
        if area is not None:
            clauses.append('전용면적 BETWEEN ? AND ?')
            args.extend(area)
        where = ' AND '.join(clauses)
        label = "단지명 || ' · ' || 평형대 || ' (' || 주소 || ')'"
        individual, monthly, found = {}, {}, set()
        for name, kind in (('매매', 'sale'), ('전세', 'lease')):
            if trade_type == '매매만' and kind == 'lease' or trade_type == '전세만' and kind == 'sale':
                continue
            table = f'selected_{kind}'
            individual[name] = con.execute(f'''SELECT 계약년월,단지명,전용면적,ROUND(가격/10000,1) AS 가격_억,
                층,CAST(FLOOR(전용면적*0.4) AS INTEGER) AS 추정평형,평형대,{label} AS 비교대상
                FROM {table} WHERE {where} ORDER BY 계약년월,주소,평형대''', args).fetchdf()
            monthly[name] = con.execute(f'''SELECT 계약년월,median(가격)/10000 AS 중위가_억,
                count(*) AS 거래량,{label} AS 비교대상 FROM {table} WHERE {where}
                GROUP BY 계약년월,단지명,평형대,주소 ORDER BY 계약년월,비교대상''', args).fetchdf()
            found.update(con.execute(f'SELECT DISTINCT 시도,시군구,읍면동,단지명,주소,평형대 FROM {table} WHERE {where}', args).fetchall())
        n, high, low = con.execute(f'''SELECT count(*),ROUND(max(가격)/10000,1),ROUND(min(가격)/10000,1)
            FROM selected_sale WHERE {where}''', args).fetchone()
        recent = con.execute(f'''SELECT 계약년월,단지명,전용면적,ROUND(가격/10000,1) AS 가격_억,층
            FROM selected_sale WHERE {where} ORDER BY 계약년월 DESC,가격 DESC LIMIT 3''', args).fetchdf()
    return dict(individual=individual, monthly=monthly, missing=[t for t in targets if t not in found],
                stats=dict(총거래건수=n, 최고가_억=high, 최저가_억=low, 최근거래=recent))
