# Terra V — Terra Vertical `[REVIEW-REQUIRED core]`

First-class 제품 타입: **수직(vertical)** 유닛으로, Terra H보다 훨씬 키가 크고, 자체 사이즈 세트와
전용 케이싱 테이블을 가진다. 코드상 Terra V는 (아직) 독자 `ProductFamily`가 아니다 —
`ProductFamily.TERRA`로 해결되고 런타임에 `TerraVariant.TERRA_V`로 구분된다. `[CONFIRMED]` 근거:
`schemas/header_prepopulate.py`(`TERRA`는 "의도적으로 성긴(coarse)" enum; `terra_variant`가 Terra-V
규칙을 게이트). 확정된 *목표*는 `TERRA → TERRA_H + TERRA_V` 분리 — 아직 열림, `[[open-questions]]` 참고.

## 감지

`submittal/coilmaster_drawing_extract.py::detect_product_and_size`가 모델 코드를 읽는다. Terra V는
`TV_B_###` / `TV###` 형식(`B` = base-mounted, 스킵)을 쓰며, Terra H의 스케줄 형식 `TR_[CV]_###`과
구별된다. *인식 못 한* 코드는 느슨한 full-PDF 스캔으로 떨어지고, 거기서 떠도는 필터-부록 `V###`
토큰이 감지를 오염시킬 수 있다 — 메모리 `[[submittal-product-detect-and-water-header]]` 참고.

## 사이즈 — 13개 (Terra H는 9개)

`R-076`은 Terra V에 자체 열거를 준다: Terra H의 9개 사이즈 **+** `060/072/084/100`. `[CONFIRMED]`
근거: `R-076` `TERRA_V:` = `["006","009","012","015","018","024","032","040","048","060","072","084","100"]`
(`CHK Units sheet`; Terra H에서 분리 `John 2026-06-29`). 엔진 사이즈 게이트는 `terra_variant`로
분기해 성긴 `TERRA` 세트 대신 `TERRA_V`를 고른다.

## 케이싱 — 전용 `TERRA_V|INTEGRATED` 테이블

수직 유닛은 훨씬 키가 크기 때문에 Terra V는 Terra H의 케이싱을 **빌리지 않는다**. `R-074`는 전용
`TERRA_V|INTEGRATED|<size>` 블록(13행)을 담는다, 예: `006→30×51`, `032→48×78`, `100→77×80`.
`[REVIEW-REQUIRED]` 근거: `R-074` `lookup` 행 `TERRA_V|INTEGRATED|006…100`, Terra-Vertical
"Overall Dimensions" 시트에서 옮겨 적음(`John 2026-06-30`). 케이싱은 `MEDIUM`(단일 출처 체크리스트)
이라 구성상 review-required — `[[confidence-gate]]` 참고.

> **드리프트 참고 (닫힌 항목):** 더 큰 케이싱 4행 `060/072/084/100`은 한때 "owed by John"이었다.
> 지금은 `R-074`에 **존재**한다(`060/072/084 → 69×78`, `100 → 77×80`). 메모리
> `[[terra-v-sop-finalized]]`와 `CLAUDE.md`는 여전히 owed라 설명한다 — 그 남은 항목은 **CLOSED**.
> 조정을 위해 `[[open-questions]]`에 기록됨.

## SOP-confirmed 스페셜 케이스 (모두 2026-06-28에 LOW → HIGH 승격)

Terra V는 대체로 SOP 단일 출처지만, DX/HGRH/water 스페셜은 `SOP 2024018`에서 픽스되고 사인오프되어
`[CONFIRMED]`이며 **blocked가 아니다**:

| 카테고리 | 규칙 | 무엇 | 배지 | 근거 |
| --- | --- | --- | --- | --- |
| DX | `R-021v` | 모든 I/O → `2.75` | `[CONFIRMED]` | `SOP 2024018 §DX-TNVH SPECIAL CASE`, `John 2026-06-28 (SOP-confirmed)` |
| DX | `R-023` | return spacing `Rn = (n−0.5)·D + (n−1)·1.5 + 0.75` | `[CONFIRMED]` | `SOP 2024018 §DX-TNVH SPECIAL CASE Terra V`, `John 2026-06-28` |
| HGRH | `R-046` | `supply_io=2.75`, `supply_sl=5`, `return_sl=12` | `[CONFIRMED]` | `SOP 2024018 §HGRH-TNVH SPECIAL CASE`, `John 2026-06-28` |
| CWC/HWC | `R-061v` | I/O = `2.75` — **공급·리턴 동일** | `[CONFIRMED]` | `SOP 2024018 §CWC/HWC SPECIAL CASE FOR TERRA V`, `John 2026-06-28`, 데이텀 정정 `John 2026-07-29` |
| CWC/HWC | `R-067` | `vent_drain = HDR ENDS` (Supply 1 & Return 1) | `[CONFIRMED]` | `SOP 2024018 §CWC/HWC SPECIAL CASE`, `John 2026-06-28` |

