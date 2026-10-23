"""
구글 시트 출력 모듈

트래킹 결과를 구글 시트에 기록한다.
서비스 계정 인증 방식을 사용한다.
"""

import os
from datetime import datetime

import gspread

from src.config import PROJECT_ROOT

# 구글 시트 설정
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SERVICE_ACCOUNT_KEY = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY_PATH")
if SERVICE_ACCOUNT_KEY and not os.path.isabs(SERVICE_ACCOUNT_KEY):
    SERVICE_ACCOUNT_KEY = str(PROJECT_ROOT / SERVICE_ACCOUNT_KEY)

# 시트에 기록할 헤더 (컬럼 순서)
HEADERS = [
    "시도", "시군구", "읍면동",
    "단지명", "전용면적", "평형", "세대수", "건축년도", "연식",
    "기준월", "데이터최신월", "수치상태",
    "매매중앙값", "매매건수", "직거래제외건수", "매매전월대비",
    "신규전세중앙값", "신규전세건수",
    "갱신전세중앙값", "갱신전세건수", "전세전월대비",
    "매매-전세갭", "갭전월대비",
    "전세가율(%)", "전세가율전월대비(%p)",
    "전고점", "전고점대비(%)",
    "전월기준월", "전월매매중앙값", "전월신규전세중앙값",
    "전월갭", "전월전세가율(%)",
    "비고",
]


def _format_value(value, comma: bool = True) -> str:
    """값을 시트에 기록할 형태로 변환한다."""
    if value is None:
        return "-"
    if isinstance(value, float):
        if value == int(value):
            return f"{int(value):,}" if comma else str(int(value))
        return str(round(value, 1))
    if isinstance(value, int):
        return f"{value:,}" if comma else str(value)
    return str(value)


def _row_from_data(data: dict) -> list[str]:
    """트래킹 데이터 딕셔너리를 시트 행으로 변환한다."""
    # 콤마를 붙이지 않을 키
    no_comma = {
        "건축년도", "연식", "평형", "기준월", "데이터최신월", "전월기준월",
    }
    keys = [
        "시도", "시군구", "읍면동",
        "단지명", "전용면적", "평형", "세대수", "건축년도", "연식",
        "기준월", "데이터최신월", "잠정수치",
        "최근매매가", "매매거래건수", "직거래제외건수", "매매전월대비",
        "최근전세가", "신규전세거래건수",
        "갱신전세가", "갱신전세거래건수", "전세전월대비",
        "매매전세갭", "갭전월대비",
        "전세가율", "전세가율전월대비",
        "전고점", "전고점대비",
        "전월기준월", "전월매매", "전월전세", "전월갭", "전월전세가율",
        "비고",
    ]
    row = []
    for key in keys:
        if key == "잠정수치":
            if data.get("기준월") is None:
                row.append("-")
            else:
                row.append("잠정" if data.get(key) else "확정")
            continue
        row.append(_format_value(data.get(key), comma=(key not in no_comma)))
    return row


def update_sheet(tracking_data: list[dict]) -> None:
    """
    트래킹 결과를 구글 시트에 기록한다.
    기존 데이터를 지우고 새 데이터로 교체한다.
    """
    if not SHEET_ID or not SERVICE_ACCOUNT_KEY:
        print("구글 시트 설정이 없습니다. .env 파일에 다음 항목을 추가하세요:")
        print("  GOOGLE_SHEET_ID=시트ID")
        print("  GOOGLE_SERVICE_ACCOUNT_KEY_PATH=서비스계정키.json")
        return

    # 서비스 계정으로 인증
    gc = gspread.service_account(filename=SERVICE_ACCOUNT_KEY)
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.sheet1

    # 기존 데이터 삭제
    ws.clear()

    # 헤더 기록
    ws.append_row(HEADERS)

    # 데이터 기록
    rows = [_row_from_data(d) for d in tracking_data]
    if rows:
        ws.append_rows(rows)

    # 마지막 업데이트 일시
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    ws.update_cell(len(rows) + 3, 1, f"마지막 업데이트: {update_time}")

    print(f"구글 시트 업데이트 완료 ({len(rows)}건, {update_time})")


def print_table(tracking_data: list[dict]) -> None:
    """
    트래킹 결과를 콘솔에 테이블 형태로 출력한다.
    구글 시트가 설정되지 않았을 때 확인용으로 사용한다.
    """
    if not tracking_data:
        print("트래킹 데이터가 없습니다.")
        return

    print(f"\n{'='*100}")
    print("관심단지 시세 트래킹")
    print(f"{'='*100}\n")

    for data in tracking_data:
        print(f"[{data['시군구']} {data['읍면동']}] {data['단지명']} "
              f"({data['전용면적']}㎡, {data.get('평형', '-')}평)")
        print(f"  세대수: {_format_value(data.get('세대수'))}  |  "
              f"건축년도: {_format_value(data.get('건축년도'), comma=False)}  |  "
              f"연식: {_format_value(data.get('연식'), comma=False)}년")
        기준월 = _format_value(data.get("기준월"), comma=False)
        if data.get("기준월") is None:
            수치상태 = "-"
        else:
            수치상태 = "잠정" if data.get("잠정수치") else "확정"
        print(f"  기준월: {기준월} ({수치상태})")
        데이터최신월 = _format_value(data.get("데이터최신월"), comma=False)
        print(f"  데이터 최신월: {데이터최신월}")
        print()

        매매 = _format_value(data.get("최근매매가"))
        매매건수 = _format_value(data.get("매매거래건수"))
        직거래건수 = _format_value(data.get("직거래제외건수"))
        매매변동 = _format_value(data.get("매매전월대비"))
        전세 = _format_value(data.get("최근전세가"))
        신규전세건수 = _format_value(data.get("신규전세거래건수"))
        갱신전세 = _format_value(data.get("갱신전세가"))
        갱신전세건수 = _format_value(data.get("갱신전세거래건수"))
        전세변동 = _format_value(data.get("전세전월대비"))
        print(f"  매매 중앙값: {매매}만원 ({매매건수}건, 직거래 {직거래건수}건 제외)")
        print(f"    전월대비: {매매변동}만원")
        print(f"  신규 전세 중앙값: {전세}만원 ({신규전세건수}건)")
        print(f"    전월대비: {전세변동}만원")
        print(f"  갱신 전세 중앙값: {갱신전세}만원 ({갱신전세건수}건)")
        print()

        갭 = _format_value(data.get("매매전세갭"))
        갭변동 = _format_value(data.get("갭전월대비"))
        전세가율 = _format_value(data.get("전세가율"))
        전세가율변동 = _format_value(data.get("전세가율전월대비"))
        print(f"  갭: {갭}만원 (전월대비 {갭변동})")
        print(f"  전세가율: {전세가율}% (전월대비 {전세가율변동}%p)")
        print()

        전고점 = _format_value(data.get("전고점"))
        전고점대비 = _format_value(data.get("전고점대비"))
        print(f"  전고점: {전고점}만원 (전고점 대비 {전고점대비}%)")
        print()

        전월매매 = _format_value(data.get("전월매매"))
        전월전세 = _format_value(data.get("전월전세"))
        전월갭 = _format_value(data.get("전월갭"))
        전월전세가율 = _format_value(data.get("전월전세가율"))
        print(f"  전월 → 매매: {전월매매}만원  |  전세: {전월전세}만원  |  갭: {전월갭}만원  |  전세가율: {전월전세가율}%")

        비고 = data.get("비고")
        if 비고:
            print(f"\n  ⚠ 비고: {비고}")
        print(f"\n{'-'*100}\n")

    print(f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
