"""
주소 관련 공통 유틸리티

Python 함수(parse_sigungu, build_road_address_key)와
DuckDB SQL 표현식(SIDO_SQL, SIGUNGU_SQL 등)을 함께 제공한다.

매매/전월세 테이블의 시군구 컬럼 형식 예시:
  - 3-part: "서울특별시 강남구 압구정동"
  - 4-part(구): "경기도 성남시 중원구 은행동"
  - 4-part(읍리): "충청남도 예산군 예산읍 예산리"
  - 5-part: "충청남도 천안시 서북구 성환읍 율금리"
  - 세종: "세종특별자치시  조치원읍 상리" (더블스페이스)
"""

# 특별시/광역시 목록 (주소 파싱용)
특별시_광역시 = [
    "서울특별시", "부산광역시", "대구광역시", "인천광역시",
    "광주광역시", "대전광역시", "울산광역시",
]


# ─────────────────────────────────────────────
# Python 함수 (테스트, 단건 처리용)
# ─────────────────────────────────────────────

def parse_sigungu(sigungu: str) -> dict[str, str]:
    """
    시군구 문자열을 시도 / 시군구 / 읍면동으로 분리한다.

    예:
    - 서울특별시 강동구 고덕동 -> 서울특별시 / 강동구 / 고덕동
    - 경기도 성남시 분당구 정자동 -> 경기도 / 성남시 분당구 / 정자동
    - 세종특별자치시 한솔동 -> 세종특별자치시 / 세종시 / 한솔동
    """
    parts = sigungu.split()
    if not parts:
        return {"시도": "", "시군구": "", "읍면동": ""}

    if parts[0] == "세종특별자치시":
        dong = parts[1] if len(parts) > 1 else ""
        return {"시도": parts[0], "시군구": "세종시", "읍면동": dong}

    if len(parts) >= 4:
        return {
            "시도": parts[0],
            "시군구": f"{parts[1]} {parts[2]}",
            "읍면동": parts[3],
        }

    if len(parts) >= 3:
        return {"시도": parts[0], "시군구": parts[1], "읍면동": parts[2]}

    if len(parts) == 2:
        return {"시도": parts[0], "시군구": parts[1], "읍면동": ""}

    return {"시도": parts[0], "시군구": "", "읍면동": ""}


def get_sigungu_lookup_keyword(sigungu: str) -> str:
    """
    공동주택 주소 매칭에 사용할 시군구 키워드를 반환한다.
    """
    parts = sigungu.split()
    if not parts:
        return ""

    if parts[0] == "세종특별자치시":
        return parts[0]

    parsed = parse_sigungu(sigungu)
    return parsed["시군구"]


def build_road_address_key(시군구_raw: str, 도로명: str) -> str:
    """
    매매/전월세 테이블의 시군구+도로명으로 좌표 테이블 조인용 키를 생성한다.

    좌표 테이블의 도로명주소 형식에 맞춰 변환:
      - 특별시/광역시: 시도 + 구 + 도로명
      - 도+시: 도 + 시 + 도로명 (구 제외)
      - 세종: "세종특별자치시 세종시 " + 도로명
    """
    if not 시군구_raw or not 도로명 or str(시군구_raw) == "nan" or str(도로명) == "nan":
        return ""

    parts = [p for p in str(시군구_raw).split(" ") if p]
    도로명 = str(도로명).strip()

    if not parts or not 도로명:
        return ""

    시도 = parts[0]

    # 세종특별자치시
    if "세종특별자치시" in 시도:
        return f"세종특별자치시 세종시 {도로명}"

    # 특별시/광역시: 시도 + 구 + 도로명
    if 시도 in 특별시_광역시:
        시군구 = parts[1] if len(parts) > 1 else ""
        return f"{시도} {시군구} {도로명}" if 시군구 else ""

    # 도 단위: 도 + 시/군 + 도로명 (구는 제외)
    시군 = parts[1] if len(parts) > 1 else ""
    return f"{시도} {시군} {도로명}" if 시군 else ""


# ─────────────────────────────────────────────
# DuckDB SQL 표현식 (대량 처리용 — CTE 내에서 사용)
# ─────────────────────────────────────────────

# parse_sigungu()가 split()으로 처리하는 공백 정규화 규칙을 SQL 표현식에서도 사용한다.
_NORMALIZED_SIGUNGU_SQL = "trim(regexp_replace(시군구, '\\s+', ' ', 'g'))"
_SIGUNGU_WORD_COUNT_SQL = f"len(string_split({_NORMALIZED_SIGUNGU_SQL}, ' '))"


def _sigungu_part(position: int) -> str:
    """정규화된 시군구 문자열에서 N번째 단어를 꺼내는 DuckDB SQL 조각."""
    return f"split_part({_NORMALIZED_SIGUNGU_SQL}, ' ', {position})"


# 시군구 컬럼에서 시도를 추출하는 SQL 표현식
SIDO_SQL = _sigungu_part(1)

# 시군구 컬럼에서 parse_sigungu() 기준 시군구를 추출하는 SQL 표현식
SIGUNGU_SQL = f"""
CASE
    WHEN {_NORMALIZED_SIGUNGU_SQL} LIKE '세종특별자치시%'
    THEN '세종시'
    WHEN {_SIGUNGU_WORD_COUNT_SQL} >= 4
    THEN {_sigungu_part(2)}
         || ' ' || {_sigungu_part(3)}
    WHEN {_SIGUNGU_WORD_COUNT_SQL} >= 2
    THEN {_sigungu_part(2)}
    ELSE ''
END
"""

# 시군구 컬럼에서 읍면동을 추출하는 SQL 표현식
EUPMYEONDONG_SQL = f"""
CASE
    WHEN {_NORMALIZED_SIGUNGU_SQL} LIKE '세종특별자치시%'
    THEN {_sigungu_part(2)}
    WHEN {_SIGUNGU_WORD_COUNT_SQL} >= 4
    THEN {_sigungu_part(4)}
    WHEN {_SIGUNGU_WORD_COUNT_SQL} >= 3
    THEN {_sigungu_part(3)}
    ELSE ''
END
"""

# 시군구 + 도로명으로 좌표 테이블 조인용 키를 생성하는 SQL CASE 표현식
ROAD_ADDRESS_KEY_SQL = """
CASE
    -- 세종특별자치시
    WHEN regexp_replace(시군구, '\\s+', ' ', 'g') LIKE '세종특별자치시%'
    THEN '세종특별자치시 세종시 ' || 도로명

    -- 특별시/광역시: 시도 + 구 + 도로명
    WHEN split_part(regexp_replace(시군구, '\\s+', ' ', 'g'), ' ', 1) IN (
        '서울특별시','부산광역시','대구광역시','인천광역시',
        '광주광역시','대전광역시','울산광역시'
    )
    THEN split_part(regexp_replace(시군구, '\\s+', ' ', 'g'), ' ', 1)
         || ' ' || split_part(regexp_replace(시군구, '\\s+', ' ', 'g'), ' ', 2)
         || ' ' || 도로명

    -- 도 단위: 도 + 시/군 + 도로명
    ELSE split_part(regexp_replace(시군구, '\\s+', ' ', 'g'), ' ', 1)
         || ' ' || split_part(regexp_replace(시군구, '\\s+', ' ', 'g'), ' ', 2)
         || ' ' || 도로명
END
"""
