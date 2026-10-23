"""기간별 거래 구분 기준을 적용해 매매·전세 중앙값을 비교한다.

원천 DB는 읽기 전용으로 붙이고 임시 정규화 뷰만 메모리에 만든다.
Python에는 최종 Arrow 집계 결과만 전달한다.
"""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import math
import weakref
import duckdb
from src.config import DB_PATH
from projects.chapter07_price_gap_table.dashboard.metadata import prepare_nationwide, metadata_ctes
from src.preprocessing.complex_trades import normalize_trades as _normalize, _quoted

BANDS = ('10평 미만', '10평대', '20평대', '30평대', '40평대', '50평대', '60평 이상')
KEYS = '단지키, 시도, 시군구, 읍면동, 단지명, 주소, 평형대'
NUMERIC = ('매매가격','전세가격','갭','전세가율','매매건수','전세건수','고점년월','월중앙값고점','고점대비','건축년도','세대수')
SALE_TYPE_START = 202111
LEASE_TYPE_START = 202106


def lease_label(start):
    return '전세' if start < LEASE_TYPE_START else '신규 전세'

@dataclass(frozen=True)
class Query:
    start: int = 202606
    end: int = 202608
    sidos: tuple = ('서울특별시','경기도','인천광역시')
    regions: tuple = ()  # 시도+시군구: 서로 다른 시도의 동명 구를 분리
    dongs: tuple = ()    # 시도+시군구+읍면동
    bands: tuple = ('30평대',)
    floor_min: int | None = None
    floor_max: int | None = None
    area_min: float | None = None
    area_max: float | None = None

    def __post_init__(self):
        for ym in (self.start,self.end):
            if not 1900 <= ym//100 <= 2100 or not 1 <= ym%100 <= 12:
                raise ValueError('기간은 유효한 YYYYMM이어야 합니다.')
        if self.start > self.end:
            raise ValueError('시작월은 종료월보다 늦을 수 없습니다.')
        if self.floor_min is not None and self.floor_max is not None and self.floor_min > self.floor_max:
            raise ValueError('최저층은 최고층보다 클 수 없습니다.')
        if any(b not in BANDS for b in self.bands):
            raise ValueError('지원하지 않는 평형대입니다.')
        if any(value is not None and (not math.isfinite(value) or value < 0)
               for value in (self.area_min,self.area_max)):
            raise ValueError('전용면적은 0 이상의 유한한 수여야 합니다.')
        if self.area_min is not None and self.area_max is not None and self.area_min > self.area_max:
            raise ValueError('최소 전용면적은 최대 전용면적보다 클 수 없습니다.')


def database_path():
    return Path(os.environ.get('GAP_DB_PATH') or DB_PATH).expanduser()



