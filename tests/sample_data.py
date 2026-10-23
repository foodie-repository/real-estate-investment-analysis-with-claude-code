"""외부 API·실제 거래·비밀값 없이 검증하는 합성 데이터. 투자 분석용이 아니다."""
from datetime import date
import json
from pathlib import Path

import duckdb


def create_sample_database(path, *, sido="서울특별시"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    try:
        con.execute('CREATE TABLE 매매 (시군구 VARCHAR, 지번 VARCHAR, 단지명 VARCHAR, 전용면적 DOUBLE, 계약년월 INTEGER, 계약일 INTEGER, 거래금액 BIGINT, 층 INTEGER, 건축년도 INTEGER, 도로명 VARCHAR, 해제사유발생일 VARCHAR, 거래유형 VARCHAR)')
        con.execute('CREATE TABLE 전월세 (시군구 VARCHAR, 지번 VARCHAR, 단지명 VARCHAR, 전월세구분 VARCHAR, 전용면적 DOUBLE, 계약년월 INTEGER, 계약일 INTEGER, 보증금 BIGINT, 월세금 BIGINT, 층 INTEGER, 건축년도 INTEGER, 도로명 VARCHAR, 계약구분 VARCHAR)')
        con.execute('CREATE TABLE 공동주택_전국 (주소 VARCHAR, 단지명 VARCHAR, 단지구분코드 VARCHAR, 세대수 INTEGER, 단지고유번호 VARCHAR)')
        con.execute('CREATE TABLE 좌표 (도로명주소 VARCHAR, 경도 DOUBLE, 위도 DOUBLE)')
        sales, leases = [], []
        for idx in range(3):
            name=f'검증단지{idx+1}'; road=f'검증로 {idx+1}'; region=f'{sido} 강남구 역삼동'
            con.execute('INSERT INTO 공동주택_전국 VALUES (?, ?, ?, ?, ?)', [f'{region} {idx+1}',name,'1',500+idx*100,f'TEST{idx+1}'])
            con.execute('INSERT INTO 좌표 VALUES (?, ?, ?)', [f'{sido} 강남구 {road}',127.03+idx*.01,37.49+idx*.01])
            for year in range(2022,2027):
                for month in range(1,13 if year<2026 else 10):
                    for day in (1,10,20):
                        ym=year*100+month; price=80000+idx*10000+(year-2022)*2000+month*100+day
                        sales.append((region,str(idx+1),name,84.0,ym,day,price,10,2015,road,None,'중개거래'))
                        for kind,rent in [('전세',0),('월세',100)]:
                            leases.append((region,str(idx+1),name,kind,84.,ym,day,price//2,rent,10,2015,road,'신규'))
        con.executemany('INSERT INTO 매매 VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',sales)
        con.executemany('INSERT INTO 전월세 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',leases)
        for table in ('KB_매매가격지수','KB_전세가격지수','KB_전세가율'):
            col='전세가격비율' if table=='KB_전세가율' else '가격지수'
            con.execute(f'CREATE TABLE {table}(월간주간구분 VARCHAR,매물종별구분 VARCHAR,지역코드 VARCHAR,지역명 VARCHAR,날짜 DATE,{col} DOUBLE)')
            rows=[('월간','아파트',code,name,date(y,m,1),(60 if table=='KB_전세가율' else 100)+(y-2022)*2+m/10) for y in range(2022,2027) for m in range(1,13 if y<2026 else 10) for code,name in [('1100000000','서울'),('1168000000','강남구')]]
            con.executemany(f'INSERT INTO {table} VALUES (?,?,?,?,?,?)',rows)
    finally:
        con.close()
    return path


def create_sample_boundary(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{'sig_cd':'11680','sig_kor_nm':'강남구','full_nm':'서울특별시 강남구'},'geometry':{'type':'Polygon','coordinates':[[[127.00,37.47],[127.08,37.47],[127.08,37.54],[127.00,37.54],[127.00,37.47]]]}}]},ensure_ascii=False))
    return path
