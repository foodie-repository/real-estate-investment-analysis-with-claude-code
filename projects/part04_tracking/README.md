# 2부 4장. 관심단지 자동 트래킹

이 프로젝트는 관심단지 목록을 저장해 두고, DuckDB에 수집된 매매·전세 실거래가를 바탕으로 최신 거래 정보와 전세가율, 최근 거래 대비 변화 같은 지표를 확인하는 예제입니다. Google Sheets를 설정하면 결과를 시트에 기록하고, 설정하지 않으면 콘솔에 출력합니다.

## 책과 프롬프트 대응

- 책: 『감을 확신으로 바꾸는 AI 부동산 투자』 2부 4장
- 프롬프트: [2부 4장 프롬프트](../../prompts/part02/chapter04/)
- 프롬프트 목록: [관심단지를 추적해야 하는 이유](../../prompts/part02/chapter04/01_tracking_need.md), [프롬프트 설계](../../prompts/part02/chapter04/02_tracking_prompt_design.md), [실행과 관심단지 관리](../../prompts/part02/chapter04/03_execution_and_watchlist_management.md)

## 파일 구조

```text
part04_tracking/
├── data/watchlist.json  # 예시 관심단지 목록
├── main.py              # 트래킹 실행 진입점
├── tracker.py           # DuckDB 조회와 지표 계산
├── watchlist.py         # 관심단지 등록·삭제·조회
└── sheets.py            # Google Sheets 기록 또는 콘솔 출력
```

`data/watchlist.json`은 실습을 위한 예시 파일입니다. 실제로 추적할 단지는 `watchlist.py`의 등록 기능을 사용해 자신의 목록으로 바꿔 사용하세요.

## 실행 전 준비

저장소 루트에서 의존성과 환경변수를 준비합니다.

```bash
uv sync
cp .env.example .env
```

3장에서 매매·전세 실거래가와 공동주택 정보를 수집해 `data/apt_investment.duckdb`에 저장해야 합니다. 필요한 데이터가 없으면 관심단지 목록은 읽히더라도 조회 결과가 없을 수 있습니다.

## 실행

```bash
uv run python -m projects.part04_tracking.main
```

Google Sheets를 설정하지 않으면 결과가 터미널에 표 형태로 출력됩니다. Google Sheets에 기록하려면 `.env`에 다음 값을 입력하고, 서비스 계정에 대상 시트 공유 권한을 부여하세요.

```dotenv
GOOGLE_SHEET_ID=시트_ID
GOOGLE_SERVICE_ACCOUNT_KEY_PATH=서비스_계정_JSON_경로
```

## 관심단지 관리

관심단지 등록·삭제·조회 함수는 `watchlist.py`에 있습니다. 먼저 현재 예시 목록의 필드 구조를 확인한 뒤 자신의 시군구, 단지명, 전용면적 조건에 맞게 등록합니다. 등록한 목록은 `data/watchlist.json`에 저장됩니다.

## 주의할 점

- 결과는 현재 로컬 DuckDB에 수집된 기간과 신고 자료를 기준으로 합니다.
- 실거래가가 없는 기준월이나 단지는 공란 또는 결과 없음으로 표시될 수 있습니다.
- Google 서비스 계정 JSON과 실제 관심단지 정보는 공개 저장소에 추가하지 마세요.
- 이 프로젝트의 지표는 후보를 비교하기 위한 실습용 계산이며, 세금·대출·거래비용을 포함한 최종 투자수익을 의미하지 않습니다.
