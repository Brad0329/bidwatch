# 출처 필드 사전 — bid-collectors가 넘기는 값의 의미

> 작성 2026-09-25 · bid-collectors **v1.2.5** 기준. 출처별로 실제 호출(소량)과 공식 명세를 대조해 만들었다.
> - **키가 무엇이 오는가**의 정답은 실측과 코드(`bid_collectors/*.py`)다. **키가 무슨 뜻인가**의 근거는 명세다.
>   명세·화면으로 확인하지 못한 뜻은 반드시 **추정**으로 표시한다.
> - bid-collectors handover가 표준 필드의 원천이나 `extra`를 바꾸면 이 문서의 해당 절을 같은 작업에서 고친다.
> - 계약(모델·필드 규칙)은 `docs/interface.md`에 있다. 이 문서는 그 필드들이 **출처마다 실제로 무엇인지**를 다룬다.
> - 조사 스크립트·명세 원본(docx 텍스트 덤프 등)은 `scripts/_tmp/`에 있다(gitignore). 재현 명령은 각 절 끝에 있다.

## 0. 읽는 법

- **근거 표기**: `명세` = 공식 명세(활용가이드·swagger·API 상세 페이지)의 항목명·설명으로 확인 /
  `화면` = 명세가 없어 사이트 화면 라벨·스크립트와 값을 대조해 확인(알리오) / `추정` = 이름·값만 보고 추정.
- **출현 n/N**: 표본 N건 중 `extra`에 그 키가 있던 건수. `extra`에는 **비어 있지 않은 값만** 들어가므로(0·False는 남음)
  출현이 N 미만인 키는 없을 수 있다. 화면 코드는 **어떤 키든 없을 수 있다고 가정**한다. 표본 조건은 각 절 D에 적었다.
- **값 타입**: JSON 출처는 원문 타입 그대로(int가 섞인다). XML 출처(나라장터·중소벤처)는 문자열이고,
  **같은 태그가 2개 이상일 때만 list**가 된다(1개면 str — 중소벤처 첨부 참고).
- **HTML·엔티티**: `extra`는 원문이라 HTML 태그·`&amp;` 같은 엔티티가 그대로 남는다. 표시할 때 정리하는 것은 BidWatch 몫이다.

---

## 1. 표준 필드 — 출처마다 뜻이 다르다

`interface.md`의 정의는 "공고일/마감일/예산·추정가격/지역" 같은 한 단어 주석뿐이다. 실제 원천은 아래와 같다.

| 출처 | start_date | end_date | status 판정 | budget | organization | region(원문 → BidWatch가 `normalize_region`) | category |
|---|---|---|---|---|---|---|---|
| 나라장터 입찰 용역·물품 | `bidNtceDt` 공고일시 | `bidClseDt` 입찰마감 | 마감일 | `asignBdgtAmt` **배정예산** | `ntceInsttNm` **공고기관** | `dminsttNm` **수요기관명**(지역 필드 아님) | 공공조달 대>중 분류 / 물품은 세부품명 |
| 나라장터 입찰 공사 | 같음 | 같음 | 마감일 | `presmptPrce` **추정가격(부가세 제외)** — 공사엔 배정예산 태그가 없다. 예산 `bdgtAmt`는 안 씀 | 같음 | 같음(공사현장 `cnstrtsiteRgnNm`은 안 씀) | 주공종명 |
| 나라장터 사전규격 (`nara_prespec`) | `rcptDt` 접수일시 | `opninRgstClseDt` 의견등록마감 | 마감일 | `asignBdgtAmt` 배정예산 | `orderInsttNm` 발주기관 | 없음 | `prdctClsfcNoNm` (**title과 같은 값**) |
| 나라장터 낙찰 (BidWatch 미사용) | `fnlSucsfDate` 최종낙찰일 | 없음 | 항상 closed | `sucsfbidAmt` **낙찰금액** | `dminsttNm` 수요기관 | 없음 | 없음 |
| 나라장터 계약 (BidWatch 미사용) | `cntrctCnclsDate` 체결일 | `cntrctPrd` 계약기간 — **틀리는 경우 많음**(부록 A-2) | 마감일 | `thtmCntrctAmt` 금차계약금액 | `cntrctInsttNm` 계약기관 | `cntrctInsttJrsdctnDivNm` **기관 분류**(국가기관 등) | 없음 |
| K-Startup | `pbanc_rcpt_bgng_dt` **접수 시작** | `pbanc_rcpt_end_dt` 접수 마감 | **출처 플래그** `rcrt_prgs_yn=="Y"` | 없음 | `pbanc_ntrp_nm` → `sprv_inst`(**기관 유형**) → "창업진흥원" | `supt_regin` (`전국`·`전남광주` 같은 약칭) | `supt_biz_clsfc` 지원 분야 |
| 기업마당 | `reqstBeginEndDe` 신청기간 앞쪽 | 신청기간 뒤쪽. **18%는 "예산 소진시까지" 같은 문장이라 None** | 마감일(없으면 ongoing) | 없음 | `excInsttNm` 수행기관(`기초자치단체`·`직접수행` 같은 유형값 섞임) | `jrsdInsttNm` **소관기관**(부처명이 들어옴) | 지원분야 대분류 |
| 중소벤처기업부 | `applicationStartDate` 신청 시작 | `applicationEndDate` 신청 마감 | 마감일(없으면 ongoing) | 항상 None(원천 태그가 실제 응답에 없음) | 상수 "중소벤처기업부" | 없음 | `writerPosition` **담당부서명** |
| 보조금24 | 항상 None | `신청기한` — 대부분 자유 문장이라 **4%만 추출, 그것도 기간의 시작일**(부록 A-2) | 마감일(없으면 ongoing) | 없음 | `소관기관명` | 없음 | `서비스분야` |
| 알리오 | `bdate` — 화면 라벨 **"등록일"**(공고일이 아님) | `bidInfoEndDt` 입찰종료일 | 마감일(없으면 ongoing) | 없음 | `pname` 기관명 | 없음 | 없음 |
| URL 출처 (GenericScraper) | AI 설정이 고른 목록의 날짜 칸 — 사이트마다 등록일·접수기간 등 **다름** | 항상 None | **게시일로 판정**(어제 이전 게시 = closed) — BidWatch는 배지를 숨긴다 | 없음 | 상수 `config.name` | 없음 | 없음 |

