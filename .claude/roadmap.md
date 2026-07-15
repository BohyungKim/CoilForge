# 🗺️ CoilForge 로드맵
> 목표: 코일 입력(Direct Coil 폼 / submittal / 스캔 PDF) → 검토용 도면 + 붙여넣기용 필드셋 + 검증·호환 리포트
> 마지막 갱신: 2026-07-14 (Drawing Notes 자동채움 완료)

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
- [x] 폰트 추출불가 submittal 자동 OCR + OCR-blocked(토큰/쿼터) 경고 배너 (c007b75) 🆕 이번 세션
- [x] Submittal 제품/사이즈 오검지 수정 (556b366) — 텍스트경로 커버행 model코드 포착 → TERRA H/015 라이브 검증 🆕 이번 세션
- [x] Header 2 = circuit수 확정 (John 2026-07-06) + wiki multi-header-geometry 시드 (b7f71a2) 🆕 이번 세션
- [x] PR #3 생성 (2026-07-07) — claude/ccsi-autofill → main, 73커밋(브랜치 누적 작업 전부)
- [x] 저위험 SOP 승격 5개 (R-066/R-002b/R-085/R-044c/R-048 MEDIUM→HIGH, 790 green) + eyeball 사인오프(John 2026-07-07) + 결정표·재분류(R-073/R-077/R-086) + /ship(hunk격리로 R-006 등 무관작업 제외)
- [x] R-074 2차 출처 판정 + R-048/R-085 조건부 발화 검증 (fc7037c, 794 green) — R-074 내부 2차출처 부재→MEDIUM 유지 확정(외부 출처 대기); R-048/R-085 유닛테스트 4건으로 HIGH 발화 검증; 검증 중 발견한 R-048 supply≠return 공식 결함·R-085 back_to_back 실경로 미배선을 [REVIEW-REQUIRED]로 등재(hunk격리로 R-006 재배제) 🆕 이번 세션

- [x] Coil Checklist 자동화 (b8b2168) — analyze 시 백그라운드 자동채움(기본ON 토글, 수동 "Fill" 버튼 제거) + sha1(pdf_bytes) 캐시로 finalize 이중 Excel COM 제거; `_run_or_reuse_checklist`/`_CHECKLIST_CACHE`(analyze↔finalize source_id 무관 공유), 신규 10테스트+818 green, invariant-guard clean(WARN 2건 수정), 실서버 실측 270.3s→0.053s 재사용 + 브라우저 자동채움 실증 · **John eyeball 확인 완료(2026-07-14)** 🆕 이번 세션
- [x] 미시드 Ventum+ DX = not-registered 차단 (003928f, John 2026-07-14) — 미시드 Ventum+ DX가 공유 ConnectionDOWN 템플릿으로 폴백하던 걸 차단(R-032 UP를 공용이 못 그림); `_gate_unseeded_ventum_plus_dx`(DX 전용, 비-DX는 공유 폴백 유지), 시드 DX는 전용 UP 그대로; 테스트 2건 갱신+818 green, CLAUDE.md+위키 3파일 정정, 런타임 eyeball 확인 · **John 브라우저 확인 완료(2026-07-14)** 🆕 이번 세션
- [x] Analyze 진행 표시 = 확정형 % 바 + 단계명 (10544f1, John 요청 2026-07-14) — 회전 스피너+고정문구를 초록 % 바+단계 라벨(Extracting→Cover rows→Coil sections→Product line→Building drawing)로 교체; 백엔드는 단일 블로킹 POST라 클라 `pdfProgress` 트리클(92% 상한 감속, 결과 그리드가 카드 대체=완료, 강제100% 없음); 덤으로 John 스크린샷이 가리킨 빈 초록 띠 버그 수정(`#brain-case-banner[hidden]{display:none}` — `display:grid`가 UA `[hidden]`을 덮던 것); 실 27p submittal 라이브 검증(57%→89%→코일2개 결과), 라이트/다크 정상, 826 green · **John 라이브 확인(2026-07-14)** 🆕 이번 세션
- [x] 커버리지 대시보드 생성기 (16b0852) — 수기 HTML → `scripts/generate_coverage_dashboard.py`가 `catalog.list_template_entries()`에서 자동생성(+`--check` 드리프트 가드, CI에서 인코딩된 MVP 택소노미와 라이브 SHARED 버킷 불일치 시 실패) 🆕 이번 세션
- [x] Drawing Notes 자동채움 (4b6d29f, John 확정 차트 2026-07-14) — "Drawing Notes" 필드가 (제품군×코일타입)으로 자동채움; 엔진이 이미 조립하던 노트(R-007/008/080/081)를 폼필드+검토용 SVG에 배선 + **신규 R-035a/b 분배기 노트**('Distributor 6" Extension Upwards' Ventum+ DX=R-032 UP 미러 / '...Downwards' 그 외 DX=R-031 DOWN 미러, 상호배타 2룰 → DX당 정확히 1개). `assemble_drawing_notes` 헬퍼 + `_NOTES_APPEND_IDS`/루프 등록; 엔진노트를 **기존** `distributor_notes`의 CANONICAL 사본에 주입(신규 레지스트리 필드 없음=52필드 표면 무churn) — 도면 렌더러는 slot.DISTRIBUTORS를 raw candidate/typed draft에서 읽으므로 분배기 콜아웃 오염 없음; product-gated(제품/사이즈 미상 시 공란, 무발명). 828 green, 착수 전 adversarial 재검토가 블로커 2건 포착·정정. ⚠️ **미결**: DX template.svg의 NOTES는 하드코딩("Copper Straps Required", `{{slot.NOTES}}` 플레이스홀더 없음)이라 신규 노트가 템플릿 도면엔 미표시 — 재시드(DO-NOT-TOUCH) 필요, John 판정 대기 🆕 이번 세션

