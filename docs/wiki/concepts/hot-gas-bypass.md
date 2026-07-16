# Hot Gas Bypass (HGBP / ASC) — 카테고리가 아닌 직교 옵션 축 `[CONFIRMED]`

HGBP는 **코일 카테고리가 아니다.** `CoilType` enum(DX/HGRH/CWC/HWC)과 **직교하는**
`special_feature` 축에 산다. 이름이 비슷한 **HGRH(hot gas *reheat*)와 혼동 금지** — 그쪽은
카테고리다(`[[hgrh]]`).

- `[CONFIRMED]` 정규화: `catalog.py::_normalize_special_feature`가 `{ASC, HOT_GAS_BYPASS, HGBP}`
  를 모두 `HGBP`로 통일한다. `ASC`는 EZ Coil 용어, `HGBP`는 사내 표준
  (`docs/CANONICAL_COIL_MODEL.md:27` — "EZC-0013 source evidence is ASC, while the normalized
  internal special feature is HGBP by John-confirmed company standard").

## `(N ASC)`는 **개수**다 — `0 ASC` = HGBP 없음 `[CONFIRMED]`

EZ 도면은 HGBP를 distributor 문자열 안의 **카운트**로 적는다:
`(1)501-2-3/16-1.5(0 ASC)` → **hot gas bypass 없음**. `(1 ASC)` → 있음.

- `[CONFIRMED]` 근거: `phase2a/ez_style_grid.py:417`의 `(0 ASC)` 예시, 그리고 실물 참조 도면 4장
  (아래 표)이 전부 `(1 ASC)`.
- **이것이 실제 버그를 낳았다.** `_detect_hgbp`가 `"ASC" in blob` 부분 매칭이라 `0 ASC`를 HGBP로
  **거꾸로** 읽었다. 경로는 실재: `pdf_intake.py`가 Drawing Notes를
  `manufacturing_options.distributor_notes`로 넣고 → `submittal_to_drawing.py`가 전 옵션값을
  이어붙여 → `_detect_hgbp`에 먹인다. 즉 HGBP가 아닌 DX 코일이 조용히 HGBP 템플릿을 받을 수
  있었다. 2026-07-15 단어 경계 regex + 카운트 `>= 1` 조건으로 수정(그 전까지 이 함수는 **테스트가
  0개**였다).

> **detector가 둘인 이유(의도적):** `pdf_intake._package_hgbp_pages`는 **문서 전체**를 훑으므로
> **명시 문구(`HGBP` / `hot gas bypass`)만** 매치하고 **ASC를 제외**한다 — 그 제외가 "HGBP 코일
> 도면 1장이 패키지 전체를 물들이는" 것을 설계상 막는다. `submittal_to_drawing._detect_hgbp`는
> 코일별이라 카운트 `>= 1`도 인정한다. 둘 다 단어 경계 사용(`"ASC" in blob`은 "C**asc**ade",
> `"BYPASS"`는 "economizer bypass damper"에도 걸린다).

## DX 전용 + header-agnostic `[CONFIRMED]`

- `[CONFIRMED]` **DX 전용**: `catalog.py::_entry_for_dx_hgbp`가 HGBP 버킷의 **유일한** 생산자이고
  DX만 만든다. HGRH/CWC/HWC용 HGBP 버킷은 **없다** → 물/재열 코일에 HGBP를 붙이면 `found=False`로
  **도면이 조용히 빈다.** 그래서 cover 감지는 **DX 코일에만** 적용된다(fail-open이 blank보다 낫다).
- `[CONFIRMED]` **header 무관**: `catalog.py::_header_matches`가 `special_feature == "HGBP"`이면
  무조건 `True`를 반환하고, `pdf_to_template_drawing.py`는 special이 있으면 `header_type`을
  `None`으로 만든다. 즉 **HGBP × header count 버킷은 존재하지 않는다.** 2026-07-15 현행 유지 결정
  (John) — 실물 참조 4장이 모두 `HDx1`이다.

## Nova / Ventum H 전용 `[CONFIRMED]`

- `[CONFIRMED]` John 2026-07-15: **Nova와 Ventum H만** 이 옵션을 선택할 수 있다. 다른 line에서
  HGBP가 감지되면 분류가 틀린 것이지 이국적인 코일이 아니다.
- 구현은 **게이트-only** — 공유 HGBP 버킷을 유지하고 `product_family`-scoped HGBP 버킷을 만들지
  않는다. `submittal_to_drawing._gate_hgbp_unsupported_product_line`이 Terra/Ventum+ 등에 대해
  도면을 omit + 사유 표기.
- `[CONFIRMED]` **Ventum+ DX HGBP는 "시딩 안 된 버킷"이 아니라 존재하지 않는 조합이다**
  (John 2026-07-15). 이 구분이 게이트 **순서**를 정한다: `_gate_unseeded_ventum_plus_dx`도 이
  코일을 잡지만 그 사유는 *"no seeded Ventum+ DX reference matches this hand/header … **must be
  seeded first**"* — 누군가 참조 PDF를 구해오면 닫을 수 있는 **커버리지 공백**처럼 읽힌다. 그런
  참조는 만들어질 수 없으므로, HGBP 게이트가 **먼저** 실행되어 메시지를 소유한다. 같은 이유로
  `scripts/generate_coverage_dashboard.py`의 `SPECIAL_FAMILIES`가 Ventum+ 열에서 HGBP 칸을
  제외한다 — 2026-07-15 전까지 대시보드는 이 유령 gap 2칸을 `not_registered`로 세고 있었다
  (Ventum+ 20칸 중 blocked 3 = 실제로 닫을 수 있는 미시딩 hand/header만).
- `[REVIEW-REQUIRED]` **line 미해결 시 차단하지 않는다** — 도면은 그리고
  `hgbp_product_line_warning`을 띄운다(`_flag_hgbp_product_line_unverified`). "증거 없음"은
  "지원 안 되는 line임"의 증거가 아니며(never-invent), line은 `unit_size`만으로도 해결된다
  (`pdf_to_template_drawing`: `ctx.product_type or det_product or product_for_unit_size(...)` —
  Nova 사이즈 `B20`이면 product_type 없이도 NOVA). John이 product를 고르면 재-derive에서 진짜
  게이트가 작동한다. → `[[confidence-gate]]`

## 시딩된 템플릿 2개 `[CONFIRMED]`

재시딩 불필요 — 2026-07-15 John이 제시한 참조 도면과 대조 완료.

| 버킷 | source | 모델 | ASC | header | Coil ID |
| --- | --- | --- | --- | --- | --- |
| `coilmaster_dx_lh_hgbp` | `EZC-0013` | `DX-F-F-05-12-12.00x19.00-L` | `(1 ASC)` | `HDx1` | 579012 |
| `coilmaster_dx_rh_hgbp` | `FEED-DX_HB_RH` | `DX-F-F-05-14-12.00x15.00-R` | `(1 ASC)` | `HDx1` | **560562** |

- `[CONFIRMED]` John이 RH 참조로 제시한 2720 Crestwood 도면(`DXM05C14-12.00x15.00R`)은 **이미
  시딩된 그 코일**이다 — **Coil ID 560562 일치**, 치수 전부 동일. `DXM05C14-…` vs
  `DX-F-F-05-14-…`는 EZ-Coil 5.5.0.0의 모델 문자열 포맷 차이일 뿐이고 `MODEL_NUMBER`는 슬롯이라
  렌더 시점에 채워진다.
- `[CONFIRMED]` LH 참조 2910 Hilltop(`DXM05C13-12.00x15.00L`, `(1 ASC)`, `HDx1`)은 기존 LH 시드와
  같은 부류(LH DX HGBP 1-header).
- `[CONFIRMED]` 둘 다 mirror 파생 아님 — 각자 실제 참조 PDF에서 시딩
  (`tests/test_mirror_forbidden_and_ventum_unregistered.py`).
- `[CONFIRMED]` **이 둘이 Nova/Ventum H의 HGBP 커버리지 전부다** — Nova/VH는 공유 버킷에서 그리고,
  HGBP는 header 무관이므로 (hand × 2) 외에 더 필요한 버킷이 없다. 즉 **HGBP 커버리지는 완료**이며
  남은 시딩 항목이 없다. Ventum+ HGBP는 위 항목대로 **버킷 공간에 존재조차 하지 않는다**.

## Cover page 감지 `[CONFIRMED]`

HGBP는 코일 행이 아니라 **프로젝트 단위 cover 라인 아이템**으로 견적된다:
`660024-001 HGBP VALVE - DANFOSS AXV-H and hot-gas bypass stub-out on coils adder`.

- `[CONFIRMED]` 그 행은 `_is_cover_coil_row`가 `"valve"` 토큰(`_NON_COIL_ITEM_TOKENS`)으로 **정확히
  버린다**(코일이 아니므로 맞다). 따라서 플래그는 파싱된 행이 아니라 **페이지 텍스트**에서 읽는다.
- `[CONFIRMED]` 실물 검증 2026-07-15: 2910 Hilltop KS submittal(55p)에서 p.2, p.11 감지 →
  `CDXC-1`(Ventum H, H05)이 `coilmaster_dx_lh_header1` → **`coilmaster_dx_lh_hgbp`**로 이동,
  Drawing Notes가 `Distributor 6" Extension Downwards` → **`Distributor Down w/ ASC & 6" Extension`**
  으로 변경. HGBP 없는 대조군 3건(0748/1701/1702)은 SVG 해시까지 byte-identical.
- 전달 수단은 **candidate note**(`Cover option: hot-gas bypass (HGBP) adder stated on cover page …`).
  note의 literal `HGBP` 토큰을 `_detect_hgbp`가 매치하므로 **한쪽만 고쳐 쓰면 라우팅이 조용히
  끊긴다** — 양쪽에 주석 + 테스트로 고정.
- `[REVIEW-REQUIRED]` 문서 전체 스캔의 잔여 위험: 코일 페이지에 문구가 literal로 박히면 오탐 가능.
  감지된 페이지 번호를 `cover_page_hgbp_pages`로 증거 노출해 완화.

## 도면 노트 R-035c `[CONFIRMED]`

| 규칙 | 조건 | 노트 |
| --- | --- | --- |
| `R-035a` | DX + VENTUM_PLUS | `Distributor 6" Extension Upwards` |
| `R-035b` | DX + NOVA/TERRA/VENTUM_H + `not_hot_gas_bypass` | `Distributor 6" Extension Downwards` |
| `R-035c` | DX + NOVA/VENTUM_H + `hot_gas_bypass` | **`Distributor Down w/ ASC & 6" Extension`** |

- `[CONFIRMED]` John 2026-07-15. R-035c는 R-035b를 **대체**한다(추가가 아님) — *DX당 distributor
  노트 정확히 1개* 불변식 유지. Terra + HGBP는 불가능 조합이라 노트가 **안 나온다**(fail-closed).
- **함정 1:** 엔진의 노트 조립 루프가 원래 `_applies`만 읽고 **`only_when`을 무시**했다 → 게이트된
  노트 규칙이 무력(inert). 2026-07-15 루프가 `only_when`을 존중하도록 수정. CLAUDE.md의
  "`_SPECIAL_IDS` 규칙은 YAML만 고치면 inert, helper를 고쳐라" 원칙의 실사례.
  (기존 노트 규칙 6개 중 `only_when` 보유가 0개라 회귀 위험 없었음.)
- **함정 2:** `_engine_drawing_notes`가 `build_header_request`에 `hot_gas_bypass`를 안 넘기면
  R-035c는 **영원히 안 터진다**. 템플릿 선택을 이끈 **같은** `special_feature`를 재사용하므로
  paste 필드와 선택된 템플릿은 HGBP 여부에 대해 일치한다.
- `[REVIEW-REQUIRED]` R-035 계열은 paste "Drawing Notes" 필드 / preview title block에만 나타난다 —
  **DX `template.svg`의 NOTES는 하드코딩**(`NOTES: Copper Straps Required.`)이라 slot-render 되지
  않는다(기존 제약, 메모리 `[[drawing_notes_autofill]]`).
- `[REVIEW-REQUIRED]` **`slot.NOTES` 함정 (2026-07-15 확인).** `slot.NOTES`는 HGBP 코일에서도 항상
  R-035b 문구(`Distributor 6" Extension Downwards`)를 담는다 — `build_drawing_slots`에
  `hot_gas_bypass` **파라미터 자체가 없어서** 구조적으로 불가능하다(Track A/B 둘 다). 오늘은
  **무해**하다: `{{slot.NOTES}}` placeholder를 가진 `template.svg`가 **하나도 없어** 어디에도
  렌더되지 않는다(`slot_map`엔 `coilmaster_dx_lh_header1` 한 곳만 선언, 그마저 placeholder 없음).
  하지만 **함정이다** — CLAUDE.md의 "Redaction gotcha"대로 누군가 템플릿의 하드코딩 NOTES를 실제
  슬롯으로 리댁션하면, 그 순간부터 HGBP 코일에 "Downwards"가 인쇄된다. 그렇게 하기 전에
  `build_drawing_slots`에 `hot_gas_bypass`를 먼저 통과시킬 것.

## 관련

`[[confidence-gate]]`, `[[hgrh]]`, `[[ventum-plus]]`, `[[taxonomy]]`, `[[multi-header-geometry]]`.
Review aid 전용 — HGBP 도면도 `export_allowed: False`.