**공통 규칙 (코드 확인)**
- `parse_date`는 기간 문자열("A~B")이면 **시작일**을 돌려준다(`utils/dates.py`). end_date 원천이 기간 문자열인 출처에서 end_date가 틀린다.
- status는 **수집 시점의 날짜로 계산해 저장**한 값이다. 이후에는 다시 계산하지 않는다. `"cancelled"`를 만드는 코드가 없어서 나라장터 취소공고(`ntceKindNm=취소공고`)도 ongoing/closed로 들어온다.
- end_date가 없으면 status는 항상 ongoing이다(나라장터 입찰 용역 12%·물품 9%·공사 1%, 기업마당 18%, 보조금24 96%, 알리오 2%).
- content: K-Startup·중소벤처는 **앞 500자에서 자른다**. 나라장터·알리오·URL 출처는 항상 빈 문자열이다.
- budget은 출처마다 배정예산·추정가격·낙찰금액·계약금액으로 **서로 다른 개념**이다. 출처를 가로질러 금액을 비교하면 안 된다.

---

## 2. 나라장터 입찰공고 (`NaraCollector.collect`)

### A. 개요
- 조달청_나라장터 입찰공고정보서비스 `BidPublicInfoService` — data.go.kr **15129394**
- 엔드포인트 `https://apis.data.go.kr/1230000/ad/BidPublicInfoService/{op}`. 오퍼레이션: 용역 `getBidPblancListInfoServcPPSSrch` · 물품 `…ThngPPSSrch` · 공사 `…CnstwkPPSSrch`
- 조회 기준 `inqryDiv=1`(공고게시일시). 기간을 7일 단위로 나누어 모든 페이지를 받는다.
- 명세: `조달청_OpenAPI참고자료_나라장터_입찰공고정보서비스_1.2.docx`(개정 1.2, 2026-04-10. 1.1에서 평가비율, 1.2에서 `sucsfbidMthdAppStd`·`befBidBbancNo`가 추가됨)

### B. 표준 필드 ← 원문
| 표준 | 원문 | 규칙 |
|---|---|---|
| bid_no | bidNtceNo, bidNtceOrd | `{용역\|물품\|공사}-{번호}-{차수}`. **업무 구분(용역/물품/공사)은 extra에 없고 이 접두사에만 있다** |
| title | bidNtceNm | |
| url·detail_url | bidNtceDtlUrl | 실측 100% 있음 |
| content | — | 항상 `""`(목록 API에 사업개요가 없다) |
| attachments | ntceSpecDocUrl{1-10} + ntceSpecFileNm{1-10} | 이름이 없으면 `규격서{i}`. `stdNtceDocUrl`(표준공고서)은 첨부에 넣지 않는다 |
| 나머지 | §1 표 참고 | |

### C. extra 키 사전 — 근거는 전부 `명세`(예외는 표시). 출현은 용역/물품/공사, N = 1310/1108/942

**식별·공고 기본**
| 키 | 항목명 | 의미 | 예시 | 출현 |
|---|---|---|---|---|
| bidNtceNo | 입찰공고번호 | R+년도2+단계(BK=입찰)+순번8 | `R26BK01736088` | 전부 |
| bidNtceOrd | 입찰공고차수 | 재공고·재입찰 때 증가 | `000` | 전부 |
| untyNtceNo | 통합공고번호 | BM 계열 번호 | `R26BM00967396` | 전부 |
| refNo | 참조번호 | 기관 자체 공고번호 | `대전광역시 공고 제2026-1616호` | 94~97% |
| orderPlanUntyNo | 발주계획통합번호 | DD 계열 번호 | `R26DD20875280` | 1004/924/617 |
| bfSpecRgstNo | 사전규격등록번호 | 연결된 사전규격 번호. **사전규격 공고와 이어 붙이는 키** | `R26BD00272239` | 783/784/24 |
| befBidBbancNo | 이전입찰공고번호 | 재공고일 때 이전 공고 | | 229/239/25 |
| bidNtceNm | 입찰공고명 | 사업명·공사명 | | 전부 |
| ntceKindNm | 공고종류명 | 등록/변경/**취소**/재공고 | `등록공고` | 전부 |
| reNtceYn | 재공고여부 | Y/N | | 전부 |
| rgstTyNm | 등록유형명 | 조달청·나라장터 자체 공고 / 기타 공고 | | 전부 |
| chgNtceRsn | 변경공고사유 | 변경·취소 사유 | `[취소공고] …` | 172/120/109 |
| chgDt | 변경일시 | | | 드묾 |
| rgstDt / bidNtceDt | 등록일시 / 입찰공고일시 | 예시에서는 같은 값이었다(전수 비교는 안 함) | `2026-09-22 06:55:30` | 전부 |
| bidNtceDtlUrl | 입찰공고상세URL | 나라장터 상세 화면 | `https://www.g2b.go.kr/link/PNPE027_01/…` | 전부 |
| bidNtceUrl | 입찰공고URL | 용역·물품에서는 상세URL과 100% 같음 | | 1310/1108/**0** |
| stdNtceDocUrl | 표준공고서URL | 표준공고문 파일 | | 86~90% |
| ntceSpecDocUrl1~10 / ntceSpecFileNm1~10 | 공고규격서URL·파일명 | 첨부 쌍(번호가 커질수록 드묾) | `02. 계약체결기준.hwp` | 1번 ~91% |
| intrbidYn | 국제입찰여부 | WTO/FTA 대상 | `N` | 거의 전부 |

**기관·담당자**
| 키 | 항목명 | 의미 | 예시 | 출현 |
|---|---|---|---|---|
| ntceInsttCd / ntceInsttNm | 공고기관코드/명 | 공고를 **내는** 기관 → organization | `경상북도` | 전부 |
| dminsttCd / dminsttNm | 수요기관코드/명 | 계약을 의뢰한 **실제 수요기관** → region 원천. 공고기관과 같은 비율 89/96/98% | `경상북도 남부건설사업소` | 전부 |
| ntceInsttOfclNm | 공고기관담당자명 | | | 전부 |
| ntceInsttOfclTelNo | 공고기관담당자전화번호 | | `054-880-2930` | 1290/1065/926 |
| ntceInsttOfclEmailAdrs | 공고기관담당자이메일 | **용역은 항상 비어 있음** | | **0**/1108/942 |
| dminsttOfclEmailAdrs | 수요기관담당자이메일 | 명세에는 있으나 **실측에서 한 번도 값이 없음** | | 0/0/0 |
| exctvNm | 집행관명 | 95~99%가 담당자명과 같음 | | 전부 |
| crdtrNm | 채권자명 | 입찰보증금 보증채권자 | `대전광역시장` | 거의 전부 |

