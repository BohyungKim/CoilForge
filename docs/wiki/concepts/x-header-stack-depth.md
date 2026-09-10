# 도면 치수 `X` — HGRH 헤더 기하 열 `[REVIEW-REQUIRED]`

CoilMaster 도면의 타이틀블록 치수표는 `ROWS, X, FH, FL, CH, CL, CD, HD, OAL, …` 순서로 값을 싣고
(`docs/DRAWING_TEMPLATE_SPEC.md`), 일부 HGRH 시트는 같은 값을 top view의 헤더 끝단에 파란색(`#1c0a80`)
콜아웃 `… X`로도 인쇄한다.

**이 페이지의 상태(2026-09-05):** `X`가 **언제 존재하는지**는 실측으로 확정됐다. **그 값이 무엇으로
결정되는지는 아직 모른다** — 유력했던 공식이 실측 코퍼스의 절반에서 깨졌다. 엔진 배선은 **보류**이며
`slot.X`는 여전히 어떤 규칙도 방출하지 않는다.

> **2026-09-03 판에서 철회한 것 2건** — 아래 §철회 참조. 그때 이 페이지는 공식을 `[CONFIRMED]`로
> 단정했으나, 328장 실측이 그것을 과대 진술로 만들었다.

---

## 확정: `X`의 존재 여부는 리턴 연결 표기와 완전 상관 `[CONFIRMED]`

| `RETURN CONN SIZE` 표기 | `X` 있음 | `X` 공란 |
| --- | --- | --- |
| `… " OD Header` | **186** | **0** |
| `… " swt` | **0** | **142** |

**328/328, 예외 0건.** 원문 분포: `0.625" OD Header` 161 · `0.63" swt` 121 · `0.875" OD Header` 24 ·
`0.88" swt` 19 · `0.50" swt` 2 · `0.500" OD Header` 1.

`X`가 공란인 **142장은 전부 `I`·`S`·`O`·`R`도 공란**이다(부분 공란 0건). 즉 하위 헤더 기하 열이
통째로 있거나 통째로 없다.

> **용어:** 이것을 **connection-notation cohort**라 부른다. 도면의 버전·발행일 근거가 없으므로
> "구형/신형 도면 세대"라고 부르지 **않는다.** 소수 2자리(`0.63`)/3자리(`0.625`) 차이도 두 어휘의
> 부산물이지 원인이 아니다.

> `[LIKELY]` — swt(sweat/솔더) 연결 코일은 헤더가 없으므로 헤더 기하(`X`·`I`·`S`·`O`·`R`)가 애초에
> 존재하지 않는다는 해석. 물리적으로 자연스럽지만 **CoilMaster/SOP 문서로 확인되지 않았다.**
> `[[open-questions]]`에 등재.

## 작업 가설: `X` = 헤더 스택 깊이 `[REVIEW-REQUIRED]`

```
X = (h+1)·D + (h−1)·1.5        h = 그려진 헤더 수, D = 헤더(리턴) 연결 사이즈
```

이 식을 뒷받침하는 것:

- `_hgrh_cd_multi`의 Nova/Ventum-H 분기 `(n+1)*conn + (n-1)*1.5`
  (`services/header_prepopulate_engine.py`)와 **문자 그대로 같다**. `R-073` /
  `CHK HGRH!C27 branches` / `SOP §HGRH-TNVH`.
- 시드 8건이 D=0.625에서 소수점까지 일치: 1HD `1.25` · 2HD `3.375` · 3HD `5.50` · 4HD `7.625`.
- 시드 `EZC-0016`(`coilmaster_hgrh_rh_header3`)은 `CD` = `X` = 5.50이고, SVG에서 두 치수선 길이가
  같다(36.4pt, `D`만큼 평행 이동) → `X`는 `CD`의 하한이라는 해석과 맞는다.
- `FEED-HG_4_LH`는 공급 0.875"/리턴 0.625"인데 `X` = 7.625 → **공급 연결에는 불변, 리턴을 따른다.**

**그러나 실측에서 절반이 깨진다** `[CONFIRMED]`:
OD Header 코호트 **186장 중 공식 일치는 96장(52%)**. 불일치 값 `1.63`·`2.00`·`2.50`·`3.00`·`3.25`·
`1.38`·`3.37` 은 **h = 1..8 어디로도 재현되지 않는다** — D=0.625의 계단은 `1.25 → 3.375 → 5.5 → 7.625`,
D=0.875는 `1.75 → 4.125 → 6.5 → 8.875`인데 관측값이 그 **사이**에 떨어진다. 헤더 수 판정 오류가 아니다.

**결정적 반례:** `FH·FL·CH·CL·CD·OAL·SL·I·S·O`가 **완전히 동일한 두 코일**(2575 Texas football /
2504 Barrel Room)이 `X`만 1.94 대 2.00으로 다르다. **`X`를 움직이는 변수는 타이틀블록 안에 없다.**

## 계열 의존은 판정 불가 — 두 프록시가 서로 어긋난다 `[REVIEW-REQUIRED]`

