# MVP 승격 결정표 — MEDIUM → HIGH

> `docs/MVP_FINALIZATION_CHECKLIST.md` §2 "MEDIUM → HIGH promotions needing John's
> sign-off"를 구체화한 결정 문서.
>
> **상태(2026-07-07):** John이 **저위험 SOP 세트 5개**(R-066·R-002b·R-085·R-044c·R-048)를
> 승격 판정 → 실행 완료(전체 테스트 790 green + 엔진 레벨 검증). R-044a·R-074는 검토 유지,
> R-073·R-077·R-086은 승격 대상이 아니어서 아래 "재분류" 섹션으로 이동.
>
> **이 문서는 검토용이다.** 승격은 필드를 `suggestions`(검토필요)에서 `values`(자동도면)로
> 옮길 뿐 어떤 값도 새로 발명하지 않는다(`export_allowed: False` 불변, AGENTS.md 하드 경계).
>
> 근거 데이터: `src/coilforge/rules/coil_header_rules.yaml`,
> `src/coilforge/services/header_prepopulate_engine.py`

## 승격 메커니즘 — 룰마다 다르다 (탐색으로 확정)

버킷은 **오직 `confidence`로 결정**된다(`bucket_for_confidence` → `HIGH:values / MEDIUM:suggestions
/ LOW·CONFLICT:blocked`). `review_required`는 confidence에서 파생될 뿐 버킷을 고르지 않으며,
**YAML `review_required:` 필드는 엔진이 읽지 않는 문서용 필드**다(confidence만 실제 레버).

| Class | 경로 | 승격 방법 |
| --- | --- | --- |
| **A** | 제네릭 emitter (`_SPECIAL_IDS`에 없음) | YAML `confidence: MEDIUM → HIGH` 한 줄 |
| **B** | 특수 헬퍼 (Python이 `Confidence.MEDIUM` 하드코딩) | 헬퍼 코드에서 `HIGH`로 수정 (YAML 편집 무효) |
| **N/A** | 엔진이 방출 안 함 / 이미 HIGH / feature-flag 비활성 | 승격 개념 부적용 — 아래 재분류 참조 |

## 결정표 (John 판정 확정)

| 룰 | 필드 | 적용 범위 | 값/공식 | Class | 근거 | CoilForge 권장 | **John 결정** |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **R-066** | `vent_drain` | CWC/HWC | `"Connections"` | A | SOP §CWC/HWC Supply1&Return1 | 승격 | ✅ **승격 완료** |
| **R-002b** | `lifting_lugs` | 전체 | `false` | A | SOP §GEN | 승격 | ✅ **승격 완료** |
| **R-085** | `back_to_back_mounting` | 전체 (`only_when back_to_back`) | `"Mounting Holes, Bolts, 0.3125\", 12\" spacing"` | A | SOP §GEN SPECIAL CASE | 승격(저빈도) | ✅ **승격 완료** |
| **R-044c** | `supply_sl` | HGRH · VENTUM_PLUS | `6` | A | SOP §HGRH-VP · John 확정 2026-06-11(golden T09) | 승격 | ✅ **승격 완료** |
| **R-048** | `supply_position`, `return_position` | HGRH · 전체 | `x·D + (x−1)·1.5` | **B** | SOP §HGRH-TNVH · CHK HGRH!C42:C49 | 입력 조건부 승격 | ✅ **승격 완료** (헬퍼 코드 수정) ⚠️ supply≠return 결함 — 아래 §후속 |
| **R-044a** | `supply_sl` | HGRH · NOVA/VENTUM_H | `6` | A | SOP §HGRH-TNVH · CHK 기하식 `6+D/2−S1` | 검토 유지 | ⏸ **유지** — 기하식 미구현 |
| **R-074** | `casing_width`, `casing_height` | 전체 | CHK Units 룩업 | **B** | CHK Units sheet XLOOKUP | 검토 유지 | ⏸ **유지 확정** — 내부 2차 출처 부재(2026-07-08 판정); 외부 출처 대기 — 아래 §후속 |

## 승격 대상 아님 (재분류)

이 3개는 원래 §2 후보 목록에 있었으나 탐색 결과 "MEDIUM→HIGH 승격" 개념이 성립하지 않는다:

- **R-073** `casing_depth` (HGRH) — **이미 HIGH로 그려지고 있다.** 엔진은 R-073을 방출하지
  않고 `casing_depth`를 R-070(rows 기반)에서 HIGH로 낸다(`_emit_casing_depth`). R-073을 HIGH로
  올리면 같은 필드에 **HIGH↔HIGH 충돌**이 생기고 회귀가드 2개
  (`test_hgrh_cd_stays_rows_based_when_conn_present`, `test_terra_v_drawing_slots_use_sop_specials`)가
  깨진다. → 승격 금지, 현행 유지.
