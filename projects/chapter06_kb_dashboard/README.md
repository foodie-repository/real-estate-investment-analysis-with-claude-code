# 6장. KB부동산 대시보드

[이 장의 프롬프트](../../prompts/part02/chapter06/) · [전체 실행 안내](../../README.md)

## 실행 화면

![6장 KB 지수와 거래량 지도 — 원고에 수록된 실제 데이터 실행 화면](../../assets/screenshots/chapter06-kb-dashboard.png)

서울의 2026년 4월 매매·전세 지수 증감률, 전세가율과 매매 거래량을 네 지도로 비교합니다.

> 책 원고에 수록된 실제 데이터 실행 화면입니다. 캡처 당시의 조회 조건을 보여주며, 현재 시점의 시장 현황과는 다를 수 있습니다. [큰 이미지 보기](../../assets/screenshots/chapter06-kb-dashboard.png) · [조회 조건과 출처](../../assets/screenshots/README.md)

## 필요한 자료와 계산 기준

KB 매매가격지수·전세가격지수·전세가율, 아파트 매매 실거래와 `data/boundaries/시군구.geojson`이 필요합니다. 원본 KB 지수에서 전년 동월 대비 값을 계산하므로 별도의 YoY 뷰를 미리 만들 필요가 없습니다. 지도 대시보드·지도 상세·시계열 분석의 세 화면을 제공합니다.

## 실행

저장소 루트에서 실행합니다. 먼저 `.env`와 3장의 수집 자료를 준비하세요.

```bash
uv run streamlit run projects/chapter06_kb_dashboard/dashboard/app.py
```

`KB_DB_PATH`가 비어 있거나 없으면 기본 `data/apt_investment.duckdb`를 읽습니다. 다른 DB를 사용하려면 해당 파일 경로를 설정합니다. 지정한 DB에 필요한 자료가 없으면 수집 상태와 컬럼을 확인하세요.

지도 배경에는 `VWORLD_API_KEY`가 필요합니다. 키가 없거나 유효하지 않으면 배경 타일이 표시되지 않을 수 있습니다.

## 확인할 것

조회 지역·기간·면적과 거래 건수가 의도한 조건인지 확인하세요. 데이터가 없거나 거래 건수가 적은 경우와 실제 값이 0인 경우를 구분합니다. 화면의 수치는 투자 성과나 미래 가격을 보장하지 않습니다.
