# BidWatch API 설계

> **관련 문서:** [system_design.md](system_design.md) — 전체 아키텍처, [db_schema.md](db_schema.md) — DB 스키마

Backend: FastAPI, 인증: JWT (access + refresh token)

---

## 인증

```
POST   /api/auth/register          회원가입
POST   /api/auth/login             로그인 → JWT 발급
POST   /api/auth/refresh           토큰 갱신
POST   /api/auth/change-password   비밀번호 변경
```

## 공고 조회

```
GET    /api/notices                 키워드 매칭된 공고 목록 (테넌트 키워드 자동 적용)
GET    /api/notices/{id}            공고 상세
GET    /api/notices/search?q=...    자유 텍스트 검색 (FTS)
GET    /api/notices/matched         AI 매칭 공고 (프리미엄)
```

## 키워드 관리

```
GET    /api/keywords                내 키워드 목록
POST   /api/keywords                키워드 추가
DELETE /api/keywords/{id}           키워드 삭제
PATCH  /api/keywords/{id}           키워드 활성/비활성
```

## 태그/워크플로우

```
GET    /api/tags                    내 태그 목록 (태그별 필터)
POST   /api/tags                    태그 설정 (공고에 태그 부여)
DELETE /api/tags/{id}               태그 해제
GET    /api/tags/review             검토요청 공고 목록
GET    /api/tags/bid                입찰대상 공고 목록
GET    /api/tags/excluded           제외 공고 목록
```

## 출처 관리

```
GET    /api/sources/system          공공 API 출처 목록 + 수집 상태 (나라장터, K-Startup 등)
GET    /api/sources                 내 구독 출처 목록 + 수집 상태
POST   /api/sources                 URL로 출처 추가 요청
                                    → 기존 스크래퍼 있으면 즉시 구독, 없으면 AI 분석 시작
GET    /api/sources/{sub_id}        구독 상세 (스크래퍼 상태, 수집 이력)
GET    /api/sources/{sub_id}/preview  스크래퍼 테스트 수집 미리보기
POST   /api/sources/{sub_id}/confirm  미리보기 확인 후 정식 구독
PATCH  /api/sources/{sub_id}        구독 수정 (별칭, 활성/비활성)
DELETE /api/sources/{sub_id}        구독 해제 (스크래퍼 자체는 유지, 구독만 제거)
```

## 프로필 (프리미엄)

```
GET    /api/profile                 회사 프로필 조회
PUT    /api/profile                 프로필 저장/수정
POST   /api/profile/match-preview   프로필로 매칭 미리보기 (즉시 실행)
```

## 구독/결제

```
GET    /api/subscription            현재 구독 상태
POST   /api/subscription/checkout   결제 시작 (토스페이먼츠)
POST   /api/subscription/webhook    결제 웹훅
POST   /api/subscription/cancel     구독 해지
```

## 알림

```
GET    /api/notifications/settings  알림 설정 조회
PUT    /api/notifications/settings  알림 설정 변경
GET    /api/notifications/history   발송 이력
```

## 관리자 (시스템)

```
GET    /api/admin/tenants           전체 테넌트 목록
GET    /api/admin/collection/status 수집 상태 (공공 API + 스크래퍼 요약)
POST   /api/admin/collection/run    공공 API 수동 수집 실행
GET    /api/admin/collection/logs   수집 이력
GET    /api/admin/scrapers          전체 스크래퍼 목록 (구독자 수, 상태, 최근 수집)
GET    /api/admin/scrapers/{id}     스크래퍼 상세 (config, 구독 테넌트 목록, 수집 이력)
GET    /api/admin/scrapers/health   전체 스크래퍼 건강 상태 (실패율, 최근 성공/실패)
POST   /api/admin/scrapers/{id}/reanalyze  실패 스크래퍼 AI 재분석
DELETE /api/admin/scrapers/{id}     스크래퍼 삭제 (구독자 0인 경우만)
```

## 프론트엔드 페이지 구성

```
/ (랜딩)                     서비스 소개 + 요금제 + 회원가입 CTA
/login                       로그인
/register                    회원가입
/dashboard                   대시보드 (카드: 신규공고, 매칭공고, 마감임박, 키워드 수)
/notices                     공고 리스트 (키워드 매칭, 필터, 검색)
/notices/{id}                공고 상세 (첨부파일, 태그 버튼)
/matched                     AI 매칭 공고 (프리미엄)
/review                      검토요청 공고 리스트
/bid                         입찰대상 공고 리스트
/excluded                    제외 공고 리스트
/keywords                    키워드 관리
/sources                     수집 출처 관리 + URL 추가
/profile                     회사 프로필 (프리미엄)
/settings                    알림 설정, 계정 관리
/subscription                구독/결제 관리
/team                        팀원 관리
```
