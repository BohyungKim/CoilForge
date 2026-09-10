# CoilForge 위키 — 연산 로그

위키 연산의 append-only 기록, 최신순. 각 항목: 날짜 · 연산(`ingest` | `query` | `lint`) · 제목 ·
바뀐 것. 날짜는 America/Toronto이며 기록 시점에 확인된 값만 쓰고 지어내지 않는다. 이것은 *지식*-연산
로그로 — `docs/SESSION_LOG.md`(dev 인수인계 로그)와 구별된다.

<!-- LOG (newest first) -->

## 2026-09-05 · ingest — `X` 실측 코퍼스 328장: 작업가설 반증, 배선 STOP, 철회 2건
John의 family-aware 배선 지시(Terra V → blank / Terra H → 공식)를 착수 전 검증하다가 두 전제가 모두
무너졌다. Terra 도면 3건을 읽고 PO 트리의 HGRH 코일 도면을 전수 측정(511 PDF → 1,964면 → HGRH 태그
631면 → 타이틀블록 파싱 성공 **328면**). **확정된 것**: `X`의 존재 여부는 리턴 연결 표기와 완전
상관(`OD Header` 186/186 값 있음, `swt` 142/142 공란, 예외 0). 공란 142장은 `I/S/O/R`도 전부 공란.
용어는 **connection-notation cohort** — 버전 근거가 없으므로 "세대"라 부르지 않고, "swt는 헤더가
없어서"라는 인과는 `[LIKELY]`로 `[[open-questions]]`에 둔다. **반증된 것**: 작업가설
`(h+1)·D+(h−1)·1.5`는 값 있는 186장 중 96장(52%)만 설명하고, 불일치 값은 h=1..8 어디로도 재현되지
않으며, 기하가 완전히 동일한 두 코일(2575 / 2504)이 `X`만 1.94 대 2.00으로 다르다. **철회 2건**:
"Terra V는 `X`를 비운다"(순환논법 — 공란의 원인은 swt였고 신형 Terra V 3025는 1.25를 인쇄) /
"Terra H는 Nova 공식을 따른다"(표본 선택 — Hope Lodge 2장이 일치 3장 안에 있었다). **코드 변경 0줄**
(John STOP 승인). 게이트를 "Terra 도면 확보"에서 **"`X`의 engineering definition 또는 결정 input 확보"**로
교체. 갱신: `[[x-header-stack-depth]]`(전면 개정 + 재현 정보), `[[hgrh]]`, `[[index]]`,
`[[open-questions]]`(3항목 신규/교체). 스위트 1612 green(문서 전용, 불변).

## 2026-09-02 · ingest — 도면 치수 `X`의 정체 규명 (헤더 스택 깊이), 코드 변경 0줄
> ⚠️ **2026-09-05에 부분 철회됨** — 아래(최신) 항목 참조. 이 항목의 공식 주장은 실측 328장에서
> 52%만 성립했고, "Terra V는 X를 비운다"는 순환논법이었다. 기록 보존을 위해 원문은 그대로 둔다.
프로젝트 3179 TWU 실측에서 같은 프로젝트의 RHHGRC 코일이 `X`를 서로 다르게 인쇄하는 것이 드러나
(`RHHGRC-1/3` = `— X` 빈칸, `RHHGRC-2/4` = `3.38 X` 고정값) 규명한 결과: **`X` = HGRH 헤더 스택
깊이 `(h+1)·D+(h−1)·1.5` = `CD`의 하한.** `R-073`의 헤더뱅크 항과 문자 그대로 같은 식이며 시드 참조
8건이 소수점까지 일치, `EZC-0016`은 `CD` = `X` = 5.50. 저장소가 2026-06-23부터 달아온
"tube-projection" 라벨은 **오기재**로 판정(어떤 튜브 기하로도 값이 재현되지 않음) — 추적되는 4파일의
주석 정정. **배선은 착수하지 않았다**: 시드 8건이 전부 Nova/Ventum-H 계열이고 Ventum+ 타이틀블록이
1.63/2.00으로 다른 값을 쓰며 Terra 참조 도면이 코퍼스에 없다 → 3179의 Terra V 코일이 근거 없는
숫자를 인쇄받는 상태. **John 게이트(2026-09-02): Terra RHHGRC 참조 도면 1장.** 함께 기록한 구현 함정
3건 — `header_count`는 분석 경로에서 항상 `None`이라 입력은 `circuits`여야 함 / 시더가 재시드 시 `X`
콜아웃을 삭제함 / 타이틀블록 사본은 크롭 밖이라 미렌더. 신규 `[[x-header-stack-depth]]`, 갱신
`[[hgrh]]`·`[[index]]`·`[[open-questions]]`. 스위트 1612 green(변화 없음 — 문서 전용).

