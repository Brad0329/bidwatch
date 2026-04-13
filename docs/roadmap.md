# BidWatch 개발 로드맵

> **관련 문서:** [system_design.md](system_design.md) — 전체 아키텍처

---

## Phase 1: MVP — 현재 진행 중

### 완료된 작업

```
Phase 1-1~1-3: 프로젝트 셋업 + 수집 파이프라인 + AI 스크래퍼       ✅
  ├── Next.js + FastAPI 프로젝트 구조
  ├── PostgreSQL 스키마 (Alembic 마이그레이션)
  ├── JWT 인증 (회원가입/로그인/토큰갱신/비밀번호변경)
  ├── bid-collectors 패키지 연동 (nara/kstartup/bizinfo/smes/subsidy24)
  ├── 동기 수집 파이프라인 (Celery 없이 직접 실행)
  ├── AI 스크래퍼 생성 모듈 (URL → Claude API → scraper_config)
  └── URL 추가 → AI 분석 → 미리보기 → 구독 플로우

Phase 1-4: 프론트엔드 + 공고 조회 + 설정                           ✅
  ├── 공고 목록 (키워드 자동매칭, 검색, 필터, 페이지네이션)
  ├── 공고 상세 모달 (2단계 로딩: 목록 데이터 → 상세 API 보충)
  ├── 키워드 관리 (CRUD, 일괄 등록)
  ├── 출처 구독/해제
  ├── 수집 관리 (날짜 선택, 동기 수집)
  └── 사용자설정 / 관리자설정 페이지 분리

Phase 1-5: 입찰 예고 + 수집 UX 개선                               ✅
  ├── 나라장터 사전규격 수집 (nara_prespec, 연쇄 수집)
  ├── 입찰 예고 전용 페이지 (/pre-notices)
  ├── 수집 UI를 일수 → 날짜 선택으로 변경
  └── 설정 페이지 역할별 분리 (사용자/관리자)

Phase 1-6: 코드 리팩토링                                          ✅
  ├── require_role() 공통 의존성 (deps.py)
  ├── 스키마/엔드포인트 중복 제거
  ├── 상세 fetch 로직 서비스 레이어 분리
  ├── 프론트 hooks 분리 (useAdmin.ts)
  ├── SourceList 컴포넌트 통합 (showCollection prop)
  └── Sidebar/Admin 역할 기반 접근 제어
```

### 남은 작업

```
Phase 1-7: 태그 시스템
  ├── 태그 API (검토요청/입찰대상/제외/낙찰/유찰)
  ├── 공고 목록에서 태그 표시/필터
  └── 태그별 공고 조회 페이지

Phase 1-8: 대시보드
  ├── 신규 공고 수, 키워드 매칭 수, 마감 임박
  └── 출처별 수집 현황 카드

Phase 1-9: 자동 수집
  ├── Redis + Celery 또는 대안 (APScheduler 등)
  ├── 정기 수집 스케줄 (1일 1~2회)
  └── 수집 이력/로그

Phase 1-10: 배포
  ├── Docker Compose
  ├── 도메인 + SSL + Nginx
  └── 베타 테스트
```

---

## Phase 2: 안정화 + UX 개선

```
  ├── AI 스크래퍼 성공률 개선 (프롬프트 개선, 실패 사례 학습)
  ├── 스크래퍼 모니터링 (구조 변경 감지, 자동 알림)
  ├── URL 추가 UX 개선 (분석 진행 상태, 미리보기 상세화)
  ├── 이메일 알림 (신규 공고 + 마감 임박)
  ├── 수집 이력/통계 페이지
  └── 성능 최적화 (공고 10만건+ 대응)
```

---

## Phase 3: 프리미엄 — AI 매칭

```
  ├── 회사 프로필 입력 UI
  ├── AI 매칭 배치 (매일 아침)
  ├── "내게 맞는 공고" 페이지
  ├── 매칭 점수 + 이유 표시
  ├── 카카오 알림톡 연동
  ├── 첨부파일 다운로드 + PDF/HWPX 파싱
  └── AI 첨부 분석 (자격요건 체크)
```

---

## Phase 4: 성장

```
  ├── 토스페이먼츠 정기결제 연동
  ├── 요금제별 기능 제한
  ├── 팀 계정 강화 (역할별 권한, 활동 로그)
  ├── 랜딩 페이지
  ├── 모바일 반응형 최적화
  └── 입찰 이력/통계/승률 분석
```

---

## 현재 환경

| 항목 | 값 |
|------|-----|
| Python | 3.11.2 |
| PostgreSQL | 16 (로컬) |
| Redis | 미설치 (동기 수집 모드) |
| bid-collectors | editable 설치 (`C:\Users\user\Documents\bid-collectors`) |
| Backend | http://localhost:8100 |
| Frontend | http://localhost:3000 (Next.js, TypeScript, Tailwind, Zustand, TanStack Query) |
