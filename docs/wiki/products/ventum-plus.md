# Ventum+ — Ventum Plus `[CONFIRMED core]`

First-class 제품 타입 (`ProductFamily.VENTUM_PLUS`, `schemas/header_prepopulate.py`). Nova/Ventum H와
헤더 규칙 세트를 공유하지 않고 **자체 상수 세트**를 가진다 — 특히 DX distributor가 물리적으로
**반대 방향(ConnectionUp)** 이라는 점이 다른 모든 라인과 구별되는 핵심이다. 도면은 **DX**의 경우 전용
UP 시드 템플릿으로 그려지거나(미시드면 not-registered 차단, `John 2026-07-14` — 아래 참조), **비-DX**
(HGRH/HWC/CWC)는 공유 product-agnostic CoilMaster 템플릿으로 그려진다. Review aid only.

## 감지

`submittal/coilmaster_drawing_extract.py::detect_product_and_size`가 유닛-사이즈 토큰 `V20 … V150`에서
Ventum+를 감지한다 (태그 접두사가 아니라 **사이즈 토큰** 기반). `[CONFIRMED]` 근거: `R-076`
`VENTUM_PLUS:` 열거. 커버-텍스트 경로(`pdf_to_template_drawing::_suggest_product_and_size`)는 브랜드
문자열 `VENTUM+`/`VENTUM PLUS`/`VENTUM-PLUS` → `VENTUM_PLUS`, 맨 `VENTUM` → `VENTUM_H`로 매핑.
Terra-Vertical `TV_B_###`의 떠도는 `V###` 필터-부록 토큰이 감지를 오염시킬 수 있어
`_TERRA_V_MODEL_RE`가 **먼저** 매칭된다 — 메모리 `[[submittal-product-detect-and-water-header]]`.

## Nova/VH/Terra와 다른 상수

| 무엇 | 규칙 | Ventum+ 값 | vs 다른 라인 | 배지 |
| --- | --- | --- | --- | --- |
| Flange (TF/BF) | `R-011` | `1` | Nova/VH `0.625` (R-010) | `[CONFIRMED]` |
| DX distributor I | `R-029` | `12` | Nova/VH/Terra `3` (R-028) | `[CONFIRMED]` |
| **DX distributor orientation** | **`R-032`** | **`UP` (ConnectionUp)** | **Nova/Terra/VH `DOWN` (R-031)** | `[CONFIRMED]` |
| DX suction SL | `R-026` | `10` | Nova/VH `8/17` | `[CONFIRMED]` |
| HGRH return SL | `R-045a` | `10` | Nova/VH `8` (R-044b) | `[CONFIRMED]` |
| HGRH return spacing `Rn` | `R-052` | `D` | Terra/Nova/VH `n·D+(n−1)·1.5` | `[REVIEW-REQUIRED]` (`John 2026-06-25`) |
| CWC/HWC SL | `R-063b` / `R-064-sl` | `10` / `14` | Nova/VH `8` / `12` | `[CONFIRMED]` |
| 케이싱 | `R-074` | `VENTUM_PLUS\|INTEGRATED\|V20…V150` (half-height, stacked) | 패밀리별 테이블 | `[REVIEW-REQUIRED]` |

