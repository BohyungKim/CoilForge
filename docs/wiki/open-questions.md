# CoilForge 위키 — 열린 질문 / 남은 항목 원장

John에게 남았거나 사인오프를 기다리는 엔지니어링 항목의 라이브 목록, 그리고 문서/메모리가 현재 코드와
어긋나는 **드리프트**. 이 페이지는 `docs/MVP_FINALIZATION_CHECKLIST.md`(권위 있는 원장)와 **대조/조정**할
뿐 이를 대체하지 않는다. `/wiki-lint`이 "조정(Reconciliation)" 열을 갱신하고, John이 항목을 해결한다.

상태 범례: **OPEN**(남음) · **AWAITING SIGN-OFF**(MEDIUM → HIGH 원함) · **DRIFT**(문서 vs 코드 불일치) ·
**CLOSED**(해결됨, 감사 추적용 보존).

## 첫 lint 패스가 잡은 드리프트 (2026-07-04)

| # | 항목 | 조정 | 상태 |
| --- | --- | --- | --- |
| D1 | Terra-V 케이싱 `060/072/084/100` "owed by John" | 지금 `R-074` `TERRA_V\|INTEGRATED\|060…100`에 **존재**; `CLAUDE.md` L88/92도 "all 13 Terra V sizes now resolve"로 **이미 갱신됨**. 잔여 낡음은 메모리 `[[terra-v-sop-finalized]]` 본문뿐(위키-lint 고정 좌표 밖; `MEMORY.md` 인덱스가 이미 stale 표기). | **CLOSED** (2026-07-06 재확인) |
| D2 | 4HD 버킷 = `placeholder_blocked` 데드엔드 (CLAUDE.md target-vs-code 표) | 4HD DX/HGRH LH+RH 시드됨; `MVP_FINALIZATION_CHECKLIST.md` L41 `[x]`; `catalog.py` 헤더-4 버킷 `_SEEDED`. | **CLOSED** (2026-07-06 — CLAUDE.md 표 "✅ Resolved … placeholder_blocked 분기 inert"로 정정) |
| D3 | Terra V "LOW/blocked로 라우팅 (R-023/R-046/R-067)" (CLAUDE.md) | 셋 다 `HIGH`, SOP-confirmed, 2026-06-28 승격. `[[terra-v]]` 참고. | **CLOSED** (2026-07-06 — CLAUDE.md manual-review 룰 "LOW→HIGH, now drawn"으로 정정) |
| D4 | Ventum+ fork MVP 체크리스트(L43)에선 `[ ]` OPEN vs CLAUDE.md "불필요로 폐기" | 두 거버넌스 문서 간 모순. `_UNREGISTERED_PRODUCT_LINES`는 비어 있음(Ventum+ 도면화됨). | **CLOSED** (2026-07-06 — MVP 체크리스트 L43 `[x]` 폐기로 정정, 두 문서 일치) |

## MEDIUM → HIGH 승격 — RESOLVED (John 2026-07-07)

`docs/MVP_FINALIZATION_CHECKLIST.md` §"MEDIUM→HIGH promotions" 판정 완료 — 결정표 `docs/mvp_promotion_decisions.md`:
- **승격(→HIGH, 자동도면) [CONFIRMED]**: `R-066` vent_drain · `R-002b` lifting_lugs · `R-085` back-to-back ·
  `R-044c` Ventum+ supply_sl (제네릭 emitter, YAML confidence) · `R-048` HGRH positions (특수 헬퍼 코드).
  근거: `John 2026-07-07`, 스위트 790 green.
- **검토 유지 [REVIEW-REQUIRED]**: `R-044a` supply_sl(기하식 미구현) · `R-074` casing dims(CHK 단일출처).
- **승격 대상 아님(재분류)**: `R-073`(casing_depth는 이미 `R-070`으로 HIGH 방출) · `R-077`(엔진 미방출,
  `mechanical_fit` 전용) · `R-086`(feature_flag 비활성).

## 열린 엔지니어링 작업