## 2026-07-14 · ingest — 커버리지-대시보드 생성기 (수기 스냅샷 대체)
`[[open-questions]]`의 [EXT] 항목 CLOSE. `scripts/generate_coverage_dashboard.py`가
`template_population.catalog.list_template_entries()`에서 시드/미시드 버킷 커버리지를 계산해
`docs/coverage_dashboard.html`을 생성 — 2026-06-17 하드코딩 스냅샷(당시 "10/22", 지금은 33개 전부
시드) 대체. 인코딩된 MVP 택소노미(DX 10 + HGRH 8 + HWC 2 + CWC 2 = SHARED 22)를 `--check`가 라이브
SHARED 버킷과 대조(드리프트 시 실패, CI 가드). Ventum+ 갭 11개를 이번 세션 정책대로 표면화: DX 5 =
not-registered(R-032 UP), 비-DX 6 = shared-fallback. 근거: `scripts/generate_coverage_dashboard.py`,
테스트 `tests/test_coverage_dashboard_generator.py`(8건, 826 green). `[[ventum-plus]]` 참고.

## 2026-07-14 · ingest — 미시드 Ventum+ DX = not-registered 차단 (DX-only)
John 판정(2026-07-14): 미시드 Ventum+ **DX** 조합은 더 이상 공유 ConnectionDOWN 템플릿으로 fallback
하지 않고 **not-registered로 차단**한다 — Ventum+ DX distributor는 ConnectionUP(R-032)인데 공유는 DOWN을
그리므로, 실제 UP 참조가 시드되기 전엔 도면을 안 내보내는 편이 낫다는 결정. `_gate_unseeded_ventum_plus_dx`
(dedicated-preference 직후)가 `_omit_drawing` + `unregistered_ventum_plus_dx` 플래그. **DX 전용** — 미시드
비-DX(HGRH/HWC/CWC)는 distributor가 없어 공유 fallback 유지. 이전 `_flag_distributor_orientation_review`
경고는 DX에선 대체(dead). 갱신: `[[ventum-plus]]` distributor 섹션·인트로·템플릿 섹션, `[[open-questions]]`
R-032 항목. 근거: `workflows/submittal_to_drawing.py::_gate_unseeded_ventum_plus_dx`, 테스트
`test_ventum_plus_dx_unseeded_is_not_registered` / `test_ventum_plus_non_dx_unseeded_still_draws_via_shared`
(818 green). 이 결정으로 R-032 "틀린 방향 도면" 리스크는 DX에서 원천 차단(dedicated-UP 아니면 차단).

## 2026-07-08 · ingest — R-074 2차 출처 판정 + R-048/R-085 조건부 발화 검증
로드맵 후속 두 항목 처리 결과를 원장에 반영. **R-074**(casing dims): 코드베이스 내부에 독립 2차
출처 없음 판정(`mechanical_fit`/`checklist`는 R-074 소비=순환; slot `casing_height`는 다른 물리량;
SOP 등가 테이블 없음) → MEDIUM 유지 확정, 승격 트리거 = 외부 2차 출처 확보. **R-048**: 조건부 발화
(circuits+conn_size+rows) HIGH 검증 + **supply≠return 공식 결함** 발견(엔진이 supply에 return과 동일
리스트; YAML 공식은 supply=CD−[...]) → `[REVIEW-REQUIRED]` 별도 처리 등재. **R-085**: back_to_back
HIGH 발화 검증 + **실 경로 미배선**(입력이 `build_header_request`에 없음) 판정 등재. 신규 유닛테스트
4건(`test_header_prepopulate_engine.py`), R-048 YAML confidence stale(MEDIUM→HIGH) 정정. `src/` 값
변경 없음(엔지니어링 값 무발명). `[[open-questions]]`·`[[hgrh]]` 조정, 근거
`docs/mvp_promotion_decisions.md` §후속.

