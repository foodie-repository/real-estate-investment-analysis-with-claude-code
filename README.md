# 감을 확신으로 바꾸는 AI 부동산 투자

**바이브 코딩으로 만드는 나만의 부동산 분석 도구**

관심 아파트의 실거래가를 자동으로 추적하거나, 매수 시점에 따라 수익률이 얼마나 달라지는지 비교하고 싶은 분을 위한 책입니다. 코딩 경험이 적어도 클로드 코드와 함께 실거래가와 KB부동산 데이터를 모으고, 관심단지 추적 시트부터 거래량 지도까지 여섯 가지 분석 도구를 만들어 봅니다. 도구가 보여주는 숫자를 확인하고 투자 판단의 근거로 활용하는 방법도 다룹니다.

**[책 미리보기](https://foodie-repository.github.io/real-estate-investment-analysis-with-claude-code/)** · **[전체 목차](#전체-목차)** · **[실습 자료 열기](https://foodie-repository.github.io/real-estate-investment-analysis-with-claude-code/materials/)**

**책 소개 영상**

https://github.com/user-attachments/assets/b181e7bd-d273-4cd6-b6b0-26b564d1008c

<a name="책의-목차"></a>

## 전체 목차

### 저자 소개

- 저자 소개

---

### 저자의 말

- 저자의 말

---

### 이 책에 대하여

- 이 책에 대하여
- AI 대변혁의 시대
- 부동산 투자 도구로 성장한 2026년의 AI
- 단일 지표 투자 공식의 위험성
- 프롬프트를 넘어 데이터 분석 자동화로

---

### 이 책을 읽는 방법

- 이 책을 읽는 방법
- 이 책에서 완성할 여섯 가지 분석 도구
- 시작하기 전에 준비할 것
- 장별 구성과 읽는 순서
- 프롬프트와 AI 답변을 읽는 법
- 실습이 막혔을 때

---

### 1부. 바이브 코딩으로 부동산 데이터 분석 시작하기

- 1부 소개

**1장. AI로 시작하는 데이터 기반 부동산 투자**

- 1.1 자산 형성에서 부동산 투자의 역할
- 1.2 정보와 감을 넘어 데이터로 판단하기
- 1.3 손품·프롭테크의 한계와 AI가 바꾼 분석 방식
- 1.4 바이브 코딩으로 나만의 부동산 분석 시작하기

**2장. 클로드 코드와 안티그래비티로 실습 환경 만들기**

- 2.1 터미널의 역할과 기본 명령어
- 2.2 파이썬 설치
- 2.3 안티그래비티 IDE 설치
- 2.4 클로드 코드 설치
- 2.5 바이브 코딩 첫 경험
- 2.6 프로젝트 환경 구축
- 2.7 분석 도구 설치
- 2.8 설치 확인과 첫 실행
- 2.9 클로드 코드와 효과적으로 협업하는 법

**3장. 실거래가·KB부동산 데이터를 자동으로 모으고 다듬기**

- 3.1 아파트 실거래가 데이터 수집
- 3.2 KB부동산 통계 데이터 수집
- 3.3 공동주택 정보 수집
- 3.4 좌표 데이터 수집
- 3.5 경계지도 수집
- 3.6 데이터 수집 자동화
- 3.7 아파트 실거래가 데이터 전처리

---

### 2부. 관심단지와 지역을 데이터로 분석하는 도구 만들기

- 2부 소개

**4장. 관심단지 실거래가를 자동으로 추적하는 시트 만들기**

[프롬프트](prompts/prompt_ch04_tracking.md) · [실행 안내](projects/chapter04_tracking/README.md) · [결과 화면](assets/screenshots/chapter04-tracking-sheet-manuscript-6a6cc039.png)

- 4.1 관심단지 시세 추적을 자동화하는 이유
- 4.2 관심단지 트래킹을 설계하는 프롬프트
- 4.3 구글 시트를 연결하고 대화로 관심단지 관리하기
- 4.4 전세가율과 전고점 대비로 매수 후보 좁히기

**5장. 매수 시점별 아파트 수익률 계산기 만들기**

[프롬프트](prompts/prompt_ch05_roi.md) · [실행 안내](projects/chapter05_roi/README.md) · [결과 화면](assets/screenshots/chapter05-roi-sheet-manuscript-5bbb7105.png)

- 5.1 매수 시점별 수익률 비교와 계산 기준
- 5.2 수익률 계산기를 설계하는 프롬프트
- 5.3 단지별·시점별 수익률 시트 만들기
- 5.4 매수 시점·기간·면적에 따라 달라지는 수익률 비교

**6장. KB부동산 지수로 시장 흐름을 읽는 지도 대시보드 만들기**

[프롬프트](prompts/prompt_ch06_kb_dashboard.md) · [실행 안내](projects/chapter06_kb_dashboard/README.md) · [결과 화면](assets/screenshots/chapter06-kb-dashboard-manuscript-7ee1f591.png)

- 6.1 지도에서 읽는 지역 간 가격 확산
- 6.2 KB부동산 대시보드를 설계하는 프롬프트
- 6.3 KB부동산 대시보드를 실행하고 말로 고치기
- 6.4 매매·전세·전세가율·거래량으로 읽는 시장 사이클

**7장. 거래량 지도로 지역 대장 단지를 찾는 대시보드 만들기**

[프롬프트](prompts/prompt_ch07_trade_map.md) · [실행 안내](projects/chapter07_trade_map/README.md) · [결과 화면](assets/screenshots/chapter07-trade-map-manuscript-7640f4ce.png)

- 7.1 사람들의 실제 선택을 보여주는 지표
- 7.2 거래량 지도 대시보드를 설계하는 프롬프트
- 7.3 주소·좌표 연결과 거래량 순위를 AI에게 검증받기
- 7.4 거래량 순위 지도를 실행하고 말로 고치기
- 7.5 거래량과 회전율로 지역별 거래 흐름 읽기

**8장. 실거래가로 단지별 가격·갭을 비교하는 대시보드 만들기**

[프롬프트](prompts/prompt_ch08_price_gap.md) · [실행 안내](projects/chapter08_price_gap_table/README.md) · [결과 화면](assets/screenshots/chapter08-price-gap-manuscript-c0edde9e.png)

- 8.1 여러 단지를 같은 기준으로 비교하기
- 8.2 가격·갭 대시보드를 설계하는 프롬프트
- 8.3 단지 연결과 대표가격을 AI에게 검증받기
- 8.4 비교표·산점도·상자그림으로 단지 비교하기
- 8.5 AI와 함께 매수 검토 단지 탐색하기

**9장. 단지 가격·거래량 대시보드와 AI 투자 분석 보고서 만들기**

[프롬프트](prompts/prompt_ch09_price_volume.md) · [실행 안내](projects/chapter09_price_volume/README.md) · [결과 화면](assets/screenshots/chapter09-price-volume-manuscript-d68e488d.png)

- 9.1 가격과 거래량을 함께 분석하는 이유
- 9.2 가격·거래량 대시보드를 설계하는 프롬프트
- 9.3 평형 계산·이상 거래 처리와 차트를 AI에게 검증받기
- 9.4 가격·거래량 대시보드를 실행하고 말로 고치기
- 9.5 단지 추세를 읽고 AI 투자 분석 보고서 만들기

화면은 책의 실습 사례이며 실시간 시장 현황이 아닙니다. [조회 조건과 출처](assets/screenshots/README.md)를 확인하세요.

---

### 부록. 만든 도구를 점검하고 나만의 분석으로 넓히기

- 부록 전체 소개

**부록 1. 부동산 데이터를 제대로 읽는 시각화 기본 원칙**

- 질문과 기준이 분명한 좋은 차트
- 차트보다 먼저 숫자 확인하기
- 목적에 맞는 차트 고르기
- 차트의 과장 여부 확인하기
- 관찰과 해석 분리하기
- 이 책에서 만든 대시보드에 적용하기
- AI에게 차트 검수를 맡길 때 쓰는 프롬프트
- 한 페이지 체크리스트
- 판단의 재료로 쓰는 차트

**부록 2. 책의 프롬프트를 바꾸어 나만의 대시보드 만들기**

- 고칠 것인가, 새로 만들 것인가
- 책의 문안에서 가져올 것, 바꿀 것, 뺄 것
- AI와 대화해 요구사항을 한 장으로 정리하기
- 요구사항을 점검하고 첫 대시보드 만들기
- 숫자를 원자료와 대조하기
- 최종 문안을 저장하고 다른 질문으로 넓히기
- 반복할 절차를 스킬로 저장하기
- 이미 아는 사례로 스킬 확인하기
- 처음 보는 질문에 같은 스킬 쓰기
- 내 질문으로 바꾸고 확인하기

**부록 3. 세금까지 따져보는 매수와 매도**

- AI는 어떻게 도구를 사용하는가
- 세금 법령 조회와 부동산 계산기 사용 준비하기
- AI의 질문에 답하며 내 상황 정리하기
- 지역과 거래일에 맞는 계산 조건 확인하기
- 기존 집을 팔고 새 집을 살 때의 세금과 필요자금 계산하기
- 여러 주택의 매도 순서를 바꾸어 비교하기
- 반복 계산을 자동화하고 다시 실행하기
- 계산 결과를 확인하고 투자 판단에 활용하기

**부록 4. 실습에 다시 쓰는 참고 자료**

- 용어 찾아보기
- 장별 프롬프트 찾아보기와 후속 요청

---

### 에필로그

- 에필로그

## 실습 자료와 코드

책의 4~9장에서 만드는 분석 도구의 프롬프트와 참고용 완성 코드입니다. 2장에서 실습 환경을 준비하고 3장에서 데이터를 수집한 뒤 사용합니다. 실제 거래 데이터와 API 키, 구글 서비스 계정 키는 포함하지 않습니다.

### 프롬프트 전문 읽기

**[「프롬프트 전문 모음집」 PDF 다운로드](prompts/prompt_collection.pdf)**

책을 읽으며 전체 문안을 살펴보거나 설계 해설과 대조할 때 사용하는 자료입니다. 별도의 구매 인증 없이 내려받을 수 있으며, 4~9장의 전문을 본문 순서로 모았습니다. 자료 버전은 1.0.1(2026-11-22)입니다. PDF와 같은 버전의 장별 파일에는 같은 문안이 담겨 있습니다.

### 프롬프트로 직접 만들기

[실습 프롬프트 목차](prompts/README.md)에서 해당 장의 파일을 선택합니다. 클로드 코드로 열어 둔 프로젝트 폴더에 저장한 뒤 `@`로 첨부합니다. 책의 해당 절에서 준비 사항과 설계 이유를 먼저 읽고, 구현 후 계산 결과와 화면 동작을 확인합니다.

## 완성 코드 실행하기

이 README와 pyproject.toml이 있는 폴더에서 실행합니다. Python 3.11 이상과 uv가 필요합니다.

```bash
git clone https://github.com/foodie-repository/real-estate-investment-analysis-with-claude-code.git
cd real-estate-investment-analysis-with-claude-code
uv sync --locked
```

`.env.example`을 참고해 `.env`를 만들고 필요한 API 키와 시트 설정을 입력합니다. 기본 데이터 위치는 `data/apt_investment.duckdb`입니다. 시군구 경계지도는 `data/boundaries/시군구.geojson`에 둡니다. 다른 위치의 DB는 아래 환경변수로 지정할 수 있습니다.

| 장 | 도구 | 실행 명령 | 다른 DB 지정 |
| --- | --- | --- | --- |
| 4장 | 관심단지 트래킹 | `uv run python -m projects.chapter04_tracking.main` | 공통 DB |
| 5장 | 수익률 계산기 | `uv run python -m projects.chapter05_roi.main` | 공통 DB |
| 6장 | KB부동산 대시보드 | `uv run streamlit run projects/chapter06_kb_dashboard/dashboard/app.py` | `KB_DB_PATH` |
| 7장 | 거래량 지도 | `uv run streamlit run projects/chapter07_trade_map/dashboard/app.py` | `TRADE_MAP_DB_PATH` |
| 8장 | 가격·갭 비교 | `uv run streamlit run projects/chapter08_price_gap_table/dashboard/app.py` | `GAP_DB_PATH` |
| 9장 | 가격·거래량 | `uv run streamlit run projects/chapter09_price_volume/dashboard/app.py` | `PRICE_DB_PATH` |

관심단지 목록과 수익률 비교 대상은 각 도구의 `data/` 폴더에 저장됩니다. 4·5장 명령의 인수는 `--help`로 확인할 수 있습니다. 8장과 9장을 연결하려면 두 앱을 같은 DB로 각각 실행하고 8장 사이드바에 9장의 접속 주소를 입력합니다. 주소만 입력하면 9장 서버가 자동 실행되는 것은 아닙니다.

데이터 탐색과 검증 과정을 더 살펴보고 싶다면 [6장](projects/chapter06_kb_dashboard/notebooks/), [7장](projects/chapter07_trade_map/notebooks/), [9장](projects/chapter09_price_volume/notebooks/)의 노트북을 참고하세요. 대시보드를 실행하는 데 노트북은 필요하지 않습니다. 화면 부품과 설정을 함께 사용하므로 프로젝트 폴더 하나만 떼어 복사하기보다 이 실습 묶음의 구조를 유지합니다. 완성 코드는 실습을 돕는 참고 자료이며, AI가 만든 파일명과 코드 구조가 같아야 하는 것은 아닙니다.

## 코드 확인

```bash
uv run pytest tests/
uv run python -m compileall src projects tests
```

개인 DB가 필요한 검사는 자료가 없으면 건너뜁니다. 건너뛴 항목은 실제 자료로 확인한 결과와 구분합니다. 프롬프트를 고쳐 만든 도구는 책의 계산 기준과 화면 확인 절차도 함께 점검합니다.

## 라이선스

코드와 실습 프롬프트의 이용 조건은 [LICENSE](LICENSE)를 따릅니다. 책 미리보기의 발췌문과 이미지는 열람용이며 원고 전체의 재사용 허락을 뜻하지 않습니다.