## ▶️ 지금
- [ ] MVP 사인오프 마무리 — 파라미터 완전성 감사(Stage 2b) — 다음 걸음:
  승격 판정 전부 해소(승격5·유지2·재분류3, R-074/R-048/R-085 후속까지 확정 기록). 이제 남은 것은
  **템플릿 eyeball 사인오프**(Ventum+ 11 + 공용 10) + John 판정 대기 3건(R-048 supply 공식 수정 ·
  R-085 back_to_back 실경로 배선 · R-074 외부 2차 출처 확보). 결정 기록은 docs/mvp_promotion_decisions.md.

## ⬜ 앞으로
- [ ] 템플릿 eyeball 사인오프 — Ventum+ 11 + 공용 10, 실제 프로젝트 진행하며 확인 (MVP §1·§4)
- [ ] PR #3 리뷰·머지 (claude/ccsi-autofill → main) — ⚠️ 2026-07-07 병합 시도 = CONFLICTING: drawing engine 5파일 충돌(main Phase 2.6–4b 라벨/V3 vs ccsi 병렬 피처 S1·R2·HDx1·AIRFLOW·Terra V·Ventum+, 양쪽 고유). 통합 병합은 크고 위험 → **drawing 세션과 조율 후 진행 (보류)**
- [ ] CCSI Tier 1 실 mutation 라이브 end-to-end 1회 (미완) — 2026-07-05 이후 우선순위 하향.
  **프리플라이트 드라이런 (2026-07-15, /ccsi-preflight, mutation 0건)**: CoilForge측 GREEN — 서버 up·
  정적 맵 25셀렉터(13 base+12 멀티헤더)·브릿지 전역 3개(`coilforgeCoils`/`coilforgeCcsiCompare`/
  `coilforgeSelectCoil`) 로드 시 resolve. **게이팅 NO-GO = CCSI 로그인 탭 부재(John 몫)**. John 로그인
  후 T2 핸들러 typeof(`CopyRevision` 등 5)+코일 로스터 태그매칭을 마저 검증하면 GO 판정. Terra와 파일
  무충돌(브라우저측+read-only)로 병행 진행한 작업.
- [~] **Terra 스플릿 [EXT] — 점진적 병행 (John 2026-07-14 방식 확정)** — `TERRA` → `TERRA_H` + `TERRA_V`
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
  - [ ] Phase 3 — `[TERRA]` 룰 25개를 `[TERRA_H,TERRA_V]`로 리키(10 TERRA-only, 3 multi-family, 12 variant-scoped=게이트 탈피
    가능) + 엔진 테스트 ~22 사이트 마이그레이션 + coarse `TERRA` 은퇴 + 정규화 셔틀을 group-aware `_applies`로 진화 (최종 목표상태)
- [ ] (DEFER) 파라메트릭 도면엔진 SVG/DXF/PDF — MVP는 템플릿-우선, 명시 승인 전까지 보류