**일정** — 형식은 `YYYY-MM-DD HH:MM:SS`(예외 표시)
| 키 | 항목명 | 의미 | 출현 |
|---|---|---|---|
| bidQlfctRgstDt | 입찰참가자격등록마감일시 | 자격 등록 마감. **실측은 초 없이 16자**(`2026-10-12 18:00`) | 1146/1006/933 |
| bidBeginDt / bidClseDt | 입찰개시/마감일시 | 입찰서 제출 기간. 마감 → end_date | 1149/1006/933 |
| opengDt | 개찰일시 | 개찰을 **할 수 있는** 시작 시각(실제 개찰 시각이 아님) | 전부 |
| rbidOpengDt | 재입찰개찰일시 | 재입찰이 아닌 공고에도 채워져 옴 | 전부 |
| opengPlce | 개찰장소 | `국가종합전자조달시스템(나라장터)` | 93~97% |
| dcmtgOprtnDt / dcmtgOprtnPlce | 설명회 일시/장소 | 현장·과업 설명회 | 드묾 |
| cmmnSpldmdAgrmntClseDt | 공동수급협정마감일시 | | 349/44/59 |
| bidWgrnteeRcptClseDt | 입찰보증서접수마감일시 | | 0/262/49 |
| pqApplDocRcptDt | PQ신청서접수일시 | | 47/0/4 |
| arsltReqstdocRcptDt (용역) · arsltApplDocRcptDt (물품·공사) | 실적신청서접수일시 | **같은 뜻인데 업무별로 키 이름이 다르다** | 18 / 14·13 |
| dlvrDaynum | 납품일수 (물품) | `180` | 0/580/0 |

