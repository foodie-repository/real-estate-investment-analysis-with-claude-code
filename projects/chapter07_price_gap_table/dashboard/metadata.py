"""3장의 공동주택 정보로 세대수를 연결한다. 주소가 모호한 후보는 남겨둔다."""


def prepare_nationwide(con, tables):
    if '공동주택_전국' not in tables:
        con.execute('''CREATE TEMP VIEW pg_nation AS SELECT NULL::VARCHAR AS 단지고유번호,
            NULL::VARCHAR AS 주소, NULL::VARCHAR AS 지역, NULL::VARCHAR AS 단지명,
            NULL::INTEGER AS 세대수, NULL::INTEGER AS 건축년도 WHERE FALSE''')
        return
    columns={r[0] for r in con.execute('DESCRIBE source.main.공동주택_전국').fetchall()}
    required={'단지고유번호','주소','단지명','세대수','단지구분코드'}
    if not required <= columns:
        raise ValueError('공동주택_전국에 필요한 항목이 없습니다: '+', '.join(sorted(required-columns)))
    year="try_cast(left(cast(사용승인일 AS VARCHAR),4) AS INTEGER)" if '사용승인일' in columns else 'NULL::INTEGER'
    con.execute(f'''CREATE TEMP VIEW pg_nation AS
        WITH n AS (SELECT cast(단지고유번호 AS VARCHAR) AS 단지고유번호,
            trim(regexp_replace(주소,'\\s+',' ','g')) AS 주소,
            regexp_replace(trim(단지명),'\\s+','','g') AS 단지명,
            try_cast(세대수 AS INTEGER) AS 세대수, {year} AS 건축년도
            FROM source.main.공동주택_전국 WHERE trim(cast(단지구분코드 AS VARCHAR))='1')
        SELECT *, regexp_extract(주소,'^(.*) [산]?[0-9]+(-[0-9]+)?$',1) AS 지역
        FROM n WHERE 세대수>0 AND nullif(단지고유번호,'') IS NOT NULL AND nullif(주소,'') IS NOT NULL''')


def metadata_ctes(end):
    # 이름으로 보완할 때도 같은 법정동·이름·연도이고 양쪽 주소가 유일해야 한다.
    # 선택한 평형/기간 밖에 동명 단지가 있는지도 확인하여 필터에 따른 오연결을 막는다.
    return f'''identity_rows AS (
        SELECT 시도,시군구,읍면동,단지명,주소 FROM pg_sale WHERE 계약년월<={end}
        UNION ALL SELECT 시도,시군구,읍면동,단지명,주소 FROM pg_lease WHERE 계약년월<={end}),
    address_names AS (SELECT 주소,count(DISTINCT 단지명) AS 단지명수 FROM identity_rows GROUP BY 1),
    nation_lot AS (
        SELECT 주소,CASE WHEN count(DISTINCT 단지고유번호)=1 AND count(DISTINCT 세대수)=1
            THEN max(세대수) END AS 세대수,
            CASE WHEN count(DISTINCT 건축년도)=1 THEN max(건축년도) END AS 건축년도
        FROM pg_nation GROUP BY 1),
    locations AS (
        SELECT concat_ws(' ',시도,시군구,읍면동) AS 지역,단지명,
            count(DISTINCT 주소) AS 주소수
        FROM identity_rows
        GROUP BY 1,2),
    nation_address AS (
        SELECT 주소,단지명,CASE WHEN count(DISTINCT 단지고유번호)=1
            AND count(DISTINCT 세대수)=1 THEN max(세대수) END AS 세대수
        FROM pg_nation GROUP BY 1,2),
    nation_name AS (
        SELECT 지역,단지명,CASE WHEN count(DISTINCT 단지고유번호)=1
            AND count(DISTINCT 세대수)=1 THEN max(세대수) END AS 세대수,
            CASE WHEN count(DISTINCT 건축년도)=1 THEN max(건축년도) END AS 건축년도
        FROM pg_nation GROUP BY 1,2)'''
