# 🗺️ CoilForge 로드맵
> 목표: 코일 입력(Direct Coil 폼 / submittal / 스캔 PDF) → 검토용 도면 + 붙여넣기용 필드셋 + 검증·호환 리포트
> 마지막 갱신: 2026-08-06 (**[코팅·검토표면 트랙] 브라우저 교정이 산출물에 도달하지 못하던 결함 2건 — b44fdd0**:
> 성격이 같은 두 결함을 함께 닫았다 — **엔지니어가 브라우저에서 고친 값이 정작 넘겨주는 산출물에 반영되지 않던**
> 문제. ①**TR-9**: analyze는 `_engine_drawing_notes`+`_engine_drawing_dims`를 정본 기록에 태워 붙여넣기 52필드
> 표면에 올리는데 `/derive`는 그 후처리를 통째로 안 했다(**228d731 CD 회귀와 동일 계열** — analyze에만 배선된
> 후처리, 이 리포에서 두 번째). 조사해보니 **자물쇠가 둘**이었다: 백엔드는 표면을 아예 반환하지 않고
> (29키 중 부재), 프런트도 derive 응답으로 붙여넣기 표를 다시 그리지 않았다(코일 전환해도 analyze 시점 값을
> 재판독). 한쪽만 고쳤으면 **테스트는 초록인데 화면은 그대로**였을 것. 재생성엔 원본 후보가 필요한데 derive는
> 그걸 안 받으므로 **브라우저가 왕복 전달**(기존 `panel`/`sibling_coils`와 같은 관례) — 다만 John의 요구대로
> **신원은 서버가 강제**한다: 후보와 도면은 **서로 다른 경로로 도착**하므로 엉뚱한 코일 페이지에서 집어온 카드는
> tag가 어긋나 폐기된다(3단 fail-closed: 일치/불일치/tag없음, **모든 스킵이 사유를 표시** — 조용히 안 갱신된
> 패널은 "제출물에 없음"으로 읽히는데 그게 바로 이 수정이 없애려는 실패다). 후보 없으면 종전과 byte-identical.
> **plan-review 1R이 BLOCKER로 잡은 것**: derive의 `parameter_set`엔 **Tier-B 수동 override가 이미 반영**돼 있어
> 그대로 치수를 뽑으면 사람이 타이핑한 값이 `EV-ENGINE-DIM-*`/`source_type="engine_rule"`로 **엔진 산출물로 위장**
> 저장된다(analyze는 override가 없어 그 헬퍼가 사람 값을 만난 적이 없었음) → override된 키만 제외. 2R APPROVED.
> ②**코팅**: 템플릿 3장이 **코팅된 참조 도면에서 시드**돼 그 참조의 코팅명이 아트워크에 박혀 있었다 — 무코팅
> 코일에 `ELECTROFIN COATING REQUIRED`가 찍히고 HERESITE 코일엔 엉뚱한 코팅이 지시됐다. `slot.COATING_NOTE`로
> 슬롯화(+`slot_map` 등록, 안 하면 플레이스홀더가 그대로 인쇄) + 글자당 x좌표 목록 제거(ELECTROFIN의 자간으로
> 다른 코팅을 배치하던 것). **그런데 슬롯화만으론 부족했다** — 그 노트 블록은 `_strip_intruding_chrome`+viewBox
> 크롭이 이미 제거하고 있어서 **원래 화면에 안 나왔다**(템플릿만 고치고 끝냈으면 테스트 초록·화면 무변화).
> 코일 태그와 같은 방식으로 **크롭 영역 안에 직접 주입**(15px 굵게 빨강 — 제조 지시이지 메타데이터가 아님) →
> **22개 버킷 전부**에서 동작. 무코팅은 `REVIEW REQUIRED` 센티넬이 아니라 **완전 공란**(무코팅은 미결정이 아니라
> 확정 상태). **커버 라인아이템 coating 자동 인식** 신설(HGBP 어더와 동일한 스캔 창·근거 — 커버 앞은 컨설턴트
> 스펙이라 견적일 수 없음), **회사 어휘 14종에 앵커**(자유 문자열이 코팅명을 만들지 못함), 코일 자신의 상세
> 블록이 우선. 라이브 실행이 **기존 결함 1건을 드러냄**: `Coil Coating: <값>` 라벨 패턴이 줄 끝까지 삼켜
> `ELECTROFIN EVAP TEMP COATING REQUIRED`가 나왔다(값이 인쇄된 적 없어 잠자던 것) → 노트 생성 시 어휘로 정규화,
> 미인식은 버리지 않고 그대로 인쇄. **물코일 coating = John 판정 종결**: 물코일은 절대 코팅되지 않으므로 추출된
> coating은 이웃 블록에서 번져온 것 → **한 지점에서 제거**(COIL_COATING 리더가 3개라 개별 게이팅은 다음 리더가
> 구멍을 다시 엶). **수동 입력은 의도적으로 허용**(추론을 거절하는 것과 엔지니어의 명시적 결정을 거부하는 것은
> 다름 — 테스트로 고정해 다음 세션이 뒤집지 못하게). **1237 green**(+49), frozen 무접촉, 실 제출물 라이브 검증
> (EZC-0009 자동 인식·2870 무코팅 공란·2857 물코일 공란·수동 HERESITE 반영/해제·tag 가드 4분기),
> **John 브라우저 A/B 탭 눈확인 완료**. 커밋·푸시 `18ef71a..b44fdd0`(`.agents`/`.codex`/settings 격리).
> 이전: **[제출물 파싱 트랙] 2968이 드러낸 커버/상세 오독 2건 — 971e2e4**: John이
> "왜 도면에 에러가 뜨냐"고 물어온 실 제출물(2968 HTS Houston / College of the Mainland) 하나에서 결함 2개가
> 나왔고, 둘 다 원인이 **pdf_intake의 읽기 규칙**이었다. ①**HGBP 오탐** — `_package_hgbp_pages`가 124p 문서
> 전체를 훑어 p.12(Addendum 2.2 COMPRESSOR item E)의 "...liquid line, **insulated hot gas bypass line**..."에
> 걸렸다. 이건 컨설턴트 스펙의 **현장 냉매 배관 서술**이지 견적된 옵션이 아닌데, 패키지의 모든 DX 코일에
> HGBP가 찍히고 TERRA H로 해석된 CDXC-1이 `_gate_hgbp_unsupported_product_line`에 걸려 도면이 보류됐다.
> **게이트 자체는 정상 작동** — Nova/Ventum-H 기하가 Terra 태그로 나가는 걸 막았다(오탐이 상류에 있었을 뿐).
> 고침은 두 겹: 스캔 창을 **커버 페이지 이후로 제한**(옵션은 커버 라인아이템이므로 커버 앞 스펙 섹션은 그걸
> 말할 수 없다) + 정규식에서 **"<토큰> line/pipe/piping" 배관 서술형 배제**. 상한은 두지 않았다 — 어더가 코일
> 행을 내지 않는 커버 연속 페이지에 앉는 실제 케이스를 **기존 테스트가 이미 문서화**하고 있었다. 처음 제안한
> "부품번호/VALVE/adder 동반 조건"은 **구현 중 폐기** — 문제의 산문이 이미 "expansion **valve**"를 포함했고,
> 마커 없이 표기한 패키지를 조용히 놓치는 쪽(→ 잘못된 Header-N 도면이 무음 링크)이 눈에 보이는 보류보다 나쁘다.
> ②**코팅 미추출** — 제출물은 커스텀 코팅을 상세 블록의 **별표 주석**으로 적는다(`*Finkote2 Epoxy Coil Coating*`,
> p.26 단독 / p.27은 Coil Weight 줄에 꼬리로). "Coil Coating: <값>" 라벨 줄이 아니라 `COIL_COATING` 패턴이
> 매칭하지 못했고, 코팅 코일이 전부 Direct Coil 기본값 **"Plain"**으로 읽혔다. 드롭다운보다 심각한 건
> **R-080/R-081 "Do Not Coat Last 5-6 inches..." 도면 노트가 통째로 빠진 것** — `only_when: coating_set`이라
> coating이 비면 발화하지 않는다. 닫는 별표를 **필수**로 요구해 같은 블록의 한쪽만 있는 각주
> (`*Separate electrical connection required for heater`)를 걸러내고, `normalized_line`에서 읽어 host 줄을
> 소비하지 않는다(p.27은 Coil Weight와 공존). **실앱 검증**(수정 코드 로드한 별도 인스턴스, 브라우저 실업로드):
> Coil Coating `Plain`→`review required`, Drawing Notes에 `Do Not Coat Last 5-6 inches of Distributor
> Extensions.` 추가, Drawing이 `HGBP (special) — no matching template / withheld`→
> `DX / LH / Header 3 — logic-derived (coilmaster_dx_lh_header3)` + `DIMS READ 0`→`3`. 업로드 10MB 상한 때문에
> UI는 관련 8p 추림본으로 돌렸으나, **원본 124p 무트리밍**을 엔드포인트가 부르는 워크플로 함수에 그대로 태워
> 동일 결과 재확인(`cover_page_hgbp_pages []` · `special_feature None` · 두 코일 모두 coating
> `'Finkote2 Epoxy Coil Coating'`(review_required) + 도면 생성). **1188 green**(1184+8). 곁가지 교훈 2건:
> ⓐ같이 손댔던 `web/app.js` 리뷰노트 개선은 **검증해보니 죽은 코드**였다 — `field.notes`를 그리는 곳은
> `pasteReadyNotes`(Review & Export 표, **서버** surface) 한 곳뿐이고 내가 고친 `directCoilCoatingField`는
> **브라우저** surface(`fieldsByLabel`)로 가는데 `renderDcInputRow`는 value/status만 쓴다 → DOM 전수 스윕
> 0건 확인 후 **원복**(diff 0). 화면 개선은 전부 Python 쪽에서 나온 것. ⓑUI 검증이 프런트의 자동
> `/api/checklist/fill` 호출을 타서 **Downloads에 .xlsx를 쓰고 journal 3줄을 남겼다** — 클릭한 건
> "Analyze PDF" 하나뿐이었다. 검증 산출물은 승인 후 전량 삭제. ⚠️ John의 :8011은 `--reload`가 없어
> **재시작해야 반영**.
> 이전: **[Case Retrieval 트랙] 2.1 커밋 — 그리고 커밋하면서 드러난 브랜치 파손 복구
> (343b972 · f54d5f1)**: 미커밋으로 묵혀둔 Stage 2.1을 검토·커밋하려다 **브랜치가 이미 깨져 있던 걸 발견**.
> `fb894da`(7/29, 다른 세션)가 derive 심에 `features_from_result` **import를 커밋**했는데 그 함수는 작업트리에만
> 있었음. import가 `try` **바깥**이고 `/derive` 라우트는 `UnknownCoilInputError`/`ValidationError`만 잡으므로
> **클린 체크아웃에서 모든 수동 채움·제품 픽·재분석 팬아웃이 500**. 속성을 지워 커밋본을 재현해 실증
> (`ImportError: cannot import name 'features_from_result'`). **로컬은 계속 초록**이었음 — 미커밋 파일이
> 전체 스위트와 그날 브라우저 검증까지 통과시켜 줬기 때문. 로드맵에 반복 등장하는 "hunk 격리(2.1 제외)"가
> 이번엔 **한쪽만 커밋된 의존**을 만든 것. 교훈: 격리 커밋 뒤엔 `git show HEAD:<file>`로 커밋본을 대조해야 함.
> 커밋 내용 — `343b972`: `features_from_result`(ledger WRITE 축과 대칭인 질의측 추출, `record._coil_row`
> 무접촉) + 가산 `min_shared_axes` + `corpus_min` + 이웃별 축 요약(엔지니어링 축뿐이라 redaction 무영향).
> `f54d5f1`: A5 오프라인 가중치 튜닝 하네스 — 읽기 전용·자동채택 없음·근거 부족 시 `signal_too_weak`로 제안
> 거부(무발명), 라이브 경로 무접촉. **동종 구멍 전수점검**: HEAD를 임시 worktree에 체크아웃해 전체 스위트
> 실행 → 1177 통과, **미커밋 코드 의존 0**. 남은 4 실패는 `test_phase2c_*`가
> `default_po_logic_source_paths()`로 `cwd().parent/PO_Release_Engineering_Workflow`를 읽는 **형제 리포 의존**
> (실 리포 옆엔 존재해 로컬은 통과, worktree/CI에선 실패) — 기존 사항, 이번 작업 무관. 1181 green.
> 이전: **[도면 트랙] 수동 채움이 DX with-HGRH 케이싱 깊이를 되돌리던 회귀 수정 — 228d731**:
> TR-8 실행 중 도면 SVG가 `7.5 CD`인데 체크리스트는 `8.125`인 걸 발견. 기존 표시 불일치인 줄 알았으나
> **수동 채움이 유발하는 회귀**였음 — 손 안 댄 CDXC-2는 8.125, TF 오버라이드를 거친 CDXC-1만 7.5.
> `_apply_hgrh_pairing_cd`(재열 짝 DX의 R-072 with-HGRH 분기)가 **analyze 경로에만 배선**돼 있고
> `derive_coil_template_drawing`은 호출하지 않았음(`hgrh_partner_conn`이 `submittal_to_drawing.py` 밖에 존재하지
> 않음). CD는 `S = k·CD/(circuits+1)`의 입력이라 **분배기 간격 전체가 함께 이동**(S1 2.0→1.875, S3 4.125→3.75),
> 그런데 체크리스트는 자기 값을 따로 계산하므로 시트는 8.125 그대로 = **대조하지 않으면 안 보이는 무음 결함**.
> derive는 코일 하나만 풀므로 **형제 코일을 호출자가 실어 보내고 짝짓기 판정은 정본 `drain_pan_partner_tag`에
> 유지**(브라우저에서 태그 별칭표 RHHGRC/RHHGRH/HGRC/HGRH를 재구현하면 갈라짐). 보정을 **Tier-A 재실행 안에**
> 태운 게 핵심 — `_apply_hgrh_pairing_cd`는 재계산 슬롯 전체를 merge하고 application/header_count/
> qty_conn_per_header를 모르므로, 뒤에 부르면 **보완하려던 그 채움을 조용히 지움**. 짝 없는 DX·비-DX는 무동작.
> 실 2901 재검증: 오버라이드 후 도면이 CD 8.125 · S1 2.0 · S3 4.125 · S5 6.125 = 체크리스트와 일치. 1181 green.
> 이전: **[체크리스트 트랙] TR-8 실 2901 통과 + 실행이 잡은 결함 2건 수정 — 04ea72a**:
> 실 제출물로 브라우저 끝단까지 밟자 **자동 테스트가 못 잡던 결함 2건**이 나옴. ①시트의 `CH = C13+C27+C28`이
> TF를 참조해 오버라이드 시 파일에선 26.125→26.5로 움직이는데 **패널엔 26.125/26.125 ✓** — 앱만 보고 승인하면
> 엔진과 어긋난 시트를 통과시킴. 원인은 "덮어쓰기 직전 판독"이라는 설계 자체가 아니라 그 판독을 **최종 상태로
> 재사용**한 것 → 2차 재계산 뒤 재판독하되 **오버라이드 행은 제외**(포함하면 override가 자기확인 match가 되어
> 교차검증이 사라짐). 이제 `CH 26.125/26.5 ✗`. 내 테스트는 CD→S1 종속만 고정했는데 실 템플릿엔 TF→CH 경로가
> 있었음 — **테스트는 내가 상상한 종속만 검증하고, 실데이터는 시트가 실제로 가진 종속을 보여준다**.
> ②재실행마다 `... (2).xlsx`가 쌓여 최신본 식별 불가 → 같은 파일 교체(Excel에 열려 있을 때만 번호 폴백,
> 프리플라이트 삭제로 판정) + **같은 경로를 가리키던 캐시 항목 축출**(안 하면 오버라이드 없는 finalize가
> 오버라이드본을 파일링하는 새 버그가 생김 — 덮어쓰기 선택에 딸려온 함정). 1178 green. 이전:
> **[체크리스트 트랙] 수동 오버라이드를 Coil Checklist까지 전파 + 코멘트 — 0c8bb84**:
> 도면은 새 값으로 다시 그려지는데 Coil Checklist는 계속 제출물에서 재유도돼, **패널과 주문에 딸려 나가는
> .xlsx가 도면과 조용히 어긋나던** 문제(John 지적). 오버라이드는 성격이 둘로 갈린다 — **Tier A(엔진입력)** 는
> 원래 C열 **입력** 셀이라 써 넣으면 시트가 스스로 재계산 = 교차검증이 **강화**되고, **Tier B(도면 파라미터)** 는
> **수식** 셀이라 손대면 독립 대조가 사라진다. 해법은 **순서**: 입력 기록 → 재계산 → **수식 결과를 먼저 읽어둔
> 뒤** → 그 셀을 실제 그리는 값으로 덮고 코멘트(대체된 수식값+사유) → **2차 재계산**. 그래서 `.xlsx`는 도면과
> 일치하면서 대조는 `overridden` verdict로 살아남는다(match도 mismatch도 아님 — 사람의 결정이라 mismatch
> 카운트를 부풀리지 않음). 순서를 뒤집으면 read-back이 자기 값을 되읽어 **교차검증이 조용히 자기참조로 변함**
> → 그 순서를 고정하는 실-Excel 테스트를 박음. 키→슬롯 변환은 새로 짜지 않고 **도면 경로의
> `PARAM_TO_SLOT`/`_header_slot` 재사용**(멀티헤더 논리키 `S2`→parity `slot.S3`가 공짜로 일치; 별도 테이블이면
> 첫 버그 자리). Tier A는 **모든 코일에 먼저 적용**해 파트너 셀(DX시트 HGRH CONN SZ / HGRH시트 DX CD)까지 따라옴.
> 캐시 키에 오버라이드 지문 추가(없으면 종전과 동일 키) — 안 넣으면 finalize가 다른 키로 빠져 **오버라이드 없는
> 시트를 폴더에 파일링**. 실증(2901 CDXC-1 재현, 실 Excel COM + 실 사내 템플릿): TF 1.625→2.0에서 CoilForge 2 /
> Checklist(수식) 1.625 / ✎, 나머지 35개 ✓, `C27`이 수식 아닌 상수 2 + 코멘트, 그리고 **시트 자체 수식
> `CH = C13+C27+C28`이 TF를 참조**해 **CH 26.125→26.5**(+0.375) 동반 이동 = 2차 재계산의 실물 증거(무관한 CD
> 8.125 불변). 이건 테스트가 못 잡던 종속(테스트는 CD→S1만 고정)이라, 2차 재계산이 없었으면 .xlsx의 CH가
> 화면상 아무 이상 없이 TF와 어긋난 채 저장됐을 것. 무오버라이드 경로는 블록 전체 스킵 = 종전과 byte-identical.
> 신규 24테스트, **1174 green**, frozen 무접촉, 전 항목 review_required·export_allowed False. 미결=TR-8(브라우저
> Apply→1.5s 자동 재실행). 이전: **[물코일 트랙] 게이트를 열자 드러난 값 결함 5건 일괄 수정 — ae415aa**: fb894da가
> Terra V 물코일 도면을 렌더시키자 **한 번도 화면에 나온 적 없던 값 5개**가 John 눈에 걸림. 전부 기존 결함이고
> 게이트가 검증 없이 보존하고 있었음("레퍼런스 없으니 막아두자"가 안전장치가 아니라 **틀린 값의 냉동고**였던 것).
> ①**S/R = connection size**(John) — CD/2 폴백은 주석부터 "no equation to mirror"라 자백했고 시드 7장 중 0장 일치,
> 1" 코일에 1.6875를 찍고 있었음. 연결 크기는 **룰 계열의 기존 형태**(DX R-022 `R1=D`, HGRH R-052 n=1 `R=D`)이고
> 물코일은 항상 1HD 단일 연결이라 그 케이스 + SOP R-068("EZ 기본값을 두라")과도 화해(EZ 기본값이 곧 연결 크기).
> **S가 CD 의존에서 해방**돼 CD 미해결 코일도 S/R이 나옴. ②**Terra V water O = 2.75**(34.5 아님) — **데이텀 불일치**.
> 옛 주석이 "levels the return stubout with the supply stubout"이라 스스로 답을 절반 적어뒀음(수평이면 도면엔 같은
> 수). `CH−2.75`는 같은 위치의 반대편 데이텀 표현이라 2~3인치 칸에 34.5가 들어간 것. 시드 7/7이 `O==I`, `O==CH−2.75`는
> 0/7(CH 17.00~38.75 전 범위), Terra V만 자기 I와 어긋난 유일 라인. ③**Drawing Notes** — 노트가 *후보*의 product/size로
> 게이트되는데 물코일 후보엔 없고 **도면만** full-PDF 스캔으로 해결 → 도면엔 vent/drain 노트, 패널엔 unmapped
> (docstring이 "never diverge"라 약속한 바로 그 발산). 도면이 실제 해결한 값으로 재시도. **20개 (코일×제품군) 조합
> 전수조사 = 엔진 누락 0** → 순수 전달 게이트 문제. 잔여 설계공백: coating 노트는 R-080(DX)·R-081(HGRH) 전용이라
> 물코일엔 규칙 자체가 없음(무발명). ④**Air Flow Direction** — 초안 `airflow_direction`이 **모든 코일에서 blocked**이고
> 라벨 정규화로 미러 행과 충돌 → blocked의 리터럴 `"review required"`가 "값"으로 취급돼 선언된 `Horizontal`이
> **영구 死**. blocked는 선언된 기본값에 지도록(unmapped와 동일 취급). ⑤**Coil Hand = `not defined`**(John: LH 단정 금지)
> — hand가 틀리면 **도면 전체가 좌우 반전**이라 그럴듯한 기본값이 빈칸보다 위험한 유일 필드. 도면은 검토 보조물이라
> LH 아트워크로 계속 렌더 + 배너가 미기재를 명시, 데이터 필드는 hand를 주장하지 않음(그림/데이터 역할 분리).
> 덤: hand 레버가 `coil_hand_defaulted` 게이트라 **값을 채우는 순간 사라져 RH→LH 오클릭을 되돌릴 수 없던** 문제 →
> 도면 있으면 상시 제공(오독 hand도 미기재만큼 위험) + `current_value`를 피커 어휘(Left/Right)로 정규화(종전 "LH"라
> 아무것도 선택 안 됨). 회귀 8개 + **도면 노트와 패널 노트가 갈라지면 실패하는 불변식 테스트**, **1150 green**,
> frozen 무접촉, 전 값 review_required·export_allowed False. 이전: **[UI/UX 트랙] 계산 패널 Leaving DB/WB 강조 — c747ab4**: 전날 duty 강조가 입력 행에만
>걸리고 계산 패널엔 안 걸린 이유가 **라벨 정규화** — `normalizeDcLabel`이 단위 글자를 남겨 `"...(°F)"`와 바로
> `"..."`가 다른 키가 됨. 두 철자 등록 + `isDcDutyLabel`로 통일, 계산 패널은 status 클래스가 없어 sentinel 문자열로
> "값 있음" 판정. 배경 틴트는 `--accent-soft` **미정의 토큰** 때문에 폴백 rgba가 양 테마에 박히는 걸 발견하고 철회.
> JS는 동시 세션 `fb894da`에 합류, 여기 커밋은 CSS만(격리 중 구 HEAD blob을 커밋 직전에 잡아냄). 1144 green.
> 동시에 **[물코일 트랙] Terra V 물코일 도면 해금 + 빠져 있던 데이터 매핑 일괄 — 커밋
> fb894da**: 2949 Ferguson Theatre의 HWC 3개가 도면도 안 나오고 패널도 텅 비어 있던 문제. **원인이 5개, 전부
> 다른 레이어** — ①게이트(Terra V water 보류) ②추출(한 열에 세로로 쌓인 섹션 → "Max Coil Performance" 블록
> **통째 유실**) ③슬롯층(물코일 `return_spacing` 룰 부재 + Terra V 제외로 R 영구 blank) ④프런트(물코일이 DX·
> condensing 어느 fallback 분기에도 안 들어감) ⑤frozen 경로의 `or "LH"`가 hand를 조용히 가정. **적대적
> plan-review가 자책골 2건 사전 차단**: W4를 원안대로 했으면 `addSharedAirFallbackFields`가 방금 뚫은 Total
> Capacity 142.31을 리터럴 0으로, 실측 Air Vel 424를 계산값 424.24로 덮어써 **플랜 자신의 수용 기준을 파괴**
> (`setDcFieldAlias`가 추출값 루프보다 먼저 도는 순서 계약); 그리고 `condensingCandidate` 확장은 물코일에
> 냉매온도를 발명할 뻔. 리뷰가 시드 근거 오류도 정정 — 시드 7개가 확립하는 건 **대칭 `R2==S1`**이지 절대값이
> 아님(엔진 `S=CD/2`는 어느 시드도 재현 못 함; `I1=2.31` 상수인데 HWC 시드 CD 4.63이라 `CD/2=2.315`로 **우연히**
> 맞았을 뿐). **DX 회귀 아닌 실수정 발견·John 승인**: `total_capacity_mbh` 365.85→123.88 — 옛 값은 텍스트
> 파서가 `Nominal Cooling Capacity`를 잡던 것(그 값은 별도 보관 유지). 도면 슬롯은 DX 전부 무변경. 1141 green,
> frozen 무접촉. 이전: **[UI/UX 트랙] John 5건 일괄 — 커밋 3개 9ad1f25·0b9a60c·9db5f10**: ①Ambient 견적요청
> PDF 신설(패키지 모드에 내보내기가 아예 없어 Ambient에 줄 게 없던 문제; fitz 작도 + PDF 재-POST로 메모 재사용,
> 클라 SVG 주입 차단) ②Project Review·Audit CCSI 패널 제거(백엔드·테스트 유지) ③Drawing Notes를 CCSI 페이로드
> 최상위 키로 전송 + userscript `entriesOf()` 어댑터로 **실제 자동입력까지 연결**(CCSI 로그인 불가로 labelText 추론
> 셀렉터, `selector_verified:false`로 경고 표시 → TR-6) ④Leaving DB/WB 강조(값 있을 때만) ⑤RHHGRC 미매핑 해소 —
> mapping_lab 4개 실코일 전사본이 8개 구성규칙 전부 일치하는 **증거 기반**으로 condensing 확장, drain pan·System
> Type은 반증 있어 제외(무발명), HGRH 기본값 7개는 fallbackMap **뒤에서** addDcFieldAlias → 추출값 우선(실증
> 0.625가 "Calculate" 이김). 부수 버그 3건(Condensing Temp가 액체온도 표시 / 선언 기본값 전부 死 / Saturated Suction
> 별칭 누락 — 마지막 건은 **눈 검증만이 잡을 수 있던 종류**). 2라운드 적대적 계획검토 후 착수, +44테스트 **1129
> green**, 변조테스트로 가드 유효성 증명, 실 4코일 submittal 브라우저 눈검증 완료(runbook §18). 이전: **[RHHGRC 트랙]
> HGRH/RHHGRC + 냉수 미러에 Leaving Dry/Wet Bulb 표시 (43215a0·a1c0a5b)**: 84d04f6의
> "Max Coil Performance" DB/WB→Leaving 매핑이 **DX 미러에만 배선**돼, RHHGRC(HGRH 재열)는 leaving_dry_bulb_f
> =71.29를 추출하고도 응축 미러에 미표시(John이 submittal에서 손으로 읽음). 실행으로 결함이 **표시 레이어 국한**임을
> 증명(추출은 코일 무관·정상, PAGE1 RHHGRC-1=71.29) → web/app.js만 수정: leaving DB/WB를 **코일 무관 fallbackMap**
> (DX 전용 헬퍼가 아닌)에 배선(DX byte-identical=헬퍼 먼저 실행·setDcFieldAlias 우선) + 응축 미러 AIR DATA에 Leaving
> Wet Bulb 행 추가(재열=현열-only라 WB 없음=정직한 공란·무발명). 신규 HGRH 추출 회귀테스트 + app.js 문자열 배선
> 테스트, **1083 green**, frozen/paste 52필드/goldens 무접촉. hunk 격리(Stage 2.1/3.0 제외). **냉수 후속(a1c0a5b):**
> 같은 배선을 water 미러로 확장 — 냉수는 제습이라 leaving WB 의미 있음(CCWC-1=62.9 실행 확인), 온수는 현열-only
> (HHWC-1 WB=None)라 `isHotWater` 게이트로 행 오프(무발명). 신규 CWC/HWC 비대칭 테스트, **1084 green**. 미결=John
> 브라우저 눈확인(서버 재시작+재분석; RHHGRC·냉수 둘 다). 이전: **[quote 트랙] quote-package 도면에 coil tag 표시 (15bcd55) + [체크리스트 정렬 트랙]
> DX 분배기 S를 체크리스트처럼 1/8" 반올림 (1dbbf74)**: ①cdf6fc3가 SVG에 넣은 `Tag: X`가 삽입 도면 페이지엔
> 안 보이던 문제 — 크롭 viewBox가 라벨을 페이지 y 2.2~18.7에 매핑하는데 어셈블러가 y 0~16을 **불투명 배너**로
> 덮어 디센더 조각만 남김(=John이 본 좌상단 잔상). 배너를 소유한 레이어에서 수정: `_stamp_watermark_banner`가
> coil tag를 받아 배너 위 우측에 재인쇄 + `_BANNER_HEIGHT` 16→20(묻힌 라벨 완전 덮음). SVG 라벨을 아래로 내리는
> 안은 33개 시드 템플릿 좌상단 래스터 스캔으로 기각(y≈20부터 지오메트리 시작=안전지대 없음). 신규 3테스트(크로스
> 레이어 불변식 포함), 라이브 서버 `/api/package/quote` 실증(양 페이지 자기 태그·export_allowed False). ②DX
> S1/S3/S5/S7이 체크리스트 `ROUND(k·CD/(n+1)·8,0)/8`(1/8 스냅)과 달리 raw 몫으로 그려짐(CD=5.5,n=2 → 1.8333/3.6667
> vs 체크리스트 1.875/3.625). 같은 방정식이 **세 곳에 각기 다르게 틀림**(dual-path gotcha): 엔진 R-034=정수인치,
> 슬롯레이어·패널=반올림 없음 → `round_eighth`(기존 `_excel_round` 재사용=Excel half-away-from-zero) 헬퍼로 통일.
> DX 한정(CWC/HWC 시트엔 S행 없음=무발명, Terra V CD−Rn 분기 불변). 1/8은 비례 안 함(2·1.875≠3.625)=k마다 개별
> 반올림. 기존 단언 4건 갱신+신규 1건, **1082 green**. 두 건 모두 hunk 격리(Stage 2.1/3.0 미커밋 제외). 이전:
> **[AI 3단계] Review Triage Phase 3.0 = override율 측정 도구 구축·커밋 (af3b4fc)**: 원장에서
> 필드별 "flag된 (tag,project) 신원 중 John이 실제 교정한 비율"을 읽는 순수 읽기전용 `capture/triage.py::measure_override_rate`
> + CLI + `GET /api/capture/override-rate`(redact). 랭킹 UI는 Phase 3.1 보류(교정 축적+아래 설계결정 후). **plan-review MAJOR-1**:
> `compare_observation`은 coil_uid 컬럼 없음 → mechanical_fit은 `run+coil_tag` 2번째 identity 경로로 조인(ccsi는 coil_tag NULL이라
> 제외). 신규 9테스트(identity-grain+compare-join 회귀), **1078 green**(exceptions_K 불변), plan-review 1R + invariant-guard
> BLOCKER 0. **최대 실데이터 발견**: 메모리는 corrections=0이라 했으나 실원장은 이미 **7건/신원 4개**로 이동 → 도구가 실데이터
> 작동. 그런데 flag된 필드(S/CD/O) override율이 flagged-기준 **전부 0**: `S`는 ERV 코일에서 flag됐는데 교정은 **RHHGRC-1/2/3
> (project 2843, David 3058 케이스)**에서 발생·**겹침 0** → John은 엔진이 *자신있게 틀린 값을 준(flag 안 함)* 코일에서 override.
> **flag된 코일만 랭킹하면 진짜 override 코일을 놓침 = 로드맵 "스킵 금지=false negative"가 실데이터로 확증** → Phase 3.1은
> `corrected_total−corrected`(unflagged 교정) 노출 여부 John 판정 필요. 커밋은 hunk 격리(Phase 2.1/동시세션 제외). 이전:
> **[CCSI 트랙] 자동 per-field 체크마크 v2.2.1 + [quote 트랙] coil tag 스탬핑**: ①CCSI 필러가
> 값 채울 때 `#<id>_isActive` 체크마크를 자동 ON(라이브 시연이 v2.1 실버그 2건 포착→enable-먼저·맵 ccsi_readonly 스킵·
> @noframes iframe 가드로 v2.2.1 수정, 실 폼 8307776 검증, 커밋 e1b5c20·c5df0cf·d9bd11a·f507687). ②quote 도면에 coil
> tag 미표시(candidate 태그 없고 커버행에만 있는 코일)를 `_pdf_coil_pages` 최종 page.tag로 스탬프(cdf6fc3, "Tag: CDXC-2"
> 좌상단 인쇄 스크린샷). 1069 green · hunk 격리(case-retrieval/동시세션 제외). 미결=John TM v2.2.1 갱신+실 quote 확인. 이전:
> **Ambient 서플라이어 확장 2건 구축(미커밋, John eyeball 대기)**: (1) submittal
> 하나로 **Ambient용 성능페이지+도면 패키지** 생성(전사 only·selection 엔진 무접촉)+다크 도면 흰종이/클릭확대,
> (2) **비교 Excel write-back** — submittal→C열·Ambient PDF→D열 자동채움 후 Downloads 복사본(원본 무접촉).
> plan-review 각 2R APPROVED · **1058 green** · invariant-guard BLOCKER 0 · 실 COM 스모크(headless EXCEL
> 누수 발견→PID 센티넬 teardown 수정). ⚠️ 트리에 무관 미커밋 다수(CCSI/Case Retrieval 2.1/services) 공존—
> 커밋은 hunk 격리 필요. 이전: **2단계 Case Retrieval Phase 2.0 구축·커밋·푸시(66087fd)**: Gower kNN 엔진 + corpus 게이지 + `/api/capture/similar` + CLI, gated n≥50 + **rule_id→3자뷰 배선**. 코퍼스 46/50·**교정 0**(실 submittal 12개 배치 분석=feature-only). ▶️ 지금 = 2단계 원장 채우기 — 실사용으로 **교정** 축적이 진짜 관건(개수보다 이게 핵심). 미결: TR-1/TR-2 John 브라우저 눈확인)

