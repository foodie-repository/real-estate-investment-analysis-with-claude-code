"""
아파트 투자 수익률 계산 실행 스크립트

분석 대상 단지 목록을 읽고, 수익률을 계산하여 구글 시트에 기록한다.
구글 시트 미설정 시 콘솔에 결과를 출력한다.
"""

import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가 (src.config 임포트를 위해)
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from projects.part07_roi.targets import get_all
from projects.part07_roi.calculator import calculate_roi
from projects.part07_roi.sheets import update_sheet, print_table, SHEET_ID


def run(purchase_ym: int = 202201, periods: list[int] = None):
    """
    수익률 계산을 실행한다.

    Args:
        purchase_ym: 매수 시점 (YYYYMM 정수, 예: 202201 = 2022년 1월)
        periods: 보유 기간 목록 (년, 예: [2, 4]). 기본값 [2, 4]
    """
    if periods is None:
        periods = [2, 4]

    # 1. 분석 대상 목록 로드
    targets = get_all()
    if not targets:
        print("등록된 분석 대상이 없습니다.")
        print("먼저 targets.py의 add() 함수로 분석 대상을 추가하세요.")
        return

    purchase_year = purchase_ym // 100
    purchase_month = purchase_ym % 100
    periods_str = ", ".join(f"{p}년" for p in periods)
    print(f"분석 대상 {len(targets)}건의 수익률을 계산합니다...")
    print(f"매수 시점: {purchase_year}년 {purchase_month}월 | 비교 기간: {periods_str}\n")

    # 2. 수익률 계산
    roi_data = calculate_roi(targets, purchase_ym, periods)

    # 3. 결과 출력
    if SHEET_ID:
        update_sheet(roi_data, purchase_ym, periods)
    else:
        print("(구글 시트 미설정 → 콘솔 출력)\n")
        print_table(roi_data, purchase_ym, periods)


if __name__ == "__main__":
    run()