**금액** — 문자열로 온다(`"456714000"`). 단위는 원
| 키 | 항목명 | 의미 | 출현 |
|---|---|---|---|
| asignBdgtAmt | 배정예산금액 (용역·물품) | 배정된 예산 또는 설계금액 → budget | 1307/1108/**태그 없음** |
| bdgtAmt | 예산금액 (공사) | 공사의 예산. **budget에 쓰이지 않는다** | 공사 942 |
| presmptPrce | 추정가격 | 예정가격 결정 전 금액으로, **부가세·조달수수료를 뺀 값**. 국제입찰 대상 판단 기준 | 1307/1108/942 |
| VAT | 부가가치세 | 추정가격+VAT = 예산인 비율: 용역 91%·물품 95%·공사 56% | 1307/1108/942 |
| indutyVAT | 주공종부가가치세 | | 공사 92 |
| govsplyAmt | 관급금액 (공사) | | 공사 857 |
| contrctrcnstrtnGovsplyMtrlAmt / govcnstrtnGovsplyMtrlAmt | 도급자설치 / 관급자설치 관급자재금액 | | 공사 ~858 |
| mainCnsttyCnstwkPrearngAmt / mainCnsttyPresmptPrce | 주공종 공사예정금액 / 추정가격 | 적격심사용 | 공사 ~294 |
| bidPrtcptFee | 입찰참가수수료 | | 918/1103/0 |
| prdctUprc | 물품단가 | | 물품 1101 |
- **기초금액(`bssamt`)은 이 API에 없다.** 별도 오퍼레이션(`…BsisAmount`)이 필요하고 현재 수집하지 않는다.

**계약·낙찰 방식, 평가**
| 키 | 항목명 | 의미 | 예시 | 출현 |
|---|---|---|---|---|
| bidMethdNm | 입찰방식명 | 전자입찰/직찰/직찰·우편 등 | `전자입찰` | 전부 |
| cntrctCnclsMthdNm | 계약체결방법명 | 일반/제한/지명경쟁, 수의계약 | `제한경쟁` | 전부 |
| sucsfbidMthdCd / sucsfbidMthdNm | 낙찰방법 코드/명 | 낙찰자 결정 방법과 세부기준 | `적격심사제-추정가격이 4억원 미만…` | 전부 |
| sucsfbidMthdAppStd | 낙찰방법적용기준 | | `조달청 물품구매적격심사 세부기준` | 182/244/271 |
| sucsfbidLwltRate | 낙찰하한율(%) | | `87.745` | 570/421/848 |
| prearngPrceDcsnMthdNm | 예정가격결정방법명 | 복수예가/단일예가/비예가 | | 전부 |
| totPrdprcNum / drwtPrdprcNum | 총예가건수 / 추첨예가건수 | | `15` / `4` | 818/1012/940 |
| rsrvtnPrceReMkngMthdNm | 예비가격재작성방법명 | | | 527/550/772 |
| rbidPermsnYn | 재입찰허용여부 | | | 804/1027/942 |
| techAbltEvlRt / bidPrceEvlRt | 기술능력 / 입찰가격 평가비율 | 협상에 의한 계약 | `90` / `10` | 536/81/태그 없음 |
| indstrytyEvlRt | 업종평가비율 (공사) | | `100` | 공사 199 |
| aplBssCntnts | 적용기준내용 (공사) | 적격심사 기준 주체 | `행자부` | 공사 942 |
| dsgntCmptYn / arsltCmptYn | 지명경쟁 / 실적경쟁 여부 | | | 전부 / 용역·공사 |
| pqEvalYn / pqApplDocRcptMthdNm | PQ심사여부 / 신청서 접수방법 | | | 101/0/368 |
| tpEvalYn | TP심사여부 (용역) | 명세의 설명 칸이 "물품규격명"으로 **잘못 적혀 있다**. 항목명 기준으로 해석 | | 용역 182 |
| arsltApplDocRcptMthdNm | 실적신청서접수방법명 | | `수기` | 395/14/13 |
| dtlsBidYn | 내역입찰여부 | 투찰 때 내역서 첨부 | | 공사 942 |
| infoBizYn | 정보화사업여부 | | | 64/103/– |
| ppswGnrlSrvceYn / srvceDivNm | 조달청일반용역여부 / 용역구분명 (용역) | 일반·기술용역 | | 용역 전부 |

**참가 제한·공동수급·지역**
| 키 | 항목명 | 의미 | 출현 |
|---|---|---|---|
| bidPrtcptLmtYn / indstrytyLmtYn / prdctClsfcLmtYn | 입찰참가·업종·물품분류 제한여부 | | 업무별 상이 |
| mnfctYn | 제조여부 (물품) | Y면 제조업체만 투찰 가능 | 물품 1103 |
| cmmnSpldmdMethdCd / cmmnSpldmdMethdNm | 공동수급방식 코드/명 | 공500001 공동이행 … 공500012 해당없음 | 명 전부 |
| cmmnSpldmdAgrmntRcptdocMethd | 공동수급협정서접수방식 | 전자/수기/없음 | 전부 |
| cmmnSpldmdCorpRgnLmtYn | 공동수급업체지역제한여부 | | 전부 |
| cmmnSpldmdCnum | 공동수급업체수 (공사) | 숫자가 아니라 문구로 옴(`공고서에 의함`) | 공사 942 |
| rgnLmtBidLocplcJdgmBssCd / …Nm | 지역제한입찰 소재지 판단기준 | `본사또는참여지사소재지` | 267/70/503 |
| rgnDutyJntcontrctYn / rgnDutyJntcontrctRt | 지역의무공동도급 여부 / 비율(%) | | 공사 942 / 20 |
| jntcontrctDutyRgnNm1~3 | 공동도급의무지역명 | | 공사 드묾 |
| incntvRgnNm1~4 | 가산지역명 (공사) | 적격심사 가산점 지역 | 공사 13 |
| cnstrtsiteRgnNm | 공사현장지역명 (공사) | **실제 공사 지역**(`경상북도 포항시 남구`). region에 쓰이지 않는다 | 공사 942 |

**분류·품목·공종**
| 키 | 항목명 | 의미 | 출현 | 근거 |
|---|---|---|---|---|
| pubPrcrmntLrgClsfcNm / pubPrcrmntMidClsfcNm | 공공조달 대/중분류명 | 사업분류체계. 명세 표기는 `…LrgclsfcNm`(소문자 c) — **실제 키는 대문자 C** | 용역 1307 | 명세(표기 다름) |
| pubPrcrmntClsfcNo | 공공조달분류번호 | | 용역 1307 | 명세 |
| pubPrcrmntClsfcNm | (명세에 없음) | 분류번호에 해당하는 최하위 분류명으로 보임 | 용역 1307 | **추정** |
| purchsObjPrdctList | 구매대상물품목록 | `[분류번호^세부품명번호^세부품명],…` | 77/1108/– | 명세 |
| dtilPrdctClsfcNo / dtilPrdctClsfcNoNm | 세부품명번호 / 세부품명 (물품) | | 물품 1101 | 명세 |
| prdctSpecNm / prdctQty / prdctUnit | 물품 규격명·수량·단위 | | 물품 1101 | 명세 |
| dlvryCndtnNm | 인도조건명 | | 물품 510 | 명세 |
| mainCnsttyNm | 주공종명 (공사) | `전기공사업` | 공사 289 | 명세 |
| subsiCnsttyNm1~9 / subsiCnsttyIndstrytyEvlRt1~9 | 부대공종명 / 업종평가비율 | | 공사 드묾 | 명세 |
| cnsttyAccotShreRateList | 공종별지분율목록 | `[업종^비율],…` | 공사 94 | 명세 |
| cnstrtnAbltyEvlAmtList | 시공능력평가금액목록 | `[그룹^면허^코드^금액],…` | 공사 3 | 명세 |
| ciblAplYn / mtltyAdvcPsblYn / mtltyAdvcPsblYnCnstwkNm / indstrytyMfrcFldEvlYn | 건설산업법 적용 / 상호시장진출 / 적용 공사명 / 주력분야평가 | | 공사 | 명세 |

**명세에는 있지만 이 표본에서 값이 한 번도 없던 키**(extra에 나타나지 않음): `dminsttOfclEmailAdrs`, `bidPrtcptFeePaymntYn`, `bidGrntymnyPaymntYn`, `brffcBidprcPermsnYn`, `ntceDscrptYn`, `dlvrTmlmtDt`, `tpEvalApplMthdNm`, `tpEvalApplClseDt`, `sptDscrptDocUrl1~5`.

### D. 주의점·표본
- 표본: `collect(days=3)` 2026-09-25, 조회창 09-22~09-25. 용역 1,310·물품 1,108·공사 942건, errors 0. 전체 태그 목록은 1페이지 100건씩(용역 113·물품 101·공사 143태그)으로 뽑았다. 09-24 이후는 거의 0건이었다(추석 연휴로 추정). **days=1 표본은 쓰지 말 것.**
- 헷갈리는 쌍: 배정예산(`asignBdgtAmt`, 용역·물품)과 예산(`bdgtAmt`, 공사)은 같은 역할을 하는 다른 키다. 추정가격은 부가세를 뺀 값이다. 공고기관 ≠ 수요기관.
- 재현: `scripts/_tmp/nara_extra_keys.py 3`. 명세 원문 덤프는 `scripts/_tmp/guide_bidpublic.txt`(1279행~ 용역 응답 표). 명세 다운로드: data.go.kr 15129394 참고문서.

---

## 3. 나라장터 사전규격 (`collect_pre_specs`, 출처 `nara_prespec`)

### A. 개요
- 조달청_나라장터 사전규격정보서비스 `HrcspSsstndrdInfoService` — data.go.kr **15129437**. 인증 인자는 대문자 `ServiceKey`
- 오퍼레이션: 물품 `getPublicPrcureThngInfoThng` · 용역 `…Servc` · 공사 `…Cnstwk`. 조회 기준 `inqryDiv=1`(등록일시)
- 명세 `조달청_OpenAPI참고자료_나라장터_사전규격정보서비스_1.0.docx`(2026.08 차세대 현행화)
- BidWatch 사용처: `tasks/collect_api.py`(나라장터 수집 뒤 연쇄 수집) → `/api/notices/pre-specs` → 화면 `/pre-notices`

### B. 표준 필드 ← 원문
bid_no `사전규격-{업무}-{bfSpecRgstNo|refNo}` · title=category=`prdctClsfcNoNm` · url은 `https://www.g2b.go.kr` 고정, detail_url `""`(응답에 상세 링크 필드가 없다) ·
attachments = `specDocFileUrl1~5`(이름 필드가 없어서 `규격서{i}`로 붙인다) · 나머지는 §1 참고.

### C. extra 키 사전 — 근거 전부 `명세`, N=222 (용역 100·물품 100·공사 22)
| 키 | 항목명 | 의미 | 예시 | 출현 |
|---|---|---|---|---|
| bfSpecRgstNo | 사전규격등록번호 | 식별자(BD 계열). 본 공고의 `bfSpecRgstNo`와 연결된다 | `R26BD00277675` | 222 |
| refNo | 참조번호 | 기관 내부 문서번호(형식 자유) | `신속통합기획과-8321` | 222 |
| bsnsDivNm | 업무구분명 | 일반용역/기술용역/물품/공사 | | 222 |
| prdctClsfcNoNm | 품명 | 사업명 또는 물품분류명 | | 222 |
| orderInsttNm | 발주기관명 | | `한국항공우주연구원` | 222 |
| rlDminsttNm | 실수요기관명 | | | 222 |
| asignBdgtAmt | 배정예산금액(원) | | `811800000` | 222 |
| rcptDt | 접수일시 | → start_date | | 222 |
| opninRgstClseDt | 의견등록마감일시 | → end_date | `2026-09-28 23:59:00` | 222 |
| ofclNm / ofclTelNo | 담당자명 / 전화번호 | | | 182 / 128 |
| swBizObjYn | SW사업대상여부 | | `N` | 222 |
| dlvrTmlmtDt | 납품기한일시 | | | 103 |
| dlvrDaynum | 납품일수 | `0`이 대다수. 0의 의미는 명세에 없다 | | 204 |
| specDocFileUrl1~5 | 규격문서파일URL | | | 176/74/29/10/5 |
| prdctDtlList | 물품상세목록 | `[순번^세부품명번호^세부품명],…` (물품·용역) | `[1^8111179901^정보인프라구축서비스]` | 109 |
| bidNtceNoList | 입찰공고번호목록 | 이후 나온 본 공고 번호. 쉼표로 구분 | `R26BK01742848` | 11 |
| rgstDt / chgDt | 등록일시 / 변경일시 | 등록일시가 조회 기준 | | 222 / 183 |

### D. 주의점·표본
- 표본: 2026-09-23~25 등록분 1페이지씩(공사는 전수). `bidNtceNoList`는 5%만 채워져 있다. 최근 등록분이라 아직 본 공고가 나지 않은 탓일 수 있다.
- 재현: `scripts/_tmp/nara_ext_extra_survey.py 100 2`. 명세 덤프는 `scripts/_tmp/guide_prespec.txt`.

---

## 4. 나라장터 낙찰·계약 (`collect_awards`·`collect_contracts`) — BidWatch 미사용

`backend/app`·`frontend/src` 어디서도 부르지 않는다. 쓰게 되면 아래 요약을 출발점으로 삼는다(명세·실측 상세는 `scripts/_tmp/guide_award.txt`·`guide_contract.txt`와 `nara_ext_extra_survey.json`).

- **낙찰** — `ScsbidInfoService` data.go.kr **15129397**. extra 19키, 전부 명세로 확인. 핵심: `bidwinnrNm`·`bidwinnrBizno`(최종낙찰업체), `sucsfbidAmt`(최종낙찰금액), `sucsfbidRate`(낙찰금액÷예정가격×100), `prtcptCnum`(참가업체수), `rlOpengDt`(실개찰일시), `fnlSucsfDate`.
  **조회 기준이 공고게시일시**라서 `days=N`은 "최근 N일 낙찰"이 아니라 "최근 N일에 게시된 공고 중 이미 낙찰된 것"이다(표본 27건이 모두 참가 1곳짜리였다).
- **계약** — `CntrctInfoService` data.go.kr **15129427**. extra 45키, 전부 명세로 확인(공공조달 대·중분류명의 표기는 입찰공고와 같은 문제). 핵심: `untyCntrctNo`(통합계약번호), `dcsnCntrctNo`(확정계약번호. **끝 2자리가 수정차수**라 계약이 변경되면 새 bid_no가 된다), `thtmCntrctAmt`(이번 차수 금액)와 `totCntrctAmt`(장기계속 전체 금액), `corpList`·`dminsttList`(`^`로 구분한 목록 문자열), `cntrctPrd`(**자유 형식 문장**).
  `cntrctCnclsDate`(체결일자)와 `cntrctDate`(계약일자)의 차이는 명세에 설명이 없다. 공사 전용 키(`cnstwkNm`·`cbgnDate` 등)는 결함 때문에 현재 도달하지 않는다(부록 A-1).

---

## 5. K-Startup (`KstartupCollector`)

### A. 개요
- 창업진흥원_K-Startup 조회서비스 — data.go.kr **15125364**. 엔드포인트 `https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01`(odcloud JSON)
- 명세: 서비스설계서 v2.0 docx(참고문서 zip) + data.go.kr 내장 swagger. **둘이 서로 어긋나는 곳이 있다**(D 참고)
- 요청은 `perPage=100`에 기본으로 진행중만(`cond[rcrt_prgs_yn::EQ]=Y`) 받는다.

### B. 표준 필드 ← 원문
bid_no `KSTARTUP-{pbanc_sn}` · title `biz_pbanc_nm`(엔티티를 풀고, 태그는 남음) · url `detl_pg_url` → `biz_aply_url` → `biz_gdnc_url` · detail_url `detl_pg_url` ·
content = `pbanc_ctnt`를 텍스트화한 뒤 **500자에서 자름** · 나머지는 §1 참고.

### C. extra 키 사전 — N=124
| 키 | 항목명 | 의미 | 형식·예시 | 출현 | 근거 |
|---|---|---|---|---|---|
| pbanc_sn | 공고일련번호 | 공고 ID. 명세는 string, **실측은 int** | `179345` | 124 | 명세 |
| biz_pbanc_nm | 지원 사업 공고명 | 제목 | 엔티티가 섞임 | 124 | 명세 |
| intg_pbanc_yn / intg_pbanc_biz_nm | 통합공고 여부 / 통합공고 사업명 | 상위 통합공고 | `창업보육센터 지원`(엔티티 20건) | 124 | 명세 |
| pbanc_ctnt | 공고 내용 | 본문 요약. 표본에서 태그는 0건 | 32~662자 | 124 | 명세 |
| supt_biz_clsfc | 지원 분야 | 8종: 사업화·시설ㆍ공간ㆍ보육·멘토링ㆍ컨설팅ㆍ교육·행사ㆍ네트워크·창업교육·판로ㆍ해외진출·글로벌·인력 | | 124 | 명세 |
| supt_regin | 지역명 | 약칭: `전국` 76, `서울`, `전남광주`… | | 124 | 명세 |
| pbanc_rcpt_bgng_dt / pbanc_rcpt_end_dt | 공고 접수 시작/종료 일시 | 실측 `yyyyMMdd` 8자리 | `20260923` | 124 | 명세 |
| rcrt_prgs_yn | 모집진행여부 | Y 모집중 / N 마감 → status | | 124 | 명세 |
| pbanc_ntrp_nm | 창업 지원 기관명 | 공고한 기관 → organization | `경희창업보육센터` | 124 | 명세 |
| sprv_inst | 주관 기관 | **기관명이 아니라 유형**: 민간·공공기관·교육기관·지자체 | | 124 | 명세 |
| biz_prch_dprt_nm | 사업 담당자 부서명 | | | 124 | 명세 |
| prch_cnpl_no | 담당자 연락처 | 하이픈 없는 숫자 | `0262129330` | 124 | 명세 |
| detl_pg_url | 상세페이지URL | k-startup 공고 상세(`&amp;`가 엔티티로 옴) | | 124 | 명세(설계서 기준, swagger 설명은 틀림) |
| biz_gdnc_url | 사업 안내 URL | 외부 안내. 스킴이 없는 값이 섞임 | `startup.khu.ac.kr` | 92 | 명세 |
| aply_trgt | 신청 대상 | 유형 목록(쉼표): 일반인·대학생·일반기업… | | 124 | 명세 |
| aply_trgt_ctnt | 신청 대상 내용 | 자격 서술 | | 124 | 명세 |
| aply_excl_trgt_ctnt | 신청 제외 대상 내용 | | | 47 | 명세(설계서 표의 철자 `exclt`는 오타) |
| biz_enyy | 창업 기간 | **업력 구간**(사업 연도가 아님). 쉼표로 구분 | `예비창업자,1년미만,…` | 124 | 명세 |
| biz_trgt_age | 대상 연령 | 쉼표로 구분 | `만 20세 미만,…` | 124 | 명세 |
| aply_mthd_onli_rcpt_istc | 온라인 접수 설명 | 대부분 URL | | 84 | 명세 |
| aply_mthd_eml_rcpt_istc | 이메일 접수 설명 | | | 41 | 명세(설계서만) |
| aply_mthd_vst_rcpt_istc | 방문 접수 설명 | 주소 | | 9 | 명세 |
| aply_mthd_etc_istc | 기타 신청 방법 | **HTML이 들어옴(onClick 스크립트 포함)** — 표시 전에 반드시 태그 제거 | | 2 | 명세 |
| id | (명세에 없음) | 결과 목록 순번으로 보임. **공고 속성이 아님** — 화면에 쓰지 말 것 | int | 124 | **추정** |
| aply_mthd_fax_rcpt_istc · aply_mthd_pssr_rcpt_istc · prfn_matr · biz_aply_url | 팩스·우편 접수 / 우대 사항 / (공고 상세 URL?) | 표본에서 항상 null | | 0 | 명세 |

**`fetch_detail` 키**(BidWatch `services/notice.py`가 `content`가 빌 때만 extra에 병합한다): 새 정보는 없다. 위 원문을 영어 이름으로 바꾼 사본이다 —
`content`←pbanc_ctnt(자르지 않음) · `target`←aply_trgt_ctnt · `target_age`←biz_trgt_age · `biz_year`←biz_enyy · `excl_target`←aply_excl_trgt_ctnt ·
`apply_method`←onli→vst→etc 중 첫 값 · `department`←biz_prch_dprt_nm · `contact`←prch_cnpl_no · `biz_name`←intg_pbanc_biz_nm · `apply_url`←biz_aply_url(실측 0).
`pbanc_ctnt`가 124건 모두 채워져 있어서 병합은 거의 일어나지 않을 것으로 본다(추정).

### D. 주의점·표본
- 명세끼리 어긋나는 곳: `detl_pg_url` 설명(설계서 "상세페이지URL" vs swagger "사업 신청 URL" — 실측상 설계서가 맞다), 설계서 설명 칸에서 `biz_gdnc_url`과 `prch_cnpl_no`가 서로 바뀌어 있음, 날짜 형식(설계서 `yyyy-MM-dd HH:mm:ss` vs 실측 `yyyyMMdd`).
- 표본: 2026-09-25, 진행중 230건 중 100건 + 전체 30,168건 중 최신 100건 → 중복 제거 후 124건.
- 재현: `scripts/_tmp/fielddict_ks_biz.py`. 명세 덤프는 `scripts/_tmp/fd_ks_guide/dump_0.docx.txt` 86~153행.

---

## 6. 기업마당 (`BizinfoCollector`)

### A. 개요
- 기업마당 지원사업정보 API — `https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do`(인증 `crtfcKey`, data.go.kr 한도와 무관). 응답은 `{"jsonArray":[…]}`
- 명세: https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi (버전 표기 없음, 2026-09-25 조회)

### B. 표준 필드 ← 원문
bid_no `BIZINFO-{pblancId}` · title `pblancNm` · url=detail_url `pblancUrl` · content = `bsnsSumryCn`을 텍스트화(자르지 않음) ·
attachments = (`printFileNm`,`printFlpthNm`) + (`fileNm`,`flpthNm`) · 수집 기준일 컷은 `creatPnttm`. 나머지는 §1 참고.

### C. extra 키 사전 — N=100
| 키 | 항목명 | 의미 | 형식·예시 | 출현 | 근거 |
|---|---|---|---|---|---|
| pblancId | 공고ID | | `PBLN_000000000126771` | 100 | 명세 |
| pblancNm | 공고명 | | | 100 | 명세 |
| pblancUrl | 공고URL | 기업마당 상세 | | 100 | 명세 |
| jrsdInsttNm | 소관기관명 | 소관 부처·광역지자체(`중소벤처기업부`, `경상북도`) → region 원천 | | 100 | 명세 |
| excInsttNm | 수행기관명 | 실제 수행 기관(`기초자치단체`·`직접수행` 같은 유형값 섞임) → organization | | 100 | 명세 |
| bsnsSumryCn | 사업개요내용 | 본문. **HTML 100/100** | 201~904자 | 100 | 명세 |
| pldirSportRealmLclasCodeNm | 지원분야 대분류 | 경영·기술·수출·내수·인력·금융·창업 → category | | 100 | 명세 |
| pldirSportRealmMlsfcCodeNm | (명세에 없음) | 지원분야 **중분류**로 보임 | `기술사업화/이전/지도` | 100 | **추정** |
| trgetNm | 지원대상 | 중소기업·소상공인·창업벤처… | | 100 | 명세 |
| reqstBeginEndDe | 신청기간 | `YYYY-MM-DD ~ YYYY-MM-DD` 82건, **자유 문장 18건**(`예산 소진시까지` 등) | | 100 | 명세(형식은 명세 예시와 다름) |
| reqstMthPapersCn | 사업신청방법 | `\r\n` 포함 평문 | | 100 | 명세 |
| refrncNm | 문의처 | 담당·전화 | | 100 | 명세 |
| rceptEngnHmpgUrl | 사업신청URL | 외부 접수 사이트 | | 40 | 명세 |
| hashtags | 해시태그 | 쉼표로 구분(분야·지역·연도·기관). 명세 표기는 `hashTags` — **실제 키는 소문자** | `내수,전북,2026,…` | 100 | 명세(표기 다름) |
| printFileNm / printFlpthNm | 본문출력 파일명 / 경로 | 공고문 파일 | | 100 | 명세 |
| fileNm / flpthNm | 첨부파일명 / 경로 | | | 86 | 명세 |
| creatPnttm | 등록일자 | `yyyy-MM-dd HH:mm:ss` | | 100 | 명세 |
| updtPnttm | (명세에 없음) | 수정 시각으로 보임. 같은 값이 여러 건에 반복됨(일괄 갱신?) | | 100 | **추정** |
| inqireCo | 조회수 | int. **수집할 때마다 바뀜** | | 100 | 명세 |
| totCnt | 전체건수 | 목록 전체 건수(모든 항목에 같은 값). **공고 속성이 아님** | int | 100 | 명세 |

### D. 주의점·표본
- 명세의 RSS용 별칭 키(`title`·`link`·`seq`·`pubDate`…)는 JSON 응답에 **하나도 없다**. `fetch_detail`은 없다.
- 표본: 2026-09-25 pageIndex=1, 100건(전체 1,523건). 재현: `scripts/_tmp/fielddict_ks_biz.py`, 명세 `scripts/_tmp/fd_bz_apidetail.html` table 2.

---

## 7. 중소벤처기업부 사업공고 (`SmesCollector`)

### A. 개요
- 중소벤처기업부_사업공고 — data.go.kr **15113297**(2026-09-16 수정). `http://apis.data.go.kr/1421000/mssBizService_v2/getbizList_v2`(XML)
- 요청 날짜 파라미터는 **공고 등록일 기준**이다(신청일 기준이 아님, 명세 원문). 개발계정은 **100회/일**.
- 명세: data.go.kr 페이지 내장 swagger. 키 11개가 명세와 실측에서 완전히 일치한다.

### B. 표준 필드 ← 원문
bid_no `MSS-{itemId}` · title `title`(HTML 제거) · url=detail_url `viewUrl` · content = `dataContents`를 텍스트화한 뒤 **500자에서 자름** ·
attachments = `fileName[i]`+`fileUrl[i]` 짝 · budget은 원천 태그(`suptScale`)가 실제로 없어서 항상 None. 나머지는 §1 참고.

### C. extra 키 사전 — 근거 전부 `명세`. N=17(수집기) / 88(원문)
| 키 | 항목명 | 의미 | 형식·예시 | 출현(88건) |
|---|---|---|---|---|
| itemId | 게시물 키 | viewUrl의 `bcIdx`와 같음 | `1071373` | 88 |
| title | 게시물 제목 | | | 88 |
| dataContents | 게시물 내용 | **HTML 원문**(78/88) | 36~1504자 | 88 |
| applicationStartDate / applicationEndDate | 신청 시작/마감일 | `YYYY-MM-DD` | | 71 / 67 |
| writerName / writerPosition / writerPhone / writerEmail | 담당자 이름·부서·전화·이메일 | 부서명 → category | `지역혁신정책과` | ~88 |
| viewUrl | 상세페이지 URL | mss.go.kr 게시판 | | 88 |
| fileName / fileUrl | 첨부 원본파일명 / 다운로드 URL | **파일 1개면 str, 2개 이상이면 list** — 둘 다 처리할 것 | | 88 |

### D. 표본·재현
2026-09-25, 수집기 `days=30` 17건 + 원문 06-01~09-25 88건(전수). `scripts/_tmp/extra_keys_smes_sub24.py 30`, `raw_smes_sub24.py smes 2026-06-01 2026-09-25`.

---

## 8. 보조금24 (`Subsidy24Collector`)

### A. 개요
- 행정안전부_대한민국 공공서비스(혜택) 정보 — data.go.kr **15113968**. `https://api.odcloud.kr/api/gov24/v3/serviceList`
- 수집 필터는 `cond[수정일시::GTE]=YYYYMMDDHHMMSS`(문자열 비교)이다. `only_business=True`면 기업 키워드로 한 번 더 거른다.
- 명세: swagger `https://infuser.odcloud.kr/api/stages/44436/api-docs`. **키 이름·타입은 있지만 설명(description)이 전부 비어 있다.**
  그래서 아래 의미는 대부분 **추정**이다. 코드값 공식 목록도 찾지 못했다(관측값만 적음).

### B. 표준 필드 ← 원문
bid_no `GOV24-{서비스ID}` · title `서비스명` · url `상세조회URL`(없으면 gov.kr 주소를 조립) · content = `서비스목적요약` + 줄바꿈 + `지원내용`(자르지 않음) · 나머지는 §1 참고.

### C. extra 키 사전 — 키가 한글이다. A=수집기 100건 / B=원문 첫 페이지 100건
| 키 | 의미 | 형식·예시 | 출현 A/B | 근거 |
|---|---|---|---|---|
| 서비스ID | 공공서비스 고유 식별자 | 12자리 `127000000022` | 100/100 | 명세(같은 API 다른 모델) |
| 서비스명 | 서비스(혜택) 이름 | | 100/100 | 추정 |
| 서비스목적요약 | 목적 한 줄 요약 | | 100/100 | 추정 |
| 지원유형 | 지원 형태. **`\|\|`로 여러 값** | `민원\|\|현금(감면)` — 현금·현물·이용권·상담/법률지원… | 100/100 | 추정(구분자는 정부24 API 명세로 확인) |
| 지원대상 | 자격 서술 | 최대 1,713자 | 100/100 | 추정 |
| 선정기준 | 선정 기준 | `지원대상과 동일` | **27**/99 | 추정 |
| 지원내용 | 지원 내용 본문 | 최대 1,589자 | 100/100 | 추정 |
| 신청방법 | 신청 경로. `\|\|`로 여러 값 | 방문신청·온라인신청·신청불필요… | 100/100 | 추정 |
| 신청기한 | 신청 기간 안내. **날짜가 아니라 문장** | `상시신청`·`별도 공고기한내`·`2025.04.01~2026.03.31` | 100/100 | 추정 |
| 상세조회URL | 정부24 상세 페이지 | | 100/100 | 추정 |
| 소관기관코드 / 소관기관명 / 부서명 | 담당 기관·부서 | `1270000` / `법무부` / `국적과` | 100/100 | 추정 |
| 소관기관유형 | 기관 종류 | 중앙행정기관·공공기관(표본 편중) | 100/100 | 추정 |
| 사용자구분 | 수혜 대상 구분. `\|\|`로 여러 값 | 개인·법인/시설/단체·가구·소상공인 | 100/100 | 추정 |
| 서비스분야 | 분류 → category | 보육·교육·고용·창업… | 100/100 | 추정 |
| 접수기관 | 신청서를 받는 기관 | | **18**/80 | 추정 |
| 전화문의 | `기관/전화번호`. `\|\|`로 여러 값 | | 100/100 | 추정 |
| 조회수 | 정부24 조회수. **int, 수집할 때마다 바뀜** | | 100/100 | 명세(타입) |
| 등록일시 / 수정일시 | 최초 등록 / 마지막 수정 | `YYYYMMDDHHMMSS` | 100/100 | 추정 |

