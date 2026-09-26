# 요청 — bid-collectors: 기관 수집기 4종 상세 조회(`fetch_detail`) (작성 2026-09-26, bidwatch)

> bidwatch → bid-collectors 요청서. 구현·버전·`docs/interface.md` 갱신은 bid-collectors 세션이 하고,
> 끝나면 평소대로 `docs/handover/v<버전>.md`로 넘긴다. 이 파일은 bidwatch 쪽 기록이다(bid-collectors 저장소를 고치지 않는다).

## 1. 왜
- 사용자 실테스트(2026-09-26): 수자원 공고("송산글로벌교육센터 수직정원 개선공사", `KWATER-B3202603397`) 상세 팝업이
  "공고 사이트 바로가기"로 여는 기관 화면보다 **정보가 너무 적다**. 수자원 목록 API는 필드 12개뿐이다.
- 나머지 셋도 같은 방식으로 비교했다(기관 화면 vs v1.4.0 목록 `extra`). **표본은 기관당 1건** — 필드 출현율은 bid-collectors가 실측해 달라.

## 2. 비교 (2026-09-26, bidwatch 조사)

| 기관 | 상세 원천 | 인증 | 목록 extra에 없고 상세에만 있는 것 | 차이 |
|---|---|---|---|---|
| **수자원** | 기관 사이트 내부 JSON `POST https://ebid.kwater.or.kr/bidpblanc/bidpblancsttus/selectBidPblancDtl.do`, 본문 `{"dmaSearchData":{"tndrPbanno":"B3202603397"}}` (Content-Type JSON). 사이트 화면(WebSquare)이 쓰는 주소 — **공식 API 아님** | 없음(세션·쿠키 없이 200 + `message.code:"success"` 확인) | `data.tndrPblanc`: 요청금액 `rqestAmt`(목록 예정가격은 0) · 입찰방법 `tndrMthNm` · 낙찰자결정 `sucbidrDcsnMthCdNm` · 담당자 이메일·전화 · 입찰장소 · 공동도급 `jntctrYn` · 입찰보증금률 `tndrGtnAmtRt` · 예가공개 `prdprcOthbcYn` · 발주계획번호 `ordgPlanNo` / `data.tndrPrgsOrdrList`: **입찰 일정 5단계**(공고·가격입찰서 제출·예가추첨·서류제출·결과발표, 각 `strtDt`·`closDt`) — 목록은 마감일 약 65%가 `-` / `data.atchflList`: **첨부**(`docNm`·`docFileNm`·`atchflId`·`fileSavePath`·`saveFileNm`, 표본 5개) | **큼** |
| **국방 d2b** | data.go.kr 15158416 상세 오퍼레이션 4종 — `getDmstcCmpetBidPblancDetail`·`getFcltyCmpetBidPblancDetail`·`getOutnatnCmpetBidPblancDetail`·`getDmstcOthbcVltrnNtatPlanDetail` (파라미터는 bid-collectors `scripts/_tmp/measure_d2b.py` batch_b에 이미 있다) | `DATA_GO_KR_KEY`, **오퍼레이션당 100/일** | 추정가격 `estmPrce` · 낙찰하한율 `scsbidLwltRt` · 사정률 상하한 · 낙찰자결정 `sucbidrDecsnMth` · 계약종류 · 담당자·연락처 · 입찰장소. 시설경쟁은 **현장 위치 `lc`**·**지역 제한 `areaLmttList`**·**면허 제한 `lcnsLmttList`**·원가 내역(재료비·노무비 등) (응답 예: bid-collectors `scripts/_tmp/d2b_raw/dt_dm.txt`·`dt_fc.txt`). 국내 수의 시설(`getFcltyOthbcVltrnNtatPlanList`) 상세는 조사 안 됨 | **큼**, 공식 API |
| **가스공사** | 기관 사이트 HTML `https://bid.kogas.or.kr:9443/supplier/contents/bid/bid_detail_view_notice.jsp?notice_code=…&bid_code=001&round=01` (EUC-KR, 서버 렌더) | 없음 | **추정가격·부가세·합계금액**(목록은 금액 없음) · 계약담당·연락처 · 업무구분·계약방법 상세(예 "일반경쟁 -최저가 -총액") · 견적방법 · 납품장소·납품조건 · 계약기간 · 낙찰자결정방법·입찰보증금·하자담보 · 기타사항(입찰참가자격 문장) · 입찰 진행순서(공고·마감·개찰 일시, 개찰장소) · 품목 내역(수량·단위) · **첨부**(`/supplier/bid/bid_download_attfile.jsp?notice_code=…&seq=1`) | **큼**, HTML 파싱 |
| **LH** | 기관 사이트 HTML — v1.4.0 `url`과 같은 주소(예 `…BidctrctgdsDetailListCmd.dev?bidNum=2603437&bidDegree=00`, 서버 렌더) | 없음 | 금액은 목록에 이미 있다. 더 있는 것: **첨부**(표본 3개 — 링크가 `javascript:fn_dds_open('10', 파일명, '/attachEBID/bidinfo/…')`라 실제 다운로드 주소 조립 확인 필요) · 공고부서(지역본부 이름) · 입찰방법(총액)·입찰방식 · 재입찰 · 현장설명 일시·장소 · 참가지역 이름 · 공동수급협정서 마감 | 작음 — 첨부가 주 |

