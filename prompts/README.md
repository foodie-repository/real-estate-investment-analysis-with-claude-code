# 도서 실습 프롬프트

『감을 확신으로 바꾸는 AI 부동산 투자』의 1장부터 부록 2까지 확인하여, AI에 입력하는 구현·검증·후속 요청을 모았습니다. 책 본문과 AI 답변은 포함하지 않습니다.

동기화 기준일: 2026-10-24. 현재 원고의 프롬프트 문안을 기준으로 갱신했습니다. 이 날짜는 모든 프롬프트의 실행·결과 재검증일을 뜻하지 않습니다.

## 사용 방법

1. 책에서 진행 중인 장·절의 파일을 엽니다.
2. 준비 사항과 앞선 대화가 필요한지 확인한 뒤, 해당 단계의 `text` 블록을 복사합니다.
3. 자신의 프로젝트를 연 AI 대화창에 붙여넣습니다.
4. 지역·기간·단지·첨부 자료와 자리표시자를 자신의 상황에 맞춰 확인합니다.

한 파일에는 구현, 검증, 오류 해결과 선택적인 후속 요청이 함께 있습니다. 모든 블록을 연속 실행하는 절차가 아닙니다. 짧고 모호한 요청은 비교용 예시이며, 실제 구현에는 전체 문안을 사용합니다. 대화형 사례의 후속 요청은 앞선 결과와 자료가 있어야 합니다.

API 키와 인증 정보는 로컬 `.env`에서 관리하고 GitHub에 올리지 않습니다. 프롬프트 안의 키 자리표시자는 실제 비밀값이 아닙니다.

7장과 9장의 연결은 두 장의 구현 요구사항을 적용한 뒤 같은 DB로 두 대시보드를 각각 실행하여 확인합니다. 연결 기능만으로 9장 서버가 자동 실행되지는 않습니다.

## 1부. 바이브 코딩으로 부동산 데이터 분석 시작하기

### 1장. AI로 시작하는 데이터 기반 부동산 투자

1장은 개념과 완성 사례를 소개하며, 독립된 실습 프롬프트는 없습니다. 실제 실습은 2장부터 시작합니다.

### 2장. 클로드 코드와 안티그래비티로 실습 환경 만들기

- [2.2 파이썬 설치](part01/chapter02/02_python_installation_help.md)
- [2.4 클로드 코드 설치](part01/chapter02/04_claude_code_check.md)
- [2.5 바이브 코딩 첫 경험](part01/chapter02/05_first_vibe_coding.md)
- [2.6 프로젝트 환경 구축](part01/chapter02/06_project_setup.md)
- [2.7 분석 도구 설치](part01/chapter02/07_analysis_tools.md)
- [2.8 설치 확인 및 첫 실행](part01/chapter02/08_environment_verification.md)
- [2.9 클로드 코드와 효과적으로 협업하는 법](part01/chapter02/09_collaboration_workflow.md)

### 3장. 실거래가·KB부동산 데이터 자동으로 모으고 다듬기

- [3.1 아파트 실거래가 데이터 수집](part01/chapter03/01_trade_data.md)
- [3.2 KB부동산 통계 데이터 수집](part01/chapter03/02_kb_statistics.md)
- [3.3 공동주택 정보 수집](part01/chapter03/03_housing_complex.md)
- [3.4 좌표 데이터 수집](part01/chapter03/04_coordinates.md)
- [3.5 경계지도 수집](part01/chapter03/05_boundary_map.md)
- [3.6 데이터 자동 수집](part01/chapter03/06_collection_automation.md)
- [3.7 아파트 실거래가 데이터 전처리](part01/chapter03/07_trade_preprocessing.md)

## 2부. 관심단지와 지역을 데이터로 분석하는 도구 만들기

### 4장. 관심단지 실거래가를 자동으로 추적하는 시트 만들기

- [4.1 관심단지를 추적해야 하는 이유](part02/chapter04/01_tracking_need.md)
- [4.2 추적할 단지와 시세 조건을 AI에게 설명하는 프롬프트](part02/chapter04/02_tracking_prompt_design.md)
- [4.3 구글 시트 연결과 대화로 관심단지 관리하기](part02/chapter04/03_execution_and_watchlist_management.md)
- [4.4 전세가율과 전고점 대비로 매수 후보 좁히기](part02/chapter04/04_analysis_and_improvement.md)

### 5장. 매수 시점별 아파트 수익률 계산기 만들기

- [5장. 매수 시점별 아파트 수익률 계산기 만들기](part02/chapter05/01_roi_calculator.md)

### 6장. KB부동산 지수로 시장 흐름을 읽는 지도 대시보드 만들기

- [6장. KB부동산 지수로 시장 흐름을 읽는 지도 대시보드 만들기](part02/chapter06/01_kb_dashboard.md)

### 7장. 실거래가로 단지별 가격·갭을 비교하는 대시보드 만들기

- [7장. 실거래가로 단지별 가격·갭을 비교하는 대시보드 만들기](part02/chapter07/01_price_gap_dashboard.md)

### 8장. 거래량 지도로 지역 대장 단지를 찾는 대시보드 만들기

- [8장. 거래량 지도로 지역 대장 단지를 찾는 대시보드 만들기](part02/chapter08/01_trade_map_dashboard.md)

### 9장. 단지 가격·거래량 대시보드와 AI 투자 분석 보고서 만들기

- [9장. 단지 가격·거래량 대시보드와 AI 투자 분석 보고서 만들기](part02/chapter09/01_price_volume_dashboard.md)

## 부록

- [부록 1. 차트 검수 프롬프트](appendix/01_visualization_principles.md)
- [부록 2. 실습에 다시 쓰는 후속 요청 8개](appendix/02_practice_reference.md)

## 파일과 번호 안내

기존 링크를 유지하기 위해 공개 파일명은 보존했습니다. 5~9장의 `01_`은 파일 순서이며 책의 1절을 뜻하지 않습니다. 각 요청의 「책 위치」에서 현재 장·절을 확인하세요.

이 폴더는 현재 원고의 프롬프트 모음입니다. 저장소의 참고용 완성 코드에는 이전 `partXX` 경로가 남아 있으므로, 현재 장 번호와 코드 폴더의 대응은 [저장소 안내](../README.md)를 확인하세요. 프롬프트 갱신과 완성 코드 갱신은 별개입니다.
