# BidWatch 전체 계획 (단일 원본)

> PLAN MODE에서 최초 작성/주요 변경 시 갱신. Phase 완료 시 메인 agent가 체크박스 `[x]` + 완료일.
> `Phase_XXX.md`는 실패한 접근·버린 대안이 있을 때만 만든다.
> 2026-09-23 기존 `docs/roadmap.md`에서 이관 — 구 번호 "Phase 1-N"은 "Phase 00N"과 같다.

## 시스템 개요
- 정부·공공기관 입찰공고를 공공 API(나라장터·K-Startup·기업마당·중소벤처기업부·보조금24)와 사용자가 추가한
  URL(AI 스크래퍼)에서 수집하고, 고객사(테넌트)별 키워드·지역·구독 출처로 걸러 보여주는 구독형 SaaS.
  대상은 입찰 담당자 1~3명 규모의 중소 IT/컨설팅 업체. 공고는 1회 수집해 전 테넌트가 공유하고,
  구독·키워드·태그는 테넌트별로 분리한다. 요구사항 상세는 `docs/REQUIREMENTS.md`.

## 아키텍처
- 백엔드: Python 3.11 · FastAPI · SQLAlchemy 2.0(async) · Alembic · PostgreSQL 16 · JWT(bcrypt, HS256)
- 프론트: Next.js 16(App Router) · TypeScript · Tailwind · Zustand(인증) · TanStack Query(서버 상태)
- 수집: `bid-collectors` 패키지(별도 저장소 `C:\Users\user\Documents\bid-collectors`, editable 설치) —
  인터페이스는 `docs/interface.md`. 현재 관리자 수동·동기 수집(Redis 미설치, Celery 코드는 있으나 미사용).
  URL 출처 AI 분석은 접수 시 FastAPI BackgroundTasks로 즉시 실행(2026-09-23).
- AI: Claude API — URL → scraper_config JSON 생성(F-009)
- 상세: `docs/system_design.md`(구조·데이터 분리) · `docs/api_spec.md`(엔드포인트) · `docs/SCHEMA.md`(스키마 결정)

## Phase 체크리스트

> **가장 위험한 것을 먼저 한다.** "위험한 것" = 틀리면 되돌리기 비싼 것, 가능한지 아직 모르는 것.

- [x] Phase 001: 프로젝트 셋업 + DB + 인증 (2026-04-11) — 로그 `Phase_001-003.md`
- [x] Phase 002: bid-collectors 연동 + 수집 파이프라인 (2026-04-11) — 로그 `Phase_001-003.md`
- [x] Phase 003: AI 스크래퍼 생성 + URL 구독 플로우 (2026-04-11) — 로그 `Phase_001-003.md`
- [x] Phase 004: 프론트엔드 + 공고 조회 + 설정 (2026-04-11)
- [x] Phase 005: 입찰 예고(사전규격) + 수집 UX 개선 (2026-04-13)
- [x] Phase 006: 코드 리팩토링 + 사용자/관리자 분리 (2026-04-13)
- [x] Phase 007: 태그 시스템 + 검토요청 페이지 (2026-04-14)
- [x] Phase 008: 지역 필터링 (2026-04-16, 정규화 버그 수정 2026-08-05)
- [ ] Phase 009: 대시보드 (F-012)
  - 착수 전 F-012 수용 기준 확정(무엇을 "신규"로 셀지·마감 임박 기준일 수 등 모호점 질문)
  - 신규 공고 수, 키워드 매칭 수, 마감 임박, 출처별 수집 현황 카드
- [ ] Phase 010: 자동 수집 (F-013)
  - Redis+Celery vs APScheduler 등 결정(→ '미정') · 정기 수집 1일 1~2회 · 수집 이력/로그
- [ ] Phase 011: 배포 — 보안 3층 ③ 전체 리뷰(`/security-review`) 통과가 선행 조건
  - Docker Compose(운영용) · 도메인 + SSL + Nginx · 베타 테스트
  - CLAUDE.md '배포 체크리스트' 2~4 채우기 · REQUIREMENTS '공개 범위' 확정
- [ ] 운영 단계 전환 (CLAUDE.md 정책 "운영 모드"로 갱신)

## 이후 단계 (Phase 번호 미발급 — 착수 시 번호를 받고 위 체크리스트로 옮긴다)

- **안정화 + UX**: AI 스크래퍼 성공률 개선 · 스크래퍼 모니터링(구조 변경 감지) · URL 추가 UX(진행 상태·미리보기 상세) ·
  이메일 알림(신규 공고·마감 임박) · 수집 이력/통계 페이지 · 성능 최적화(공고 10만 건+, ILIKE → FTS 전환 검토)
- **프리미엄 — AI 매칭**: 회사 프로필 입력 · AI 매칭 배치(매일 아침) · "내게 맞는 공고" + 점수·이유 ·
  카카오 알림톡 · 첨부파일 PDF/HWPX 파싱 · AI 첨부 분석(자격요건 체크)
