# 감을 확신으로 바꾸는 AI 부동산 투자

이 저장소는 종이책 『감을 확신으로 바꾸는 AI 부동산 투자』의 독자 실습 자료 저장소입니다.

책 본문 전체는 포함하지 않습니다. 책에서 사용하는 실습용 프롬프트와 완성 사례 코드, 노트북, 테스트를 참고하고 싶을 때 이 저장소를 사용하세요.

## 책의 목차

출판사 최종 편집본의 본문 구조에 맞춰 1부와 2부를 구분했습니다. 장별 자료 링크를 따라가면 책의 설명과 함께 사용할 프롬프트와 실행 예제를 바로 확인할 수 있습니다.

### 1부. AI 부동산 투자의 준비

| 장 | 제목 | 독자용 자료 |
| --- | --- | --- |
| 1장 | AI로 시작하는 데이터 기반 부동산 투자 | - |
| 2장 | 실습 환경 구축 | [프롬프트](prompts/part01/chapter02/) |
| 3장 | 데이터 수집과 전처리 | [프롬프트](prompts/part01/chapter03/) |

### 2부. 데이터 기반 부동산 투자 분석

| 장 | 제목 | 프롬프트 | 실행 프로젝트 |
| --- | --- | --- | --- |
| 4장 | 관심단지 자동 트래킹 | [프롬프트](prompts/part02/chapter04/) | [프로젝트](projects/part04_tracking/) |
| 5장 | 수익률 계산기 시스템 구축 | [프롬프트](prompts/part02/chapter05/) | [프로젝트](projects/part05_roi/) |
| 6장 | KB부동산 시각화 대시보드 구축 | [프롬프트](prompts/part02/chapter06/) | [프로젝트](projects/part06_kb_dashboard/) |
| 7장 | 거래량 지도 대시보드 구축 | [프롬프트](prompts/part02/chapter07/) | [프로젝트](projects/part07_trade_map/) |
| 8장 | 가격 및 거래량 대시보드 구축 | [프롬프트](prompts/part02/chapter08/) | [프로젝트](projects/part08_price_volume/) |

### 에필로그

- 에필로그

절별 구성과 프롬프트 전문은 [도서 실습 프롬프트 목차](prompts/README.md)에서 확인할 수 있습니다.

## 포함된 내용

```text
prompts/                 # 출판사 최종 편집본 기준 실습용 프롬프트
src/                     # 공통 설정, 데이터 수집기, 전처리, 주소 유틸리티
projects/                # 출판사 최종 편집본 기준 2부 4~8장 실행 예제
tests/                   # 주요 단위 테스트와 통합 테스트
pyproject.toml           # Python 의존성
uv.lock                  # 재현 가능한 uv 잠금 파일
.env.example             # 환경변수 템플릿
```

## 책의 프롬프트

책에 실린 프롬프트는 [도서 실습 프롬프트 목차](prompts/README.md)에서 출판사 최종 편집본의 부·장·절 순서대로 확인할 수 있습니다. 실행 예제 폴더도 최종 편집본의 4~8장 번호에 맞춰 정리했습니다.

### 예시 입력 자료

`projects/part04_tracking/data/watchlist.json`과 `projects/part05_roi/data/targets.json`은 실습 흐름을 확인하기 위한 예시 단지 목록입니다. 개인의 실제 관심 단지나 투자 계획을 공개한 자료가 아니며, 책을 따라 실습할 때 자신의 조건에 맞게 바꿔 사용하세요.

## 빠른 시작

```bash
git clone https://github.com/foodie-repository/real-estate-investment-analysis-with-claude-code.git
cd real-estate-investment-analysis-with-claude-code

uv sync
cp .env.example .env
```

`.env` 파일에 필요한 API 키를 입력한 뒤 실습을 진행합니다. 로컬 데이터베이스는 기본적으로 `data/apt_investment.duckdb`에 생성됩니다. `data/`와 `.env`는 GitHub에 올리지 않습니다.

## 주요 실행 명령

```bash
# 데이터 수집
uv run python -m src.collectors.실거래가 --year 2024 --sido 서울특별시
uv run python -m src.collectors.KB통계
uv run python -m src.collectors.공동주택
uv run python -m src.collectors.좌표

# 2부 4~5장 콘솔 또는 Google Sheets 출력
uv run python -m projects.part04_tracking.main
uv run python -m projects.part05_roi.main

# 2부 6~8장 Streamlit 대시보드
uv run streamlit run projects/part06_kb_dashboard/dashboard/app.py
uv run streamlit run projects/part07_trade_map/dashboard/app.py
uv run streamlit run projects/part08_price_volume/dashboard/app.py

# 테스트
uv run pytest tests/
```

## 환경변수

`.env.example`을 `.env`로 복사한 뒤 필요한 값만 채웁니다.

| 이름 | 용도 |
|------|------|
| `PUBLIC_DATA_API_KEY` | 공공데이터포털 실거래가, 공동주택 API |
| `KAKAO_API_KEY` | 카카오 주소 좌표 변환 API |
| `VWORLD_API_KEY` | V-World 지도 타일, 경계지도 API |
| `GOOGLE_SHEET_ID` | 2부 4장 관심단지 트래킹 Google Sheets 출력 |
| `ROI_SHEET_ID` | 2부 5장 수익률 계산 Google Sheets 출력 |
| `GOOGLE_SERVICE_ACCOUNT_KEY_PATH` | Google 서비스 계정 JSON 키 경로 |
| `KB_DB_PATH` | 2부 6장 대시보드용 외부 DuckDB 경로 |
| `PRICE_DB_PATH` | 2부 8장 대시보드용 외부 DuckDB 경로 |

Google Sheets를 쓰지 않으면 2부 4~5장은 콘솔에 결과를 출력합니다.

## 데이터 파일 주의

이 저장소에는 로컬 DuckDB 파일과 API 키가 포함되어 있지 않습니다. 실습 과정에서 생성되는 아래 파일은 각자 PC에만 보관하세요.

```text
data/
.env
*.duckdb
service_account*.json
credentials*.json
```

## 노트북

2부 6~8장에는 탐색용 Jupyter Notebook이 포함되어 있습니다.

```text
projects/part06_kb_dashboard/notebooks/
  01_eda.ipynb
  02_preprocessing.ipynb
  03_chart_prototype.ipynb
projects/part07_trade_map/notebooks/
  01_eda.ipynb
  02_preprocessing.ipynb
  03_map_prototype.ipynb
projects/part08_price_volume/notebooks/
  01_eda.ipynb
  02_preprocessing.ipynb
  03_chart_prototype.ipynb
```

노트북은 책의 설명을 보충하기 위한 참고 자료입니다. 데이터베이스가 없는 상태에서는 일부 셀이 실행되지 않을 수 있습니다.

## 라이선스

이 저장소의 코드와 프롬프트는 책 독자의 학습과 개인 실습을 위해 공개합니다. 자세한 조건은 `LICENSE`를 확인하세요.