### D. 표본·재현
2026-09-25, A = `수정일시 ≥ 30일 전` 1,378건 중 첫 100건, B = 조건 없이 10,940건 중 첫 100건. 출현율이 표본마다 크게 다르다(선정기준 27 vs 99).
재현: `scripts/_tmp/extra_keys_smes_sub24.py 30`, `raw_smes_sub24.py sub24 1`, `sub24_swagger_dump.py`.

---

## 9. 알리오 (`AlioCollector`)

### A. 개요
- 알리오 입찰공고 화면이 부르는 내부 JSON이다. `https://alio.go.kr/occasional/findBidList.json?type=title&word=&pageNo=N&area=`(인증 없음, 페이지당 10건)
- **공식 명세가 없다**(알리오 오픈API 메뉴에 입찰은 없음). 의미는 화면 라벨·스크립트와 값을 대조해 확인했다.
- 상세 URL `https://alio.go.kr/occasional/bidDtl.do?seq={seq}`. 상세 JSON(`findBidDtl.json`)은 수집기가 부르지 않는다. 원문 URL·첨부·금액은 그쪽에만 있다.

### B. 표준 필드 ← 원문
bid_no `ALIO-{seq}` · title `rtitle`(공백 정규화) · organization `pname` · start_date `bdate` · end_date `bidInfoEndDt` · content·budget·region·category·attachments는 비어 있음.

