from textwrap import dedent


def main():
    print(
        dedent(
            """
            VibeCoding-APT-Investment

            현재 구현 상태:
            - 4장부터 9장까지의 실행 가능한 참고 코드와 프롬프트가 준비되어 있습니다.
            - 데이터 수집기: src/collectors
            - 전처리 모듈: src/preprocessing
            - 4장 관심단지 트래킹
            - 5장 수익률 계산기
            - 6장 KB 대시보드
            - 7장 가격·갭 비교표
            - 8장 거래량 지도
            - 9장 가격·거래량 대시보드

            시작 명령 예시:
            - uv run python -m src.collectors.실거래가 --year 2024 --sido 서울특별시
            - uv run python -m projects.chapter04_tracking.main
            - uv run python -m projects.chapter05_roi.main
            - uv run streamlit run projects/chapter06_kb_dashboard/dashboard/app.py
            - uv run streamlit run projects/chapter07_price_gap_table/dashboard/app.py
            - uv run streamlit run projects/chapter08_trade_map/dashboard/app.py
            - uv run streamlit run projects/chapter09_price_volume/dashboard/app.py

            전체 구조와 공개 배포 기준:
            - README.md
            - projects/README.md
            - prompts/README.md
            """
        ).strip()
    )


if __name__ == "__main__":
    main()
