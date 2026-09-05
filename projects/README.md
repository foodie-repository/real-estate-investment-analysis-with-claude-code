# 실행 예제 프로젝트

이 폴더에는 『감을 확신으로 바꾸는 AI 부동산 투자』 2부에서 만든 실행 예제가 들어 있습니다. 책의 2부 4~8장 흐름에 맞춰 관심단지 추적, 수익률 계산, 데이터 시각화 대시보드를 단계적으로 실행할 수 있습니다.

## 프로젝트 목록

| 책의 위치 | 프로젝트 | 결과물 | 실행 안내 |
| --- | --- | --- | --- |
| 2부 4장. 관심단지 자동 트래킹 | [`part04_tracking/`](part04_tracking/) | 관심단지별 최신 매매·전세 정보와 투자 지표 | [`README.md`](part04_tracking/README.md) |
| 2부 5장. 수익률 계산기 | [`part05_roi/`](part05_roi/) | 매수 시점과 보유 기간별 수익률 비교 | [`README.md`](part05_roi/README.md) |
| 2부 6장. KB부동산 시각화 대시보드 | [`part06_kb_dashboard/`](part06_kb_dashboard/) | KB 지표와 지역별 변화를 보여주는 Streamlit 대시보드 | [`README.md`](part06_kb_dashboard/README.md) |
| 2부 7장. 거래량 지도 | [`part07_trade_map/`](part07_trade_map/) | 단지별 거래량과 회전율 순위 지도 | [`README.md`](part07_trade_map/README.md) |
| 2부 8장. 가격 및 거래량 대시보드 | [`part08_price_volume/`](part08_price_volume/) | 개별 거래와 월별 가격·거래량 비교 대시보드 | [`README.md`](part08_price_volume/README.md) |

## 공통 준비

프로젝트를 실행하기 전에 저장소 루트에서 의존성을 설치하고 환경변수 파일을 준비합니다.

```bash
uv sync
cp .env.example .env
```

`.env`에는 사용하는 데이터 수집 API 키와 Google Sheets 또는 지도 기능에 필요한 설정만 입력합니다. API 키, 서비스 계정 JSON, DuckDB 파일은 GitHub에 올리지 마세요. 기본 데이터베이스 경로는 `data/apt_investment.duckdb`입니다.

## 실행 순서

책의 실습 흐름을 그대로 따라가려면 다음 순서로 진행합니다.

1. 3장에서 필요한 실거래가·KB부동산·공동주택·좌표 데이터를 수집합니다.
2. 2부 4장에서 관심단지를 등록하고 최신 거래 정보를 확인합니다.
3. 2부 5장에서 분석할 단지를 등록하고 매수 시점별 수익률을 비교합니다.
4. 2부 6~8장에서 같은 데이터베이스를 사용해 대시보드를 실행합니다.

데이터 수집 명령은 저장소 루트의 [README.md](../README.md)를 참고하세요. 데이터베이스에 필요한 기간과 지역의 자료가 없으면 프로젝트가 실행되더라도 결과가 비어 있을 수 있습니다.

## 관련 자료

- [도서 실습 프롬프트](../prompts/README.md)
- [2부 4장 프롬프트](../prompts/part02/chapter04/)
- [2부 5장 프롬프트](../prompts/part02/chapter05/)
- [2부 6장 프롬프트](../prompts/part02/chapter06/)
- [2부 7장 프롬프트](../prompts/part02/chapter07/)
- [2부 8장 프롬프트](../prompts/part02/chapter08/)

각 프로젝트 README에는 해당 프로젝트의 파일 구조와 실행 조건을 더 자세히 설명합니다.