def connect(path):
    path=Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f'데이터베이스가 없습니다. GAP_DB_PATH 또는 기본 DB 경로를 확인하세요: {path}')
    # 장기 조회의 디스크 임시 파일이 다른 연결·프로세스와 충돌하지 않게 한다.
    temporary=TemporaryDirectory(prefix='price_gap_')
    try:
        con=duckdb.connect(':memory:',config={'temp_directory':temporary.name})
    except Exception:
        temporary.cleanup(); raise
    weakref.finalize(con,temporary.cleanup)
    try:
        con.execute("SET memory_limit='1GB'")
        con.execute('SET threads=4')
        con.execute("ATTACH '"+str(path).replace("'","''")+"' AS source (READ_ONLY)")
        # 한쪽에만 지번이 있는 독자 DB에서는 양쪽 모두 완성된 도로명주소를 사용한다.
        use_lot=all({'번지','지번'} & {r[0] for r in con.execute(f'DESCRIBE source.main.{t}').fetchall()} for t in ('매매','전월세'))
        _normalize(con,'매매','sale',use_lot); _normalize(con,'전월세','lease',use_lot)
        tables={r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_catalog='source'").fetchall()}
        meta=next((t for t in ('공동주택_기본정보','공동주택정보','공동주택') if t in tables),None)
        cols={r[0] for r in con.execute(f'DESCRIBE source.main.{_quoted(meta)}').fetchall()} if meta else set()
        if {'도로명주소','세대수','단지코드'} <= cols:
            # 주소가 같은 복수 관리단지는 임의 합산하거나 첫 행을 선택하지 않는다.
            con.execute(f'''CREATE TEMP VIEW pg_meta AS SELECT regexp_replace(도로명주소,'\\s+','','g') AS 주소키,
              CASE WHEN count(DISTINCT 단지코드)=1 THEN max(세대수) END::INTEGER AS 세대수
              FROM source.main.{_quoted(meta)} WHERE 세대수>0 GROUP BY 1''')
        else:
            con.execute('CREATE TEMP VIEW pg_meta AS SELECT NULL::VARCHAR AS 주소키, NULL::INTEGER AS 세대수 WHERE FALSE')
        prepare_nationwide(con,tables)
        return con
    except Exception:
        con.close(); raise


def _where(q, *, current=False):
    conditions=['계약년월 <= ?']; args=[q.end]
    if current:
        conditions.append('계약년월 >= ?'); args.append(q.start)
    for values,expr in ((q.sidos,'시도'),(q.regions,"시도||' '||시군구"),(q.dongs,"시도||' '||시군구||' '||읍면동"),(q.bands,'평형대')):
        if values:
            conditions.append(expr+' IN ('+','.join('?' for _ in values)+')'); args.extend(values)
    if q.floor_min is not None: conditions.append('층 >= ?'); args.append(q.floor_min)
    if q.floor_max is not None: conditions.append('층 <= ?'); args.append(q.floor_max)
    if q.area_min is not None: conditions.append('전용면적 >= ?'); args.append(q.area_min)
    if q.area_max is not None: conditions.append('전용면적 <= ?'); args.append(q.area_max)
    return ' AND '.join(conditions),args


def comparison_sql(q):
    w,args=_where(q)
    sql=f'''WITH {metadata_ctes(q.end)}, sales AS (SELECT * FROM pg_sale WHERE {w}),
    cur AS (SELECT {KEYS}, median(가격) AS 매매가격, count(*)::INTEGER AS 매매건수,
      min(건축년도)::INTEGER AS 건축년도, max(도로명주소) AS 도로명주소 FROM sales WHERE 계약년월 >= ? GROUP BY {KEYS}),
    rents AS (SELECT {KEYS}, median(가격) AS 전세가격, count(*)::INTEGER AS 전세건수,
      min(건축년도)::INTEGER AS 건축년도, max(도로명주소) AS 도로명주소 FROM pg_lease WHERE {w} AND 계약년월 >= ? GROUP BY {KEYS}),
    months AS (SELECT 단지키,평형대,계약년월,median(가격) AS 월중앙값,count(*)::INTEGER AS 고점월건수 FROM sales GROUP BY 1,2,3),
    peaks AS (SELECT * FROM months QUALIFY row_number() OVER (PARTITION BY 단지키,평형대 ORDER BY 월중앙값 DESC,계약년월 DESC)=1),
    firsts AS (SELECT 단지키,평형대,min(계약년월) AS 고점조회시작월 FROM sales GROUP BY 1,2),
    joined AS (SELECT {','.join('coalesce(c.'+k.strip()+',r.'+k.strip()+') AS '+k.strip() for k in KEYS.split(','))},
      c.매매가격,r.전세가격,coalesce(c.매매건수,0)::INTEGER AS 매매건수,coalesce(r.전세건수,0)::INTEGER AS 전세건수,
      coalesce(c.건축년도,r.건축년도) AS 건축년도, coalesce(c.도로명주소,r.도로명주소) AS 도로명주소
      FROM cur c FULL OUTER JOIN rents r ON c.단지키=r.단지키 AND c.평형대=r.평형대)
    SELECT j.*,j.매매가격-j.전세가격 AS 갭,100*j.전세가격/nullif(j.매매가격,0) AS 전세가율,
      p.월중앙값 AS 월중앙값고점,p.계약년월 AS 고점년월,p.고점월건수,f.고점조회시작월,
      100*j.매매가격/nullif(p.월중앙값,0) AS 고점대비,
      coalesce(n.세대수,CASE WHEN an.단지명수=1 AND nl.건축년도=j.건축년도 THEN nl.세대수 END,m.세대수,CASE WHEN j.주소=j.도로명주소 AND l.주소수=1 AND nn.건축년도=j.건축년도 THEN nn.세대수 END) AS 세대수
    FROM joined j LEFT JOIN peaks p USING(단지키,평형대) LEFT JOIN firsts f USING(단지키,평형대)
    LEFT JOIN address_names an ON j.주소=an.주소
    LEFT JOIN nation_lot nl ON j.주소=nl.주소
    LEFT JOIN nation_address n ON j.주소=n.주소 AND j.단지명=n.단지명
    LEFT JOIN locations l ON concat_ws(' ',j.시도,j.시군구,j.읍면동)=l.지역 AND j.단지명=l.단지명
    LEFT JOIN nation_name nn ON l.지역=nn.지역 AND l.단지명=nn.단지명
    LEFT JOIN pg_meta m ON regexp_replace(j.도로명주소,'\\s+','','g')=m.주소키
    ORDER BY j.시도,j.시군구,j.단지명,j.주소,j.평형대'''
    return sql,args+[q.start]+args+[q.start]


def compare(path, q):
    con=connect(path)
    try:
        sql,params=comparison_sql(q)
        return con.execute(sql,params).fetch_arrow_table()
    finally: con.close()


def monthly(path,q,keys):
    if not keys: raise ValueError('분석할 단지를 선택하세요.')
    w,args=_where(q)
    key_sql=','.join('?' for _ in keys)
    con=connect(path)
    try:
        parts=[]; params=[]
        for src,kind in [('sale','매매'),('lease','전세')]:
            parts.append(f"SELECT 단지키,평형대,계약년월,'{kind}' AS 종류,median(가격) AS 가격,count(*)::INTEGER AS 건수 FROM pg_{src} WHERE {w} AND 단지키 IN ({key_sql}) GROUP BY 1,2,3")
            params.extend(args+list(keys))
        return con.execute(f'''WITH x AS ({' UNION ALL '.join(parts)}) SELECT 단지키,평형대,계약년월,
          max(가격) FILTER(WHERE 종류='매매') AS 매매가격,max(가격) FILTER(WHERE 종류='전세') AS 전세가격,
          coalesce(max(건수) FILTER(WHERE 종류='매매'),0) AS 매매건수,coalesce(max(건수) FILTER(WHERE 종류='전세'),0) AS 전세건수
          FROM x GROUP BY 1,2,3 ORDER BY 1,2,3''',params).fetch_arrow_table()
    finally: con.close()


def filter_sort(table,*,sort='고점대비',descending=False,sale_min=None,sale_max=None,lease_min=None,lease_max=None,gap_min=None,gap_max=None,min_sale=0,min_lease=0):
    if sort not in NUMERIC: raise ValueError('지원하지 않는 정렬 항목입니다.')
    clauses=['매매건수 >= ?','전세건수 >= ?']; params=[min_sale,min_lease]
    for value,expr in [(sale_min,'매매가격 >= ?'),(sale_max,'매매가격 <= ?'),(lease_min,'전세가격 >= ?'),(lease_max,'전세가격 <= ?'),(gap_min,'갭 >= ?'),(gap_max,'갭 <= ?')]:
        if value is not None: clauses.append(expr); params.append(value)
    c=duckdb.connect(':memory:')
    try:
        c.register('results',table)
        return c.execute(f"SELECT * FROM results WHERE {' AND '.join(clauses)} ORDER BY {_quoted(sort)} {'DESC' if descending else 'ASC'} NULLS LAST,단지키,평형대",params).fetch_arrow_table()
    finally: c.close()


def inventory(path):
    c=connect(path)
    try:
        regions=c.execute('SELECT DISTINCT 시도,시군구,읍면동 FROM pg_sale UNION SELECT DISTINCT 시도,시군구,읍면동 FROM pg_lease ORDER BY 1,2,3').fetchall()
        dates=c.execute('SELECT min(계약년월),max(계약년월) FROM (SELECT 계약년월 FROM pg_sale UNION ALL SELECT 계약년월 FROM pg_lease)').fetchone()
        return regions,dates
    finally: c.close()


def floor_limits(path):
    c=connect(path)
    try:
        low,high=c.execute('SELECT min(층),max(층) FROM (SELECT 층 FROM pg_sale UNION ALL SELECT 층 FROM pg_lease)').fetchone()
        # 기존 기본값 2~100층을 유지하면서 DB에 수록된 지하층·고층도 선택할 수 있다.
        return min(1,low if low is not None else 1),max(100,high if high is not None else 100)
    finally: c.close()


def area_limits(path,q):
    """선택한 지역·평형대의 매매·전세에서 확인되는 면적 범위를 구한다."""
    where,args=_where(q)
    c=connect(path)
    try:
        return c.execute(f'''SELECT min(전용면적),max(전용면적) FROM (
          SELECT 전용면적 FROM pg_sale WHERE {where}
          UNION ALL SELECT 전용면적 FROM pg_lease WHERE {where})
          WHERE isfinite(전용면적)''',args+args).fetchone()
    finally: c.close()