## ✅ 완료
- [x] Phase 2A MVP 코어 — YAML 룰 엔진 + 템플릿-우선 SVG 도면 파이프라인 동작
- [x] 22개 템플릿 시드 완료 — per-hand 실참조 + 4HD(DX/HGRH LH+RH), 미러 생성 없음
- [x] Terra V SOP 확정 — 10개 델타값 LOW→HIGH 승격, 13개 사이즈·케이싱 전부 해소
- [x] Ventum+ 포크 (2026-07-06) — catalog.py product_family 축(2-pass) + 전용 11템플릿(R-032 UP 분배기 실물 포착); hand 미표기 2666/2658=LH 확정 → 11이 참조 폴더의 완전한 시드 집합; /verify 런타임 PASS(2026-07-07: 실서버 /api/coil-drawing/derive → 전용 라우팅+경고드롭+Nova 게이트 무회귀 6드라이브)
- [x] Mechanical Fit + Coil Checklist 자동채움 — WIDTH/HEIGHT/INSTALL 판정, xlsx 복사본 채움+역검증
- [x] Engineering Wiki — LLM 유지 지식베이스(뱃지+인용), /wiki-ingest·query·lint 드리프트 점검
- [x] CCSI Tier 0/1 — 25키 push + green/red 대조 + 5개 Claude-in-Chrome 스킬(fill/compare/sync/rfo/revise)
- [x] Exceptions-first 프로젝트 검토 게이트 (0cbb391) — K∝문제수, 상수시간 코일 검토
- [x] 원클릭 deliverable + 자동 이메일 초안 + 다회로 S 리포트 반영 (882d468)
- [x] 폰트 추출불가 submittal 자동 OCR + OCR-blocked(토큰/쿼터) 경고 배너 (c007b75)- [x] Submittal 제품/사이즈 오검지 수정 (556b366) — 텍스트경로 커버행 model코드 포착 → TERRA H/015 라이브 검증- [x] Header 2 = circuit수 확정 (John 2026-07-06) + wiki multi-header-geometry 시드 (b7f71a2)- [x] PR #3 생성 (2026-07-07) — claude/ccsi-autofill → main, 73커밋(브랜치 누적 작업 전부)
- [x] 저위험 SOP 승격 5개 (R-066/R-002b/R-085/R-044c/R-048 MEDIUM→HIGH, 790 green) + eyeball 사인오프(John 2026-07-07) + 결정표·재분류(R-073/R-077/R-086) + /ship(hunk격리로 R-006 등 무관작업 제외)
- [x] R-074 2차 출처 판정 + R-048/R-085 조건부 발화 검증 (fc7037c, 794 green) — R-074 내부 2차출처 부재→MEDIUM 유지 확정(외부 출처 대기); R-048/R-085 유닛테스트 4건으로 HIGH 발화 검증; 검증 중 발견한 R-048 supply≠return 공식 결함·R-085 back_to_back 실경로 미배선을 [REVIEW-REQUIRED]로 등재(hunk격리로 R-006 재배제)
- [x] Coil Checklist 자동화 (b8b2168) — analyze 시 백그라운드 자동채움(기본ON 토글, 수동 "Fill" 버튼 제거) + sha1(pdf_bytes) 캐시로 finalize 이중 Excel COM 제거; `_run_or_reuse_checklist`/`_CHECKLIST_CACHE`(analyze↔finalize source_id 무관 공유), 신규 10테스트+818 green, invariant-guard clean(WARN 2건 수정), 실서버 실측 270.3s→0.053s 재사용 + 브라우저 자동채움 실증 · **John eyeball 확인 완료(2026-07-14)**- [x] 미시드 Ventum+ DX = not-registered 차단 (003928f, John 2026-07-14) — 미시드 Ventum+ DX가 공유 ConnectionDOWN 템플릿으로 폴백하던 걸 차단(R-032 UP를 공용이 못 그림); `_gate_unseeded_ventum_plus_dx`(DX 전용, 비-DX는 공유 폴백 유지), 시드 DX는 전용 UP 그대로; 테스트 2건 갱신+818 green, CLAUDE.md+위키 3파일 정정, 런타임 eyeball 확인 · **John 브라우저 확인 완료(2026-07-14)**- [x] Analyze 진행 표시 = 확정형 % 바 + 단계명 (10544f1, John 요청 2026-07-14) — 회전 스피너+고정문구를 초록 % 바+단계 라벨(Extracting→Cover rows→Coil sections→Product line→Building drawing)로 교체; 백엔드는 단일 블로킹 POST라 클라 `pdfProgress` 트리클(92% 상한 감속, 결과 그리드가 카드 대체=완료, 강제100% 없음); 덤으로 John 스크린샷이 가리킨 빈 초록 띠 버그 수정(`#brain-case-banner[hidden]{display:none}` — `display:grid`가 UA `[hidden]`을 덮던 것); 실 27p submittal 라이브 검증(57%→89%→코일2개 결과), 라이트/다크 정상, 826 green · **John 라이브 확인(2026-07-14)**- [x] 커버리지 대시보드 생성기 (16b0852) — 수기 HTML → `scripts/generate_coverage_dashboard.py`가 `catalog.list_template_entries()`에서 자동생성(+`--check` 드리프트 가드, CI에서 인코딩된 MVP 택소노미와 라이브 SHARED 버킷 불일치 시 실패)- [x] Drawing Notes 자동채움 (4b6d29f, John 확정 차트 2026-07-14) — "Drawing Notes" 필드가 (제품군×코일타입)으로 자동채움; 엔진이 이미 조립하던 노트(R-007/008/080/081)를 폼필드+검토용 SVG에 배선 + **신규 R-035a/b 분배기 노트**('Distributor 6" Extension Upwards' Ventum+ DX=R-032 UP 미러 / '...Downwards' 그 외 DX=R-031 DOWN 미러, 상호배타 2룰 → DX당 정확히 1개). `assemble_drawing_notes` 헬퍼 + `_NOTES_APPEND_IDS`/루프 등록; 엔진노트를 **기존** `distributor_notes`의 CANONICAL 사본에 주입(신규 레지스트리 필드 없음=52필드 표면 무churn) — 도면 렌더러는 slot.DISTRIBUTORS를 raw candidate/typed draft에서 읽으므로 분배기 콜아웃 오염 없음; product-gated(제품/사이즈 미상 시 공란, 무발명). 828 green, 착수 전 adversarial 재검토가 블로커 2건 포착·정정. ⚠️ **미결**: DX template.svg의 NOTES는 하드코딩("Copper Straps Required", `{{slot.NOTES}}` 플레이스홀더 없음)이라 신규 노트가 템플릿 도면엔 미표시 — 재시드(DO-NOT-TOUCH) 필요, John 판정 대기
- [x] Human-in-the-loop 수동 채움 (bc0c145, John 요청 2026-07-15) — 코일 데이터 blocked 시 엔지니어가 브라우저에서 누락값을 채우면 도면이 재생성됨(멈춰서 Claude로 돌아오는 루프 제거). Tier A=엔진입력 재계산(동결 `pdf_to_template_drawing` 대신 비동결 `derive_coil_template_drawing`에서 `build_drawing_slots` 재실행+`slot.X` 병합, 세 입력 application/header_count/qty_conn 있을 때만 발화=무회귀 byte-identical), Tier B=도면파라미터 직접 override(패널만, SVG 불변). 자동노출 fill-plan(product/size picker 포함) + tag기준 헤드리스 `/derive` 재적용 + `ManualOverride` 감사로그 + 하드중단 가드(`UnknownCoilInputError`/unknown_unit_size→picker) + API 검증(500 없음) + `COILFORGE_MANUAL_FILL` 킬스위치. **착수 전 4회 독립 적대검토**(C1 동결파일 위반·멀티코일 재분석 캐시결함 등 전건 해소 후 GO). 신규 17테스트(tests/test_manual_fill.py), 857 green, 라이브 eyeball(CD 5.5 un-gate 확인). ⚠️ 실 고객 PDF 브라우저 최종확인은 John 몫(고객데이터 gitignore) 🆕 이번 세션
- [x] **오버라이드 → 체크리스트 전파 + 코멘트 (0c8bb84, John 요청 2026-07-29)** — 위 수동채움의 반쪽 완성. 도면만
  갱신되고 Coil Checklist는 제출물에서 재유도돼 **패널·주문용 .xlsx가 도면과 어긋나던** 문제. Tier A(엔진입력)는
  C열 입력 셀이라 그대로 기록→시트 재계산(교차검증 강화), Tier B(도면 파라미터)는 수식 셀이라 **수식 결과를 먼저
  읽어둔 뒤** 덮고 셀 코멘트(대체값+사유)+2차 재계산 — 대조는 `overridden` verdict로 생존(mismatch로 안 셈).
  키→슬롯은 도면 경로의 `PARAM_TO_SLOT`/`_header_slot` 재사용(멀티헤더 `S2`→`slot.S3` 자동 일치), 캐시 키에
  오버라이드 지문(없으면 종전 키 그대로), `/api/checklist/fill` JSON 바디 폼 + finalize 스레딩(안 하면 오버라이드
  없는 시트가 파일링됨), 프런트는 tag 기준 수집 + 1.5s 디바운스 재실행(재분석 팬아웃은 1회만). 신규 24테스트
  (실 Excel COM으로 읽기→덮어쓰기 **순서**·종속 재계산·셀 코멘트 고정), **1174 green**, frozen 무접촉.
  실증: 2901 CDXC-1 재현에서 TF 1.625→2.0 시 `C27` 상수화+코멘트, 시트 수식 `CH=C13+C27+C28`이 따라 26.125→26.5.
  ⚠️ 브라우저 Apply→자동 재실행 확인은 John 몫(TR-8) 🆕 이번 세션

