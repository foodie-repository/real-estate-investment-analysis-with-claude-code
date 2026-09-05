"""
구글 시트 출력 모듈

수익률 계산 결과를 구글 시트에 기록한다.
서비스 계정 인증 방식을 사용한다.
"""

import os
from datetime import datetime

import gspread

from src.config import PROJECT_ROOT

# 구글 시트 설정
SHEET_ID = os.getenv("ROI_SHEET_ID")
SERVICE_ACCOUNT_KEY = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY_PATH")
if SERVICE_ACCOUNT_KEY and not os.path.isabs(SERVICE_ACCOUNT_KEY):
    SERVICE_ACCOUNT_KEY = str(PROJECT_ROOT / SERVICE_ACCOUNT_KEY)


def _ym_label(ym: int) -> str:
    """YYYYMM → '2020.1' 형태의 라벨."""
    return f"{ym // 100}.{ym % 100}"


def _add_years(ym: int, years: int) -> int:
    """YYYYMM에 N년을 더한다. 예: 202001 + 2 = 202201"""
    return (ym // 100 + years) * 100 + (ym % 100)


def _build_headers(purchase_ym: int, periods: list[int]) -> list[str]:
    """기간 목록에 따라 동적으로 헤더를 구성한다."""
    purchase_label = _ym_label(purchase_ym)

    headers = [
        "시도", "시군구", "읍면동",
        "단지명", "전용면적", "평형", "세대수", "건축년도",
        f"{purchase_label} 매매가", f"{purchase_label} 전세가",
        f"{purchase_label} 갭",
    ]
    for period in periods:
        sale_label = _ym_label(_add_years(purchase_ym, period))
        p = f"{period}년"
        headers.extend([
            f"{sale_label} 매매가", f"{sale_label} 전세가",
            f"{sale_label} 갭",
            f"{p} 매매차익", f"{p} 수익률(%)",
        ])
    return headers


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


def _row_from_data(data: dict, periods: list[int]) -> list[str]:
    """수익률 데이터 딕셔너리를 시트 행으로 변환한다."""
    no_comma = {"건축년도", "평형"}
    keys = [
        "시도", "시군구", "읍면동",
        "단지명", "전용면적", "평형", "세대수", "건축년도",
        "매수_매매가", "매수_전세가", "매수_갭",
    ]
    for period in periods:
        p = f"{period}년"
        keys.extend([
            f"{p}_매매가", f"{p}_전세가", f"{p}_갭",
            f"{p}_매매차익", f"{p}_수익률",
        ])
    return [_format_value(data.get(k), comma=(k not in no_comma)) for k in keys]


def update_sheet(roi_data: list[dict], purchase_ym: int,
                 periods: list[int]) -> None:
    """
    수익률 결과를 구글 시트에 기록한다.
    기존 데이터를 지우고 새 데이터로 교체한다.
    """
    if not SHEET_ID or not SERVICE_ACCOUNT_KEY:
        print("구글 시트 설정이 없습니다. .env 파일에 다음 항목을 추가하세요:")
        print("  ROI_SHEET_ID=시트ID")
        print("  GOOGLE_SERVICE_ACCOUNT_KEY_PATH=서비스계정키.json")
        return

    # 서비스 계정으로 인증
    gc = gspread.service_account(filename=SERVICE_ACCOUNT_KEY)
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.sheet1

    # 기존 데이터 삭제
    ws.clear()

    # 헤더 기록
    headers = _build_headers(purchase_ym, periods)
    ws.append_row(headers)

    # 데이터 기록
    rows = [_row_from_data(d, periods) for d in roi_data]
    if rows:
        ws.append_rows(rows)

    # 메타데이터: 매수시점, 비교기간, 업데이트 일시
    purchase_label = _ym_label(purchase_ym)
    periods_str = ", ".join(f"{p}" for p in periods)
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    metadata = (f"매수시점: {purchase_label} | "
                f"비교기간: {periods_str}년 | "
                f"마지막 업데이트: {update_time}")
    ws.update_cell(len(rows) + 3, 1, metadata)

    print(f"구글 시트 업데이트 완료 ({len(rows)}건, {update_time})")


def print_table(roi_data: list[dict], purchase_ym: int,
                periods: list[int]) -> None:
    """
    수익률 결과를 콘솔에 테이블 형태로 출력한다.
    구글 시트가 설정되지 않았을 때 확인용으로 사용한다.
    """
    if not roi_data:
        print("수익률 데이터가 없습니다.")
        return

    purchase_label = _ym_label(purchase_ym)

    print(f"\n{'='*100}")
    print(f"수익률 비교 분석 (매수시점: {purchase_label})")
    print(f"{'='*100}\n")

    for data in roi_data:
        print(f"[{data['시군구']} {data['읍면동']}] {data['단지명']} "
              f"({data['전용면적']}㎡, {data.get('평형', '-')}평)")
        print(f"  세대수: {_format_value(data.get('세대수'))}  |  "
              f"건축년도: {_format_value(data.get('건축년도'), comma=False)}")
        print()

        매수가 = _format_value(data.get("매수_매매가"))
        전세가 = _format_value(data.get("매수_전세가"))
        갭 = _format_value(data.get("매수_갭"))
        print(f"  [{purchase_label}] 매매가: {매수가}만원 | "
              f"전세가: {전세가}만원 | 갭: {갭}만원")
        print()

        for period in periods:
            p = f"{period}년"
            sale_label = _ym_label(_add_years(purchase_ym, period))
            매매가 = _format_value(data.get(f"{p}_매매가"))
            전세가 = _format_value(data.get(f"{p}_전세가"))
            갭 = _format_value(data.get(f"{p}_갭"))
            매매차익 = _format_value(data.get(f"{p}_매매차익"))
            수익률 = _format_value(data.get(f"{p}_수익률"))
            print(f"  [{sale_label}] 매매가: {매매가}만원 | "
                  f"전세가: {전세가}만원 | 갭: {갭}만원")
            print(f"          매매차익: {매매차익}만원 | 수익률: {수익률}%")

        print(f"\n{'-'*100}\n")

    print(f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
