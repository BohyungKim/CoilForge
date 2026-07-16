# 🗺️ CoilForge 로드맵
> 목표: 코일 입력(Direct Coil 폼 / submittal / 스캔 PDF) → 검토용 도면 + 붙여넣기용 필드셋 + 검증·호환 리포트
> 마지막 갱신: 2026-07-16 (Capture Ledger 5b 완료 — coil_manual_fill 저널 복구, 5c 대기)

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

## ▶️ 지금
- [ ] **5c — 우회 라우트 어댑터**. "각 1줄"이 아님(shape 이질적, 대부분 결과를 이름에 바인딩조차 안 함);
  `/api/review/build-packet`은 `workflow_input` 조건부바인딩 `UnboundLocalError` 함정;
  `/api/ccsi-compare`는 body에 코일 신원이 없어 **어댑터로 불가** → 1a′ 프론트+백 tag 스레딩
- [ ] **1b** — H4 + **D2**(`previous_value` 복구; Tier-B baseline = `parameter_set_from_template_drawing`을
  overrides 없이 재호출 → 멀티헤더/ZD 자동해결) + `correction` 테이블. **1단계 필수** — 그 전 correction은
  "무엇을→무엇으로"의 절반이 영구히 빈다
- [ ] **1c** — `FieldResult.rule_id`(`exclude=True`) + 27개 생성자 + H3/H3b/H5 + `rule_firing`/`engine_call`/
  `rule_snapshot`. **유일한 엔진 침습** (페이로드는 바이트 동일). 착수 전 phase5 워크트리 병합 여부 확인
- [ ] **1d** — `/api/capture/health` + `run_dedup` 뷰 + `scripts/replay_run.py`(Time Machine) +
  **랜덤 감사 샘플 추출기**(주당 3~5코일 — 4단계 소비지만 *시간이 만드는 데이터*라 1단계 착수)
- [ ] **2단계 Case Retrieval** (~2주, n≥50) — "이 코일 전에 본 적 있어?" 21필드 최근접이웃으로 John의
  과거 교정을 증거로 검색(값 발명 아님 = never-invent 호환). numpy brute force면 충분, 벡터DB 불필요
- [ ] **3단계 Review Triage** (3~6개월, 양성 200~400) — exceptions_K **랭킹**(스킵 금지 — false negative =
  틀린 값 자동승인). 실제 override율은 1단계가 처음 알려줌 → **그 숫자를 보고 착수, 미리 약속 안 함**
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
- [ ] (DEFER) 파라메트릭 도면엔진 SVG/DXF/PDF — MVP는 템플릿-우선, 명시 승인 전까지 보류