- **성장**: 토스페이먼츠 정기결제 · 요금제별 기능 제한(키워드 수·**URL 출처 수 상한** — 2026-09-23 여기서 정하기로) · 팀 계정 강화(역할별 권한·활동 로그) ·
  랜딩 페이지 · 모바일 반응형 · 입찰 이력/통계/승률 분석

## 결정된 것 / 미정인 것

**확정**
- 공고는 1회 수집 → 전 테넌트 공유, 테넌트별 데이터는 구독·키워드·태그·프로필 — AI 비용·API 한도 절약(`docs/system_design.md` 2.3)
- 같은 URL은 스크래퍼 1개를 공유(scraper_registry.url_hash UNIQUE) — 두 번째 테넌트의 AI 비용 0
- 키워드 매칭은 조회 시점 ILIKE — 한국어 부분 일치에 유리. 데이터 증가 시 FTS 재검토
- 공고당 태그 1개(상태 전이 모델), 태그는 테넌트 단위 공유 — `Phase_007.md`
- 지역은 수집 시점에 17개 시/도 짧은 이름으로 정규화 — `Phase_008.md`
- 나라장터는 상세 fetch를 하지 않는다(API 단건 조회·사업개요 미지원, g2b 스크래핑 타임아웃) — `Phase_006.md`
- 2026-09-23 작업 체계를 greenfield 템플릿으로 이식: Phase 로그는 실패한 접근이 있을 때만 · 화면은 개발자가 본다
  (AI의 브라우저 자동화·스크린샷으로 대신하지 않는다)

**미정**
- 자동 수집 방식(Celery+Redis / APScheduler / OS 스케줄러) — Phase 010
- 배포 환경·도메인·공개 범위 — Phase 011
- 보조금24 출처 노출 여부 — 현재 프론트 `HIDDEN_TYPES`로만 숨김(백엔드는 수집 가능)
- 테스트 전용 DB 분리 여부 — 아래 보류 항목 참조

## 사용자 실테스트 대기
- **사용자설정 > 구독 출처 > 직접 추가한 사이트** (2026-09-23): URL 입력 → 목록에 "AI 분석 중" → 1분 안에
  "사용 가능"으로 바뀌는지 / 게시판이 아닌 주소(예: 기관 홈 첫 화면)를 넣으면 "자동 인식 실패"로 끝나는지(고장 시나리오) /
  `http://localhost` 입력 시 "사용할 수 없는 URL입니다" / 구독 해지. member 계정에는 입력칸이 안 보여야 함.
  ⚠️ 수집된 공고가 '공고 목록'에 나오는 것은 아직 아님(⑤⑥ 미구현).

## 보류 항목 (나중에 할 것)

> 조사만 하고 미룬 것을 여기 남긴다. **다시 조사하지 않아도 되도록 실측 결과와 근거까지** 적는다.

- **템플릿 규칙 위반 — 이식 시점(2026-09-23) 발견, 코드 미수정**. 착수 시 한 커밋씩:
  - `backend/app/tasks/collect_api.py:149` `except ImportError: pass` — 조용한 실패(celery 미설치 시 태스크 등록을
    건너뛰는 의도이나 로그·주석 없음). 로그 한 줄 + 이유 주석.
  - `backend/app/routers/sources.py:261` 미리보기 실패 시 `detail=f"스크래핑 실패: {e}"` — 예외 원문이 응답에 노출
    (보안 ① "오류 응답에는 상태만"). 원인은 로그로, 응답은 상태만.
- **테스트가 개발 DB를 공유** — `backend/tests/conftest.py`가 앱의 DATABASE_URL을 그대로 쓴다. 테스트가 회원가입 등으로
  개발 DB에 행을 쌓는다. 분리하려면 테스트 전용 DB + alembic upgrade 픽스처(일반 트랙 — 사용자 확인 필요).
- **수용 기준의 테스트 미대응** — F-004~F-008·F-010·F-011 필터 부분은 백엔드 테스트가 없다(`docs/REQUIREMENTS.md`에
  항목별 표시). 해당 기능을 다음에 건드릴 때 그 기능의 테스트부터 붙인다.