### C. extra 키 사전 — N=440
| 키 | 화면 라벨 | 의미 | 형식·예시 | 출현 | 근거 |
|---|---|---|---|---|---|
| seq | (표시 없음) | 알리오 게시물 번호. extra에서는 int, 상세 JSON에서는 str | `3580351` | 440 | 화면(상세 링크 인자) |
| rtitle | 제목 | 원문 제목 | | 440 | 화면 |
| pname | 기관명 | 공시한 공공기관 | `국립공원공단` | 440 | 화면 |
| bdate | **등록일** | 알리오에 등록된 날짜. 원 조달시스템의 공고일과 같은지는 미검증 | `2026.09.23` | 440 | 화면 |
| bidInfoEndDt | 입찰종료일 | 입찰 마감(날짜만) | `2026.09.30` | 432 | 화면 |
| cdNo | (표시 없음) | 수시공시 서식 코드. `B1030`=입찰공고 | 440건 모두 `B1030` | 440 | 값은 화면으로 확인, 키 뜻은 추정 |
| rnum | (표시 없음) | 목록 순번. **새 공고가 오면 값이 밀린다 — 공고 속성이 아님** | int | 440 | 추정 |
| logo / imgPathNo | (이미지) | 기관 로고 파일명 / 로고 경로 번호 | `국립공원공단 ci.jpg` | 420 | 화면(`alioUtils.js getImgPath`) |