| 단일계열 프로젝트 (유닛 코드 기준) | 일치 | 불일치 |
| --- | --- | --- |
| NOVA | 19 | 9 |
| TERRA_H | 3 | 12 |
| TERRA_V | 3 | 0 |
| VENTUM(모호) | 5 | 16 |

같은 데이터를 `TF=BF=0.63`(계열 프록시)으로 자르면 **77 일치 / 15 불일치 = 84%**가 나온다.
**두 프록시가 어긋난다.** 어느 쪽도 신뢰할 수 없다 — `TF`/`BF`는 계열 프록시로 깨끗하지 않고
(시드 `coilmaster_hgrh_rh_header2`가 `TF=1.63/BF=0.38`), 프로젝트 폴더의 유닛 코드는 다중유닛
프로젝트에서 오염된다(2607 UCSB = `TR_C` 6종 혼재).

## 철회 (2026-09-05)

1. **"Terra V는 `X`를 원래 비운다"** — **순환논법이었다.** "I/S/O/R 공란"으로 Terra V를 정의하고
   "X 공란"을 결론으로 삼았는데 둘은 같은 현상이다. Terra V 독립 마커(`I1=2.75`/`SL1=5` 산문, `R-046`)는
   코퍼스 전체에서 **1장**뿐이다. 실제로 단일 Terra V 프로젝트 전수는:

   | 프로젝트 | 코드 | `X` | 리턴 연결 |
   | --- | --- | --- | --- |
   | 2628 Hoffman 2709 Laurel | `TV_B_009` | 공란 | `0.63" swt` |
   | 2864 Okaloosa | `TV_B_018` | 공란 | `0.63" swt` |
   | 3025 Bauducco (3면) | `TV_B_024` | **1.25** | `0.625" OD Header` |

   → 공란은 Terra V 규칙이 아니라 **swt 코호트**였다. **Terra V는 특별하지 않다.**

2. **"Terra H는 Nova 공식을 따른다"** — 1970 Hope Lodge 2장(4HD `7.63`, 2HD `3.38`)으로 일반화했으나,
   그 두 장이 Terra H **일치 3장** 안에 들어 있었다. **표본 선택이었다.**

## 측정의 재현 정보

**대상 선정 기준**
```
glob: ...\Sales - Documents\02 - POs\*\Accessory Order Forms\Coil*master\*.pdf
    + ...\Sales - Documents\02 - POs\*\Accessory Order Forms\*RHHGRC*.pdf
page 채택: 본문에 /\b(RHHGRC|HGRC)-\d+/ 가 있고 타이틀블록 치수표가 파싱될 것
값 매핑 : 시더 `_title_block_tokens`와 동일 로직 — 라벨 최밀집 y-band = 헤더 행,
          그 아래 25pt 내 숫자를 x 중심 거리로 열에 매칭
일치 판정: X == (h+1)*D + (h-1)*1.5 를 h = 1..8 전부 시도 (헤더 수 판정과 무관)
```

**퍼널** — glob 511 PDF → 열기 실패 1 → 510 열림 → 전체 1,964 페이지 → HGRH 태그 없음 1,333 제외 →
태그된 631 → 타이틀블록 파싱 실패 303 제외 → **측정 코퍼스 328**.

**제외 303건은 양성 제외** (표본 확인함):
- `치수 라벨 없음` 248 — 전부 각 코일 PDF 1페이지의 **CoilMaster 성능/표지 시트**
  (머리글 `440 Industrial Drive * Moscow, TN * …`). 도면이 아니다.
- `라벨 밀집 <6` 55 — 표본(2097 Go Green)은 **텍스트 레이어가 비어 있다**(추출 결과 ` | | | |`).
  이미지 전용 페이지로 보인다. → ⚠️ **텍스트 레이어 없는 도면은 이 측정의 사각지대다.**
- 열기 실패 1 — `2575 … Coils Performances & Drawings.pdf` `FileNotFoundError`
  (OneDrive 미하이드레이트 추정).

**좌표 스팟체크 4건** (수동 검증, `X` 헤더 중심 대비 값 위치):

| 코호트 | 문서 | 라벨/값 | `X` 헤더 중심 | `X` 열 ±22pt 내 값 |
| --- | --- | --- | --- | --- |
| OD Header / 일치 | `1970 Hope Lodge` p5 | 19 / 19 | 98.2 | `7.63 @104.2` |
| OD Header / 불일치 | `2504 Barrel Room` p4 | 19 / 19 | 98.1 | `2.00 @104.2` |
| swt / 공란 | `2864 Okaloosa` p3 | 19 / 14 | 98.2 | **없음** |
| swt / 공란 | `2628 Hoffman` p3 | 19 / 14 | 98.2 | **없음** |

## 오늘의 코드 동작 — 8개 버킷이 두 가지로 갈린다 `[CONFIRMED]`

`slot.X`를 채우는 배선이 **전무**하다. 어떤 YAML 규칙도 방출하지 않고 `PARAM_TO_SLOT`에도 없다.