## 2026-07-07 · lint — MEDIUM→HIGH 승격 원장 정정
`open-questions.md`의 "AWAITING SIGN-OFF"(R-044a/c·R-048·R-066·R-002b·R-073·R-074·R-077·R-085·R-086)를
John 2026-07-07 판정 결과로 갱신: 승격 5(R-066/R-002b/R-085/R-044c/R-048)·검토유지 2(R-044a/R-074)·
재분류 3(R-073/R-077/R-086). 근거 `docs/mvp_promotion_decisions.md` + `coil_header_rules.yaml`.

## 2026-07-06 · ingest — Ventum+ 전용 템플릿 시드 (product_family fork)
R-032 UP 갭 근본 해결: catalog에 `product_family` 축(2-pass: 전용 우선→공유 fallback) 추가 후, 실제
Ventum+ 선정 도면(2폴더·69페이지 스윕, `scripts/inventory_ventum_selection.py`)에서 **11개 전용 템플릿
시드** — DX 5·HGRH 3·HWC 2·CWC 1. 시더는 vector artwork를 그대로 복사하므로 distributor UP이 자연
캡처됨(eyeball로 hgrh_lh/cwc_lh 모델번호 `-L` 확인). 미시드 조합·타 라인은 공유 22버킷 그대로(무회귀,
776 tests green). `[[ventum-plus]]` 템플릿 섹션 갱신, `[[index]]`·`[[open-questions]]` 조정. John eyeball
게이트 대기.

## 2026-07-06 · query+ingest — Ventum+ distributor orientation (R-032 UP)
질의: "Ventum+ 전용 template을 이미 시딩했나?" → **아니오.** 2026-07-03은 전용 시드가 아니라 공유
템플릿 재사용 un-block(`[[open-questions]]` D4). 조사 중 로드-베어링 갭 발견: R-032가 Ventum+ DX
distributor를 `ConnectionUp`으로 `HIGH` 계산하지만 도면 경로가 `dist_orientation`을 소비하지 않아
distributor를 `DOWN`으로 오도(誤導). 처리(2026-07-06): 프로즌 경로 loud 경고
(`_flag_distributor_orientation_review`) + 파라메트릭 엔진이 `slot.DIST_ORIENTATION`→
`HeaderSpec.orientation`→UP top-edge 배치로 소비. 새 페이지 `[[ventum-plus]]` 생성(스텁 승격),
`[[index]]` 제품 섹션 추가, `[[open-questions]]`에 eyeball-대기 항목 추가. 771 테스트 그린.

## 2026-07-06 · lint — 2차 드리프트 재확인 패스
전체 위키 8파일 점검. 위키↔코드: 15 규칙 ID + enum 2 전부 일치 (드리프트 0). D2/D3/D4는 여전히
활성 — `CLAUDE.md`가 Terra V를 "LOW/blocked (R-023/R-046/R-067)"라 하지만 셋 다 `HIGH`(D3);
target-vs-code 표는 4HD를 `placeholder_blocked`라 하나 `catalog.py`는 4버킷 `_SEEDED`(D2);
Ventum+ 모순(D4) 미조정. 소스 수정은 John에게 (엄격 프로토콜). D1은 `CLAUDE.md`가 이미 수정됨
(L88/92) → `[[open-questions]]` D1을 CLOSED로 조정; 잔여 낡음은 메모리 파일뿐(위키 범위 밖).

## 2026-07-04 · ingest — 위키 부트스트랩 (Karpathy LLM-Wiki 패턴)
사내 정제 소스로부터 위키를 시드함. `[[WIKI]]`(스키마), `[[index]]`, `[[sources]]`,
`[[open-questions]]`, 그리고 엔티티/개념 유형별 워크드 예시 한 개씩 생성:
`[[hgrh]]`, `[[terra-v]]`, `[[confidence-gate]]`. 모든 주장은 배지 + `coil_header_rules.yaml`까지
추적 가능한 `evidence_ref`를 지닌다. 원본 소스는 읽거나 수정하지 않음; `src/` 변경 없음. 사실 출처:
R-021v/R-023/R-040b/R-046/R-052/R-067/R-070/R-074/R-076/R-090 및 `schemas/header_prepopulate.py`의 enum.