- [x] **MVP 사인오프 마무리 (John 2026-07-15)** — 파라미터 완전성 감사(Stage 2b) 판정 전부 해소.
  **템플릿 eyeball 사인오프 승인**(Ventum+ 11 + 공용 10, review-aid only·`export_allowed=False`·프로덕션 승인 아님) +
  대기 3건 처분: **R-048** supply≠return 결함 수정(supply를 문서 공식 `CD−[(Xmax+2)D+(Xmax−1)1.5]`로 —
  단 미검증·음수가능(CD 부족 시)이라 **HIGH 아닌 MEDIUM/review-required** 발화, return은 HIGH 유지; R-048
  테스트 2건 green; 공식 검증은 open-questions 유지) · **R-085** back_to_back 실경로 배선 **보류**(입력 출처
  정의 선행) · **R-074** casing 외부 2차출처 **MEDIUM 수용**(단일출처 CHK, review-required 유지).
  **커밋 완료: 91a50cb(feat, R-048 수정) + 58329c1(docs, 사인오프 기록)** — 동시 HGBP 기능과 공유
  엔진 파일에 함께 랜딩, 895 green. 🆕 이번 세션
- [x] Hot-gas-bypass(HGBP) 코일 지원 (91a50cb, 동시 세션 작업 · John 완벽동작 확인 2026-07-15) —
  R-035c 분배기 노트('Distributor Down w/ ASC & 6" Extension', HGBP DX Nova/Ventum H, R-035b와
  상호배타 only_when 게이팅) + coating 노트 게이팅(R-080 coating_set) + pdf_intake HGBP 검지 +
  템플릿 선택 + web UI + wiki/커버리지 문서. 제가 트리 정리 커밋(공유 엔진 파일에 R-048과 동반). 🆕 이번 세션

- [x] **AI 로드맵 확정 + 계획 승인 (John 2026-07-15)** — "코일 선정/견적마다 쌓이는 데이터를 SQL로
  축적해 AI/ML에 쓴다"는 브레인스토밍 → **7단계 로드맵 확정**(Capture Ledger → Case Retrieval →
  Review Triage → Rule Observatory → Auto-YAML → Format-Agnostic Extraction → Commercial
  Intelligence). John 확정: 볼륨 주당 코일 50~150(연 2,600~7,800 = **3~6개월이면 실학습 가능**),
  상업데이터는 `outcome` seam만 비워둠. **재구성:** CoilForge는 도면생성기가 아니라 *사람 오라클이
  붙은 전문가 시스템* — 매 실행이 `(입력→제안→교정)` 3항조합을 만드는데 **전부 HTTP 응답과 함께
  증발 중**(DB 없음, `coil_manual_fill` 저널은 `web_app.py:72` 신원 early-return으로 조용히 드롭).
  계획서 `~/.claude/plans/ultrathink-hazy-gizmo.md` (rev4). **착수 전 3라운드 독립 적대검토** —
  매 라운드 "내가 새로 쓴 부분"에서 BLOCKER: rev1 근본원인 오진(화이트리스트가 아니라 신원
  early-return) / rev2 미들웨어는 `_StreamingResponse`라 응답 dict 못 봄 / rev3 body 5종이라
  미들웨어가 `input_hash` 못 만듦(`case-to-drawing`은 `{case_id}`뿐). **rev4 구조적 결정:
  `dedup_key`를 정의하지 않고 컴포넌트 컬럼+뷰로 파생** → 3연속 틀린 정의의 비가역성 자체를 제거
  ("소급 불가"라던 전제가 틀렸다 — 비가역성은 파생값을 원시값처럼 저장할 때 생긴다). 🆕 이번 세션

- [x] **1단계 Capture Ledger — 5a 원장 코어 완료 (2026-07-16)** — 엔진 무수정, **912 green**(895+17),
  라이브 4코일 submittal 실증. 신규 `src/coilforge/capture/`(`db.py` WAL+`busy_timeout=5000`+`.git`탐색
  리포경로거부+`COILFORGE_CAPTURE=0` 킬스위치 / `schema.py` forward-only 9테이블 / `record.py` 어댑터).
  **훅은 1개** — `_journal_milestone`의 신원 게이트 **앞**에서 `capture_milestone` 호출 → 기존 11개
  호출부가 코드변경 0으로 캡처를 얻고, 저널이 버리는 데모/derive run도 잡힘.
  **미들웨어·워크플로훅 불필요 판명**(rev4 대비 구조 변경): 라우트가 `pdf_bytes`+`result`+`cover_page_hint`를
  동시에 보유 → B2(contextvar/to_thread)·R10(`_StreamingResponse`)·R11(body 5종) 소멸.
  **잡은 함정 3개:** ①`page["coil_type"]`=커버행 item텍스트, `page["product_type"]`=기본값"DX"인 패밀리
  → 진짜 값은 `workflow.template_drawing.extracted` ②`result["drawing_parameter_set"]`=선택된 1코일뿐
  → per-coil은 `page["workflow"]` ③engine stage는 **1a로 불가능 확정**(`HeaderPrepopulateResponse`가
  `pdf_to_template_drawing.py:286`에서 폐기) → 1c 필요성 코드로 증명. `terra_variant`는 `resolve_product_line`
  순수 파생. **구현 중 자체 발견:** 스위트가 진짜 코퍼스에 픽스처 19run/21coil을 쓰고 있었음 →
  `tests/conftest.py` 세션 격리 + 오염분 삭제. **불변식 감사 BLOCKER 0** + 감사가 잡은 라벨오염
  (`_gate_rows`가 checklist 없이 게이트 재계산 → exception 코일이 `pass`로 저장) 수정 + 회귀테스트.
  라이브 결과: project 2862, 4코일(DX/HGRH×NOVA/TERRA H), 394 field_obs, `capture_error` 0. 🆕 이번 세션

- [x] **5b — D1 저널 복구 3부작 완료 (2026-07-16)** — `coil_manual_fill`(유일한 사람 라벨)이 저널에서
  100% 유실되던 걸 복구. **914 green**(+2) + 라이브 실증. **크로스-리포 계약 먼저 확인:** Case Reader
  (`PO_Release_Case/src/case_reader/correlate.py:683,1470`)가 `value.milestone`을 화이트리스트로 대조 안 하고
  `setdefault`로 rollup(`direct_coil_verified`만 특별취급) → 4개 추가 forward-compatible 확정.
  **(a)** `web/app.js::deriveSpecFromTemplate`가 `state.pdfIntakeSummary`의 project identity를 스펙에 실음 +
  `:958`이 `request_payload=clean` 전달(derive result엔 `pdf_intake_summary`/`pdf_coil_pages` 둘 다 없음).
  **(a2)** `_journal_milestone`에 단수 `payload["tag"]` 수집(derive tag는 단수, 없으면 `coil_tags:[]`).
  **(b)** `MILESTONES` 4개 추가(coil_manual_fill/project_review/ccsi_export_audit/deliverable_finalized).
  **(c)** `record_coil_milestone` 반환을 `(event_id, error)` 튜플로 변경(내부 계약만, JSONL 라인포맷 불변)
  → **append-only 위해 journal을 capture보다 먼저 실행**(`_write_journal_line` 추출), event_id를 `run`에 링크,
  journal 실패를 `run.journal_error`로 표면화 + **AST 가드**(모든 `_journal_milestone` 리터럴 ⊆ MILESTONES →
  7번째 재발 불가). 라이브: derive → 저널에 `coil_manual_fill` + `tags:['CDXC-1']` + project 24-118,
  원장 run에 `journal_event_id` 링크, `capture_error` 0, 진짜 저널 무오염(임시 dir 격리). 🆕 이번 세션
