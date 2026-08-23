# 부동산 투자 분석 with 클로드 코드

이 저장소는 종이책 『부동산 투자 분석 with 클로드 코드』의 독자 실습 자료 저장소입니다.

책 본문 전체는 포함하지 않습니다. 책에서 사용하는 실습용 프롬프트와 완성 사례 코드, 노트북, 테스트를 참고하고 싶을 때 이 저장소를 사용하세요.

## 포함된 내용

```text
prompts/                 # 출판사 최종 편집본 기준 실습용 프롬프트
src/                     # 공통 설정, 데이터 수집기, 전처리, 주소 유틸리티
projects/                # 원고 개편 전 Part06~10 경로를 유지한 실행 예제
tests/                   # 주요 단위 테스트와 통합 테스트
pyproject.toml           # Python 의존성
uv.lock                  # 재현 가능한 uv 잠금 파일
.env.example             # 환경변수 템플릿
```

## 책의 프롬프트

책에 실린 프롬프트는 [도서 실습 프롬프트 목차](prompts/README.md)에서 부·장·절 순서대로 확인할 수 있습니다. 프롬프트 폴더의 번호는 출판사 최종 편집본을 기준으로 하며, 관련 코드 폴더의 기존 `Part06~10` 번호와의 대응도 목차에 함께 안내합니다.

### 예시 입력 자료

`projects/part06_tracking/data/watchlist.json`과 `projects/part07_roi/data/targets.json`은 실습 흐름을 확인하기 위한 예시 단지 목록입니다. 개인의 실제 관심 단지나 투자 계획을 공개한 자료가 아니며, 책을 따라 실습할 때 자신의 조건에 맞게 바꿔 사용하세요.

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

# Part06~07 콘솔 또는 Google Sheets 출력
uv run python -m projects.part06_tracking.main
uv run python -m projects.part07_roi.main

# Part08~10 Streamlit 대시보드
uv run streamlit run projects/part08_kb_dashboard/dashboard/app.py
uv run streamlit run projects/part09_trade_map/dashboard/app.py
uv run streamlit run projects/part10_price_volume/dashboard/app.py

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
| `GOOGLE_SHEET_ID` | Part06 관심단지 트래킹 Google Sheets 출력 |
| `ROI_SHEET_ID` | Part07 수익률 계산 Google Sheets 출력 |
| `GOOGLE_SERVICE_ACCOUNT_KEY_PATH` | Google 서비스 계정 JSON 키 경로 |
| `KB_DB_PATH` | Part08 대시보드용 외부 DuckDB 경로 |
| `PRICE_DB_PATH` | Part10 대시보드용 외부 DuckDB 경로 |

Google Sheets를 쓰지 않으면 Part06~07은 콘솔에 결과를 출력합니다.

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

Part08~10에는 탐색용 Jupyter Notebook이 포함되어 있습니다.

```text
projects/part08_kb_dashboard/notebooks/
  01_eda.ipynb
  02_preprocessing.ipynb
  03_chart_prototype.ipynb
projects/part09_trade_map/notebooks/
  01_eda.ipynb
  02_preprocessing.ipynb
  03_map_prototype.ipynb
projects/part10_price_volume/notebooks/
  01_eda.ipynb
  02_preprocessing.ipynb
  03_chart_prototype.ipynb
```

노트북은 책의 설명을 보충하기 위한 참고 자료입니다. 데이터베이스가 없는 상태에서는 일부 셀이 실행되지 않을 수 있습니다.

## 라이선스

이 저장소의 코드와 프롬프트는 책 독자의 학습과 개인 실습을 위해 공개합니다. 자세한 조건은 `LICENSE`를 확인하세요.
