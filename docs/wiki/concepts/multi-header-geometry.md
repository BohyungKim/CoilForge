# 멀티헤더 지오메트리 — circuits/feeds → Nth 헤더 `[CONFIRMED]`

DX와 HGRH는 헤더 수 **1HD–4HD**를 지원한다(`[[hgrh]]` 참고). 헤더 수는 **템플릿 선택**을 이끌고
(`template_population/catalog.py`), 두 번째/N번째 물리 헤더의 도면 치수 컬럼(`I2`/`S2`/`O2`/`R2`/`HD2`/`ZD2`)을
추가한다. 규칙 엔진은 이 멀티헤더 지오메트리를 `circuits`/`feeds` 입력으로 계산한다.

## circuit 수 = 공급 헤더 수 (DX/HGRH)

제출물이 "Coil Style: Interlaced N Circuits"로 회로 수를 명시하면
(`pdf_intake.py::_circuits_from_coil_style` → `geometry.circuits`), 그 값이
`workflows/submittal_to_drawing.py`에서 "Header N" 템플릿 키를 이끈다 — 즉 **N 회로 = N 공급 헤더**.

- `[CONFIRMED]` 근거: `John 2026-07-06: 2 interlaced circuits = 2 supply headers`. 예) ALS Palmetto
  `CDXC-1`은 "Interlaced 2 Circuits"라 `circuits=2` → **Header 2**로 옳게 그려진다. **같은 프로젝트의**
  `RHHGRC-1`은 `circuits=1` → Header 1. circuit 수와 헤더 수를 동일시하는 것은 버그가 아니라 확정된
  동작이다. (태그별 상수가 아니다 — 프로젝트 3095의 `RHHGRC-1`은 `circuits=2` → Header 2다.)

> **circuits 출처 함정:** circuit 수는 별도 "Circuits" 셀이 아니라 "Coil Style" 산문에만 있을 때가
> 많다("Interlaced 2 Circuits"). 숫자 없는 맨 "Interlaced"는 절대 2로 추정하지 않는다(소스에 없는 값
> 금지 → `MEDIUM`/review-required). 메모리 `[[circuit-count-in-coil-style]]` 참고.

> **수량이 단어로 적히는 표기 `[CONFIRMED]`:** 산문이 항상 "Circuit"이라는 낱말을 쓰지는 않는다.
> 프로젝트 3095는 `Coil Style: Dual Face Split`(HGRH) / `Dual Interlaced`(DX)로 적었고, R-086이
> 이미 규정한 어휘다 — DX `Interlaced N Circuits`, HGRH `Face Split N Circuits`
> (`docs/rules/coil_header_rule_extraction.md`). 그래서 `_circuits_from_coil_style`은 수량 단어가
> 네 서술자(`Circuit`/`Interlaced`/`Intertwined`/`Face Split`) 중 **바로 옆에 붙었을 때만** 회로수로
> 읽는다. 인접 조건이 있는 이유: "Single Row"의 `Single`은 행 수다. 근거 없이 `circuits`가 1로
> 떨어지면 `_flag_header_count_conflict`가 "Qty Conn. / Header"와 대조해 배너를 띄운다(값은 불변).

> **헤더 수 이중 검증 `[CONFIRMED]` (John 2026-10-14, 프로젝트 2950):** 2950 `RHHGRC-1`은
> `Coil Style: Face Split`(숫자 없음) + `Qty Conn. / Header 2`였다. 회로 수를 읽지 못해 intake
> 기본값 `Header 1`로 그려졌고, 2헤더 코일이 1헤더 아트로 출하됐다. 이제 두 층으로 막는다.
> - **Layer 1** (`submittal/header_count.py`) — 원문 신호를 모두 모아 판정한다.
>   - 회로 수 신호: Circuits 칸, Coil Style 숫자, 실제로 읽힌 Header Type.
>   - 회로 수 신호끼리 다르면 `conflict`다.
>   - 회로 수 신호가 없으면 `Qty Conn./Header` 하나로 답한다(John Q1=A, 코퍼스 52/52 일치).
>   - `Standard`는 신호가 아니다. intake 기본값 줄도 신호가 아니다.
>   - 스캔 도면의 `C1:/C2:`는 `absent`만 막고 값은 정하지 않는다.
> - **Layer 2** (`_gate_header_count`) — 실제 그린 아트의 헤더 수가 Layer 1 값과 다르거나,
>   원문이 헤더 수를 세우지 못하면(`absent`/`conflict`) 도면을 **보류**하고 Circuits 입력을 요청한다.
>   - 사람이 친 Circuits는 그대로 그리고 `overridden`으로 표시한다.
>   - analyze에서는 Layer 1이 고른 circuits로 아트가 선택되므로 Layer 2가 거의 동어반복이다.
>     Layer 2가 독립적으로 지키는 것은 최종 상태다(전용 버킷 교체·derive 재선택·`absent`/`conflict`).
> - 같은 값을 도면, 체크리스트(DX/HGRH), Direct Coil paste 필드, 동관 strap 가격이 함께 쓴다.

## 멀티헤더 공식 규칙

`circuits`/`feeds`가 second/Nth 헤더의 지오메트리를 계산한다: `R-022`, `R-034`, `R-048`,
`R-052`(리턴 스페이싱 `Rn`), `R-072`/`R-073`(케이싱 깊이). 패밀리별 분기 있음 — `[[hgrh]]`의 케이싱
깊이 `R-073` `(circuits+1)·D+(circuits−1)·1.5` 참고.

> **물-코일 주의:** CWC/HWC는 **1HD 전용**이며 그 `geometry.circuits`는 전기 회로수이지 헤더 수가
> 아니다 — `submittal_to_drawing.py`가 물-코일 헤더를 강제로 1로 고정한다(그렇지 않으면 존재하지 않는
> "Header 4" 버킷이 선택되어 도면이 실패). `[[confidence-gate]]` / `[[hgrh]]` 참고.

관련: `[[hgrh]]`, `[[taxonomy]]`, 메모리 `[[multi-header-mapping]]`.
