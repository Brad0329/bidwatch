# Phase 1-6 작업 로그

> 작성일: 2026-04-13
> 범위: 코드 리팩토링 (백엔드 의존성/스키마/서비스 분리, 프론트엔드 컴포넌트 통합 + 역할 기반 접근제어)
> 다음 작업: 나라장터 상세 API 재검토, 태그 시스템, 대시보드, 자동 수집

---

## 결정과 이유

- **require_role() 팩토리 패턴:** admin.py 로컬의 require_admin()을 deps.py로 이동하면서 단순 이동이 아닌 `require_role(*roles)` 팩토리로 구현. 향후 member 전용 엔드포인트 추가 시 `require_role("member", "admin", "owner")` 형태로 즉시 재사용 가능.
- **SourceSubscriptionList 삭제 → SourceList에 showCollection prop:** Phase 1-5에서 분리했던 두 컴포넌트가 80% 동일 코드. 하나로 합치고 showCollection prop으로 수집 버튼 표시 여부만 분기.
- **프론트 role guard + 백엔드 403 이중 보호:** /admin 경로에 프론트 레벨 역할 체크 추가. 백엔드 403만으로도 보안은 충분하지만, 비권한 사용자가 403 화면을 보는 대신 /dashboard로 자연스럽게 redirect되어 UX 향상.
- **GET 요청의 side-effect를 서비스 레이어로 분리:** notices.py의 _fetch_detail_via_collector()가 GET 핸들러 안에서 DB write를 수행하는 구조. 이를 services/notice.py의 enrich_notice_detail()로 분리하여 라우터는 요청/응답만, 서비스는 비즈니스 로직(상세 보충 + DB 저장) 담당.
- **중복 엔드포인트(GET /api/admin/collection/status) 삭제:** GET /api/sources/system과 동일 데이터를 반환하므로 제거. 프론트엔드에서 이미 sources/system을 사용 중이어서 영향 없음.

## 추가 작업: 나라장터 상세 모달 필드 보강 (2026-04-13)

- **NaraExtra 컴포넌트에 누락된 extra 필드 7개 추가:** bid-collectors README 확인 결과, data.go.kr API는 단건 조회와 content(사업개요)를 지원하지 않음. 대신 수집 시점에 extra에 12개 필드를 저장하고 있었으나 모달에서 5개만 표시 중이었음. contract_method, award_method, tech_eval_ratio, price_eval_ratio, contact_email, bid_qual, budget 추가.
- **평가비율 한 줄 표시:** tech_eval_ratio + price_eval_ratio를 "기술 60% : 가격 40%" 형태로 합쳐 표시.
- **첨부파일은 이미 표시 중이었음:** attachments 렌더링 코드(164~189줄)가 이미 존재. 나라장터 API가 bidNtceFlUrl/ntceSpecDocUrl로 첨부파일 URL을 제공하고 bid-collectors가 수집하고 있음.
- **나라장터 상세 API 재검토 결론:** fetch_detail() 개선 불필요. bid-collectors에서 이미 확인 완료 — API 단건 조회 미지원, content 미제공. SKIP_DETAIL_TYPES 유지가 맞음.

## 외부 제약

- (이번 Phase에서 새로운 외부 제약 없음. 기존 제약 유지.)

## 다음 작업

- 태그 시스템 (검토요청/입찰대상/제외)
- 지역 필터링 (Phase 1-8 신규 추가)
- 대시보드 구현
- 자동 수집 (Redis/Celery 또는 대안)