- [x] **5a+5b 커밋·푸시 (8bc8ef7, 2026-07-16)** — 브랜치 claude/ccsi-autofill, 이번 세션 11파일만
  (`.agents`/`.codex` 제외; DB 0). 914 green 재확인 후 **push 완료**(`b1001d7..8bc8ef7`).
  **PO_Release_Case 계약문서 별도 커밋(ae086f7)** — 그 리포엔 진행중인 대규모 작업(200+ case) 존재라
  계약문서 1파일만 격리 스테이징, push 안 함(그 리포 관례 미상). 🆕 이번 세션
- [x] **5c — 우회 라우트 캡처 완료 (2026-07-16)** — `_journal_milestone`을 안 부르던 5개 라우트 배선.
  **917 green**(+3) + 라이브 실증. **탐색이 rev5 §5c 오류 2개 정정:** ①`compare_observation`은
  스키마만 있고 삽입코드 없는 **죽은 테이블**이었음(진짜 일은 hoist가 아니라 `_compare_rows` 신설)
  ②`build-packet` UnboundLocalError 함정은 **없음**(`workflow_input`은 변수 재참조 안 됨).
  **워크플로 3라우트**(submittal-to-drawing/-direct-draft=기존 intake milestone 재사용, build-packet=신규
  review_packet)는 hoist만. **compare 2라우트**는 `_compare_rows` 신설이 핵심 — **verdict 어휘 2종**:
  mechanical_fit은 중첩(coils[i].{width,height,drain_pan}.verdict, PASS/FAIL/CANNOT_EVALUATE, tag 있음→조인가능),
  ccsi는 flat(fields[j].verdict, match/mismatch/…, **신원 없음→coil_tag NULL 고아행 명시**=1a′로 분리).
  둘 다 `capture_milestone` 직접 호출(신원 없어 저널 스킵, ledger만) → MILESTONES엔 review_packet만 추가.
  라이브: mechanical-fit 6행(tag+PASS), ccsi 2행(NULL+match/mismatch, R 3.317 vs 1.3125 실사례), run
  coil_count 0, capture_error 0. **감사 BLOCKER 0**, NIT 2건(drain_pan label=partner_tag / 죽은 enum 제거) 수정. 🆕 이번 세션

## ✅ 완료 (이어서)
- [x] **1b — D2 `previous_value` 복구 (2026-07-16)** — Tier-B 수동 override의 (before→after) 교정을 `correction`
  테이블(M2)에 기록. before는 저장 없이 `parameter_set_from_template_drawing`을 override 없이 재호출해
  결정론적 재계산(Tier-B는 panel-only라 slot_values 무변경 → baseline 재현 성립). 훅은 `capture_milestone`의
  per-view 루프(coil_uid 발급 지점), `view.params`의 `mode=="manual"` 키로 교정 식별 + `circuits` 스레딩
  (previous_mode 정확성), `_correction_rows`는 자체 예외를 삼켜 `[]` 반환(마일스톤 전체 유실 방지, `.get`으로
  KeyError 원천 차단). **962 green**(+4 테스트), invariant-guard clean(BLOCKER/HIGH/MEDIUM 0), **헤드리스
  라이브**: `/api/coil-drawing/derive` CD override → `correction` 행 `5.5(default)→3.25(manual)`, capture_error 0.
  **5라운드 독립 플랜검토(HIGH 2→0 수렴)** 후 착수. 계획서 `~/.claude/plans/1b-1c-1d-snazzy-lemur.md`.
  ⚠️ 커밋은 Ambient Dynamics(동시 세션) 제외 hunk 격리. 🆕 이번 세션

- [x] **[별개 트랙] Ambient Dynamics quick-ship 서플라이어 확장 (e30c36f, 2026-07-16)** — Direct Coil(기본)
  vs Ambient 선택 축. Ambient는 도면생성이 아니라 **성능 검증** 워크플로: Ambient 회신 Performance PDF 파싱 →
  baseline submittal과 coil별 비교 → capacity/coil-volume을 **Coil Utilities acceptance 밴드**로 판정.
  Direct Coil 경로 byte-identical(신규 패키지+신규 라우트만). **`coil_utilities/` 재사용 내부 테이블** —
  `Coil Utilities - HWC DX.xlsx`에서 이식(R32 14-킷 EKEXVA→tonnage capacity/volume 밴드, circuits 스케일,
  geometry 엔진, heating 용량식, Allowable Ranges; R410a는 상수 미확보로 빈 TODO=invent 금지). `ambient/`
  (pdf_intake Btu/hr→MBH·degraded-OCR 방어, model/mapping/compare category-keyed+whole-coil not_compared,
  range_provider baseline→Ambient 폴백, rfq). web: `/api/ambient/compare`(multipart)·`/rfq`·`COILFORGE_AMBIENT`
  킬스위치·supplier 토글+green/red/grey 패널. `_match` keyword-only 확장(byte-safe). **독립 재검토 2라운드**
  (HIGH 2+MEDIUM 3+LOW 1 전건 반영) + **실 2975 데이터 브라우저 눈 확인**(FPI 10 vs 9 mismatch, Capacity/Volume
  Range in-band green). 963 green(+34). 계획서 `~/.claude/plans/ambient-cozy-barto.md`. 🆕 이번 세션

- [x] **[별개 트랙] Ambient submittal→패키지 경로 + 도면 UX (c3a0ac7, 2026-07-21)** — 기존 Ambient는 비교하려면
  EZ Coil selection을 손으로 뽑아야 했음. 신규 optional 경로: **submittal만 드롭하면**(Direct Coil처럼) Ambient
  페이지에서 **Ambient용 성능페이지+도면 패키지**가 나와 Ambient에 전달 → EZ Coil selection 불필요. 성능페이지=
  submittal에 이미 추출된 값 **전사(transcription) only**(신규 계산·selection 엔진 무접촉=AGENTS.md 준수),
  밴드는 `coil_utilities.ranges` 조회 재사용. 도면=EZ Coil 있으면 그대로, 없으면 Track B 생성물(per-coil
  `pdf_coil_pages[i].workflow.template_drawing`에서, 게이트 withhold는 omitted_reason 표면화). 신규 `ambient/
  package.py`(`build_ambient_package`, `_PERFORMANCE_FIELDS`를 `PDF_INTAKE_FIELD_RULES`에서 파생+식별/도면 필드
  제외 allowlist) + `POST /api/ambient/package`(never-raise·멱등캐시) + Ambient 패널 **모드 토글**(Compare/Package,
  package 모드는 상단 Direct Coil 인테이크 숨김) + `renderAmbientPackage`. **도면 UX**: 다크모드에서 안 보이던
  도면을 흰 "종이"(`--drawing-paper`)+non-scaling-stroke로 legible + **클릭 확대 모달**. plan-review 2R APPROVED
  (BLOCKER-1: `build_ambient_rfq`가 실은 키 불일치로 깨져 있어 재사용 금지→submittal 실키로 파생·이중 용량키;
  MAJOR-1: 도면 소스 키 정정) + invariant-guard(WARN 1=circuits 무언 기본값→`circuits_assumed` 정직 플래그).
  계획서 `~/.claude/plans/i-d-like-to-discuss-calm-wolf.md`. **hunk 격리 커밋·푸시(c3a0ac7 — 아래 Excel
  write-back과 동일 커밋, 무관 CCSI/Case Retrieval 2.1 제외).** ⚠️ **미결: John 실 submittal+Ambient PDF
  브라우저 눈검증**(고객데이터 gitignore). 🆕 이번 세션
- [x] **[별개 트랙] Ambient 비교 Excel write-back (Phase 6, c3a0ac7, 2026-07-21)** — 로드맵 "John 제공 대기"였던
  `XXXX - Coilmaster-Ambiant Dynamics Coil Comparison.xlsx` 템플릿 확보(코일당 시트 CDXC-1/RHHGRC-1 마스터,
  B열 라벨·**C열=우리(submittal)·D열=Ambient**). submittal+Ambient PDF → 코일별 시트에 C/D 자동채움 → Downloads
  복사본. **체크리스트 writer 미러**(격리 DispatchEx·템플릿 read-only+SaveCopyAs·**원본/OneDrive 무접촉**) +
  C/D **이중 키 매핑**(C=`finned_height`, D=`finned_height_in`) + **셀단위 `HasFormula` 보호**(Coil Volume·HGRH
  Super Heat D·Vapor Temp C 자동보존)+CalculateFull + 한쪽만/물코일=시트+warning(무발명). 신규 `ambient/
  excel_map.py`(순수)+`ambient/excel_writer.py`(COM)+`POST /api/ambient/excel`+Compare 모드 버튼. **1058 green**
  (신규 14). plan-review 2R APPROVED(MAJOR-1: 라벨 추측→openpyxl로 실템플릿 introspect→실채움 skipped 0으로 실증;
  MAJOR-2: 한쪽만 있는 코일 합집합 처리). invariant-guard BLOCKER 0(WARN 수정). **실 COM 스모크가 headless EXCEL
  좀비 누수(status_board_excel_lock) 발견→참조해제+gc+PID 센티넬 teardown(자기 인스턴스만)으로 확정 수정** —
  체크리스트 writer보다 강한 정리. 계획서 `~/.claude/plans/ambient-excel-writeback.md`. **c3a0ac7 커밋·푸시
  (hunk 격리, 위 패키지 경로와 동일 커밋, +1879/11파일).** ⚠️ **미결: John이 실 submittal+Ambient PDF로
  Compare→"Fill comparison Excel"→Downloads 복사본 눈검증**(원본 템플릿 무접촉 확인). 🆕 이번 세션

- [x] **[3058 검토 트랙] Coil Checklist 공식 정렬 — DX/HGRH CD·S·SL (89727e8, 2026-07-16)** — David가 3058
  packet에서 CDXC-2 CD=7.5(→8이어야)+stale S1/S3/S5, RHHGRC-2 CD/S1/SL1 지적. 근본원인: CoilForge가
  **Coil Checklist Template.xlsx 공식(확정 엔지니어링 진실원)**에서 이탈. 3개 병렬 Explore 진단 → 초기
  "stale 캐시" 가설을 실측 반증(전역 extract rows=None)하고 진짜 원인 확정. **Phase 1(DX):** 재열 HGRH와
  페어인 DX는 체크리스트 with-HGRH 분기(`circuits·(D+1.5)+(D−D_hgrh)/2`)를 써야 함 — 공식은 엔진에 이미
  있었으나 `with_hgrh`/`hgrh_conn_size`가 `build_drawing_slots`(도면+체크리스트 compare 공용)에 미배선. 배선
  + 도면경로는 비동결 호출부에서 재실행+SVG 재-population(프로즌 `pdf_to_template_drawing` 미변경). CDXC-2
  CD 7.5→8.0, S 2/4/6. **Phase 2(HGRH, John: 체크리스트가 이전결정 우선):** CD `max(base, 제품군 multi)`
  (Terra V 제외=CD·S=CD−Rn 보존), S1 `TERRA H/VENTUM+→conn` else CD공식(k-비례 아님), SL1 `feeds/circuits=1→3`.
  RHHGRC-2 CD 2.875→3.125·S1→0.875·SL1→5.5625, 4 HGRH코일 전부 일치(HGRH는 프로즌 경로 자동상속=배선0).
  **John이 2026-06-26(SL slot마다 다름)/2026-06-27(single-feed SL1=3 제거) 결정 2개 폐기 확정** → 해당 테스트
  갱신. 독립 invariant-guard 리뷰 clean(0 HIGH, MEDIUM feeds/circuits 대리값 정밀정렬+테스트 반영), **968 green**. 🆕 이번 세션

- [x] **[신규 우선 트랙] 편집 가능 Drawing Params → 도면 반영 + event-sourced 교정 — Phase 1 완료 (3411453, John 요청 2026-07-16)** —
  John: "체크리스트는 rule-of-thumb, 내가 조정할 때마다 그 변경을 DB에 누적해 CoilForge 값을 점점 신뢰 가능하게".
  하단 Drawing Params를 **"Update drawing" 버튼**(기존 manual-drawing-mode 토글로 unlock)으로 편집→적용 시
  Tier-B override가 **도면에 반영**(panel-only 결정 번복, John 2026-07-16): 비동결 `_reflect_param_overrides_into_slots`가
  slot_values 병합 + `populate_template_slots`로 SVG 재-population(프로즌·resolver 패널빌더 무접촉).
  **캡처는 event-sourcing**: 병합 前 기계 제안을 `manual_override_events`에 스냅샷 → `_correction_rows`가 그걸 읽어
  (before + `override_reason` 배선, 종전 NULL 유실 수정), 스냅샷 없으면 재계산 폴백. 이 before가 Phase 2 3자 비교의
  "CoilForge logic" 열이자 미래 ML 라벨. 안전: mode='manual'/review_required 유지·HIGH 승격 없음·export_allowed False·
  watermark·no-override byte-identical·킬스위치 유지. **착수 전 5개 지적 독립 적대검토 반영**(MAJOR-1 3자 열 오염 등).
  **972 green(+4)** + invariant-guard clean(BLOCKER 0/WARN 0) + 실 HTTP(CD 3.75→9.5 slot·SVG 반영, before=5.5
  event-source, reason 보존). 실 고객 PDF 브라우저 눈확인은 John 몫. 계획서 `~/.claude/plans/bottom-twinkly-garden.md`. 🆕 이번 세션

- [x] **[신규 우선 트랙] 편집 spec data + 3자 비교 뷰 — Phase 2 완료 (b04bcf3, 2026-07-17)** — 엔지니어가
  엔진 관련 spec(circuits/rows/feeds/return_conn_size/coating)을 **필드별 lock/unlock 패널**로 여유될 때 교정 →
  편집 시 도면 재계산(conn→slot, coating→R-080/081/035c 노트) + `stage='spec_field'` correction 축적
  (`spec_overrides`, event-sourced, reason 보존, 마이그레이션 0, 킬스위치 포함). 신규 `services/three_way_view.py`
  (순수 read-only, derive 결과에 `three_way` 부착)가 **submittal(raw) vs CoilForge(engine) vs engineer(manual)**
  를 나란히, `_match` 재사용 green/red. **MAJOR-1 라이브 증명:** override된 필드의 CoilForge 열은 event-source된
  기계 제안(`previous_value`)을 읽음 — CD override 9.5여도 열엔 5.5 표시(도면·패널은 9.5). `rule_id`는 nullable
  (1c가 "어느 룰" 열 채움). 안전: 값 변경/승인 없음·미지 키 거부·export_allowed False·프로즌 무접촉. **978 green(+6)**
  + invariant-guard clean(0 findings) + 실 HTTP(rows 4→6, CD 열=5.5). 브라우저 눈확인은 John 몫(TR-2). 🆕 이번 세션

- [x] **1c — 엔진 provenance 캡처 완료 (418e8e0, 2026-07-17)** — 1a가 "불가능"이라 증명했던 엔진 단계(어느
  룰이 발화했나 + confidence)를 캡처. **유일한 엔진 침습**이나 순수 additive: `FieldResult.rule_id: str|None =
  Field(default=None, exclude=True)`(직렬화 바이트동일·phase5 미병합 병합안전) + **27개 생성자 전수 rule_id=**
  (다중룰 primary: notes→R-007, DX·HGRH casing→R-070; 값·confidence·로직 무변경, 엔진 79테스트 불변). **seam=A**
  (John 확정): Tier-A-fill derive 응답만 캡처(`_rerun_slots_with_manual_inputs` = 유일하게 응답 반환하는 비동결
  경로), PDF-analyze는 out-of-scope. `_attach_engine_provenance`→`result["engine_provenance"]`→record.py가
  `rule_firing`(필드 grain)+`engine_call`(카운트) 기록(presence-gated·fail-closed·킬스위치). **M3 additive**
  (rule_snapshot 보류=_SPECIAL_IDS confidence inert; engine_call은 product/terra/size 제외=coil 조인). **착수 전
  게이트 전부 이행**: 사전점검(27=one-liner) + exclude 코드검증 + **독립 적대검토(REVISE→MAJOR2+MINOR3 전건 해소,
  engine_call 단순화)**. **983 green(+5)** + invariant clean(0) + 실 라이브(rule_firing 19행: casing_depth=R-070
  HIGH·dist_extension=R-033…, capture_error 0). ⚠️ **후속(소):** 캡처된 rule_id를 3자 뷰 "어느 룰" 열에 표시
  배선(현재 `three_way_view`는 `rule_id:None`; seam-A derive면 `engine_provenance`에서 바로 채울 수 있음). 🆕 이번 세션