- **AI 스크래퍼 성공률 1차 실측 (2026-09-23, claude-opus-5, `backend/scripts/measure_ai_scraper.py`)** —
  lets_portal 손 설정 39곳을 정답으로 비교. 기준선(손 설정) 1건 이상인 **29곳 중 성공 13곳(45%)**.
  실패 16곳 원인: ① AI 응답이 JSON이 아님 8곳(HTML 이어쓰기·"Assistant{" 등 — 50K에서 잘린 HTML 뒤에
  지시 없이 끝나는 프롬프트 구조 문제, 그중 2곳은 뒤에 유효 JSON이 있었음) ② 셀렉터 0건 3곳(gbsa·kocca·koipa)
  ③ 겹침 낮음 3곳(gnto·jbba·dips) ④ POST 전용 사이트 2곳(itp·gntp — GET 분석으로는 구조적으로 불가).
  기준선 0건 10곳 중 3곳(ijto·kised·touraz)은 AI가 공고를 찾음 = 손 설정이 사이트 개편으로 낡음.
  부수 발견: AI가 pagination을 전체 URL이나 `?`로 시작하는 쿼리로 내서 2페이지부터 URL이 이중으로 붙음 /
  같은 사이트도 실행마다 설정이 달라짐(gwto 14건→7건) / bid-collectors `create_client`가 커스텀 transport를
  써서 `verify_ssl=False`가 무시됨(dicia·jica 기준선 0건의 원인 — bid-collectors `152f930`에서 수정, 실측 0→10·0→9건).
  단 bidwatch `analyze_url`의 페이지 fetch는 여전히 SSL 검증을 켜므로 이 두 곳은 AI 분석 단계에서 실패한다.
- **2차 실측 (2026-09-23, `566f144` 프롬프트·파싱·pagination 수정 후)** — 평가 가능 32곳(verify_ssl 수정으로
  기준선 살아난 3곳 포함) 중 판정 SUCCESS 22곳. 1차와 같은 29곳 기준 13→22곳(45%→76%). "JSON 아님" 8→0.
  PARTIAL 5곳의 제목을 직접 대조하니 4곳(gnto·jbba·keiti·sjtp)은 **손 설정이 틀리고 AI가 맞음**(분류 라벨·본문까지
  긁던 정답 쪽 결함) → 실질 성공 **26/32(81%)**. 판정 스크립트는 제목 정확일치라 이런 경우를 PARTIAL로 잡는다.
  남은 실패 6곳: analyze_url fetch의 SSL 검증 3곳(kcpi·dicia·jica) / POST 전용 2곳(itp·gntp) / 셀렉터가
  일부 행만 잡음 1곳(ctp — 1차에는 30/30 성공, 실행 간 비결정성).
- **3차 실측 (2026-09-23, `fe5a5f0` 시험 수집·재시도 후)** — 평가 가능 32곳 중 판정 SUCCESS 23, PARTIAL 5(그중 4곳은
  2차와 같은 손 설정 결함) → 실질 **27/32(84%)**. 인천TP가 재시도(1회 탈락 후)로 살아남. **멀쩡한 사이트를 탈락시킨
  사례 0** — FAIL_TRIAL 2곳(alio: 템플릿 `{{ item.rtitle }}`만 있는 JS 렌더링 / kiat: 500)은 기준선도 0건인 곳.
  ctp는 시험 수집을 통과한 채 3/30 — 원인은 **html.parser가 이 사이트 표를 잘못 읽음**(같은 셀렉터로 날짜
  html.parser 1/10행, lxml 10/10행). 손 설정이 `"parser": "lxml"`이던 이유. → parser 자동 전환 + "제목 있는 행 중
  날짜 파싱 50% 미만" 탈락 기준 추가 후 ctp 단독 재측정 30/30(parser=lxml).
  남은 실패 5곳: analyze_url fetch의 SSL 검증 3곳(kcpi·dicia·jica) / POST 전용 1곳(gntp) / 사이트 측 0건 제외.
- **승인 규칙 효과 확인 (2026-09-23 `/approval-audit`, `a3a7131`)** — ruff·git 읽기·git push·bid-collectors 교차
  작업을 settings.local.json에 열었다. 다음 세션에서 `python scripts/measure_wait.py --grep ruff`(·`git -C`)로
  8초 초과가 사라졌는지 확인하고 이 줄을 지운다.
- **SSRF 남은 위험** (2026-09-23 접수·구독 작업에서 기본 방어 적용 — `services/url_guard.py`: 접수 시 형식 검사 +
  분석용 페이지 요청은 리다이렉트까지 매 요청 공인 IP 확인 + AI 설정의 list_url·session_init_url 사전 확인).
  남은 것: ① 확인과 접속 사이 DNS 재바인딩 ② bid-collectors GenericScraper의 요청(시험·정기 수집)은 훅을 안 거쳐
  **리다이렉트로 내부망에 갈 수 있다** — bid-collectors에 요청 훅 주입 인자를 추가해야 막힘(양쪽 저장소 작업).
  Phase 011 전체 리뷰 전에 ②는 닫는다.
- **분석 중 서버 재시작 시 status가 analyzing에 남음** — BackgroundTasks는 프로세스와 함께 사라진다. 지금은 같은 URL을
  다시 제출해도 재분석하지 않는다(failed만 재분석). 기동 시 오래된 analyzing을 pending/failed로 되돌리는 복구가 필요.
