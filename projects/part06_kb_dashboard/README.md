# 2부 6장. KB부동산 시각화 대시보드

이 프로젝트는 KB부동산 지표를 지역과 기간별로 조회하고, 시계열 차트와 지도 시각화로 변화를 확인하는 Streamlit 대시보드 예제입니다. 데이터베이스에 저장된 지표의 범위에 따라 선택할 수 있는 지역과 기간이 달라집니다.

## 책과 프롬프트 대응

- 책: 『감을 확신으로 바꾸는 AI 부동산 투자』 2부 6장
- 프롬프트: [2부 6장 KB부동산 대시보드 프롬프트](../../prompts/part02/chapter06/01_kb_dashboard.md)

## 파일 구조

```text
part06_kb_dashboard/
├── dashboard/
│   ├── app.py           # Streamlit 화면과 사용자 입력
│   ├── constants.py     # 화면 표시용 상수
│   ├── db.py            # DuckDB 연결과 조회
│   ├── preprocessing.py # 지표 전처리
│   ├── charts.py        # 시계열 차트
│   ├── choropleth.py    # 지역별 색상 지도
│   └── geo.py           # 지역·경계 데이터 처리
└── notebooks/
    ├── 01_eda.ipynb
    ├── 02_preprocessing.ipynb
    └── 03_chart_prototype.ipynb
```

## 실행 전 준비

저장소 루트에서 의존성과 환경변수를 준비합니다.

```bash
uv sync
cp .env.example .env
```

KB부동산 통계 데이터를 포함한 DuckDB가 필요합니다. 기본 경로는 `data/apt_investment.duckdb`이며, 별도의 데이터베이스를 사용하려면 다음처럼 지정할 수 있습니다.

```dotenv
KB_DB_PATH=/절대/경로/또는/프로젝트/기준/상대경로.duckdb
```

지역별 색상 지도를 사용하려면 저장소에 포함된 경계지도와 지도 타일 설정도 확인하세요. V-World 타일을 사용하는 경우 `.env`의 `VWORLD_API_KEY`를 설정합니다.

## 실행

```bash
uv run streamlit run projects/part06_kb_dashboard/dashboard/app.py
```

터미널에 표시되는 로컬 주소를 브라우저에서 엽니다. 사이드바에서 지표와 지역, 기간을 선택해 시계열과 지도 결과를 비교합니다.

## 노트북

`notebooks/`의 파일은 대시보드를 만들기 전에 데이터 구조와 전처리 결과, 차트 형태를 살펴보는 참고 자료입니다. 노트북은 실행 시점의 DuckDB와 환경에 의존하므로, 데이터베이스가 없거나 필요한 지표가 부족하면 일부 셀이 실행되지 않을 수 있습니다.

## 해석할 때 주의할 점

- 지표의 기준과 대상 지역을 먼저 확인한 뒤 지역 간 변화를 비교하세요.
- 데이터베이스에 저장된 기간과 최신 수집 시점을 함께 기록하세요.
- 지수 변화는 실거래가와 동일한 의미가 아니므로 실거래·거래량 결과와 교차 확인하세요.
- 지도와 차트는 분석을 돕는 시각화이며, 상승이나 하락을 보장하는 예측 도구가 아닙니다.