## 2026-07-04 · lint — 첫 드리프트 패스 (기록만, 아직 조정 전)
John을 위해 라이브 위키↔코드 / 문서↔문서 드리프트 3건을 플래그함(상세는 `[[open-questions]]`):
1. **Terra-V 케이싱 값** 060/072/084/100 이 `R-074`(`TERRA_V|INTEGRATED|*`)에 **존재**하는데,
   메모리/CLAUDE.md는 아직 "owed by John"이라 설명함. → 남은 항목 CLOSED.
2. **4HD** DX/HGRH가 시드됨(`MVP_FINALIZATION_CHECKLIST.md` L41 `[x]`)인데, CLAUDE.md의
   target-vs-code 표는 여전히 4HD 버킷을 `placeholder_blocked` 데드엔드라 부름. → 낡음.
3. **Terra-V 라우팅**: CLAUDE.md는 Terra V가 "LOW/blocked로 라우팅(R-023/R-046/R-067)"이라 하지만,
   셋 다 지금 `HIGH`(SOP-confirmed, 2026-06-28 승격). → 낡음.
추가로 문서↔문서 모순: **Ventum+ fork**가 MVP 체크리스트(L43)에선 `[ ]` 열림인데 CLAUDE.md에선
"불필요로 폐기됨". → 조정 필요.

## 2026-07-07 · ingest — multi-header-geometry 스텁 시드
`[[multi-header-geometry]]` 스텁을 시드함(circuits/feeds → Nth 헤더). 핵심 `[CONFIRMED]` 사실:
**John 2026-07-06 — N interlaced circuits = N 공급 헤더 (DX/HGRH)**, 따라서 `circuits`가
`submittal_to_drawing.py`에서 "Header N" 템플릿 키를 옳게 이끈다(버그 아님). 근거: 세션 라이브 확인
(ALS Palmetto `CDXC-1` "Interlaced 2 Circuits" → circuits=2 → Header 2). 인덱스: 스텁 → 개념 섹션으로
이동. `src/` 변경 없음. 관련 공식 규칙 R-022/R-034/R-048/R-052/R-072/R-073 참조.

## 2026-07-15 · ingest — hot-gas-bypass 개념 페이지 시드 (실코드 버그 2건 동반 수정)
`[[hot-gas-bypass]]`를 시드함 — 시드된 버킷 2개와 `special_feature` 축이 있는데도 위키에 HGBP
언급이 **0건**이던 실제 공백. 핵심 `[CONFIRMED]` 사실:
1. **`(N ASC)`는 플래그가 아니라 개수** — `(0 ASC)` = HGBP 없음(`ez_style_grid.py:417`). 위키가
   존재하는 이유 그 자체인 도메인 사실: `_detect_hgbp`의 `"ASC" in blob` 부분 매칭이 이를 **거꾸로**
   읽어, HGBP가 아닌 DX 코일이 조용히 HGBP 템플릿을 받을 수 있었다(이 함수는 테스트 0개였음).
2. **HGBP는 카테고리가 아님** — DX 전용·header 무관의 직교 `special_feature`. 물/재열 코일에 붙이면
   `found=False`로 도면이 조용히 빈다.
3. **Nova/Ventum H 전용** (John 2026-07-15) — 게이트-only, 새 버킷/재시딩 없음.
4. **재시딩 불필요**: John이 RH 참조로 제시한 2720 Crestwood 도면은 **이미 시딩된 그 코일**
   (Coil ID 560562 일치); 모델 문자열 포맷만 EZ-Coil 5.5.0.0로 달랐다.

동반 `src/` 변경(John 승인): `_detect_hgbp` 단어경계+카운트 수정, cover-page HGBP 감지
(`_package_hgbp_pages`, DX 한정 note 전달), Nova/VH 게이트 2개, R-035c 노트
(`Distributor Down w/ ASC & 6" Extension`, R-035b를 `not_hot_gas_bypass`로 대체). 엔진의 노트 조립
루프가 이제 `only_when`을 존중한다 — 그 전엔 무시해서 게이트된 노트 규칙이 inert였다.
검증: 891 tests green(baseline 857 → +34), 2910 Hilltop 실물에서 라우팅+노트 확인,
HGBP 없는 대조군 3건(0748/1701/1702) SVG 해시까지 byte-identical.