- [x] **1d — 관측·재현·감사 완료 (41139a8, 2026-07-17) → 1단계 Capture Ledger 전체 종료(1a·1b·1c·1d)** —
  원장을 읽는/재현하는/샘플링하는 read-side 도구(엔진·프로즌 무접촉). **M4 additive**: `run_dedup` 뷰(재분석
  다중성 접기, `WHERE input_hash IS NOT NULL`로 derive/text 제외+NULL-GROUP-BY 함정 회피, latest_run_id는 uuid라
  제거) + `audit_sample` 큐 테이블. `capture/observe.py`: `health()`(상태+테이블별 카운트+에러 **타입만**·DB
  미생성 read) / `draw_audit_sample()`(flag-무관 랜덤, **(tag,project) identity로 dedup**=multiplicity 편향 차단,
  Python seed, 킬스위치 존중) / `replay_run()`(엔진-only 재실행 vs `stage='slot'`, overlay·복원불가=**not_replayable
  never 거짓 mismatch**, 허용오차 `_match`). `GET /api/capture/health` + `scripts/replay_run.py` +
  `scripts/draw_audit_sample.py`. **독립 적대검토(REVISE→MAJOR4+MINOR3 전건 해소)**: latest_run_id 제거·replay
  소스필터·샘플러 identity dedup(테스트가 잔여 재추출 포착)·seed Python·health no-create·last_error redact·킬스위치.
  invariant-guard(MAJOR last_error 누출 사후수정). **991 green(+9)** + 4도구 라이브(health 200/exists-false-무생성,
  replay overlay=not_replayable, 샘플 dedup, 스크립트 2개 실행). 🆕 이번 세션

- [x] **[quote-package 트랙] 다중 견적페이지 copper-strap 스탬핑 (0366a79, John 리포트 2026-07-17)** —
  코일 수량이 많아 견적 스케줄이 2페이지 이상으로 넘칠 때 **첫 견적 페이지만** copper-strap 노트가
  찍히고 2번째+ 페이지 코일은 무시되던 버그. 근본원인: 연속 견적 페이지는 per-row `Cost Each` 앵커는
  있으나 `COIL QUOTE` 헤더가 없는데(헤더는 1페이지에만) `_quote_page_index`가 `COIL QUOTE` 기준 첫
  페이지만 반환 → `_stamp_quote_price_notes`가 한 페이지만 스탬핑. **가격 계산·도면 삽입 루프는 이미
  정상**(코일 전수 순회) — 버그는 스탬핑 단계에 국한. **수정(assembler.py 1파일):** `_quote_page_indices`가
  `Cost Each`(모든 가격 페이지에 존재) 기준 전 견적 페이지 반환(`_quote_page_index`는 하위호환 래퍼) +
  `_stamp_quote_price_notes` 페이지별·**alias 인식**(`coil_tag_aliases` 재사용)·**2-pass**(pass1=이 페이지 태그
  코일 정확배치, pass2=이전 페이지에서 넘어온 경계코일을 남은 행에 흡수) + 공유 `stamped` 집합 스레딩 +
  `MultiCoilPackageResult.quote_page_indices` 가산 필드. **착수 전 독립 적대검토(REVISE→MAJOR 1건=경계코일
  테스트 부재+MINOR 3 전건 반영)**. 신규 6테스트(경계-spill·alias 포함), **997 green**. **실 26p 2843 파일
  실증**: 8코일 전부 노트 — 견적 p0 +4, **p1 +4(종전 0)**. 주의: 그 `_Revised.pdf`는 구버그 출력물이라
  p0에 노트 4개 선존재 → **증분(delta)으로 검증**(절대개수 아님). review-aid 불변식 무변경(노트 오버레이만,
  원본 견적 숫자 불변). 계획서 `~/.claude/plans/agile-nibbling-aurora.md`, memory `multi_page_quote_copper_strap.md`. 🆕 이번 세션

- [x] **2단계 Case Retrieval Phase 2.0 구축·커밋 (66087fd, 2026-07-19)** — numpy masked-Gower 최근접이웃으로
  원장에서 비슷한 과거 코일을 찾아 John의 `correction`(before→after→reason)을 **증거로 제시**(값 발명·자동적용
  없음, never-invent 무손상). **핵심 설계 = `(tag, project_number)` identity 그레인**: feature(analyze run의
  `run_input`)와 correction(`coil_manual_fill` run)이 **다른 coil_uid에 살아서** 단일 coil_uid로는 케이스 미완성
  — 착수 전 **독립 적대검토가 이 BLOCKER를 잡음**. 신규 `capture/retrieve.py`(Gower kNN·numpy lazy-import)+corpus
  게이지(health에 fold, distinct-identity 카운트)+`GET/POST /api/capture/similar`(HTTP=redact: reason·project_number
  제거)+`scripts/find_similar.py`(로컬 full)+15테스트. unit_size/suction_conn_size 범주형(John)·same_category
  프리필터·min_shared_axes=4·n<50 `insufficient_corpus` degrade. **동봉 micro-step: rule_id→3자뷰 배선**
  (`engine_provenance.firings`→`PARAM_TO_ENGINE_FIELD`(CD→casing_depth)→"어느 룰" 열, 엔진 미실행 시 None). read-only·
  additive·**마이그레이션 0**·frozen 무접촉·export_allowed 불변. **1014 green** + invariant-guard clean + E2E 스모크
  (HTTP redaction·CLI·identity-그레인 증거 실증). **코퍼스 현황 46/50·교정 0** — 실 submittal 12개(2298/2519/2572/
  2606/2667/2775/2808/2857/2870…) 배치 분석으로 22→46(feature-only). `submittals/` 소진(재분석=dedup 무증가);
  `Case/` 83개는 템플릿 시드 레퍼런스라 미투입(오염 방지, John 동의). 계획서 `~/.claude/plans/playful-shimmying-donut.md`,
  memory `case_retrieval_stage2.md`. 🆕 이번 세션

