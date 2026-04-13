# BidWatch API 명세

> **관련 문서:** [system_design.md](system_design.md) — 전체 아키텍처, [db_schema.md](db_schema.md) — DB 스키마

Backend: FastAPI (Python 3.11), 인증: JWT (access 30분 + refresh 7일), 포트: 8100

---

## 인증 (`/api/auth`)

```
POST   /api/auth/register          회원가입 (tenant + owner 자동 생성)
POST   /api/auth/login             로그인 → access_token + refresh_token
POST   /api/auth/refresh           토큰 갱신 (refresh_token → 새 access/refresh)
POST   /api/auth/change-password   비밀번호 변경 [인증 필요]
GET    /api/auth/me                현재 사용자 정보 [인증 필요]
```

## 공고 조회 (`/api/notices`) [인증 필요]

```
GET    /api/notices                공고 목록 (구독 출처 + 키워드 자동매칭)
                                   ?page=1&page_size=20&q=검색어&source_id=1&status=ongoing
GET    /api/notices/pre-specs      입찰 예고(사전규격) 목록 (nara_prespec 고정)
                                   ?page=1&page_size=20&q=검색어&status=ongoing
GET    /api/notices/{id}           공고 상세 (content 없으면 fetch_detail로 보충 → DB 캐시)
```

## 키워드 관리 (`/api/keywords`) [인증 필요]

```
GET    /api/keywords               내 키워드 목록
POST   /api/keywords               키워드 추가 (max_keywords 제한, 중복 체크)
PATCH  /api/keywords/{id}          키워드 활성/비활성 토글
DELETE /api/keywords/{id}          키워드 삭제
```

## 출처 관리 (`/api/sources`) [인증 필요]

```
GET    /api/sources/system                     공공 API 출처 목록 + 수집 상태
GET    /api/sources/system/subscriptions        내가 구독 중인 출처 ID 목록
POST   /api/sources/system/{id}/subscribe       시스템 출처 구독
DELETE /api/sources/system/{id}/unsubscribe     시스템 출처 구독 해제

GET    /api/sources                             내 커스텀 스크래퍼 구독 목록
POST   /api/sources                             URL 추가 → AI 분석 디스패치
GET    /api/sources/{sub_id}                    구독 상세 (스크래퍼 상태 폴링)
GET    /api/sources/{sub_id}/preview            스크래퍼 테스트 수집 미리보기
POST   /api/sources/{sub_id}/confirm            미리보기 확인 후 구독 확정
PATCH  /api/sources/{sub_id}                    구독 수정 (별칭, 활성/비활성)
DELETE /api/sources/{sub_id}                    구독 해제 (soft delete)
```

## 관리자 (`/api/admin`) [인증 필요, owner/admin 역할]

```
POST   /api/admin/collection/run    수동 수집 실행 (sync/async, 단일/전체)
                                    body: {source_id?, days, sync}
GET    /api/admin/collection/stats  수집 통계 (bid/scraped/scraper 건수)
```

## 기타

```
GET    /api/health                  서버 상태 확인
```

---

## 프론트엔드 페이지 구성 (현재 구현)

```
/                    인증 여부에 따라 /dashboard 또는 /login으로 리다이렉트
/login               로그인
/register            회원가입
/dashboard           대시보드 (placeholder)
/notices             공고 목록 (검색, 필터, 페이지네이션, 상세 모달)
/pre-notices         입찰 예고 (사전규격 공고)
/settings            사용자설정 (구독 출처 + 키워드 관리)
/admin               관리자설정 (수집 관리) — owner/admin만 접근
```

---

## 미구현 API (향후)

```
-- 태그/워크플로우
GET/POST/DELETE  /api/tags           공고 태그 관리 (검토요청/입찰대상/제외)

-- 프로필 (프리미엄)
GET/PUT  /api/profile               회사 프로필 관리
POST     /api/profile/match-preview 매칭 미리보기

-- 알림
GET/PUT  /api/notifications/settings 알림 설정

-- 구독/결제
GET/POST /api/subscription          구독 관리 (토스페이먼츠)
```