- **[도면] `X`의 engineering definition 또는 `X`를 결정하는 source input 확보** `[REVIEW-REQUIRED]` —
  **이것이 `X` 배선의 게이트다** (John 2026-09-05). 2026-09-03에 유력했던 공식
  `(h+1)·D+(h−1)·1.5`는 PO 트리 HGRH 도면 **328장 실측**에서 값이 있는 186장 중 **96장(52%)**만
  설명한다. 불일치 값(`1.63`·`2.00`·`2.50`·`3.00`·`3.25`)은 h = 1..8 어디로도 재현되지 않고,
  `FH·FL·CH·CL·CD·OAL·SL·I·S·O`가 완전히 같은 두 코일이 `X`만 1.94 대 2.00으로 다르다 →
  **결정 변수가 타이틀블록 안에 없다.** 코퍼스 역추정으로는 닫히지 않으므로 **SOP / CoilMaster의
  열 정의**가 필요하다. 이전 게이트였던 "Terra 참조 도면 1장 확보"는 **무효** — 도면 3장을 읽은
  결과가 오히려 공식을 반증했다(3025 Bauducco = 신형 Terra V가 `X` 1.25를 인쇄). 상세와 재현 정보는
  `[[x-header-stack-depth]]`. **OPEN (John: SOP/CoilMaster 정의 탐색).**
- **[도면] `swt` 코호트에 `X`가 없는 이유** `[LIKELY]` — 리턴 연결 표기가 `… " OD Header`인 페이지는
  **186/186 전부** `X`를 인쇄하고, `… " swt`인 페이지는 **142/142 전부** 비운다(예외 0건, n=328).
  공란 142장은 `I`·`S`·`O`·`R`도 전부 공란이다. **상관관계는 확정**이나, "swt는 헤더가 없는 연결이라
  헤더 기하가 존재하지 않는다"는 **인과 해석은 미확인**이다. 도면의 버전·발행일 근거가 없으므로
  "구형/신형 세대"라 부르지 않고 **connection-notation cohort**로 부른다. CoilMaster/SOP 확인 필요.
  **OPEN.**
- **[측정] 텍스트 레이어 없는 도면은 미측정 사각지대** `[CONFIRMED]` — 위 328장 측정에서 HGRH 태그가
  붙은 631장 중 303장이 타이틀블록 파싱 실패로 빠졌다. 248장은 코일 PDF 1페이지의 CoilMaster
  성능/표지 시트(도면 아님, 양성 제외)이지만 **55장은 텍스트 레이어가 비어 있는 이미지 전용
  페이지**(표본 2097 Go Green)다. 그 55장의 `X`는 알 수 없다. OCR 없이는 닫히지 않는다. **OPEN.**
- **[도면] 물 코일(CWC/HWC)의 `X`** `[REVIEW-REQUIRED]` — 시드 템플릿의 타이틀블록 `X`가
  `cwc_lh` 3.90 · `cwc_rh` 2.60 · `hwc` 1.38 / `vplus_hwc_rh` 1.88로 갈린다. 물 템플릿에는 도면 영역
  `X` 콜아웃이 없어 인쇄되지 않으므로 우선순위는 낮다. HGRH의 `X`와 같은 양인지 미확인. **OPEN.**
- **[MVP] R-074 케이싱 dim 2차 출처 확보** `[REVIEW-REQUIRED]` — `casing_width`/`casing_height`는
  CHK Units 시트 **단일출처**라 MEDIUM. 2026-07-08 판정: **코드베이스 내부에 독립 2차 출처가
  없다** — `mechanical_fit.py`(R-078)·`checklist/mapping.py`는 R-074 출력을 소비(순환참조),
  slot 레이어 `casing_height`(`CH=FH+TF+BF`≈13")는 유닛 캐비닛 치수(≈20"+)와 **다른 물리량**,
  SOP엔 등가 테이블 없음(`coil_header_rules.yaml:888`). **승격 트리거 = 외부 2차 출처(실물
  overall-dimension 도면 또는 SOP dims 테이블) 확보.** 확보 시 HIGH 재검토. 근거
  `docs/mvp_promotion_decisions.md` §후속. **OPEN (외부 출처 대기).**
- **[MVP] R-048 supply_position 공식 결함** `[REVIEW-REQUIRED]` — 엔진이 `supply_position`에
  `return_position`과 **동일** 리스트를 낸다(`header_prepopulate_engine.py` R-048 블록 line 519).
  YAML 공식은 supply = `CD − [(Xmax+2)·D + (Xmax−1)·1.5]`(`coil_header_rules.yaml:598`)로 달라야
  하며, 멀티회로 HGRH에서 supply 헤더 위치가 틀린다(단일회로면 우연히 일치). 조건부 발화 자체는
  검증됨(`tests/test_header_prepopulate_engine.py::test_r048_hgrh_positions_high_when_multi_circuit`).
  supply 공식 구현은 CD(케이싱 폭)가 slot 레이어에서 와야 해 dual-path 편집 필요 → **John 확정
  후 별도 수정.** `[[hgrh]]` 참고. **OPEN.**
