# Phase 1-5 작업 로그

> 작성일: 2026-04-13 (2차 갱신)
> 범위: 입찰 예고 (나라장터 사전규격) + 수집 UX 개선 + 설정 분리
> 다음 작업: 코드 리팩토링, 나라장터 상세 API 재검토, 태그 시스템, 대시보드, 자동 수집

---

## 결정과 이유

- **별도 SystemSource(nara_prespec)로 분리:** 기존 bid_notices 테이블에 notice_type 컬럼 추가 대신, source_id로 자연스럽게 일반 공고와 사전규격을 구분. 기존 아키텍처와 일관성 유지.
- **연쇄 수집(CHAINED_COLLECTORS):** 나라장터 수집 버튼 클릭 시 사전규격도 자동 수집. admin.py에서 처리하여 프론트엔드 변경 최소화.
- **설정 페이지에서 nara_prespec 숨김:** 사전규격은 나라장터 수집 시 자동으로 같이 수집되므로 별도 구독/수집 UI 불필요. HIDDEN_TYPES에 추가.
- **사전규격 전용 API(/api/notices/pre-specs):** 기존 /api/notices와 분리. source를 nara_prespec으로 고정하여 구독 여부와 무관하게 사전규격만 표시.
- **NaraCollector 재사용:** 별도 collector 클래스 생성 대신 기존 NaraCollector.collect_pre_specs() 메서드 활용. collect_api.py에서 collector_type별 분기 처리.
- **수집 UI를 일수에서 날짜 선택으로 변경:** last_collected_at을 기본값으로 활용하여 불필요한 중복 API 호출 방지. 날짜에서 days를 역산하여 기존 백엔드 API 변경 없이 구현.
- **설정 페이지 분리 (사용자설정/관리자설정):** 현재는 관리자 겸 사용자로 사용하되, 나중에 role 기반 분리 용이하도록 메뉴와 페이지를 미리 분리. 사용자설정은 구독+키워드만, 관리자설정은 수집 관리.
- **SourceSubscriptionList 컴포넌트 분리:** 기존 SourceList(수집 버튼 포함)와 별도로 구독 전용 컴포넌트를 만들어 사용자설정에서 사용.

## 실패한 접근

1. **alembic upgrade 시 002 migration 불일치:** 테이블은 이미 존재하지만 alembic_version이 001에 머물러 있음. `alembic stamp 002`로 버전 동기화 후 003 적용.
2. **CollectionButton 날짜 선택 레이아웃 깨짐:** 한 줄 레이아웃에서 텍스트 줄바꿈 발생. SourceList를 label 한 줄 구조에서 div 2줄 구조(상단: 출처 정보, 하단: 수집 컨트롤)로 변경하여 해결.

## 외부 제약

- **collect_pre_specs() 반환 타입 차이:** NaraCollector.collect_pre_specs()는 list[Notice]를 반환 (collect()의 CollectResult와 다른 인터페이스). _collect_source()에서 별도 분기 필요.
- **사전규격 API ServiceKey 대문자:** HrcspSsstndrdInfoService API는 ServiceKey 파라미터가 대문자 S (나라장터 입찰공고 API의 serviceKey와 다름). bid-collectors에서 이미 처리됨.
- **data.go.kr API 날짜 형식:** yyyyMMddHHmm (분 단위). 초 단위 불가하므로 일 단위 중복 허용이 현실적.

## 환경

- 백엔드: http://localhost:8100
- 프론트: http://localhost:3000

## 다음 작업

- 코드 리빌딩/리팩토링 (새 세션)
- 나라장터 상세 API 방안 재검토
- 태그 시스템 (검토요청/입찰대상/제외)
- 대시보드 구현
- 자동 수집 (Redis/Celery 또는 대안)
