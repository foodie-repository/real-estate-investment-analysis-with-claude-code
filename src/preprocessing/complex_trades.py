"""두 대시보드에서 같은 주소·단지·평형대를 식별하는 읽기 전용 정규화 뷰."""
from src.utils.address import SIDO_SQL, SIGUNGU_SQL, EUPMYEONDONG_SQL

SALE_TYPE_START = 202111
LEASE_TYPE_START = 202106

def _quoted(name):
    return '"'+name.replace('"','""')+'"'


def normalize_trades(con, table, kind, use_lot=True, *, detail=False, direct=False):
    columns={r[0] for r in con.execute(f'DESCRIBE source.main.{_quoted(table)}').fetchall()}
    area='전용면적(㎡)' if '전용면적(㎡)' in columns else '전용면적'
    money=('거래금액(만원)' if '거래금액(만원)' in columns else '거래금액') if kind=='sale' else ('보증금(만원)' if '보증금(만원)' in columns else '보증금')
    needed={'시군구','단지명',area,money,'계약년월','층','도로명'}
    needed |= {'거래유형','해제사유발생일'} if kind=='sale' else ({'전월세구분'} if detail else {'전월세구분','계약구분'})
    missing=needed-columns
    if missing:
        raise ValueError(f'{table}에 필요한 항목이 없습니다: {", ".join(sorted(missing))}')
    # 외부 DB는 지역 분리 컬럼을 사용하고 독자 DB는 공통 주소 파서를 재사용한다.
    sido='trim(시도)' if '시도' in columns else SIDO_SQL
    gu='trim(시군구)' if '시도' in columns else SIGUNGU_SQL
    dong="coalesce(trim(읍면동),'')" if '읍면동' in columns else EUPMYEONDONG_SQL
    if '리' in columns:
        dong=f"trim(({dong}) || CASE WHEN nullif(trim(리),'') IS NOT NULL AND NOT ends_with(({dong}),trim(리)) THEN ' '||trim(리) ELSE '' END)"
    year='try_cast(건축년도 AS INTEGER)' if '건축년도' in columns else 'NULL::INTEGER'
    # 구분 항목 제공 전의 미상 거래만 포함한다. 직거래·갱신 명시 건은 전 기간 제외한다.
    if detail:
        # 9장 상세 이력은 전세의 신규·갱신을 모두 포함한다.
        if kind == 'sale':
            where = "(해제사유발생일 IS NULL OR 해제사유발생일 IN ('None','-',''))"
            if not direct:
                where += " AND (거래유형 IS NULL OR 거래유형 != '직거래')"
        else:
            where = "전월세구분='전세'"
    else:
        type_column, known, cutoff = ('거래유형','중개거래',SALE_TYPE_START) if kind=='sale' else ('계약구분','신규',LEASE_TYPE_START)
        unknown=f"coalesce(lower(trim(cast({type_column} AS VARCHAR))), '') IN ('','-','none','nan','null')"
        eligible=f"(trim({type_column})='{known}' OR (try_cast(계약년월 AS INTEGER)<{cutoff} AND {unknown}))"
        where=eligible+" AND coalesce(lower(trim(cast(해제사유발생일 AS VARCHAR))), '') IN ('','-','none','nan','null')" if kind=='sale' else "trim(전월세구분)='전세' AND "+eligible
    if '주택유형' in columns:
        where += " AND 주택유형 = '아파트'"
    road="trim(regexp_replace(coalesce(도로명,''), '\\s+', ' ', 'g'))"
    # 매매 도로명은 건물번호가 누락될 수 있어 공통 지번을 우선한다.
    lot_column=next((name for name in ('번지','지번') if name in columns),None)
    lot=f"nullif(trim(cast({_quoted(lot_column)} AS VARCHAR)),'')" if use_lot and lot_column else 'NULL::VARCHAR'
    lot = f"CASE WHEN regexp_full_match({lot}, '[0-9]+(-[0-9]+)?') THEN cast(try_cast(split_part({lot},'-',1) AS BIGINT) AS VARCHAR) || CASE WHEN coalesce(try_cast(split_part({lot},'-',2) AS BIGINT),0)>0 THEN '-'||cast(try_cast(split_part({lot},'-',2) AS BIGINT) AS VARCHAR) ELSE '' END ELSE {lot} END"
    con.execute(f'''CREATE TEMP VIEW pg_{kind} AS
      WITH n AS (SELECT {sido} AS 시도, {gu} AS 시군구, {dong} AS 읍면동,
        regexp_replace(trim(단지명),'\\s+','','g') AS 단지명, {road} AS 도로명, {lot} AS 번지,
        try_cast({_quoted(area)} AS DOUBLE) AS 전용면적,
        try_cast(replace(cast({_quoted(money)} AS VARCHAR), ',', '') AS DOUBLE) AS 가격,
        try_cast(계약년월 AS INTEGER) AS 계약년월, try_cast(층 AS INTEGER) AS 층,
        {year} AS 건축년도 FROM source.main.{_quoted(table)} WHERE {where}),
      a AS (SELECT *, CASE WHEN 번지 IS NOT NULL AND 번지 NOT IN ('-','0') AND 읍면동 <> '' THEN concat_ws(' ',시도,시군구,읍면동,번지)
        WHEN regexp_matches(도로명, ' [0-9]+(-[0-9]+)?$') THEN concat_ws(' ',시도,시군구,도로명) END AS 주소,
        CASE WHEN regexp_matches(도로명, ' [0-9]+(-[0-9]+)?$') THEN concat_ws(' ',시도,시군구,도로명) END AS 도로명주소,
        CASE WHEN floor(전용면적*0.4)<10 THEN '10평 미만' WHEN floor(전용면적*0.4)>=60 THEN '60평 이상'
          ELSE cast(cast(floor(전용면적*0.4/10)*10 AS INTEGER) AS VARCHAR)||'평대' END AS 평형대
        FROM n WHERE 가격>0 AND 전용면적>0 AND nullif(단지명,'') IS NOT NULL)
      SELECT *, md5(to_json(list_value(시도,시군구,읍면동,주소,regexp_replace(단지명,'\\s+','','g')))) AS 단지키
      FROM a WHERE 주소 IS NOT NULL''')
