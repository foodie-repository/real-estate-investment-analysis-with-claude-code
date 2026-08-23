# 도서 실습 프롬프트

이 폴더에는 종이책 『부동산 투자 분석 with 클로드 코드』에서 독자가 클로드 코드에 직접 입력하는 실습용 프롬프트를 모았습니다. 책 본문과 AI 답변 예시는 포함하지 않습니다.

프롬프트의 부·장·절 번호는 출판사 최종 편집본을 기준으로 합니다. 관련 예제 코드의 `Part06~10` 폴더명은 원고 개편 전 개발 경로이므로, 아래 대응표를 참고하세요.

## 사용 방법

1. 책에서 진행 중인 장과 절에 해당하는 파일을 엽니다.
2. 파일 안의 `text` 코드 블록을 위에서부터 순서대로 복사합니다.
3. 이 저장소를 연 클로드 코드 대화창에 붙여넣습니다.
4. 파일 생성·수정·삭제나 명령 실행 전에는 클로드 코드가 제시한 대상과 영향을 확인합니다.

API 키가 필요한 프롬프트의 자리표시자는 자신의 키로 바꾸되, 실제 키는 반드시 로컬 `.env`에만 저장하세요. `.env`, DuckDB 파일과 서비스 계정 JSON은 GitHub에 올리지 않습니다.

## 1부. AI 부동산 투자의 준비

### 2장. 실습 환경 구축

- [P01-C02-S02 파이썬 설치 문제 해결](part01/chapter02/02_python_installation_help.md)
- [P01-C02-S04 클로드 코드 작동 확인](part01/chapter02/04_claude_code_check.md)
- [P01-C02-S05 바이브 코딩 첫 경험](part01/chapter02/05_first_vibe_coding.md)
- [P01-C02-S06 프로젝트 환경 구축](part01/chapter02/06_project_setup.md)
- [P01-C02-S07 분석 도구 설치](part01/chapter02/07_analysis_tools.md)
- [P01-C02-S08 설치 확인 및 첫 실행](part01/chapter02/08_environment_verification.md)
- [P01-C02-S09 클로드 코드 협업 방법](part01/chapter02/09_collaboration_workflow.md)

### 3장. 데이터 수집과 전처리

- [P01-C03-S01 아파트 실거래가 데이터 수집](part01/chapter03/01_trade_data.md)
- [P01-C03-S02 KB부동산 통계 데이터 수집](part01/chapter03/02_kb_statistics.md)
- [P01-C03-S03 공동주택 정보 수집](part01/chapter03/03_housing_complex.md)
- [P01-C03-S04 좌표 데이터 수집](part01/chapter03/04_coordinates.md)
- [P01-C03-S05 경계지도 수집](part01/chapter03/05_boundary_map.md)
- [P01-C03-S06 데이터 자동 수집](part01/chapter03/06_collection_automation.md)
- [P01-C03-S07 아파트 실거래가 데이터 전처리](part01/chapter03/07_trade_preprocessing.md)

## 책 번호와 예제 코드 대응

| 최종 책 위치 | 프롬프트 | 관련 코드 |
| --- | --- | --- |
| 1부 3장 데이터 수집과 전처리 | `prompts/part01/chapter03/` | `src/collectors/`, `src/preprocessing/` |
| 2부 4장 관심단지 트래킹 | 추후 출판사 최종 편집본에서 추가 | `projects/part06_tracking/` |
| 2부 5장 수익률 계산기 | 추후 출판사 최종 편집본에서 추가 | `projects/part07_roi/` |
| 2부 6장 KB부동산 대시보드 | 추후 출판사 최종 편집본에서 추가 | `projects/part08_kb_dashboard/` |
| 2부 7장 거래량 지도 | 추후 출판사 최종 편집본에서 추가 | `projects/part09_trade_map/` |
| 2부 8장 가격·거래량 대시보드 | 추후 출판사 최종 편집본에서 추가 | `projects/part10_price_volume/` |

## 프롬프트 표기 규칙

- `P01-C03-S01`은 각각 1부(`P01`), 3장(`C03`), 3.1절(`S01`)을 뜻합니다.
- 한 파일에는 같은 절에서 이어서 사용하는 준비, 구현, 실행과 검증 프롬프트를 책의 순서대로 넣습니다.
- 터미널 명령어, 본문 설명, AI 답변 예시와 저자·편집자 검토 메모는 제외합니다.
- 공개 프롬프트의 내용은 출판사 최종 편집본을 기준으로 관리합니다.
