# 신뢰도 게이트 (Confidence Gate) `[CONFIRMED]`

CoilForge의 중심 불변식이자, 이 위키가 배지 시스템으로 물려받은 규율. `coil_header_rules.yaml`의 모든
규칙은 `confidence`를 지니며, 그 신뢰도가 규칙의 출력을 *라우팅*한다. 무엇도 이를 우회하지 않는다.

## 게이트 (엔진 쪽)

`services/header_prepopulate_engine.py::bucket_for_confidence`가 해결된 각 필드를 라우팅한다:

| 신뢰도 | 버킷 | 의미 |
| --- | --- | --- |
| **`HIGH`** | `values` | 자동 프리파퓰레이트 / 도면화. 사인오프됐거나 SOP-정확. |
| **`MEDIUM`** | `suggestions` | 항상 `review_required` — 드러내되 **절대 조용히 도면화하지 않음**. |
| **`LOW`** / **`CONFLICT`** | `blocked` | `value = None` + `blocked_reason`. |

이 게이트는 데이터-컨트랙트 계층에서 다시 강제된다(`FieldValue`는 null이 아니고 override가 아닌
모든 값에 `source_evidence`를 요구) — 맨값을 몰래 넣을 수 없다. `[CONFIRMED]` 근거: `CLAUDE.md`
"confidence gate is the central invariant"; `AGENTS.md` 안전 규칙.

## 게이트 (위키 쪽) — 배지

이 위키는 게이트를 산문 배지로 반영한다(`[[WIKI]]` 참고):

- **`[CONFIRMED]`** ⇔ `HIGH` — 엔지니어링/John 사인오프. 날짜 있는 `John:` ref, `CHK`, `SOP`, 또는
  `EZC` 근거를 인용해야 함.
- **`[REVIEW-REQUIRED]`** ⇔ `MEDIUM` — 추론 / 단일 출처. 사인오프 안 된 모든 것의 기본값. 드러내되
  확정 아님.
- **`[BLOCKED]`** ⇔ `LOW`/`CONFLICT` — `blocked_reason`을 지님.

### 워크드 예시 — `CONFLICT`

`R-084`(DX ASC 방향, hot-gas-bypass)는 `CONFLICT`/`[BLOCKED]`: SOP는 "Left"라 하고 체크리스트는
LH→UP / RH→DOWN이라 한다 — 조용히 화해시킬 수 없는 서로 다른 좌표 규약. 그래서 Direct-Coil 필드
네이밍 규약이 생길 때까지 blocked로 남는다. `[BLOCKED]` 근거: `SOP §DX-TNVH SPECIAL CASE 'Left'`
vs `CHK DX!C61 LH→UP/RH→DOWN`.

### 워크드 예시 — 자동 도면화되면 안 되는 `MEDIUM`

`R-074` 케이싱 dim은 단일 출처(체크리스트만; SOP엔 동등 테이블 없음)라 케이싱 룩업 전체가 `MEDIUM`
→ `[REVIEW-REQUIRED]`. 따라서 그 위에 세워진 모든 mechanical-fit 판정은 `review_required` — **PASS는
절대 승인이 아니다.** `[REVIEW-REQUIRED]` 근거: `R-074` `confidence: MEDIUM`; `CHK Units sheet`.

## 왜 여기서 load-bearing인가

이 규율 없는 위키는 그럴듯하게 들리는 허구로 흘러간다 — `AGENTS.md`가 금지하는 바로 그것
("엔지니어링 값을 지어내지 않는다", "추론된 매핑을 확정으로 취급하지 않는다"). 배지는 모든 페이지가
*얼마나 확신하는지*와 *누구의 권위로*를 선언하게 강제한다. `[REVIEW-REQUIRED]`에서 `[CONFIRMED]`로의
승격은 **엔지니어링 이벤트**(날짜 있는 `John:` 사인오프)이며 `[[log]]`에 기록된다 — 조용한 편집이 아니다.

관련: `[[terra-v]]`(그 스페셜들은 2026-06-28에 LOW→HIGH 승격됨), `[[open-questions]]`(John의 HIGH
사인오프를 기다리는 `MEDIUM` 항목들).