- **[MVP] R-085 back_to_back 실 경로 미배선** `[REVIEW-REQUIRED]` — 룰 자체는 `back_to_back=True`에서
  HIGH 발화 확인됨(`test_r085_back_to_back_mounting_high_when_flagged`). 단 `back_to_back` 입력은
  `schemas/header_prepopulate.py:103`에 정의만 있고 `build_header_request`/submittal 경로가 세팅하지
  않아 **실 UI 경로에선 구조적 미발화**. 실 트리거 배선은 입력 출처 정의 선행 후 별도 결정.
  `docs/mvp_promotion_decisions.md` §후속 참고. **OPEN (미배선 판정).**
- **[EXT] Terra 분리** `TERRA → TERRA_H + TERRA_V` (~15개 Terra 규칙 + 엔진 콜사이트 + 리졸버 + 테스트
  리키). `MVP_FINALIZATION_CHECKLIST.md` L61 `[ ]`. `[[terra-v]]` 참고. **OPEN.**
- **[MVP] R-084 ASC 방향** — Direct-Coil 필드 네이밍 규약이 생길 때까지 `CONFLICT`/`[BLOCKED]`.
  `[[confidence-gate]]` 참고. **OPEN (blocked).**
- **[DEFER] 템플릿 하드코딩 dim** — CWC/HWC/HGRH 템플릿이 리댁션 안 된 as-built dim 숫자(슬롯 아님)를
  담음; `docs/TEMPLATE_HARDCODED_DIMS_BACKLOG.md`; `John 2026-06-22` 연기; DX는 클린. 메모리
  `[[template-hardcoded-dims-deferred]]`. **OPEN (deferred).**
- **[DEFER] R-082** Terra 마운팅 홀 — `CONFLICT`/`LOW`, blocked. **OPEN (deferred).**
- **[MVP] R-090 카퍼 스트랩** — CWC/HWC 배수 미확정(`[BLOCKED]`); DX/HGRH 확정. `[[hgrh]]` 참고.
  **OPEN (water는 blocked).**
- **[EXT] 커버리지-대시보드 생성기** — `scripts/generate_coverage_dashboard.py`가 라이브 카탈로그
  (`list_template_entries()`)에서 `docs/coverage_dashboard.html`을 생성(수기 스냅샷 대체); `--check`는
  택소노미↔SHARED 버킷 드리프트 가드. Ventum+ 갭을 DX=not-registered / 비-DX=shared-fallback으로 표면화.
  **CLOSED 2026-07-14** (8테스트, 826 green).
- **[MVP] Ventum+ distributor orientation (R-032 UP) 도면 반영** — 엔진은 UP을 `HIGH`로 계산하나 도면
  경로가 소비 안 하던 갭 (2026-07-06 발견). **근본 해결:** catalog `product_family` fork + 실제 Ventum+
  참조에서 **11개 전용 템플릿 시드**(vector artwork 그대로 복사 → UP 자연 캡처); 시드 조합은 전용 라우팅.
  미시드 **DX**는 not-registered 차단(`John 2026-07-14` — 틀린 방향 도면 원천 차단, `_gate_unseeded_ventum_plus_dx`),
  미시드 **비-DX**만 공유 fallback. 파라메트릭 엔진도 UP 지원(`schematic_layout`). 남은 것:
  각 시드 템플릿의 **John eyeball 게이트**. hand 미표기 프로젝트 hand 확정 완료(John 2026-07-06):
  **2666 Pembroke HQ DX = LH, 2658 Fitchburg CWC = LH** → 둘 다 기존 시드(dx_lh_header3, cwc_lh)와 중복,
  신규 버킷 없음. **11개가 이 참조 폴더의 완전한 시드 집합.**
  `[[ventum-plus]]` 참고. **OPEN (eyeball 대기).**

## 닫힘 (감사 추적)
- Terra-V 4 케이싱 값 → 채워짐 (D1). · 4HD → 시드됨 (D2). · Terra-V DX/HGRH/water 스페셜 →
  2026-06-28 HIGH 승격 (D3). · Ventum+ → 언블록, 2026-07-03 공유 템플릿으로 도면화 (D4 문서 측).
- 커버리지-대시보드 생성기 → `scripts/generate_coverage_dashboard.py`로 CLOSED (2026-07-14).
