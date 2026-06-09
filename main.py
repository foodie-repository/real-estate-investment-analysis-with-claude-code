from textwrap import dedent


def main():
    print(
        dedent(
            """
            부동산 투자 분석 with 클로드 코드

            이 저장소는 책 독자를 위한 실습 코드 저장소입니다.
            Part04~10 실행 가능한 코드와 노트북을 포함합니다.

            포함된 코드:
            - 데이터 수집기: src/collectors
            - 전처리 모듈: src/preprocessing
            - Part06 관심단지 트래킹
            - Part07 수익률 계산기
            - Part08 KB 대시보드
            - Part09 거래량 지도
            - Part10 가격·거래량 대시보드

            시작 명령 예시:
            - uv sync
            - cp .env.example .env
            - uv run python -m src.collectors.실거래가 --year 2024 --sido 서울특별시
            - uv run python -m projects.part06_tracking.main
            - uv run python -m projects.part07_roi.main
            - uv run streamlit run projects/part08_kb_dashboard/dashboard/app.py
            - uv run streamlit run projects/part09_trade_map/dashboard/app.py
            - uv run streamlit run projects/part10_price_volume/dashboard/app.py
            """
        ).strip()
    )


if __name__ == "__main__":
    main()
