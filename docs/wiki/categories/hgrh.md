# HGRH — Hot-Gas Reheat Coil `[CONFIRMED core]`

CoilForge의 네 코일 **카테고리** 중 하나(`[[dx]]`, **HGRH**, `[[hwc]]`, `[[cwc]]`). 카테고리는 PDF
인테이크에서 유닛/코일 **태그 접두사**로 감지된다; 이는 제품 패밀리(`[[terra-v]]` 등)나 헤더 수와는
*별개의* 감지다.

## 태그 감지 & 별칭 스펠링

`submittal/pdf_intake.py::_COIL_TYPE_BY_PREFIX`가 접두사 → `"HGRH COIL"`로 매핑한다. HGRH는 **여러
허용 스펠링**을 가진 유일한 카테고리이며, 같은 코일을 다르게 쓴 것으로 취급된다:

- `RHHGRC`, `HGRC`, `RHHGRH`, `HGRH` → 모두 HGRH. `[CONFIRMED]` 근거: `pdf_intake.py`의
  `_COIL_TAG_SPELLING_VARIANTS`; Oxygen8 제출물은 `…RC`와 `…RH` 리히트 스펠링을 둘 다 씀(예: 2766
  Olympic은 `RHHGRH-1` 사용).

> **함정:** 접두사가 없으면 = **코일이 조용히 드롭됨**. `…RH` 스펠링과 맨 `HGRH`는 한때 테이블에서
> 둘 다 빠져 있었고, 추가한 것이 그 픽스였다. 메모리 `[[rhhgrh-tag-spelling]]` 참고. HWC/PHWC와는
> 구별됨 — 이들은 *의도적으로 분리 유지*(별칭 아님).

## 헤더 수

DX와 HGRH는 헤더 수 **1HD–4HD**를 지원하며 모두 first-class다. 4HD는 실제 4HD 레퍼런스 PDF가 시드된
뒤에만 빌드 가능(서로게이트/미러 생성 절대 금지). `[CONFIRMED]` 근거: 4HD DX/HGRH 레퍼런스 LH+RH
시드됨, `docs/MVP_FINALIZATION_CHECKLIST.md` L41 `[x]`. 헤더 수는 **템플릿 선택**
(`template_population/catalog.py`)을 이끌지 규칙 엔진이 아니다 — 엔진은 멀티헤더 지오메트리를
`circuits`/`feeds` 입력으로 처리한다. `[[multi-header-geometry]]` 참고.

## 핵심 지오메트리 규칙

| 필드 | 규칙 | 값 / 공식 | 배지 | 근거 |
| --- | --- | --- | --- | --- |
| Supply I/O (Nova/Ventum/Ventum+) | `R-040` | `2` | `[CONFIRMED]` | `SOP §HGRH-TNVH`, `CHK HGRH!C33` |
| Supply I/O (Terra H / Terra H C) | `R-040b` | `2` | `[CONFIRMED]` | `John 2026-06-23: TERRA H / Terra H C HGRH supply I/O = 2` |
| Conn angle | `R-047` | `LAS` | `[CONFIRMED]` | `SOP §HGRH-TNVH/-VP`, `CHK HGRH SupConnAngle=LAS` |
| Return spacing `Rn` | `R-052` | `Terra/Nova/Ventum_H: n·D+(n−1)·1.5` ; `Ventum+: D` | `[REVIEW-REQUIRED]` | `John 2026-06-25`, `CHK HGRH!C42:C49` |
| Casing depth (멀티헤더) | `R-073` | `(circuits+1)·D+(circuits−1)·1.5` (패밀리별 분기) | `[REVIEW-REQUIRED]` | `SOP §HGRH-TNVH`, `CHK HGRH!C27 branches` |
| 도면 치수 `X` | *규칙 없음* | 미상 — 작업가설 `(h+1)·D+(h−1)·1.5`는 실측 52%만 설명 | `[REVIEW-REQUIRED]` | 실측 328장, `John 2026-09-05` |

> **R-040b 참고:** Terra H는 이전에 supply-I/O 규칙이 *없어서* 도면의 "I"가 항상 빈칸이었다. R-040b는
> `[TERRA_H, TERRA_H_C]`로 스코프되어 `[[terra-v]]`의 `R-046`과 절대 충돌하지 않는다. I/R 빈칸 역사:
> 메모리 `[[hgrh-i-r-mapping-fix]]`, `[[hgrh-r-suntion-typo]]`.

> **`X` 참고:** `X`가 **언제 존재하는지**는 확정됐다 — 리턴 연결 표기가 `OD Header`면 항상 값이
> 있고 `swt`면 항상 비어 있다(실측 328/328, 예외 0). **값이 무엇으로 결정되는지는 미상**이다:
> `R-073`의 헤더뱅크 항과 같은 형태의 작업가설이 값 있는 186장 중 52%만 설명하고, 기하가 완전히
> 동일한 두 코일이 서로 다른 `X`를 갖는다. 엔진 규칙은 **없고** 8개 공유 버킷 중 `lh_header1`만
> 빈칸을, 나머지 7개는 시드 as-built 숫자를 인쇄한다. 배선 보류(John 2026-09-05 STOP) —
> 전체는 `[[x-header-stack-depth]]`.

## 카퍼 스트랩 (HGRH 전용 가격)

`R-090`은 헤더당 배수와 함께 `copper_straps_required`를 설정 — **HGRH = 헤더당 스트랩 2개**(DX = 1).
DX/HGRH만 확정; CWC/HWC는 `[BLOCKED]`(`not_applicable`, 절대 스탬프 안 됨). `[CONFIRMED]` 근거:
`John 2026-06-23: DX = 1 strap/header, HGRH = 2 straps/header`; 패키지 어셈블러는 스트랩 노트를
DX/HGRH에만 적용(`copper_strap_pricing.COPPER_STRAP_COIL_TYPES`).

## Mechanical fit

HGRH는 드레인-팬 INSTALL 체크를 위해 파트너 코일과 페어링됨(DX+HGRH 페어):
`this_CD + partner_CD < drain-pan width`(`R-077`, `compatibility/mechanical_fit.py`가 소비, 절대
도면화 안 함). 케이싱 dim은 `MEDIUM`이라 모든 핏 판정은 `review_required`. `[[mechanical-fit]]`,
`[[confidence-gate]]` 참고.

관련 패밀리: `[[terra-v]]`(그 HGRH 스페셜은 `R-046`), `[[nova]]`, `[[ventum-plus]]`.
관련 개념: `[[x-header-stack-depth]]`, `[[multi-header-geometry]]`.