## 2026-07-15 · 정정 — Ventum+ DX HGBP는 "미시딩 gap"이 아니라 **존재하지 않는 조합**
John 확인: HGBP LH & RH (Nova & Ventum H)는 **시딩 완료**이고, **Ventum+ DX HGBP는 존재하지 않는다.**
이는 같은 날 앞선 결정을 뒤집는다 — 그때는 Ventum+ DX HGBP를 "전용 버킷이 아직 없는 조합"으로 보고
HGBP 게이트를 `_gate_unseeded_ventum_plus_dx` **뒤에** 두어 R-032 사유를 남겼다. 그 사유는
*"…must be seeded first"* 라서 **참조 PDF만 구하면 닫을 수 있는 공백**처럼 읽혔다 — 만들 수 없는
참조를 찾으라는 지시. 수정 3건:
1. **게이트 순서 뒤집음** — HGBP 게이트가 먼저 실행되어 진짜 사유("Nova and Ventum H only")를 소유.
   HGBP 없는 Ventum+ DX 미시딩 hand/header는 여전히 R-032 사유를 받는다(그건 진짜 닫을 수 있는 공백).
2. **대시보드 유령 gap 제거** — `SPECIAL_FAMILIES`로 Ventum+ 열에서 HGBP 칸 제외. Ventum+ 22칸 →
   **20칸**, blocked 5 → **3**. SHARED의 HGBP 2칸(둘 다 seeded)은 유지. `--check` 드리프트 0.
3. 문서/테스트 정정 — 옛 순서를 고정하던 테스트를 반대로 뒤집고, 대시보드 테스트가 명시적으로 세던
   `LH-HGBP, RH-HGBP -> not registered`를 제거.
**HGBP 커버리지는 완료** — header-agnostic이라 (hand × 2)가 버킷 공간 전부이며 남은 시딩 항목 없음.

## 2026-07-15 · ingest — 코팅 노트(R-080/R-081)는 custom coating일 때만
John 2026-07-15: *"Do Not Coat Last 5-6 inches of Supply Stubouts" 는 FinCoat / AA Coat 같은 custom
coating이 필요할 때만 포함. 아니면 넣을 필요 없음.* 같은 날 앞선(2026-06-11) *"Direct Coil에 coating
trigger 필드가 없으니 항상 붙인다"* 를 **뒤집는다** — 아무도 코팅하지 않는 코일에 "마지막 5-6인치는
코팅하지 마라"는 지시는 의미가 없다.

- `only_when: coating_set`으로 게이트(이미 `_condition_met`에 있었으나 **쓰는 규칙이 0개인 죽은
  조건**이었다). 방금 노트 조립 루프가 `only_when`을 존중하게 고친 덕에 그대로 동작한다.
- `coating_set` = 명시되었고 `NONE`이 아님. checklist vocab(`COATING_OPTIONS`) 14개 중 `NONE` 외
  13개(FINKOTE*/HERESITE*/ELECTROFIN*/BLYGOLD*/BLACK POLY)가 **전부 custom coating**이라
  "set"과 "custom"이 일치한다. 표준 코팅이 나중에 vocab에 추가되면 실패하도록 테스트로 고정.
- **함정:** `coating`이 엔진에 도달하지 않고 있었다 → 규칙만 바꿨으면 노트가 **영원히** 사라졌을
  것(우연히 "항상 생략"). `manufacturing_options.coil_coating` → `ctx["coating"]` →
  `build_header_request`로 연결함.
- `[CONFIRMED]` 실측: 2910/0748 submittal 모두 **coating 언급 0건** — Oxygen8 submittal은 코팅이
  없으면 필드 자체를 안 쓴다. 그래서 "미명시 = 코팅 없음"으로 읽는 것이 옳고(fail-closed), 2910의
  Drawing Notes에서 코팅 노트가 정확히 사라졌다.
- 골든 케이스 5건 갱신: T01/T03/T05/T08(코팅 입력 없음 → 노트 없음), T17(원래 케이스가
  `coating=HERESITE`인 **코팅된** 코일 → 노트 유지). 새 동작이 오히려 T17의 원래 의도에 가깝다.
- `[REVIEW-REQUIRED]` John이 예시로 든 **"FinCoat" / "AA Coat"** 는 `COATING_OPTIONS`에 그 철자로
  없다("FINKOTE 2/CC/HP/ZX" 계열은 있음). 별칭인지, vocab에 빠진 항목인지 확인 필요.