| 버킷 | 상태 | 도면 출력 |
| --- | --- | --- |
| `coilmaster_hgrh_lh_header1` | `{{slot.X}}` 슬롯화됨 (SVG + `slot_map.json` 양쪽) | **`— X` 빈칸** |
| 나머지 7개 | 시드 as-built 숫자가 리터럴로 잔존 | **시드 숫자 그대로** (`1.25`/`3.38`/`5.50`/`7.63`) |

3179 실측: `RHHGRC-1`/`-3` = `— X`, `RHHGRC-2`/`-4` = `3.38 X`.
슬롯 치환은 `slot_map.json`에 등록된 slot_id만 대상으로 하므로(`slot_population.py`) 리터럴 콜아웃은
**어떤 기존 테스트에도 잡히지 않는다.** 인벤토리 가드 `tests/test_template_hardcoded_dims.py::_KNOWN_OPEN`이
이 7건을 **등식**으로 고정한다.

**리댁션만 단독 실행 금지 (John 2026-09-05):** 규칙 없이 7개를 슬롯화하면 모든 계열이 `— X`가 되는
회귀가 된다. `_SLOT_ENGINE_FIELD`는 `values`(HIGH)만 읽으므로 중간 상태가 없다.

## 배선 착수 시의 함정 3건 `[CONFIRMED]`

### 1. 🔴 `header_count`로는 규칙이 발화하지 않는다 — 입력은 `circuits`
`capture/record.py`: *"derive_slot_values passes an explicit subset, so application /
**header_count** / qty_conn_per_header are structurally absent on the analyze path."*
`submittal/pdf_to_template_drawing.py`의 `build_drawing_slots(...)` 호출에 `header_count` 인자가 없다.
올바른 입력은 `circuits`다 — `workflows/submittal_to_drawing.py`: *"``circuits`` **IS the header count
on this path**"*, 그리고 `pdf_to_template_drawing.py`가 `header_type = f"Header {circuits}"`로
**버킷을 고르는 그 수량**이다.

> ⚠️ `_hgrh_cd_multi`의 `n = qty_conn_per_header or circuits` 관용구를 **복사하면 안 된다.**
> 3095처럼 `qty_conn_per_header=2, circuits=1`인 코일은 Header 1 템플릿을 그리는데 n=2가 된다.

### 2. 🔴 시더는 재시드 시 `X` 콜아웃을 삭제한다
`scripts/seed_templates_from_pdf.py`의 `if label == "X": return ""` (`John 2026-06-27`).
지금 어느 HGRH 버킷을 `build-one`으로 재시드하면 `X`가 사라지고 인벤토리 가드가
`known − found` 방향으로 실패한다.

### 3. 타이틀블록 사본은 렌더되지 않는다 (범위 밖)
`X` 숫자는 타이틀블록 치수표(x = 95.0, y_screen = 523.3)에도 있으나 리뷰 도면의 크롭
`x[110, 652] y[19, 492]`(`workflows/submittal_to_drawing.py`) **바깥이라 인쇄되지 않는다.**

## 배선 시 넣지 말아야 할 곳 `[CONFIRMED]`

**Drawing Parameters 패널에 `X` 행을 추가하지 않는다.** 패널 키 목록에 카테고리 필터가 없어
DX/CWC/HWC 전부에 빈 `X` 행이 생기고, `review/project_gate.py::_classify_coil`이 빈 값을 blocked
예외로 세므로 **거의 모든 코일에서 `exceptions_K`가 +1** 된다. 또 `X`는 CCSI Direct Coil 폼에 필드가
없다 — `drawing/label_authority.py`의 `_GEOMETRY_LABEL_BASES`가 이미 "13키 패널 밖이지만 실재하는
도면 라벨"로 올바르게 분류한다.

## 물 코일의 `X` `[REVIEW-REQUIRED]`

CWC/HWC 템플릿의 타이틀블록 `X`는 `coilmaster_cwc_lh` 3.90 · `coilmaster_cwc_rh` 2.60 ·
`hwc` 1.38 / `vplus_hwc_rh` 1.88로 갈린다. 물 템플릿에는 도면 영역 `X` 콜아웃이 없어 인쇄되지 않는다.
HGRH와 같은 양인지 미확인.

---

## 다음에 필요한 것

코퍼스 역추정으로는 닫히지 않는다(값이 공식의 계단 사이에 떨어지고, 동일 기하 코일이 서로 다른 `X`를
가진다). 필요한 것은 **`X`가 무엇을 재는 치수인가의 정의** 또는 **`X`를 결정하는 source input의 이름**이다.
`[[open-questions]]` 참조.

관련: `[[hgrh]]`, `[[multi-header-geometry]]`, `[[confidence-gate]]`, `[[terra-v]]`,
`[[ventum-plus]]`, `[[open-questions]]`. 규칙 사전: `docs/rules/coil_header_rule_extraction.md`.
인벤토리 백로그: `docs/TEMPLATE_HARDCODED_DIMS_BACKLOG.md`.
