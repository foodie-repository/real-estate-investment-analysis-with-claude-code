# 장별 실행 프로젝트

현재 책의 4~9장에 대응하는 참고 코드입니다. [전체 프롬프트](../prompts/README.md)와 함께 사용하고, 설치·데이터 준비는 [저장소 안내](../README.md)를 따르세요.

| 장 | 도구 | 실행 안내 |
| --- | --- | --- |
| 4장 | 관심단지 시세 트래킹 | [chapter04_tracking](chapter04_tracking/README.md) |
| 5장 | 매수 시점별 수익률 계산 | [chapter05_roi](chapter05_roi/README.md) |
| 6장 | KB부동산 대시보드 | [chapter06_kb_dashboard](chapter06_kb_dashboard/README.md) |
| 7장 | 가격·갭 비교 대시보드 | [chapter07_price_gap_table](chapter07_price_gap_table/README.md) |
| 8장 | 거래량·회전율 지도 | [chapter08_trade_map](chapter08_trade_map/README.md) |
| 9장 | 가격·거래량 대시보드 | [chapter09_price_volume](chapter09_price_volume/README.md) |

## 기존 경로에서 업데이트하는 경우

실행 코드의 기준 경로는 현재 장 번호와 같은 `chapterXX`입니다. 이전 `partXX` 명령은 연결용 실행 파일을 통해 현재 코드로 이동합니다. 내부 모듈을 직접 import한 개인 코드는 새 경로로 변경하세요.

| 이전 경로 | 현재 경로 |
| --- | --- |
| `part04_tracking` | [chapter04_tracking](chapter04_tracking/) |
| `part05_roi` | [chapter05_roi](chapter05_roi/) |
| `part06_kb_dashboard` | [chapter06_kb_dashboard](chapter06_kb_dashboard/) |
| `part07_trade_map` | [chapter08_trade_map](chapter08_trade_map/) |
| `part08_price_volume` | [chapter09_price_volume](chapter09_price_volume/) |

기존 관심단지·분석 대상 JSON을 수정했다면 먼저 백업한 뒤 현재 장 폴더의 `data/`로 옮깁니다. 기존 폴더의 목록을 자동으로 덮어쓰거나 읽지 않습니다.

## 데이터 준비 순서

1. 매매·전월세와 필요한 KB 통계를 수집합니다.
2. 공동주택 기본정보, 주소별 좌표와 시군구 경계지도를 준비합니다.
3. DB의 실제 지역·기간과 단지·면적을 확인합니다.
4. 해당 장의 코드를 실행하고 필터·계산 결과를 확인합니다.

데이터가 없는 새 설치에서도 테스트용 합성 자료로 계산 로직을 검증할 수 있습니다. 검증 범위와 제한은 [검증 기록](../VALIDATION.md)을 참고하세요.