근거: `rules/coil_header_rules.yaml` (R-011/R-026/R-029/R-031/R-032/R-045a/R-052/R-063b/R-074),
`docs/rules/coil_header_rule_extraction.md` (테스트 케이스 `T03 — DX / VENTUM+ / V40`:
`dist i=12, dist_orientation=UP, dist_extension=6`). `dist_extension`(R-033=6")는 **모든 패밀리 동일** —
길이가 아니라 **방향**이 반대라는 점에 주의.

## Distributor orientation UP — 도면 반영 상태 `[REVIEW-REQUIRED]`

**로드-베어링 사실.** R-032는 Ventum+ DX distributor가 `ConnectionUp`임을 `HIGH`로 계산하지만,
공유 CoilMaster 템플릿은 Nova/VH 표준인 `ConnectionDown`으로 시드되었고 프로즌 템플릿 경로는
`dist_orientation`을 **소비하지 않는다**. 그래서 프로즌 도면의 distributor는 방향이 틀린다. 처리 상태:

- **엔진 → slot**: `build_drawing_slots`가 `dist_orientation`을 `slot.DIST_ORIENTATION`으로 방출
  (DX 전용; HGRH/CWC/HWC엔 distributor 없음). `[CONFIRMED]` 근거: `services/direct_coil_drawing_pipeline.py`,
  테스트 `test_dx_distributor_orientation_slot_emitted_per_family` (`2026-07-06`).
- **파라메트릭 엔진 (실제 geometry 수정)**: `schematic_model.HeaderSpec.orientation` →
  `schematic_layout.layout_header_side_view`가 `UP`이면 supply distributor를 **top 케이싱 엣지** 기준으로,
  아니면 기존 `DOWN`(bottom)으로 배치. UP/DOWN(수직)은 LH↔RH 미러(수평)와 직교. `[CONFIRMED]` 근거:
  테스트 `test_distributor_orientation_up_lifts_supply_to_top_half` 등 (`2026-07-06`).
- **미시드 DX → not-registered 차단 (DX-only, `John 2026-07-14`)**: 미시드 Ventum+ DX는 공유 DOWN
  템플릿으로 그리지 않고 **아예 차단**한다 — `_gate_unseeded_ventum_plus_dx`(dedicated-preference 단계
  직후 실행)가 `_omit_drawing`으로 svg를 비우고 `not_registered_reason` + `unregistered_ventum_plus_dx`
  플래그를 세팅. 틀린 방향 도면이 경고와 함께라도 나가는 것보다, 실제 UP 참조가 시드되기 전엔 도면을
  안 내보내는 편이 낫다는 판정. (이전 `_flag_distributor_orientation_review` 경고는 DX에선 이제 **대체됨**
  — 모든 Ventum+ DX는 dedicated-UP 아니면 차단이라 공유-DOWN 경고 경로가 dead.) `[CONFIRMED]` 근거:
  `workflows/submittal_to_drawing.py::_gate_unseeded_ventum_plus_dx`, 테스트
  `test_ventum_plus_dx_unseeded_is_not_registered` (`2026-07-14`).
- **전용 템플릿 시드 (근본 해결, 2026-07-06)**: 실제 Ventum+ 참조 도면에서 시드하면 vector artwork를
  그대로 복사하므로 UP distributor가 자연 캡처된다. 시드된 조합은 dedicated 템플릿으로 라우팅된다
  (`dedicated_family_template=="VENTUM_PLUS"`). 아래 "템플릿" 섹션 참고.

즉 **시드된 전용 템플릿은 UP을 실물 그대로 그리고**, 미시드 **DX**는 not-registered 차단, 미시드
**비-DX**만 공유 fallback으로 그린다(파라메트릭 엔진도 UP 지원). 각 시드 템플릿의 UP geometry는 John의
eyeball 게이트로 CLOSE — `[[confidence-gate]]`.

## 템플릿 — 전용 시드 (product_family fork, 2026-07-06)

과거(2026-07-03)엔 공유 product-agnostic 템플릿만 재사용했으나, DX distributor 방향(R-032 UP)이 공유
DOWN 템플릿에 표현되지 않는 문제 때문에 **catalog `product_family` fork를 구현**하고 **11개 전용 Ventum+
템플릿을 실제 선정 도면에서 시드**했다(`[CONFIRMED]` 근거: `template_population/catalog.py::VENTUM_PLUS_TEMPLATES`,
`scripts/seed_templates_from_pdf.py::VPLUS_BUCKETS`, 테스트 `test_ventum_plus_renders_across_categories` 등):

- **DX (5):** `rh_header1`(2798), `lh_header1/2`(2760), `lh_header3`(1929), `rh_header2`(2619)
- **HGRH (3):** `lh_header1`(2760), `rh_header1`(2619), `rh_header2`(2839)
- **HWC (2):** `lh`(2802), `rh`(2523) · **CWC (1):** `lh`(2773)

Template 선택은 이제 `(supplier, category, hand, header, special, **product_family**)` 2-pass — 전용 버킷
우선, 없으면 공유 fallback. 그래서 **다른 라인은 공유 22버킷 그대로**(무회귀); 미시드 Ventum+ **비-DX**는
공유 fallback, 미시드 Ventum+ **DX**는 not-registered 차단(`John 2026-07-14`, 위 distributor 섹션). 각
아티팩트는 review-aid only(`export_allowed=false`); 참조 PDF는 `Case/feed/vplus_*`에 gitignored 스테이징.
surrogate/mirror 금지 원칙대로 각 (hand,header)는 자기 실제 참조 페이지에서 시드됨.

관련: `[[hgrh]]`(R-052 Ventum+ 분기), `[[nova]]`(공유 헤더 규칙 세트, 스텁), `[[confidence-gate]]`,
`[[taxonomy]]`(스텁), 메모리 `[[submittal-product-detect-and-water-header]]`.