## 3. 요청
기관 수집기 4종에 `fetch_detail(bid_no)` 구현. 계약은 알리오(v1.3.0)와 같게:
- 반환 dict = **상세 응답의 비어 있지 않은 필드 전부, 원래 이름 그대로**(v1.2.5 원칙 ①) + `attachments: [{"name", "url"}, …]`
  (없으면 `[]` — bidwatch가 "조회함"을 구분한다) + 있으면 `content`(없으면 `""`). HTML 원천(가스·LH)은 항목명→값 키를 어떻게 줄지
  bid-collectors가 정해 interface.md에 적어 달라(원문에 필드 이름이 없으니 화면 항목명 그대로도 좋다).
- 실패는 알리오와 같이 **예외**(HTTP 오류·성공 코드 아님·형식 이상·bid_no 형식 불일치). bidwatch는 경고 로그 후 팝업은 띄우고 다음에 다시 시도한다.
- 수집 시점에 부르지 않는다 — bidwatch가 팝업을 열 때 1건씩, 한 번 받으면 DB에 저장해 다시 부르지 않는다.
  국방은 오퍼레이션당 100/일이라 **호출 수가 한도에 닿는지**(팝업은 사람이 여는 만큼) handover에 적어 달라.
- 수자원·가스·LH는 **비공식 경로**(기관 화면)다 — 사이트 개편 시 깨질 수 있다는 점을 interface.md에 적고, 깨짐을 예외로 드러내 달라(빈 dict로 조용히 넘기지 말 것).
- 수자원 첨부는 다운로드 주소 조립법이 확인되지 않았다(`atchflId`·`fileSavePath`·`saveFileNm`만 있음) — 조립이 안 되면 `url` 없이 이름만이라도.
- 우선순위 제안: 수자원(사용자 제보) → 국방(공식 API) → 가스공사 → LH. 순서는 bid-collectors가 정한다.

## 4. bidwatch가 받은 뒤 할 일 (참고 — bidwatch 세션이 한다)
- `services/notice.py` `enrich_notice_detail`에 네 출처를 더한다(알리오와 같은 구조 — `attachments`가 None이면 조회).
- 상세 팝업 `InstitutionExtra`: 금액(수자원 요청금액·국방 추정가격·가스 추정가격 — 이름별, 없으면 `-`) · 입찰 일정 · 담당자 · 첨부 목록 ·
  국방 시설 지역·면허 제한. 수자원 마감일이 비어 있으면 상세 일정의 마감으로 보여 줄지(저장까지 할지)는 그때 사용자에게 묻는다.
- 국방 시설 현장 위치(`lc`)로 지역을 채울지(지금 "지역 미상")는 수집 시점 정규화라 별도 결정.