- **R-077** `drain_pan_width` — **엔진이 방출하지 않는 데이터 전용 룰**(`_FIT_DATA_IDS`).
  `compatibility/mechanical_fit.py`와 체크리스트가 룩업 테이블로만 소비한다. 도면 버킷에
  들어가지 않으므로 승격 대상이 아니다. → 현행(fit 리포트 review-aid) 유지.
- **R-086** `coil_style` — **feature_flag 비활성**(`_ENABLED_FEATURE_FLAGS` 비어 있음). 플래그를
  켜야 발화하며, 그건 별도 기능 결정이다. → MVP 보류(deferred) 유지.

## 요약 결과

- **승격 완료(5)**: R-066, R-002b, R-085 (Class A 상수) · R-044c (Class A 상수, Ventum+ 전용) ·
  R-048 (Class B 공식) — 2026-07-07
- **검토 유지(2)**: R-044a (기하식 미구현), R-074 (CHK 단일출처 — 2차 출처 확보 후 재검토)
- **재분류(3)**: R-073, R-077, R-086 — 위 참조

## 후속 판정 (2026-07-08) — R-074 2차 출처 · R-048 결함 · R-085 배선

승격 배치 후 로드맵 "지금"에 남았던 두 항목(R-074 2차 출처 판정, R-048/R-085 조건부
발화 실사례 확인)을 처리한 결과다. 세 룰 모두 **엔지니어링 값을 새로 발명하지 않았고**
도면/템플릿 경로도 건드리지 않았다.

### R-074 — 검토 유지(MEDIUM) 확정, 외부 2차 출처 대기
탐색 결과 **코드베이스 내부에 독립 2차 출처가 없다**:
- `compatibility/mechanical_fit.py`(R-078)·`checklist/mapping.py`는 둘 다 R-074 출력을
  `engine_value("casing_width/height")`로 **소비**한다 → 순환참조, 대조 불가.