> **데이텀 정정 (2026-07-29).** 슬롯 레이어는 Terra V water 리턴에 SOP 문구 "return CH−2.75"를
> 그대로 써서 `slot.O2`에 **34.5**를 찍고 있었다(2949 Ferguson HHWC-1, CH 37.25). `slot.O{even}`은
> **스터브아웃 I/O 콜아웃**이라 2~3인치대 치수를 담는 칸이고, `CH−2.75`는 **같은 물리적 위치를
> 반대쪽 데이텀에서 표현한 값**이다 — 값이 다른 게 아니라 기준면이 다른 것. 옛 주석이 스스로
> "levels the return stubout with the supply stubout"이라 적어둔 것이 단서였다(수평이면 도면엔
> 같은 수가 찍혀야 한다). 시드 물코일 레퍼런스 **7/7이 `O == I`**이고 `O == CH−2.75`는 **0/7**
> (CH 17.00~38.75 전 범위). Terra V만 자기 `I`와 어긋나던 유일한 라인이었다. → 특례 제거,
> 리턴도 `R-061v`의 2.75를 그대로 쓴다. 2026-07-28 게이트 해제 전까지는 Terra V water 도면이
> 그려지지 않아 **화면에 드러난 적이 없었다.**

> **드리프트 참고 (낡은 문서):** `CLAUDE.md`는 여전히 Terra V가 "LOW/blocked로 라우팅(`R-023` DX
> spacing, `R-046` HGRH, `R-067` CWC/HWC vent-drain)"이라 한다. 2026-06-28 SOP 사인오프 이후로 **셋 다
> `HIGH`** — 그 라우팅 주장은 낡았다. 이 위키는 현재의 진실을 기술한다; 드리프트는 `CLAUDE.md`를
> 고치도록 `[[open-questions]]`에 파일링됨.

## Terra V water는 공유 템플릿으로 도면화 (2026-07-28 해제)

Terra V CWC/HWC 도면은 제출물 게이트
(`workflows/submittal_to_drawing.py::_gate_unregistered_product_line`)에서 **생략되었으나**,
John이 2026-07-28 해제했다 — Ventum+를 un-block했던 것과 같은 근거로, CoilMaster water-coil
도면의 *형상*은 어느 Oxygen8 AHU에 실리든 동일하고 **제품별로 다른 것은 찍히는 값뿐**이다.
따라서 공유 Nova/Ventum-H water 템플릿(`coilmaster_{cwc,hwc}_lh`)이 올바른 캐리어이고,
값은 이미 Terra V로 계산되고 있었다(`R-061v` I/O = 2.75,
`R-067` vent/drain). 같은 템플릿 위에서 Terra V와 Terra H가 **서로 다른 `slot.O2`** 로
해결되는 것이 회귀 테스트로 고정되어 있다
(`tests/test_mirror_forbidden_and_ventum_unregistered.py::test_terra_v_water_carries_terra_v_drawing_parameters`).
`[CONFIRMED]` 근거: `John 2026-07-28 (2949 Ferguson Theatre HWC 도면 미생성 보고)`;
`CLAUDE.md` 제품-패밀리 규칙.

`[REVIEW-REQUIRED]` 잔여 caveat: 공유 water 템플릿에는 아직 슬롯화되지 않은 as-built 치수
숫자가 남아 있다(메모리 `[[template-hardcoded-dims-deferred]]`, John 2026-06-22 보류). 이는
그 템플릿을 쓰는 **모든** 라인에 이미 존재하던 상태이며 Terra V도 동일하게 상속한다 —
검토 보조물로만 사용.

관련: `[[hgrh]]`, `[[confidence-gate]]`, `[[terra-h]]`(스텁), 메모리 `[[terra-v-sop-finalized]]`.
