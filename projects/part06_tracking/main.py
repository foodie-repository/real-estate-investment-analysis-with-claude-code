"""
관심단지 시세 자동 트래킹 실행 스크립트

관심단지 목록을 읽고, 시세를 조회하여 구글 시트에 기록한다.
구글 시트 미설정 시 콘솔에 결과를 출력한다.
"""

import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가 (src.config 임포트를 위해)
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from projects.part06_tracking.watchlist import get_all
from projects.part06_tracking.tracker import get_tracking_data
from projects.part06_tracking.sheets import update_sheet, print_table, SHEET_ID


def run():
    """트래킹을 실행한다."""
    # 1. 관심단지 목록 로드
    watchlist = get_all()
    if not watchlist:
        print("등록된 관심단지가 없습니다.")
        print("먼저 watchlist.py의 add() 함수로 관심단지를 추가하세요.")
        return

    print(f"관심단지 {len(watchlist)}건 트래킹을 시작합니다...\n")

    # 2. 시세 조회 및 투자 지표 계산
    tracking_data = get_tracking_data(watchlist)

    # 3. 결과 출력
    if SHEET_ID:
        update_sheet(tracking_data)
    else:
        print("(구글 시트 미설정 → 콘솔 출력)\n")
        print_table(tracking_data)


if __name__ == "__main__":
    run()