- slot 레이어의 `casing_height`(`CH = FH+TF+BF ≈ 13"`, 코일 인클로저)는 R-074의 유닛
  캐비닛 치수(≈20"+)와 **다른 물리량** → 대조 불가.
- SOP엔 등가 casing 테이블 없음(`coil_header_rules.yaml:888`).

→ **판정: MEDIUM 유지 확정. 승격 전제 = 외부 2차 출처(실물 overall-dimension 도면 또는
SOP dims 테이블) 확보.** 확보 시 재검토. `docs/wiki/open-questions.md`에 트리거로 등재.

### R-048 — 조건부 발화 검증됨 + supply≠return 결함(별도 처리)
`circuits + conn_size + rows`가 모두 있으면 `supply_position`/`return_position`이 HIGH로
발화함을 유닛테스트로 확인(`tests/test_header_prepopulate_engine.py::
test_r048_hgrh_positions_high_when_multi_circuit` + `..._missing_inputs_when_no_circuits`).
YAML confidence stale(MEDIUM)를 HIGH로 동반 정정(엔진 무영향, 문서 일관성).

⚠️ **결함(John 확정 후 별도 수정):** 엔진이 `supply_position`에 `return_position`과 **동일**
리스트를 낸다(`header_prepopulate_engine.py` R-048 블록 line 519). YAML 공식은 supply =
`CD − [(Xmax+2)·D + (Xmax−1)·1.5]`로 달라야 하며, 멀티회로 HGRH에서 supply 헤더 위치가
틀린다. `docs/wiki/open-questions.md`에 [REVIEW-REQUIRED]로 등재.

### R-085 — 룰 발화 검증됨 + 실 경로 미배선(판정)
`back_to_back=True`면 `back_to_back_mounting`이 HIGH로 발화함을 유닛테스트로 확인
(`test_r085_back_to_back_mounting_high_when_flagged` + `test_r085_absent_when_not_flagged`).
단 **`back_to_back` 입력은 실 파이프라인에 배선되지 않았다** — `schemas/header_prepopulate.py`
에 정의만 있고 `build_header_request`/submittal 경로가 세팅하지 않아 실 UI 경로에선 미발화.
→ **판정: 룰 정확성은 유닛레벨 확인. 실 트리거 배선은 입력 출처 정의 선행 후 별도 결정.**
`docs/wiki/open-questions.md`에 등재.

## 반영 절차 (실행 기록)

1. **Class A**: YAML `confidence: MEDIUM → HIGH`(문서 일관성 위해 `review_required`도 `false`
   동반 수정, 단 엔진은 이 필드를 안 읽음). **Class B**: 특수 헬퍼의 `Confidence.MEDIUM →
   HIGH` + `review_required=True` 인자 제거.
2. 테스트 갱신: `test_t09_hgrh_ventum_plus_v20`만 `suggestions→values`로 수정(R-044c).
   `test_t08`(Nova, R-044a)은 유지라 미변경. → `python -m pytest -q` **790 passed**.
3. 엔진 레벨 검증: Ventum+ HGRH `supply_sl`·CWC `vent_drain`·`lifting_lugs`·HGRH positions
   모두 `values/HIGH`, Nova `supply_sl`은 `suggestions/MEDIUM` 유지 확인.
4. 실사례 눈검사(Phase Gate): **John 사인오프 완료 (2026-07-07)** — 엔진 검증 근거로 승인.
   `direct_coil_drawing_pipeline.build_header_request` + `prepopulate` 실행 결과:
   - **R-044c** Ventum+ HGRH V20 `supply_sl=6` **[VALUES/HIGH]** · **R-066** CWC(VENTUM_H H10)
     `vent_drain="Connections"` **[VALUES/HIGH]** · **R-002b** `lifting_lugs=false` **[VALUES/HIGH]**.
   - 스코핑 대조군: Nova HGRH A16 `supply_sl=6`은 **[SUGGESTIONS/MEDIUM]** 유지 → R-044c가
     Ventum+에만 스코프됨을 확인(과잉적용 없음).
   - **후속(조건부 발화)**: R-048(supply/return position, 멀티-포지션 입력 필요)·R-085
     (back_to_back 플래그 필요)는 별도 트리거 config로 재확인 예정.
   - 참고: manual `/api/coil-drawing/derive`는 설계상 모든 슬롯을 review_required로 표시하고
     이 필드들은 paste-ready 필드값(도면 지오메트리 아님)이라, 승격의 HIGH 진입은 엔진 출력/
     submittal 필드패널에서 확인하는 것이 정확함(도면 렌더로는 안 보임).

## MVP 사인오프 마무리 (John 2026-07-15)

Stage 2b(파라미터 완전성 감사) 판정을 전부 해소하고 MVP 사인오프를 마무리했다.

### 템플릿 eyeball 사인오프 — 승인
Ventum+ 11 + 공용 10 템플릿을 **review-aid로 사인오프**(John 2026-07-15). production 승인
아님 — `export_allowed=False`·워터마크 유지, 실제 프로젝트 진행 중 이상 발견 시 재검토.
MVP 체크리스트 §4 반영.

### 대기 3건 처분
- **R-048 supply≠return 결함 — 수정(단, MEDIUM/review-required 발화).** 엔진이
  `supply_position`에 `return_position`과 동일 리스트를 내던 결함을 수정: 문서 공식
  `Supply = CD − [(Xmax+2)·D + (Xmax−1)·1.5]`(Xmax=circuits, D=conn_size, CD=casing_depth)로
  발화하도록 변경(`header_prepopulate_engine.py` R-048 블록). **다만 HIGH가 아니라
  MEDIUM/review-required로 발화** — 이 SOP 공식은 실사례 미검증이고 CD가 연결 런보다 작으면
  음수 위치(예: NOVA B20 circuits=2 → CD 3.75, supply −0.25)를 낼 수 있어, confirmed 자동표기는
  invariant("never invent engineering values")에 위배되기 때문. `return_position`은 검증된
  공식이라 HIGH 유지. supply_position/return_position은 현재 어떤 도면·출력도 소비하지 않는
  필드라 실 도면 영향은 0이나, 결함 자체는 제거. 테스트 `test_r048_hgrh_positions_multi_circuit`
  갱신(supply≠return, supply∈suggestions/MEDIUM). **공식 자체의 실사례 검증은 open-questions 유지.**
- **R-085 back_to_back 실경로 배선 — 보류.** 룰 정확성은 유닛레벨 확인됐으나 `back_to_back`
  입력이 실 파이프라인(`build_header_request`/submittal)에 배선되지 않음. 입력 출처 정의가
  선행돼야 배선 가능 → **보류**(John 2026-07-15). open-questions 유지.
- **R-074 casing 외부 2차 출처 — MEDIUM 수용.** casing dims는 단일출처(CHK only)라 외부 2차
  출처가 없으면 review-required로 두는 것이 안전 기본값. **MEDIUM 유지 수용**(John 2026-07-15),
  출처 확보 시 승격 가능하도록 open-questions 유지.
