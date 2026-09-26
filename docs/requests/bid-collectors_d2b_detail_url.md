# 요청 — bid-collectors: 국방전자조달(d2b) 공고 `url`을 상세 화면 주소로 (작성 2026-09-26, bidwatch)

> bidwatch → bid-collectors 요청서. 구현·버전·`docs/interface.md` 갱신은 bid-collectors 세션이 하고,
> 끝나면 평소대로 `docs/handover/v<버전>.md`로 넘긴다. 이 파일은 bidwatch 쪽 기록이다(bid-collectors 저장소를 고치지 않는다).

## 1. 왜
- 사용자 실테스트(2026-09-26): 국방전자조달 공고 팝업의 "공고 사이트 바로가기"가 d2b **첫 화면**으로 열린다.
  `d2b.py`가 `url=SITE_URL`("https://www.d2b.go.kr/")로 넣기 때문이다(목록 12개 오퍼레이션에 상세 링크 필드가 없다 — 맞는 판단이었다).
- bidwatch 조사로 **d2b 사이트 상세 화면이 로그인 없이 GET 한 줄로 열리고, 필요한 값이 전부 목록 원문(`extra`)에 있다**는 것을 확인했다.
  사이트는 폼 POST(`/js/common/gitis_common.js` `f_submit`, 클릭 처리 `/js/index.js` 220~387행)로 여는데, 같은 파라미터를 쿼리스트링으로 줘도 같은 화면이다.
  **공식 API가 아니라 사이트 화면 경로**라 개편 시 깨질 수 있다.

## 2. 종류별 주소 (2026-09-26 bidwatch 실측, 쿠키 없이 GET → 응답에 그 공고의 건명이 있는지로 판정)

모두 `https://www.d2b.go.kr` 뒤에 붙인다. `{}` 안은 목록 원문 필드 이름(bidwatch DB 418행 전부에서 결측 0).

| 구분 | 경로·파라미터 | 표본 | 결과 |
|---|---|---|---|
| 국내경쟁(물품·용역) | `/pdb/bid/bidAnnounceView.do?dprt_code={orntCode}&anmt_divs={pblancSeCode}&anmt_numb={pblancNo}&rqst_degr={pblancOdr}&dcsn_numb={dcsNo}&rqst_year={demandYear}` | 30 | 30/30 |
| 시설경쟁 | `/peb/bid/announceView.do?` + 국내경쟁과 같은 틀, 단 `dcsn_numb={cntrwkNo}`, `rqst_year={pblancYear}` | 30 | 26/30 — 실패 4건은 아래 3-① |
| 국외경쟁 | `/pcb/bid/bidAnnounceView.do?grd_anmtYear={pblancYear}&grd_bidxDate={opengDt 앞 8자}&grd_anmtNumb={pblancNo}&grd_dgNumb={purchsRequstNo}&grd_anmtRqst={pblancOdr}&grd_dprtCode={pblancNo 앞 3자}&grd_dcsnNumb={dcsNo}&grd_gropNumb={groupNo}&menuOption=1` | 4(전체) | 4/4 |
| 국내수의 | `/pdb/openNego/openNegoPlanView.do?dmst_itnb={iemNo}&dcsn_numb={dcsNo}&negn_pldt={ntatPlanDate}&negn_degr={pblancOdr}&dprt_code={orntCode}&ordr_year={demandYear}&anmt_numb={pblancNo}` | 30 | 30/30 — 예외 1건은 3-② |
| 시설수의 | `/peb/openNego/openNegoPlanView.do?csrt_numb={cntrwkNo}&negn_pldt={ntatPlanDate}&dprt_code={orntCode}&ordr_year={cntrwkNo 앞 4자}&negn_degr={pblancOdr}&anmt_numb={pblancNo}` | 30 | 30/30 |

