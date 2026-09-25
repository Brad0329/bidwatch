# 요청 — bid-collectors: 알리오 상세 조회(`AlioCollector.fetch_detail`) (작성 2026-09-25, bidwatch)

> bidwatch → bid-collectors 요청서. 구현·버전·`docs/interface.md` 갱신은 bid-collectors 세션이 하고,
> 끝나면 평소대로 `docs/handover/v<버전>.md`로 넘긴다. 이 파일은 bidwatch 쪽 기록이다(bid-collectors 저장소를 고치지 않는다).

## 1. 왜
- bidwatch 공고 상세 팝업에서 알리오 공고가 너무 부실하다. 목록 API(`findBidList.json`)에는 제목·기관·등록일·마감일뿐이다
  (`docs/source_fields.md` §9).
- 알리오 **상세** JSON(`https://alio.go.kr/occasional/findBidDtl.json?seq={seq}`, 인증 없음)에는 쓸 만한 것이 있다.
  실측(2026-09-25, DB의 알리오 공고 무작위 20건, `bidwatch/scripts/_tmp/alio_detail_probe.py`):

  | 항목 | 20건 중 | 비고 |
  |---|---|---|
  | 첨부 `fileList`(`fileNm`·`fileNo`=URL) | **20** | 공고문 hwp·pdf·규격서 1~5개 |
  | 원문 링크 `refrUrl` | 19 | 나라장터 13 · 한전 SRM·수자원·LH·한수원 전자입찰 6 |
  | 나라장터 공고번호(`refrUrl`의 `bidPbancNo`) | 13 | 13건 모두 bidwatch DB의 나라장터 공고와 일치 |
  | 본문 `content` | **0** | 알리오는 본문을 주지 않는다 |
  | `bidType` | 1:12 · 3:7 · 0:1 | 1 = 나라장터 연계로 보임(추정) |

  응답 예(seq 3580350): `scripts/_tmp/fielddict_alio_dtl_3580350.json` — `data.bidDtl`(공고 필드) + `data.fileList`(첨부).
  `bidDtl.bFiles`는 같은 첨부를 `URL|파일명***URL|파일명` 문자열로 한 번 더 담는다.

## 2. 무엇을
`AlioCollector.fetch_detail(bid_no)` 구현. `bid_no`는 `ALIO-{seq}`.

반환 dict (bidwatch `services/notice.py`의 `enrich_notice_detail`이 그대로 병합한다):
| 키 | 값 | 비고 |
|---|---|---|
| `attachments` | `[{"name": fileNm, "url": fileNo}, …]` | `fileList` 기준. 없으면 `[]`(None 아님 — bidwatch가 "조회함"을 구분하는 데 쓴다) |
| `content` | 본문 텍스트(HTML 제거) | 늘 빈 값이면 `""` |
| 그 밖의 키 | `data.bidDtl`의 **비어 있지 않은 필드 전부, 원래 이름 그대로** | v1.2.5 원칙 ① 그대로 — `refrUrl`·`bidType`·`apbaId`·`ingStatus`·`totContAmt`·`disclosureNo`·`submissionNo`·`idate`… `bFiles`는 `fileList`와 중복이라 빼도 됨(판단은 bid-collectors) |

- 실패(HTTP 오류·`status != success`·JSON 형식 이상): 지금 K-Startup처럼 예외를 던지든 None이든 좋다 —
  bidwatch는 둘 다 경고 로그로 받는다. **어느 쪽인지 interface.md에 적어 달라.** 키가 들어간 URL은 없다(알리오는 인증 없음).
- **수집 시점에 부르지 말 것**: 공고 1건당 호출이 1회 늘어난다(7일치 약 1,500건). bidwatch가 팝업을 열 때만 부른다.
- `docs/interface.md` §2 `fetch_detail` 설명("K-Startup만 구현")을 갱신.

## 3. bidwatch가 받은 뒤 할 일 (참고 — bidwatch 세션이 한다)
- 팝업을 열 때 상세 보충(이미 있는 구조) → 첨부파일 목록 · "원문 바로가기 (나라장터 / 한전 전자입찰 …)" 버튼 ·
  나라장터 번호가 있으면 "연결된 공고 → 나라장터 공고 보기"(F-018과 같은 방식). 목업 확인 2026-09-25 사용자 "이대로".
- 한 번 조회한 공고는 다시 부르지 않는다(`attachments`가 None이 아니면 조회함).

## 4. 함께 볼 것 — bid-collectors 결함·불일치 10건
`bidwatch/docs/source_fields.md` 부록 A (2026-09-25 필드 사전 조사). 이번 요청과 별개로 전달 대기 중.