### D. 표본·재현
2026-09-25 `collect(days=2)` 440건 46페이지, errors 0. bdate는 09-23에 몰려 있었다(등록이 하루 이상 늦게 반영되는 것으로 보임, 1회 관찰).
재현: `scripts/_tmp/fielddict_alio.py 2`.

---

## 10. URL 출처 (`GenericScraper`)

- **extra는 없다(항상 None).** v1.2.5의 "원문 전부" 원칙 적용 범위 밖이다.
- source = organization = `config.name`(AI가 만든 사이트 표시명) · title = `title_selector` 텍스트 · start_date = `date_selector` 칸(기간이면 시작일) ·
  end_date 없음 · status는 **게시일로 판정** · url·detail_url = 제목 링크 · bid_no = `SCR-{source_key}-{md5(title+url)[:10]}`(제목이 바뀌면 다른 공고가 된다).
- start_date가 무슨 날짜인지(등록일·공고일·접수기간)는 사이트와 AI 설정에 따라 다르다. 코드는 이를 모른다.

---

## 부록 A. bid-collectors 쪽 결함·불일치 (2026-09-25 조사 중 발견 — bid-collectors에 전달할 것)

| # | 내용 | 영향 | BidWatch 영향 |
|---|---|---|---|
| 1 | 계약 공사: 응답의 제목이 `cnstwkNm`인데 수집기가 `cntrctNm`을 필수로 요구 → **공사 100/100건이 건너뛰어짐**(경고 로그만 남음) | 계약 공사 수집 0건 | 없음(미사용) |
| 2 | `parse_date`가 기간 문자열에서 **시작일**을 돌려줘서 end_date가 틀림 — 계약 `cntrctPrd`, 보조금24 `신청기한`(보조금24는 bid-collectors plan.md에 이미 보류 등록) | 접수 중인 건이 closed로 판정됨 | 보조금24(현재 화면에서 숨김) |
| 3 | 나라장터 입찰 첨부 루프가 `bidNtceFlNm{i}`/`bidNtceFlUrl{i}`를 읽는데, 명세에도 실측에도 없는 태그다 | 죽은 코드 | 없음 |
| 4 | 중소벤처 budget 원천 `suptScale`이 명세·실측 모두에 없다 | budget 항상 None | 없음 |
| 5 | 나라장터 공사 budget = 추정가격(부가세 제외). 예산 `bdgtAmt`를 쓰지 않는다 | 용역·물품과 금액 의미가 다름 | 공고 목록 예산 칸 |
| 6 | region 원천이 지역 필드가 아니다: 나라장터 = 수요기관명, 기업마당 = 소관기관(부처명), 계약 = 기관 분류. 공사현장지역(`cnstrtsiteRgnNm`)은 쓰지 않음 | 지역이 부정확함 | `normalize_region` 입력 — 지역 필터 |
| 7 | K-Startup organization의 두 번째 폴백 `sprv_inst`는 기관 유형(`민간` 등)이다 | 발주기관 칸에 유형이 표시될 수 있음 | 공고 목록·상세 |
| 8 | status `"cancelled"`를 만드는 코드가 없다 — 나라장터 취소공고(`ntceKindNm`)도 ongoing/closed (bid-collectors REQUIREMENTS 원칙 ②에 등록됨) | | 취소된 공고가 진행중으로 보임 |
| 9 | K-Startup 진행중 필터를 걸어도 종료 판정을 `totalCount`로 한다(`matchCount`가 아님) → 호출이 1회 더 나감(추정, 미실측) | 호출 낭비 | 없음 |
| 10 | 문서 파일명 오기: bid-collectors `docs/bid_collectors.md`의 `smes24.py`, `dev_reference.md`의 `mss_biz.py` → 실제는 `smes.py` | | 없음 |

## 부록 B. handover v1.2.5 §2 표 보정

- #1 `contact_email` 대체 키 `dminsttOfclEmailAdrs`는 실측에서 한 번도 값이 없었다. 용역은 `ntceInsttOfclEmailAdrs`도 비어 있어서 **용역 공고의 담당자 이메일은 표시할 수 없다.**
- #1 입찰 구분을 `bid_no` 접두사에서 자르는 방식은 맞다. extra에는 업무 구분이 없다(`srvceDivNm` 일반/기술용역은 용역에만 있다).
- #1 금액: 공사에는 `asignBdgtAmt` 태그가 없다. 공사 "배정 예산"을 보이려면 `bdgtAmt`를 읽어야 한다.
- #3 값 타입은 list(중소벤처 첨부, **1개면 str**) 외에도 int가 온다(`pbanc_sn`·`inqireCo`·`조회수`·알리오 `seq`).
- 화면에 쓰면 안 되는 키(공고 속성이 아니거나 수집할 때마다 바뀜): K-Startup `id`, 기업마당 `totCnt`·`inqireCo`, 알리오 `rnum`, 보조금24 `조회수`.
