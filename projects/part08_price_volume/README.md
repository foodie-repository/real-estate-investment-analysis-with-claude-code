# 2부 8장. 가격 및 거래량 대시보드

이 프로젝트는 아파트 매매·전세 실거래가를 개별 거래와 월별 집계로 나누어 보여주는 Streamlit 대시보드 예제입니다. 지역, 단지, 거래유형, 평형대, 기간을 선택해 가격 수준과 거래량 변화를 함께 비교할 수 있습니다.

## 책과 프롬프트 대응

- 책: 『감을 확신으로 바꾸는 AI 부동산 투자』 2부 8장
- 프롬프트: [2부 8장 가격·거래량 대시보드 프롬프트](../../prompts/part02/chapter08/01_price_volume_dashboard.md)

## 파일 구조

```text
part08_price_volume/
├── dashboard/
│   ├── app.py           # Streamlit 화면과 필터
│   ├── constants.py     # 평형대 등 화면 설정
│   ├── db.py            # DuckDB 연결과 스키마 정규화
│   ├── preprocessing.py # 개별 거래·월별 집계 조회
│   └── charts.py        # Plotly 차트
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

매매·전세 실거래가와 공동주택 정보가 포함된 DuckDB가 필요합니다. 기본 경로는 `data/apt_investment.duckdb`이며, 별도 데이터베이스를 사용하려면 다음처럼 지정할 수 있습니다.

```dotenv
PRICE_DB_PATH=/절대/경로/또는/프로젝트/기준/상대경로.duckdb
```

## 실행

```bash
uv run streamlit run projects/part08_price_volume/dashboard/app.py
```

화면의 지역 필터를 먼저 선택한 뒤 거래유형과 평형대를 조정합니다. `개별 실거래가` 탭에서는 거래별 분포를, `월별 중위가` 탭에서는 기간별 가격 흐름을 확인할 수 있습니다. 하단 요약 정보에서는 선택 조건의 거래 규모를 함께 살펴볼 수 있습니다.

## 노트북

`notebooks/01_eda.ipynb`는 데이터 탐색, `02_preprocessing.ipynb`는 집계 전처리, `03_chart_prototype.ipynb`는 차트 시제품을 다룹니다. 노트북은 현재 로컬 DuckDB의 데이터 범위와 스키마를 기준으로 동작합니다.

## 해석할 때 주의할 점

- 월별 중위가는 평균과 다른 지표이므로 두 값을 혼동하지 마세요.
- 면적대와 거래유형을 바꾸면 비교 대상 자체가 달라집니다.
- 최신 월은 신고·정정 자료가 아직 반영되지 않은 부분 집계일 수 있습니다.
- 가격과 거래량의 동반 변화는 2부 4~7장의 관심단지·수익률·거래량 분석과 함께 확인하세요.
- 차트에서 보이는 관계만으로 원인이나 미래 가격을 단정하지 말고, 데이터 범위와 외부 근거를 별도로 확인하세요.
