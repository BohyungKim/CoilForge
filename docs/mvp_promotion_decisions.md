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
| **R-048** | `supply_position`, `return_position` | HGRH · 전체 | `x·D + (x−1)·1.5` | **B** | SOP §HGRH-TNVH · CHK HGRH!C42:C49 | 입력 조건부 승격 | ✅ **승격 완료** (헬퍼 코드 수정) |
| **R-044a** | `supply_sl` | HGRH · NOVA/VENTUM_H | `6` | A | SOP §HGRH-TNVH · CHK 기하식 `6+D/2−S1` | 검토 유지 | ⏸ **유지** — 기하식 미구현 |
| **R-074** | `casing_width`, `casing_height` | 전체 | CHK Units 룩업 | **B** | CHK Units sheet XLOOKUP | 검토 유지 | ⏸ **유지** — CHK 단일출처(2차 검증 前) |

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