- [x] **[CCSI 트랙] 자동 per-field 체크마크 + ApplyVDConstraints (e1b5c20, John 요청 2026-07-21)** — CCSI Direct
  Coil 폼은 편집 가능한 각 치수를 형제 체크박스 `#<id>_isActive`(ON이어야 폼이 편집을 수용, 인라인
  `onClickDimisActive` onclick)로 게이트 → John이 필드마다 손으로 체크하던 걸 제거. 필러 `fillOne`이 값 채우기
  **직전** 그 체크마크를 자동 ON(`enableFieldForUpdate`: `.checked=true`론 onclick 미발화라 실 `.click()`, 꺼져
  있을 때만=이미 켠 건 무건드림). RF/HF/CH는 readOnly 가드가 먼저 return→체크마크 OFF 유지(John의 "자동 3개").
  BF/HD/TF/SL/ZD/HD2·3/ZD2·3은 체크박스 없음=항상 편집가능. **CD 편집 확정**(라이브 readOnly:false)→`ccsi_readonly`
  제거(문서용일 뿐, 실 스킵은 라이브 DOM 구동)→CoilForge가 채움+enable. 폼레벨 `#ApplyVDConstraints`=HGBP 코일만
  ON·그 외 OFF(신규 payload `hot_gas_bypass`, `special_feature`서 유도; clipboard·Send-to-CCSI 브릿지 **양 경로**
  탑재, 브릿지는 `#drawing-parameters` `dataset.specialFeature` 스탬프서 읽음). **라이브 DOM 캡처**(John 로그인,
  coil 8307776)로 `_isActive` 규칙·인라인 onclick·readOnly·VD 무핸들러 확정. **plan-review 2R**(round-1 REVISE:
  HGBP 경로 오진 2건 사전 포착→round-2 APPROVED). 맵 v2026-07-21, 문서 3파일 정정. hunk 격리 커밋(app.js 2헌크만,
  case-retrieval/동시세션 제외). review-aid·never auto-saves·export_allowed False 불변. [[plan-independent-review-gate]] 준수.
  **라이브 시연이 v2.1.0 실버그 2건을 잡아 v2.2.1까지 수정:** ①`_isActive`가 값 input의 `readOnly`를 제어 → `fillOne`의
  `readOnly` 가드가 enable보다 먼저라 체크 꺼진 필드를 전부 스킵(=John 증상: 값은 뜨는데 체크 안 됨→Apply 무시). 스킵 기준을
  라이브 readOnly→**맵 `ccsi_readonly`**(RF/HF/CH)로, 순서를 **enable 먼저→값**으로 수정(d9bd11a). ②드로잉 뷰어 iframe에도
  TM이 주입해 중복 빈 패널 → **`@noframes`+top-frame 가드**(f507687). +패널 헤더 버전 배지·`@updateURL`(c5df0cf, "옛 사본이
  조용히 도는" 문제 가시화). **실 CCSI 폼(8307776) 라이브 검증**: CD/I/S/O/R enable+fill·RF/HF/CH OFF·before/after 스크린샷.
  userscript **v2.2.1**, 1069 green. 🆕 이번 세션
- [x] **[quote 트랙] 리뷰용 도면 coil tag 스탬핑 (cdf6fc3 = 동시세션 2bb3524 위에, John 리포트 2026-07-22)** — quote
  `_Revised.pdf`의 CoilForge 도면에 coil tag가 안 찍혀 John이 손으로 씀. **근본원인(재현 확정):** `page.tag`는 candidate
  **또는 커버 스케줄 행**에서 오는데(`_pdf_coil_pages`) 도면은 candidate 태그로만 찍힘 → candidate 태그가 비고 태그가 커버
  행에만 있는 코일(=Salmon Creek CDXC-2)은 `page.tag`는 보여도 도면엔 태그 없음. (2bb3524는 slot.TAG 있을 때만 찍는 기반
  메커니즘 — 이 갭을 못 잡음.) **수정:** `_pdf_coil_pages`가 최종 `page.tag`(candidate→커버행→"Coil N")를 정한 뒤 도면에
  태그 없으면 스탬프(`_stamp_missing_drawing_tag`, 이미 있으면 no-op·"Coil N" 플레이스홀더 제외). frozen 무접촉·review-aid
  전용. **첫 진단(candidate 폴백)은 재현으로 틀림을 확인**하고 커버-태그 소스까지 추적해 고침(추측 커밋 회피). 신규 3테스트,
  1069 green, hunk 격리(case-neighbors 제외). **라이브 시연:** 커버-only 태그 코일 도면에 "Tag: CDXC-2" 좌상단 인쇄 스크린샷.
  실제 Salmon Creek quote end-to-end는 그 PDF가 세션 미공유라 미실행(대표 코일 도면 레벨까지 검증). 🆕 이번 세션

- [x] **[AI 3단계] Review Triage Phase 3.0 — override율 측정 도구 (af3b4fc, 2026-07-22)** — 랭킹의 핵심 신호(어느
  필드를 John이 실제로 고치나)를 원장에서 측정. John 범위확정: **측정+CLI만 지금**(랭킹 UI는 교정 축적 후), 신호는
  확장 exception 정의(fit FAIL + confidence LOW·MEDIUM + n_blocked), 통합 목표는 기존 `/api/review/project` gate(Phase
  3.1). 신규 `capture/triage.py::measure_override_rate`((tag,project) identity 그레인, `retrieve`/`observe` 규율 미러) +
  `scripts/override_rate.py` + `GET /api/capture/override-rate`(redact+안전플래그). **plan-review MAJOR-1**: `compare_observation`
  coil_uid 컬럼 부재 → 2-path 조인(coil_uid 테이블 vs mechanical_fit=run+coil_tag; ccsi=NULL tag 제외). 신규 9테스트,
  **1078 green**(exceptions_K 불변·기존 무이동), invariant-guard BLOCKER/HIGH/MEDIUM 0. **실데이터 작동 실증**: 실원장이
  0→7교정/신원 4로 이동, 도구가 실측 산출 + health 대조(coils_with_corrections 4==4). **최대 발견**: flag된 필드 override율이
  flagged-기준 전부 0인데 그 필드는 flag 안 된 다른 코일에서 override됨(S: ERV flag ↔ RHHGRC/2843 교정, 겹침 0) =
  false-negative 실증 → Phase 3.1 설계 입력. 커밋 hunk 격리(Phase 2.1/동시세션 제외). memory `review_triage_stage3.md`. 🆕 이번 세션

- [x] **[quote 트랙] quote-package 삽입 도면에 coil tag 표시 (15bcd55, John 리포트 2026-07-23)** — cdf6fc3가
  `Tag: X`를 리뷰용 SVG에 주입한 건 **정상 작동**(라벨이 실제로 SVG 안에 있음)이나, quote-package로 조립하면
  눈에 안 보였음. **근본원인(재현·좌표산술 확정):** 크롭 viewBox(110,19,…)가 라벨을 페이지 y 2.2~18.7로 매핑
  → 어셈블러(`package/assembler.py`)가 삽입 CoilForge 페이지마다 y 0~16을 **불투명 흰 배너**로 칠함 → 라벨 몸통을
  묻고 디센더 조각만 삐져나옴(=John이 본 좌상단 잔상). **수정(배너를 소유한 레이어):** `_stamp_watermark_banner`가
  coil tag를 인자로 받아 배너 위 우측에 재인쇄(그 위엔 아무것도 안 그려짐=가려질 수 없음) + `_BANNER_HEIGHT`
  16→20(묻힌 SVG 라벨 완전 덮음, 클립 대신). 빈 태그=무인쇄(never-invent). **SVG 라벨을 아래로 내리는 대안은
  경험적 기각** — 33개 시드 템플릿 좌상단 래스터 스캔이 page-relative y≈20부터 실 도면 지오메트리 검출(Ventum+
  DX/HGRH/HWC/CWC 등)=안전한 하단 배치 없음. **범위 밖:** 단일코일 `assemble_drawing_package`는 태그 미표시(22~38pt
  배너가 라벨 완전 덮어 잔상 없음, 계약에 tag 키 없음). 신규 3테스트(실 주입 라벨 측정→배너 높이 충분 단언하는
  크로스레이어 불변식 포함), **1081 green**. **라이브 서버 `/api/package/quote`(브라우저 버튼과 동일 엔드포인트·
  페이로드) 실증:** 삽입 양 페이지가 자기 태그(HHWC-1/-2)를 bbox (475.5,3.3)~(532,15.7)에 인쇄·잔상 소거·
  export_allowed False. hunk 격리(Stage 2.1/3.0 제외). 🆕 이번 세션

- [x] **[체크리스트 정렬 트랙] DX 분배기 S를 체크리스트처럼 1/8" 반올림 (1dbbf74, John 리포트 2026-07-23)** —
  체크리스트가 S1/S3/S5/S7을 `ROUND(k·CD/(n+1)·8,0)/8`(분배기 중심을 가장 가까운 1/8"로 스냅)으로 계산하는데
  CoilForge는 안 함: 슬롯/도면 레이어는 raw 몫 유지(CD=5.5,n=2 → 1.8333/3.6667), 엔진 R-034는 **정수 인치**로
  반올림(`_excel_round` → 3/6/9). John이 체크리스트에서 1.875/3.625로 읽는 코일이 도면엔 1.8333/3.6667로 그려짐.
  **같은 방정식이 세 곳에 각기 다르게 틀림(dual-path gotcha)** → 헬퍼 하나로 통일: 엔진 R-034 dist_s / `build_drawing_slots`
  (도면에 실제로 찍히는 값) / `drawing_param_resolver`(파라미터 패널). 신규 `round_eighth()`는 기존 `_excel_round`를
  재사용해 Excel의 half-away-from-zero ROUND 일치(`round_eighth(0.0625)=0.125`, Python banker's 0.0 아님).
  **범위=DX 한정:** CWC/HWC 체크리스트 시트엔 S행 자체가 없음=따를 방정식 없음(무발명), Terra V의 S=CD−Rn 분기는
  시트도 1/8 안 하므로 불변. 1/8은 비례 안 함(2·1.875=3.75≠3.625)=k마다 개별 반올림(S1에서 곱하기 금지).
  **실측:** DX NOVA B20 rows=4 → CD=5.5, circuits=2가 S1=1.875·S3=3.625(체크리스트 스크린샷 일치). 구현 고정하던
  단언 4건을 no-round/정수인치 → 체크리스트 값으로 갱신 + 신규 1건(John 케이스·비비례 1/8 함정 잠금). **1082 green**,
  golden 무접촉. 부수효과: 체크리스트 자동채움 비교표의 S 행이 mismatch→match로 뒤집힘(독립 검증 지점). hunk 격리. 🆕 이번 세션

- [x] **[RHHGRC 트랙] HGRH/RHHGRC 미러에 Leaving Dry/Wet Bulb 표시 (43215a0, John 리포트 2026-07-23)** — John:
  "RHHGRC HG 코일 데이터 매핑 완벽한가? DB/WB의 RHHGRC도 안 나타났는데 반영됐나?" **조사 결과 = DX만 반영이었음.**
  84d04f6("Max Coil Performance" DB/WB→Leaving air)이 **DX 화면 미러에만** 배선 → 카테고리별 3미러(DX/응축=HGRH/
  water) 중 응축 미러가 leaving을 못 받음. **실행으로 결함 위치 확정(도메인 스킬 '대표 케이스 추적'):** DX+HGRH 픽스처
  분석 시 PAGE1 RHHGRC-1이 `leaving_dry_bulb_f=71.29`를 **이미 추출**(추출은 `max_performance` context 매핑=코일
  무관·정상), `leaving_wet_bulb_f=None`(재열=현열-only라 소스에 WB 없음). 즉 **결함은 순수 표시 레이어**. 수정(web/app.js
  만): ①leaving DB/WB를 **코일 무관 fallbackMap**(entering DB/WB와 동일 패턴)에 배선 — DX 전용 `addDxAirFallbackFields`
  에만 있던 걸 승격, **DX byte-identical**(헬퍼가 먼저 실행·`setDcFieldAlias` 우선→범용 `addDcFieldAlias`가 값 덮지 않음)
  ②응축 미러 AIR DATA에 "Leaving Wet Bulb" 행 추가(DX 화면과 패리티, 재열은 공란 유지=무발명). 신규 회귀 2건(HGRH 추출
  71.29/WB None 잠금 + app.js 배선 문자열 assert), **1083 green**(1082+1), frozen `pdf_to_template_drawing`/paste 52필드
  표면/goldens 무접촉·review-aid only. hunk 격리(app.js 4hunk 중 내 2개만 `git apply --cached`로 스테이지, Stage 2.1
  renderCaseNeighbors 2hunk 제외). **냉수 후속 (a1c0a5b, John 요청 2026-07-24):** 동일 배선을 water 미러로 확장 —
  냉수(CWC)는 제습이라 leaving WB 의미 있음(CCWC-1=64.1/62.9 실행 확인), 온수(HWC)는 현열-only(HHWC-1=85.8/None)라
  entering WB와 동일한 `isHotWater` 게이트로 행 오프(무발명). 값은 이미 코일 무관 fallbackMap이 흘려줌 → water 미러엔
  행만 추가. 신규 CWC/HWC 비대칭 테스트 + app.js 게이트 문자열 assert, **1084 green**, 재차 hunk 격리. ⚠️ **미결:
  John 브라우저 눈확인(TR-5)** — UI 렌더는 자동테스트 불가.

- [x] **[UI/UX 트랙] John 5건 일괄 (9ad1f25·0b9a60c·9db5f10, 2026-07-28)** — RHHGRC/Ambient 실사용에서 나온 5건.
  **①Ambient 견적요청 PDF**(신규 `ambient/quote_request_pdf.py` + `POST /api/ambient/quote-request-pdf`): 패키지
  모드는 코일별 성능페이지+도면을 만들면서 **내보내기가 아예 없어** 정작 Ambient에 줄 게 없었음. 페이지는 fitz
  프리미티브로 작도(≈40행 테이블=열폭 측정+페이지네이션 필요; 도면 페이지만 `svg_to_pdf_bytes`), 라우트는 렌더된
  JSON 대신 **PDF 재-POST + 패키지 메모 재사용**(클라가 SVG 주입·안전플래그 조작 불가), `export_allowed` 하드와이어
  False. **②Project Review·Audit CCSI 패널 제거**(John: 버튼 최소화) — 백엔드·테스트는 전부 유지(capture/record.py가
  게이트를 독립 재유도). **③Drawing Notes를 CCSI 페이로드 최상위 키로** 전송 — 필드맵 계약테스트가 치수키만 허용하고
  텍스트 노트엔 unit이 없어 14번째 field로 넣지 않음. **④Leaving DB/WB 강조**(값 있을 때만 — 재열코일의 빈 WB가
  강조된 빈칸이 되면 안 됨). **⑤RHHGRC 미매핑 해소**: 회사규칙 fallback이 DX 전용 게이트에 막혀 있던 것을
  `examples/mapping_lab` case_004/005/006 **4개 실코일 전사본이 8개 구성규칙 전부 일치**하는 증거로 condensing까지
  확장. drain pan·DX 분배기는 DX 전용 유지(HGRH 시드 양쪽에 부재), System Type은 case_006 RHHGRC-1이
  "Dual-Circuit Face Split"이라 연결수 유도식으로 만들 수 없어 **unmapped 유지(무발명)**. 승인된 HGRH 기본값 7개는
  **fallbackMap 뒤에서 `addDcFieldAlias`** 로 적용 → 추출값이 항상 기본값을 이김(실증: Return Conn Size 0.625가
  "Calculate" 기본값을 이김). 부수 발견 버그 3건 수정: **Condensing Temp가 sourceLabel 때문에 액체온도를 표시**(벤더용
  화면의 오값), **선언된 행 기본값이 전부 죽어 있음**(+실코일에서 틀린 System Type 기본값 제거), **Saturated Suction이
  sourceLabel 별칭 누락으로 기본값 미도달**(눈 검증이 잡음 — substring 테스트가 구조적으로 못 보는 종류). **⑥CCSI
  Drawing Notes 실제 자동입력 배선**(9db5f10): `selectors: []`로 값만 도착하던 걸 userscript `entriesOf()` 어댑터로
  실제 채움까지 연결. CCSI 로그인은 John만 가능해 **Phase-0 캡처 없이 labelText 전략 추론** → `selector_verified:false`로
  패널이 **실제 resolve된 엘리먼트를 표시하고 경고**, John 확인 후 기록. 착수 전 **2라운드 적대적 계획검토**(BLOCKER 2·
  MAJOR 2 전건 해소, 라운드2 APPROVED), 신규 44테스트 **1129 green**, 변조테스트로 가드 유효성 증명(규칙값 변조·기본값
  순서 hoist 둘 다 실패 확인), **실 4코일 Oxygen8 submittal로 브라우저 눈검증 완료**(절차는 runbook §18).

- [x] **[UI/UX 트랙] 계산 패널 Leaving DB/WB 강조 (JS는 fb894da에 합류 · CSS c747ab4, John 요청 2026-07-29)** —
  전날 넣은 duty 강조가 **입력 행에만** 걸리고 바로 옆 계산 패널(오른쪽 열)엔 안 걸려서, John이 실제로 보는
  "Leaving Dry Bulb 53.43"은 여전히 눈으로 찾아야 했음(스크린샷에 직접 동그라미). **원인은 라벨 정규화**:
  `normalizeDcLabel`이 구두점은 지우되 **단위 글자는 남겨서** 입력 행 `"Leaving Dry Bulb(°F)"`→`leavingdrybulbf`,
  계산 패널 `"Leaving Dry Bulb"`→`leavingdrybulb` = **서로 다른 키**. `(°F)` 철자만 집합에 있어 계산 패널은 애초에
  매칭 불가였음 → 두 철자 모두 등록 + `isDcDutyLabel` 헬퍼로 양쪽 통일. 계산 패널엔 status 클래스가 없어
  `dcCalculatedValue`의 sentinel(`unmapped`/`calculated`/`review required`)로 "값 있음"을 판정(`DC_NON_VALUES`) —
  값 없는 duty 행은 강조 안 함(입력 행의 `status !== "unmapped"`와 동일 규칙). **테마 함정 하나 회피**: 배경 틴트를
  `var(--accent-soft, rgba(...))`로 넣었다가 `--accent-soft`가 **미정의 토큰**이라 폴백 rgba가 라이트/다크 양쪽에
  박히는 걸 발견 → 입력 행과 동일하게 배경 없이 accent 좌측바+볼드로 통일(CLAUDE.md의 Mechanical-Fit 흰카드 버그와
  같은 부류). 가드 3건(두 철자 등록 / 값 있을 때만 / accent 토큰 사용), **1144 green**, 실 submittal 브라우저 확인
  (Leaving Dry Bulb만 4px accent, Entering DB/WB·Air Pressure Drop·용량은 무변화). ⚠️ **커밋 격리 주의**: 동시
  세션이 같은 파일을 작업 중이라 JS 변경분은 그쪽 `fb894da`에 함께 실려 갔고, 여기 커밋은 **CSS만**. 격리 과정에서
  구 HEAD 기준으로 만든 blob을 커밋 직전 diff 검토로 잡아냄(그대로 갔으면 물코일 작업을 되돌릴 뻔) — 동시 세션이
  있을 땐 `git diff --cached`를 반드시 눈으로 확인할 것. 🆕 이번 세션

- [x] **[물코일 트랙] Terra V 물코일 도면 해금 + 데이터 매핑 복구 (fb894da, John 리포트·승인 2026-07-28~29)** —
  2949 Ferguson Theatre HWC 3개가 도면 미생성 + 패널 대량 공란. **5개 원인이 각기 다른 레이어**라 한 곳만 고치면
  나머지가 남는 구조. **①게이트 해제(John 승인)**: Terra V CWC/HWC를 보류하던 `_gate_unregistered_product_line`
  분기 제거 — Ventum+를 un-block했던 것과 같은 근거(CoilMaster water 도면 *형상*은 AHU 무관, 제품별로 다른 건
  찍히는 값뿐). 파라미터는 **이미** Terra V로 정확했고(`O2=CH−2.75` 실측 34.5) 게이트만 SVG를 지우고 있었음 =
  3층 분리가 실제로 지켜졌다는 방증. 같은 템플릿에서 Terra V≠Terra H `slot.O2` 회귀로 고정. **②추출 —
  적층 섹션**: Oxygen8 상세 그리드가 한 열에 `Coil Operating Setpoint` 위에 `Max Coil Performance`를 쌓는데
  `_detail_table_section_columns`가 **열당 컨텍스트 1개**만 등록 → 아래 블록 전체가 위 블록 라벨맵과 대조돼
  전멸. per-column `(row_index, context)` **switch**로 일반화(`_context_at_row`), 같은 `DB (F)`가 setpoint와
  **leaving** DB로 갈리는 게 핵심. **라벨맵은 이미 다 있었음** — 막힌 경로를 연 것(무발명). HWC 7필드 해금
  (Capacity 142.31·Air Vel 424·Air PD 0.07·Fluid Flow 9.69·Fluid PD 8.79·Fluid Vel 5.34·Leaving DB 95).
  **DX가 멀쩡했던 건 우연** — max-perf 행이 빈 줄에 놓여 텍스트 파서가 건졌을 뿐, 물코일은 Coil 열이 촘촘해
  한 줄에 라벨 2개가 겹치며 우연이 깨짐. **③슬롯층 `R = S`(John 확정)**: 시드 **7/7**이 `R{even}==S{odd}`
  (`O==I`도 동일). 물코일용 `return_spacing` 룰이 없고(R-022/023=DX, R-052=HGRH) 일반 안전망은 Terra V 제외 +
  DX 이름 `suction_conn_size` 의존이라 **모든 제품군에서 R이 blank**였음. water 분기가 R을 **소유**(일반망으로
  fall-through 금지 — S가 빈 R은 근거가 없음) + `slot.S` 존재 가드(un-gated 코일에서 KeyError→`{"error"}`로
  무너지는 "template not registered" 실패모드 차단). YAML 룰은 **의도적 미추가** — 이 분기가 먼저라 영구
  shadow될 죽은 규칙이 됨(Terra V `O=CH−2.75` 선례대로 슬롯층 주석). blocked 문구도 카테고리별 교정(conn size가
  **있는데** "extract에 없음"이라 오진하던 것). **④프런트 — 별도 `waterCandidate`**: `condensingCandidate`를
  넓히면 같은 함수 끝의 `addCondensingDefaultFallbackFields`가 물코일에 **냉매온도를 발명**하므로 술어 분리.
  air fallback을 `addExtractedAirFallbackFields`(재라벨만)와 `addDxReviewDefaultAirFields`(capacity 0·계산
  face velocity)로 쪼개 물코일엔 전자만 — 후자는 `setDcFieldAlias`가 추출 루프보다 먼저 돌아 **142.31→0,
  424→424.24로 덮어쓸** 뻔했음(plan-review BLOCKER-2, 직접 재확인). **⑤가정된 coil hand**: frozen
  `ctx.coil_hand or extract.hand or "LH"` + Oxygen8 커버행이 물코일 handing을 비워둠 → hand(=LH/RH 템플릿 =
  도면 전체 미러)가 조용히 가정되고 화면엔 읽은 것처럼 표시. `_flag_defaulted_coil_hand(result, **ctx**)` —
  ctx 필수(그 시점엔 기본값이 접혀 `extracted["hand"]`가 양쪽 다 "LH") + `template_input` fill 아이템 +
  `deriveSpecFromTemplate`가 `pick("coil_hand", ex.hand)`(하드코딩이라 패널이 선택을 주고도 값이 **버려지던**
  것) → RH 선택이 실제로 미러 템플릿 재선택하는 것까지 테스트. **⑥Number Of Feeds**는 백엔드가 이미 유도한
  `template_header_context.feeds`를 읽음(JS 재유도=구현 이원화 회피). **plan-review 1R REVISE**(BLOCKER 4·
  MAJOR 4·MINOR 2) **전건 반영** — 위 자책골 2건 + "DX byte-identical" 오판 + 시드 절대값 근거 오류 + `cd is
  None` KeyError + 죽은 YAML 룰 + coil_hand 4-touchpoint까지. **John 승인 필요 변경 보고·승인**: DX
  `total_capacity_mbh` 365.85→123.88(CDXC-1/2)·574.91→168.73(CDXC-3) — 옛 값은 텍스트 파서가 `Nominal Cooling
  Capacity`를 Total Capacity로 잡던 것(그 값은 `nominal_cooling_capacity_mbh`로 유지). **도면 슬롯은 DX 전부
  무변경.** 신규 13테스트 **1141 green**, frozen 3파일 무접촉, 전 값 review_required·`export_allowed` False.
  ⚠️ **미결(범위 밖·보고만)**: 물코일 `S` 공식이 시드 7개 중 **하나도 재현 못 함** — `R=S`가 그 불확실성을
  그대로 물려받음. 계획서 `~/.claude/plans/r-value-purrfect-crescent.md`. 🆕 이번 세션

- [x] **[물코일 트랙] 게이트 해제로 드러난 값 결함 5건 (ae415aa, John 리포트·확인 2026-07-29)** — fb894da가
  Terra V 물코일 도면을 렌더시키자 **한 번도 화면에 나온 적 없던 값 5개**가 전부 틀린 채로 드러남. 각각 다른
  레이어의 기존 결함이고, 게이트가 "레퍼런스 없으니 보류"라는 이름으로 **검증 없이 보존**하고 있었다.
  **① S/R = connection size** (슬롯층) — CD/2 폴백은 주석부터 "no equation to mirror"라 자백했고 시드 7장 중
  0장 일치. 연결 크기는 룰 계열의 기존 형태(DX `R-022 R1=D`, HGRH `R-052` n=1 `R=D`)이고 물코일은 항상 1HD
  단일 연결이라 그 케이스 — 새 관례가 아니다. SOP `R-068`("leave all S/R as EZ Coil default values")과도 화해:
  단일 연결의 EZ 기본값이 곧 연결 크기. **S가 CD 의존에서 해방**돼 CD 미해결 코일도 S/R을 받는다.
  **② Terra V water `O` = 2.75** (34.5 아님) — **데이텀 불일치**. `slot.O{even}`은 스터브아웃 I/O 칸(2~3인치)인데
  SOP 문구 `CH−2.75`(같은 위치의 반대편 데이텀 표현)를 그대로 써서 34.5를 찍었다. 옛 주석 "levels the return
  stubout with the supply stubout"이 답을 절반 적어둔 상태였다(수평이면 같은 수). 시드 **7/7 `O==I`**,
  `O==CH−2.75`는 **0/7**(CH 17.00~38.75), Terra V만 자기 `I`와 어긋난 유일 라인.
  **③ Drawing Notes** — 노트가 *후보*의 product/size로 게이트되는데 물코일 후보엔 없고 **도면만** full-PDF
  모델코드 스캔으로 해결 → 도면엔 vent/drain 노트, 패널엔 `unmapped`(`_engine_drawing_notes` docstring이
  "never diverge"라 약속한 바로 그 발산). 도면이 실제 해결한 값으로 재시도하도록 수정. **20개 (코일타입 ×
  제품군) 조합 전수조사 → 엔진 노트 누락 0** = 순수 전달 게이트 문제였음. 잔여 설계공백(보고만): coating 노트는
  `R-080`(DX)·`R-081`(HGRH) 전용이라 **물코일엔 규칙 자체가 없음** — 무발명 원칙상 비워둠.
  **④ Air Flow Direction** — 초안 `airflow_direction`이 **모든 코일에서 blocked**이고 라벨 정규화로 미러 행과
  충돌 → blocked가 내는 리터럴 `"review required"`가 "값"으로 취급돼 선언된 `Horizontal` 기본값이 **영구 死**.
  blocked도 `unmapped`처럼 선언된 기본값에 지도록 수정(기본값 없는 행은 불변).
  **⑤ Coil Hand = `not defined`** (John: LH 단정 금지) — hand가 틀리면 값 하나가 아니라 **도면 전체가 좌우
  반전**이라, 그럴듯한 기본값이 빈칸보다 위험한 유일한 필드. 도면은 검토 보조물이므로 LH 아트워크로 계속
  렌더하고 배너가 미기재를 명시하되, **데이터 필드는 hand를 주장하지 않는다**(그림/데이터 역할 분리).
  덤으로 실사용 결함 2건: hand 레버가 `coil_hand_defaulted` 게이트라 **값을 채우는 순간 사라져 RH→LH 오클릭을
  되돌릴 수 없었고**(설정 행동이 되돌릴 유일한 수단을 제거), `current_value`가 `"LH"`인데 선택지는
  `["Left","Right"]`라 **피커에 현재값이 선택되지 않았다** → 도면 있으면 상시 제공 + 어휘 정규화.
  회귀 8개(증상별 가드 + **도면 노트와 패널 노트가 갈라지면 실패하는 불변식 테스트**), **1150 green**,
  frozen 3파일 무접촉, 전 값 `review_required`·`export_allowed` False.
  **John 눈확인 통과 + 푸시 완료 (`e548475..5930fc0`, 2026-07-29)** — 브랜치 `claude/ambient-supplier`,
  다른 세션의 capture/tuning 미커밋 작업은 격리.
- [x] **[제출물 파싱 트랙] 2968이 드러낸 커버/상세 오독 2건 (971e2e4, John 리포트 2026-08-01~02)** — 실 제출물
  하나(2968 HTS Houston / College of the Mainland, 124p)에서 결함 2개. 레이어는 둘 다 **source extraction**
  (`pdf_intake.py`) — 게이트·기하·렌더러·템플릿 카탈로그 무접촉.
  **①HGBP 오탐**: `_package_hgbp_pages`의 전체 문서 스캔이 p.12 컨설턴트 스펙의 "insulated hot gas bypass
  **line**"(현장 냉매 배관 서술)에 걸려 패키지 전 DX 코일에 HGBP를 찍었고, TERRA H인 CDXC-1이
  `_gate_hgbp_unsupported_product_line`에 막혀 도면 보류. 게이트는 제 역할을 한 것(Nova/Ventum-H 기하가 Terra
  태그로 나가는 걸 차단) — 결함은 상류. 고침: **스캔 창을 커버 페이지 이후로 제한**(`cover_page` 인자) +
  정규식에서 **`<토큰> line/pipe/piping` 배관 서술형 배제**. 상한 없음 — 어더가 코일 행 없는 커버 연속
  페이지에 앉는 케이스를 기존 테스트가 문서화. 긍정 마커(부품번호/VALVE/adder) 요구는 **폐기**: 문제의 산문이
  이미 `expansion valve`를 포함하고, 미탐(잘못된 Header-N 도면 무음 링크)이 오탐(눈에 보이는 보류)보다 나쁘다.
  **②코팅 미추출**: 코팅이 상세 블록의 별표 주석(`*Finkote2 Epoxy Coil Coating*`)으로 적혀 라벨/값 패턴이
  못 읽었고 → Direct Coil 기본값 `Plain` + **`only_when: coating_set`인 R-080/R-081 "Do Not Coat Last 5-6
  inches..." 노트 전면 누락**. `_DETAIL_COATING_ANNOTATION_RE` 신설(닫는 별표 필수 → 한쪽만 있는 각주
  `*Separate electrical connection required for heater` 배제), `normalized_line`에서 읽어 host 줄 무소비
  (p.27은 Coil Weight와 공존, 표 경로가 준 `32.94` 유지).
  **실앱 검증**(수정 코드 로드 인스턴스에 브라우저 실업로드): `Plain`→`review required`, Drawing Notes에
  `Do Not Coat Last 5-6 inches of Distributor Extensions.` 추가, Drawing `HGBP (special) — no matching
  template / withheld`→`DX / LH / Header 3 — logic-derived (coilmaster_dx_lh_header3)`, `DIMS READ 0`→`3`.
  업로드 10MB 상한 때문에 UI는 8p 추림본, **원본 124p 무트리밍은 워크플로 함수로 별도 재확인**(동일 결과).
  신규 8테스트, **1188 green**. 곁가지: ⓐ함께 손댄 `web/app.js` 리뷰노트 개선은 렌더 경로 부재로 죽은 코드임을
  DOM 스윕으로 확인하고 **원복**(diff 0) — 화면 개선은 전부 Python 쪽 산물. ⓑUI 검증이 프런트의 자동
  `/api/checklist/fill`을 타 Downloads에 .xlsx를 쓰고 journal 3줄을 남김(클릭은 "Analyze PDF" 하나뿐) →
  승인 후 전량 삭제. ⚠️ John의 :8011은 `--reload` 없음 → **재시작해야 반영**. 🆕 이번 세션

- [x] **[코팅·검토표면 트랙] 브라우저 교정이 산출물에 도달하지 못하던 결함 2건 (b44fdd0, 2026-08-06)** —
  TR-9(derive가 붙여넣기 52필드 표면을 재생성 안 함) + 템플릿에 박혀 있던 코팅명. 상세는 상단 갱신 노트 참조.
  신규 3테스트 파일 **1237 green**(+49), frozen 무접촉, plan-review 2R(1R: BLOCKER 1·MAJOR 4·MINOR 5 전건 반영 →
  2R APPROVED), 실 제출물 라이브 검증 + **John A/B 탭 눈확인 통과**. 부수 성과: 코팅 노트가 슬롯이 아니라
  **크롭 영역 주입**으로 구현돼 3장이 아니라 **22개 버킷 전부**에서 동작한다.

## 🧪 TR (Test Required — 사람 눈확인 부채, 자동 green과 별개로 추적)
- [ ] **[TR-1] Phase 1 편집 Drawing Params 브라우저 눈확인 (John)** — 서버(:8011) 실행 중 + 브라우저 열림 +
  바탕화면 `CoilForge_TEST_CDXC-1.pdf`(DX) 스테이징 완료(2026-07-16 세팅). 절차: PDF 드래그→분석 → "Manual
  drawing parameters" 체크 → CD 편집(예 3.75→9.5)+이유 → "Update drawing" → **도면 인쇄 CD가 9.5로 갱신 +
  호박색 "✎ Manually overridden: CD" 배너 + 리뷰/watermark 유지** 확인. 자동검증은 완료(972 green·invariant
  clean·실 HTTP CD 9.5 반영·before=5.5 event-source); 남은 건 실 렌더의 사람 눈 확인뿐. **Phase 2는 이 TR과
  병행 착수(John 2026-07-17 승인)** — 반영/캡처 백엔드는 Phase 2가 재사용만 하므로 눈확인 결과가 Phase 2 코드를
  되돌리지 않음.
- [ ] **[TR-2] Phase 2 편집 spec + 3자 뷰 브라우저 눈확인 (John)** — ⚠️ 서버 재시작 필요(Phase 2 코드 반영).
  절차: 코일 분석/derive → "Spec data" 패널에서 필드(예 Rows) 자물쇠 열기 → 값 편집+이유 → Save → 도면 재계산
  확인 + 코일 아래 **"Three-way review"** 테이블에서 submittal/CoilForge/engineer 3열 green/red 확인(특히 override한
  drawing param의 CoilForge 열이 기계 원제안을 보이는지). 자동검증 완료(978 green·invariant clean·실 HTTP); 남은 건
  사람 눈 확인.
- [ ] **[TR-3] CCSI 자동 체크마크 실 폼 fill self-test (John)** — 메커니즘은 실 폼(8307776)에서 라이브 검증 완료(enable+fill·
  RF/HF/CH OFF); 남은 건 John이 TM 스크립트를 **v2.2.1**로 갱신 후 자기 워크플로로 end-to-end 확인. ⚠️ TM Utilities→Install
  from URL `http://localhost:8011/static/ccsi/ccsi_autofill.user.js`로 갱신(패널 헤더 "v2.2.1" 확인) 또는 북마클릿 재드래그.
  절차: 코일 분석 → "Copy CCSI autofill payload" → CCSI Direct Coil 폼(로그인)에서 필러 열기 → Load → "Fill all
  reviewed". 확인: ① 각 편집 필드의 `_isActive`가 자동 ON + 값이 채워지고 저장/네비게이션 미발생 ② RF/HF/CH 체크마크
  OFF 유지 ③ HGBP 코일에서만 ApplyVDConstraints ON. **실 폼을 수정**(unsaved)하므로 John이 직접 실행(Claude가 자동
  실행 안 함); CCSI Save("Apply Changes")도 John 몫. 자동검증 완료(1058 green·plan 2R·라이브 DOM 캡처).
- [ ] **[TR-4] quote-package 도면 coil tag + DX S 1/8 반올림 브라우저 눈확인 (John)** — ⚠️ 서버 재시작 완료(둘 다
  반영). 절차: DX 코일 포함 quote PDF 드래그→분석(⚠️ `pdfCoilPages` 클라 캐시라 **재분석 필수**) → "Build quote
  package". 확인: ① 삽입된 CoilForge 도면 페이지 **상단 배너 우측에 `Tag: <코일태그>`** 표시 + 좌상단 잔상 소거
  ② DX 도면의 **S1/S3(다회로면 S5/S7)이 1/8 단위**(예 1.875/3.625)로 그려짐 ③ "Coil Checklist Auto-Fill" 비교표에서
  **S 행이 match(green)**. 자동검증 완료(1082 green·라이브 `/api/package/quote` 실증); 남은 건 John 실 파일 눈 확인.
- [ ] **[TR-5] RHHGRC + 냉수 미러 Leaving DB/WB 표시 브라우저 눈확인 (John)** — ⚠️ 서버 재시작 필요(app.js 반영) +
  `pdfCoilPages` 클라 캐시라 **재분석 필수**. 절차: RHHGRC(HGRH)·냉수(CWC)·온수(HWC) 포함 submittal 드래그→분석 →
  각 코일 리뷰 페이지 선택 → 미러 **AIR DATA** 확인: **① HGRH "Leaving Dry Bulb"에 값 표시**(예 71.29, 종전 공란)
  **② CWC "Leaving Wet Bulb" 행에 값 표시**(예 62.9) **③ HWC는 Leaving WB 행 없음**(현열-only, 게이트 오프=정상).
  자동검증 완료(1084 green·추출 71.29/62.9 실행 확인·DX 무회귀); 남은 건 실 렌더 사람 눈 확인.
  **부분 해소(2026-07-28)**: RHHGRC 미러에 Leaving DB/WB **행이 존재함**은 실 submittal(2862 Avon)로 확인. 다만 그
  코일은 leaving 값을 명시하지 않아 `unmapped` 표시 → **값이 실제로 찍히는 화면은 미확인**. 71.29/62.9가 나오는
  submittal로 한 번 더 확인 필요.

- [ ] **[TR-6] CCSI Drawing Notes 셀렉터 라이브 캡처 (John)** — 배선은 완료(9db5f10)이나 CCSI 로그인이 John 전용이라
  Phase-0 캡처를 못 했고, 현재 labelText **추론** 셀렉터로 동작(`selector_verified:false`). 절차: coil.ccsi.ie 로그인 →
  Direct Coil 코일 열기 → 북마클릿/유저스크립트로 CoilForge 페이로드 붙여넣기 → 패널의 **"⚠ UNVERIFIED target
  <textarea#...>"** 행에서 resolve된 엘리먼트가 진짜 Drawing Notes 칸인지 확인 → 맞으면 그 `#id`를
  `web/app.js::ccsiDrawingNotes`의 `selectors` **맨 앞**에 넣고 `selector_verified` 제거. 틀리면 채우지 말고 보고.

- [x] **[TR-7] 물코일 도면 + 데이터 매핑 브라우저 눈확인 — ✅ John 통과 (2026-07-29)** — ⚠️ `run_server.bat`은 `--reload` 없음 →
  **서버 재시작** + `pdfCoilPages` 클라 캐시라 **재분석 필수**. 절차: 2949 Ferguson Theatre submittal 드래그→분석
  → HHWC-1 선택. 확인: **①도면이 나옴**(`coilmaster_hwc_lh`, 종전 공란) **②`R`이 빨간 blocked가 아니라 `S`와
  같은 **1.6875** **③AIR DATA: Face Velocity **424**(계산값 424.24 아님)·Leaving Dry Bulb 95·Total Capacity
  **142.31**(0 아님) **④FLUID DATA: Fluid Flow 9.69·Fluid PD 8.79 **⑤OPTIONS**: Header/Connection/Casing 계열이
  회사 기본값으로 채워짐(종전 전부 unmapped) **⑥Coil Hand "LH ⚠ 가정값" 배너 + LH/RH 수동 선택 → RH 고르면
  도면이 미러됨** **⑦냉매 필드 없음**(물코일에 발명 금지) **⑧Air Flow Direction은 "Horizontal"이 review-required
  스타일 = 정상**(제출물이 명시 안 하는 값의 정직한 상태, 버그 아님). **대조군 CDXC-1**: Total Capacity가
  123.88로 바뀐 것 외 값 불변 + 도면 무변경. 자동검증 완료(1141 green·실 PDF 12개 수용기준 전부 OK); 남은 건
  실 렌더 사람 눈 확인.

- [x] **[TR-8] 오버라이드 후 체크리스트 자동 재실행 — ✅ 실 2901로 통과 (2026-07-30)** — 실 제출물
  (`Havtech - 2901 - CAP1 Ball FAC`, 83p/14.2MB, Rev0)을 앱의 진짜 인테이크(`#pdf-intake-file`)에 넣어 6코일
  (CDXC-1/2/3 + RHHGRC-1/2/3, TERRA H 040) 검출 → CDXC-1 `TF` **1.625→2.0** + 사유 → `Update drawing`.
  호출 순서 실측 `checklist/fill → coil-drawing/derive → checklist/fill`(디바운스 재실행 자동 발화). 확인:
  도면 SVG `2.0 TF` + 타이틀블록 반영, 배너 `✎ Manually overridden: TF`, 요약줄 `1 manual override(s) applied`,
  헤딩 `CDXC-1 DX · 1 mismatch · 1 overridden`, TF 행 `2 / 1.625 / ✎`(툴팁에 사유), **대조군 CDXC-2는 수식·
  코멘트 무변경**. `.xlsx` 실측: `C27` 수식→**상수 2 + 코멘트**, `C63(CH)` **26.125→26.5**, CD/S1/OAL 불변.
  **테스트가 못 잡은 결함 2건을 이 실행이 잡아 그 자리에서 수정(04ea72a)**: ①`CH = C13+C27+C28`이 TF를
  참조해 파일에선 26.5로 움직였는데 **패널은 26.125/26.125 ✓** — 앱만 보고 승인하면 엔진과 어긋난 시트를
  통과시킴 → 2차 재계산 뒤 재판독(오버라이드 행은 제외, 안 그러면 override가 자기확인 match가 됨) → 이제
  `CH 26.125/26.5 ✗`. ②재실행마다 `... (2).xlsx`가 쌓여 어느 게 최신인지 불명 → 같은 파일 교체(Excel에
  열려 있어 교체 불가일 때만 번호 폴백) + **같은 경로를 가리키던 캐시 항목 축출**(안 하면 오버라이드 없는
  finalize가 오버라이드본을 파일링). 재검증 후 1178 green. 폰 확인 페이지(1차 실행 근거):
  `claude.ai/code/artifact/976a22c8-3438-4c5f-bb14-7e91d2f4e2cc`

- [x] **[TR-9] derive가 Drawing Notes·엔진 치수를 재계산하지 않음 — ✅ 해소·John 눈확인 통과 (b44fdd0, 2026-08-06)** —
  조사 결과 **자물쇠가 둘**이었다: 백엔드가 붙여넣기 표면을 아예 반환하지 않았고(derive 29키 중 부재), 프런트도
  derive 응답으로 그 표를 다시 그리지 않았다(코일 전환 시에도 `page.workflow`의 analyze 시점 값을 재판독). 한쪽만
  고쳤으면 테스트는 초록인데 화면은 그대로였을 것 — 직전 세션의 "죽은 코드" 사건과 대칭. 재생성에 필요한 원본
  후보를 브라우저가 왕복 전달하되 **신원은 서버가 tag로 강제**(후보와 도면이 서로 다른 경로로 도착하므로 교차
  오염이 잡힌다; 3단 fail-closed + 모든 스킵에 사유 표시). plan-review 1R BLOCKER = **Tier-B override가 엔진
  출처로 위장 저장**(analyze는 override가 없어 그 헬퍼가 사람 값을 만난 적 없었음) → override 키 제외. 2R
  APPROVED. 아래 원 기록 보존:
  **[원 발견 기록 2026-07-30]** —
  228d731의 CD 회귀와 **같은 계열**(analyze에만 배선된 후처리)을 찾으려 analyze
  `_run_candidate_to_drawing_payload` vs `derive_coil_template_drawing` 후처리를 1:1 대조한 결과. 게이트 5종·
  플래그 2종·`_clean_template_svg`·`_attach_parametric_schematic`·`build_manual_fill_plan`은 양쪽 다 있고,
  **`_engine_drawing_notes` + `_engine_drawing_dims`만 analyze 전용** — derive는 `spec["panel"]`을 그대로
  되돌려줄 뿐이라 붙여넣기 52필드 세트의 Drawing Notes·엔진 치수가 **analyze 시점 값에 고정**된다.
  헤드리스 실측: `_engine_drawing_notes(coating='HERESITE')`는 R-080 `Do Not Coat Last 5-6 inches...`를 넣지만
  `derive_coil_template_drawing(coating='HERESITE')`의 반환 키는 `panel`뿐이고 노트는 재계산되지 않음.
  증상 예상: ①브라우저에서 coating을 고쳐도 코팅 노트가 안 붙음 ②게이트됐던 코일을 제품/사이즈 픽으로 풀어도
  붙여넣기 세트의 노트·치수는 unmapped 유지. **메커니즘은 코드+헤드리스로 확인, 브라우저 증상은 미재현** —
  착수 시 재현부터. 고칠 때 주의: analyze는 후보에 product/size가 없으면 도면이 해결한 값으로 **재시도**하는
  분기(1798~1807)를 갖고 있으므로 derive에도 같은 폴백이 필요하고, `distributor_notes`(도면 분배기 콜아웃)와
  섞으면 안 됨(전용 manufacturing_options 키).

## ▶️ 지금
- [ ] **2단계 Case Retrieval — 원장 채우기 단계** (엔진은 Phase 2.0으로 구축·커밋 완료, 66087fd) — 다음 걸음:
  **실사용으로 코퍼스 + 교정 축적**. 현황 **46/50 · 교정 0**. 착수조건 n≥50까지 4개 부족하나, **개수보다
  교정이 진짜 관건** — John이 "거의 안 고침"이라 교정 0은 정직한 수치(캡처 버그 아님). Stage 2가 실제로 유용해지려면
  앞으로 코일 조정을 **브라우저 edit(Update drawing / Spec data)**로 해야 `correction`이 쌓임. `submittals/` 12개
  소진(재분석 dedup); `Case/` 레퍼런스는 미투입(오염 방지). Phase 2.1(가중치·min_shared_axes 튜닝 + 이웃 품질
  눈검증 + 브라우저 "이전 교정" 패널)은 **교정이 실제로 쌓인 뒤** 착수(지금 하면 헛작업).
  **2026-07-29 보강:** 물코일 트랙(fb894da)이 이 항목을 직접 돕는다 — HWC/CWC가 이제 도면·패널까지 정상
  작동하므로 물코일도 브라우저 edit 대상이 됐고(종전엔 도면조차 없어 교정이 원천 불가), Coil Hand 수동
  레버가 새 correction 축을 하나 더 연다.
  **2026-07-30 보강:** 0c8bb84도 같은 방향으로 돕는다 — 브라우저 edit이 이제 도면뿐 아니라 체크리스트·주문용
  .xlsx까지 일관되게 끌고 가므로, "고칠 거면 브라우저에서" 라는 유인이 실제로 생긴다(종전엔 브라우저에서
  고쳐도 체크리스트가 어긋나 손으로 다시 맞춰야 했음 = 교정을 원장에 남길 이유가 약했음).
  **2026-07-31:** Phase 2.1이 드디어 커밋됨(343b972 · f54d5f1) — 이웃 패널의 질의측 추출과 A5 튜닝 하네스가
  이제 브랜치에 있다. 가중치 **채택은 여전히 미배선**(John eyeball 후 1줄)이고, 착수 조건은 그대로
  **교정 축적**이다. 덤으로 `/derive`가 클린 체크아웃에서 500이던 파손이 이 커밋으로 복구됐다.
  **2026-08-06 보강:** b44fdd0이 "브라우저에서 고칠 이유"를 한 겹 더 만든다 — 이제 브라우저 edit이 도면·
  체크리스트뿐 아니라 **붙여넣기 52필드 표면까지** 함께 끌고 가므로, 손으로 고친 값이 산출물 전체에 일관되게
  반영된다(종전엔 표가 analyze 시점에 얼어 있어 결국 손으로 다시 맞춰야 했고, 그건 교정을 원장에 남길 이유를
  약하게 만들었다). coating이 새 edit 축으로 열린 것도 같은 방향.
  ⚠️ **오염 주의(2026-08-06 실측)**: 검증용 실행이 `PO_Release_Case/journal/coil-2026080{5,6}.jsonl`에
  `intake_drawing`/`checklist_filled`/`coil_manual_fill` 라인을 남긴다(project=None). 8/6 13:58 라인 2개는
  John의 실 2755 Gumbo 실행이고 그 뒤 7개가 검증분 — **append-only 저널이라 삭제하지 않았다**. 코퍼스 카운트를
  읽을 때 project=None 검증 실행을 어떻게 다룰지는 미결(Stage 2 착수 시 판단 필요).
## ⬜ 앞으로
- [ ] **1a′ (분리됨·보류)** — ccsi-compare에 코일 tag 스레딩(프론트 `web/ccsi/` + app.js → 백). 지금은
  `compare_observation`의 ccsi 행이 coil_tag NULL 고아행 → 3·4단계가 조인 못 함. CCSI 스킬 체인과 얽힘.
- [~] **3단계 Review Triage** (3~6개월, 양성 200~400) — exceptions_K **랭킹**(스킵 금지 — false negative =
  틀린 값 자동승인). 실제 override율은 1단계가 처음 알려줌 → **그 숫자를 보고 착수, 미리 약속 안 함**
  - [x] **Phase 3.0 측정 도구 (af3b4fc)** — `measure_override_rate`가 그 override율을 원장에서 산출(위 ✅ 참조).
    실데이터가 flag≠교정 신원 disjoint를 드러냄(false-negative 실증).
  - [ ] **Phase 3.1 랭킹 (보류)** — 착수 트리거: 교정 더 축적 + **설계결정** — flag된 코일만 랭킹하면 위 disjoint로
    진짜 override 코일을 놓치므로, `corrected_total−corrected`(unflagged 교정) 신호 노출 여부 John 판정 후. 그다음
    `/api/review/project` gate에 deterministic severity 랭킹 + inert weight seam(측정값 배선은 1줄, Stage 2.0 패턴).
- [ ] **4단계 Rule Observatory** (6~12개월) — 76개 HIGH를 *선언*에서 *측정*으로. ⚠️ **표본 편향이 최대
  위험** — John은 flag된 코일만 보므로 안 보이는 곳의 틀린 규칙은 영원히 완벽해 보인다. 1d 감사샘플이
  유일한 통계적 수단; 모든 수치는 "리뷰 조건부" 라벨
- [ ] **5단계 Auto-YAML** — correction 패턴 마이닝 → evidence_refs 붙은 YAML diff 제안 → replay 검증 →
  John 승인. **제안 규칙은 MEDIUM 진입** = 기존 confidence gate가 공짜로 안전을 보장(자동으로 안 그려짐)
- [ ] **6단계 Format-Agnostic Extraction** — **의존성은 1단계뿐, 순서상 6일 뿐** (타사 서밋털 수요 생기면
  앞당김). 여기가 진짜 ML(지각) — 원장의 실패 코퍼스가 곧 테스트셋
- [ ] **7단계 Commercial Intelligence** — `outcome` seam만 유지, 비워둠 (John 확정). 착수 시
  `raw_private_data_returned:False` 철학 재검토 필요

- [ ] PR #3 리뷰·머지 (claude/ccsi-autofill → main) — ⚠️ 2026-07-07 병합 시도 = CONFLICTING: drawing engine 5파일 충돌(main Phase 2.6–4b 라벨/V3 vs ccsi 병렬 피처 S1·R2·HDx1·AIRFLOW·Terra V·Ventum+, 양쪽 고유). 통합 병합은 크고 위험 → **drawing 세션과 조율 후 진행 (보류)**
- [ ] CCSI Tier 1 실 mutation 라이브 end-to-end 1회 (미완) — 2026-07-05 이후 우선순위 하향.
  **프리플라이트 드라이런 (2026-07-15, /ccsi-preflight, mutation 0건)**: CoilForge측 GREEN — 서버 up·
  정적 맵 25셀렉터(13 base+12 멀티헤더)·브릿지 전역 3개(`coilforgeCoils`/`coilforgeCcsiCompare`/
  `coilforgeSelectCoil`) 로드 시 resolve. **게이팅 NO-GO = CCSI 로그인 탭 부재(John 몫)**. John 로그인
  후 T2 핸들러 typeof(`CopyRevision` 등 5)+코일 로스터 태그매칭을 마저 검증하면 GO 판정. Terra와 파일
  무충돌(브라우저측+read-only)로 병행 진행한 작업.
- [~] **Terra 스플릿 [EXT] — 점진적 병행 (John 2026-07-14 방식 확정)** — `TERRA` → `TERRA_H` + `TERRA_V`
  (Phase 1·2 완료; **Phase 3는 검증 후 의도적 보류** — 아래 참조)
  - [x] **Phase 1 (9be71fe)** — `TERRA_H`/`TERRA_V`를 1급 `ProductFamily`로 추가 + `prepopulate` 진입점에서
    `TERRA`+`terra_variant`로 정규화(model_copy). 모든 `[TERRA]` 룰·`product==TERRA` 직접검사(R-061v/R-065v)·
    R-076 size_key·terra_variant 분기 전부 무변경 동작; `TERRA_H_C` 서브변형 보존. 신·구 형태 결과 동일성
    테스트로 검증(DX 노트/스페이싱 + CWC 직접검사 경로), 829 green. **파운데이션만** — resolver는 아직 TERRA 발화.
  - [x] **Phase 2 (6bc5c76)** — resolver가 TERRA_H/TERRA_V를 **발화**(`_PRODUCT_LINE_RESOLUTION` family 요소 +
    `_PRODUCT` 키 2개). blast radius 검증 결과 외부 직접 판독자는 `mechanical_fit`뿐(`request.product_type.value`를
    정규화 前 읽어 R-077/R-078/application을 TERRA-키로 조회) → `_coarse_terra_family()` 헬퍼로 **조회 내부에서만**
    정규화(리포트 display는 TERRA_H/TERRA_V 유지=구분 노출). 나머지(템플릿 선택·R-076/74/77 키·omission gate·UI·CCSI·
    스키마) 전부 SAFE(엔진 정규화 셔틀 덕). YAML·픽스처 변경 0건. 적대적 재검토(GO-WITH-CHANGES)로 테스트 라인 정정 +
    정규화를 lookup 헬퍼로 이동. 830 green.
  - [~] **Phase 3 (DEFER — John 2026-07-15 검증 후 보류)** — 작업 자체는 `[TERRA]` 룰 25개를 리키 + 엔진 테스트
    ~22 사이트 마이그레이션 + coarse `TERRA` 은퇴 + 정규화 셔틀을 group-aware `_applies`로 진화(최종 목표상태).
    **왜 보류:** 두 Explore 에이전트로 엔진·YAML·mechanical_fit 대조 검증 → Terra는 기능 정상(값 정확, 830 green),
    셔틀은 진짜 no-op(숨은 취약점 없음), 외부 정규화-前 판독자 `mechanical_fit`은 `_coarse_terra_family()` 방어를
    실제로 갖춤. Phase 3는 **사용자 이득 0**(도면·값 무변경)인 순수 표현 정리인데 **회귀 리스크는 실재**: ①값 뒤집힘 —
    R-012/R-014/R-021/R-027/R-042/R-045b/R-061/R-065 8룰은 `[TERRA_H,TERRA_V]` 단순치환 시 Terra V가 last-writer-wins/`_v`
    은퇴로 H 값으로 되돌아감(반드시 `[TERRA_H]`로만 좁혀야). ②키 단절 — R-077/R-078은 `TERRA` 키만 있어 coarse 은퇴 시
    fit/drain-pan 조회 miss → Terra 코일 `CANNOT_EVALUATE`. 무이득+고위험이라 [[project_review_gate]]·Simplicity First에
    정면 위배.
    **재개 트리거:** 템플릿 선택이 Terra H/V로 갈라져야 하거나, Terra V 전용 casing/water 레퍼런스가 시드돼 variant가
    first-class 표현을 실제로 요구할 때 — 그 작업과 묶어 원자적으로. (리키 분류: 단순치환 5 / variant 1:1 12 / 주의 8 —
    상세는 memory `terra_split_phased.md`.)
- [ ] **[Ambient 트랙] Phase 6 엑셀 write-back** (`ambient/excel_writer.py`) — 실제 `Coilmaster-Ambiant
  Dynamics Coil Comparison.xlsx` 템플릿 라벨/열 전사 필요(**John 제공 대기**). `checklist/excel_writer.py` 미러.
- [ ] **[Ambient 트랙] Material 문자열 false-positive 정규화** — baseline이 `"Copper - 0.016 Plain"`처럼
  재질+두께+표면을 한 문자열로 저장 → Ambient `"Copper"`와 differ(정직하나 노이즈). 재질 토큰만 비교(John 확인).
- [ ] **[Ambient 트랙] circuits 검출 + baseline 용량 소스 + % 허용오차 확정** — 현재 circuits 기본 1,
  킷 선택 Ambient 폴백, review-only tolerance. John 결정 후 정밀화. (상세: `docs/SESSION_LOG.md` 2026-07-16)
- [ ] **[3058 트랙] Phase 3 — DIST EXTENTION 정렬** — R-033을 체크리스트 `C59=IF(SIZE in{H05,H10},17,6)`에
  맞춤(현재 상수 6, H05/H10=17 누락) + 체크리스트 compare에 CoilForge 값 노출(현재 blank). John: "체크리스트에 6 push".
- [ ] **[3058 트랙] Phase 4 — 코일별 product/size 오탐지 조사** — CDXC-3=VENTUM_H/H10 등 혼재(일부 전역폴백).
  오탐지면 R-074 casing W/H + 위 C59(17 vs 6) 틀어짐. `detect_product_and_size` per-coil 추적, 실 유닛 대조(John/BOM).
- [x] **[물코일 트랙] coating 노트가 물코일에 없음 — ✅ John 판정 종결 (b44fdd0, 2026-08-06)** —
  John: **"물코일엔 coating이 절대 안 들어간다"** → R-080(DX)/R-081(HGRH)이 물코일을 제외하는 것은
  **미해결 공백이 아니라 확정 설계**로 종결. 동작은 그대로이나 **의미가 확정**됐다(그게 도메인 오너 판정의 일).
  덤으로 한 걸음 더: 물코일에 coating이 **추출되던 경로 자체를 막았다** — 상세 블록은 경계가 서로 번지므로
  (`_DETAIL_COATING_ANNOTATION_RE` 주석이 기록한 실제 현상) 물코일이 이웃 코일의 coating을 주워올 수 있었다.
  `COIL_COATING` 리더가 **3개**(테이블 시드·별표 각주·라벨 줄)라 개별 게이팅은 네 번째 리더가 구멍을 다시 여므로
  **추출 마지막 한 지점**에서 제거. 코일 종류를 모르는 블록은 무접촉(추측으로 데이터를 버리지 않음).
  **수동 입력은 의도적으로 허용**(John 확인) — 추론을 거절하는 것과 엔지니어의 명시적 결정을 거부하는 것은 다르며,
  그 비대칭을 나중에 "버그"로 오인해 막지 않도록 테스트로 고정했다. 아래 원 기록 보존:
  **[원 기록]** — `R-080`은 `coil_type: [DX]`,
  `R-081`은 `[HGRH]` 전용이라 CWC/HWC는 coating을 지정해도 노트가 늘지 않는다(HERESITE 실측 확인).
  20조합 전수조사에서 **유일하게 남은 설계 공백**. 규칙이 없는 것이라 지어내지 않음 — 물코일에도
  coating 제외 노트가 필요한지 John 확인 후 R-080/081 범위 확장 여부 결정.
  **2026-08-02 승격 — 이론 → 실전:** 971e2e4가 별표 주석(`*Finkote2 Epoxy Coil Coating*`)에서 coating을
  실제로 추출하기 시작했다. 종전엔 제출물에서 coating이 **거의 채워지지 않아** 이 공백이 사실상 잠자고
  있었는데, 이제 CWC/HWC를 포함한 제출물이 coating을 명시하면 **DX/HGRH만 노트가 늘고 물코일은 조용히
  안 는다** = 같은 패키지 안에서 코일 타입에 따라 노트가 갈리는 게 눈에 보이게 된다. 2968은 DX+HGRH만이라
  드러나지 않았음. 물코일이 섞인 코팅 제출물이 들어오기 전에 John 판정을 받는 편이 낫다.
- [ ] **[코팅 트랙] `Coil Coating: <값>` 라벨 패턴이 줄 끝까지 삼킴 (2026-08-06 라이브가 노출, 상류 미수정)** —
  EZ 도면은 다음 열 라벨을 값에 바로 붙여 인쇄하므로 `ElectroFin Evap Temp 45` 같은 값이 **정본에 그대로 저장**된다.
  b44fdd0은 **도면 노트를 만들 때만** 어휘로 정규화했으므로, 붙여넣기 표/체크리스트의 Coil Coating 칸은 여전히
  오염된 문자열을 보여준다. 근본 수정은 `_FieldPattern("COIL_COATING", ...)`의 탐욕적 캡처를 좁히는 것인데,
  다른 라벨 패턴과 같은 형태라 회귀 범위 확인이 선행돼야 함(값이 인쇄되지 않던 동안 잠자던 결함).
- [ ] **[코팅 트랙] 커버 라인아이템 coating 인식이 실 사례로 미검증** — `_package_coating`은 HGBP 어더 패턴을
  그대로 따랐고 어휘 앵커로 안전하지만, **커버에 coating이 적힌 실 제출물을 아직 못 구했다**(리포의 12개 제출물
  전수 스캔에서 coating 언급 0건). 그런 파일이 들어오면 스캔 창·우선순위(코일 상세 블록 우선)를 실물로 확인할 것.
- [ ] (DEFER) 파라메트릭 도면엔진 SVG/DXF/PDF — MVP는 템플릿-우선, 명시 승인 전까지 보류