- 파라미터는 **전부 넣는다**. 국외경쟁은 하나씩 빼면 통과하는 것도 둘을 빼면 500. `grd_bidxDate`는 정확해야 한다(틀리면 500).
  사이트가 넘기는 `grd_docmIden`은 API에 없지만 빼도 열린다.
- 시설수의 `ordr_year = cntrwkNo 앞 4자`는 **추정**(30/30 통과) — 확인 부탁.
- **실패가 200으로 올 수 있다**: 값이 틀리면 오퍼레이션에 따라 500이거나 200 + 건명 없는 화면. 검증은 상태 코드가 아니라 본문의 건명으로.
- 서버에서 점검할 때 curl 기본 User-Agent는 400 — 브라우저 UA면 정상(사용자 클릭에는 무관).
- 재현 스크립트: bidwatch `scripts/_tmp/d2b_link_samples.py`(DB 표본) · `d2b_link_probe.py all|drop`(GET 확인·필수 파라미터) ·
  `d2b_link_keys.py`(결측 계수) · `d2b_link_iem.py`(iemNo 예외). gitignore라 bid-collectors에서 쓰려면 경로로 읽어 가 달라.

## 3. 요청
`D2bCollector.collect`가 `url`에 위 종류별 상세 주소를 넣는다. `detail_url`은 지금처럼 `""`여도 된다(bidwatch는 `url`을 바로가기로 쓴다).
- **① 시설경쟁 지명경쟁(`cntrctMth=지명경쟁`)은 로그인 필요** — 200인데 본문이 `alert("로그인 후 이용가능합니다.")` 후 물품 목록으로 간다
  (bidwatch 시설경쟁 37행 중 지명경쟁 4행, 4/4 실패). 이 경우는 **시설 공고 목록 `/peb/bid/announceList.do?key=41`** 제안
  (목록이 열리는지는 미확인). 다른 구분에도 로그인 필요 유형이 있는지 표본에서는 못 봤다 — 실측 부탁.
- **② 국내수의 `iemNo`가 `***`가 아닌 행**(116행 중 1행, `D2B-국내수의-2026SCR012438002-1`, iemNo `001`)은 500 — `dmst_itnb`를
  `001`·`***`·빈 값으로 바꿔도 500, 원인 미상. 원인을 못 찾으면 이런 행은 구분별 목록 화면으로 폴백(물품 `/pdb/bid/goodsBidAnnounceList.do?key=13`,
  용역 `/psb/bid/serviceBidAnnounceList.do?key=32`, 국외 `/pcb/bid/bidAnnounceList.do?key=51` — 첫 화면 메뉴에서 수집, 열림 미확인).
- 필드가 비어 상세 주소를 만들 수 없으면 지금처럼 첫 화면 — **조용히 넘기지 말고** 그 사실이 드러나게(errors 또는 로그, 방식은 bid-collectors가 정한다).
- 미확인: `pblancOdr`만 다른 차수 1·2가 서로 다른 화면을 여는지(둘 다 같은 건명으로 열렸다). 국외경쟁은 표본 4건뿐.
- 비공식 경로라는 점을 interface.md에 적어 달라(LH·가스·수자원 상세와 같은 취급).

## 4. bidwatch가 받은 뒤 할 일 (참고 — bidwatch 세션이 한다)
- upsert가 `url`을 갱신한다(`services/collection.py` `on_conflict_do_update`) — **다음 수집 때 받는 행은 자동으로 바뀐다.**
  수의 2종은 진행 중 전량이라 전부 바뀌지만, 경쟁 3종은 수집 `days` 밖의 기존 행이 첫 화면 주소로 남는다 →
  넓은 `days`로 한 번 수집할지(d2b 한도 100회/일, 목록 5종 × 1) 받은 뒤 정한다.
- 팝업 버튼 문구·동작은 그대로("공고 사이트 바로가기"). 사용자 실테스트: 5종 각 1건 + 지명경쟁 1건이 어디로 열리는지.
