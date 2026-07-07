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

## John의 사인오프 대기 (MEDIUM → HIGH)

`docs/MVP_FINALIZATION_CHECKLIST.md` §"MEDIUM→HIGH promotions"에서:
- `R-044a/c` supply_sl · `R-048` HGRH positions · `R-066` vent_drain · `R-002b` lifting_lugs ·
  `R-073` HGRH casing depth · `R-074` casing dims · `R-077` drain-pan · `R-085` back-to-back ·
  `R-086` coil style. **상태: AWAITING SIGN-OFF.**

## 열린 엔지니어링 작업

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
- **[EXT] 커버리지-대시보드 생성기** (`scripts/generate_coverage_dashboard.py`)로 손으로 쓴
  `docs/coverage_dashboard.html`을 대체. **OPEN.**
- **[MVP] Ventum+ distributor orientation (R-032 UP) 도면 반영** — 엔진은 UP을 `HIGH`로 계산하나 도면
  경로가 소비 안 하던 갭 (2026-07-06 발견). **근본 해결:** catalog `product_family` fork + 실제 Ventum+
  참조에서 **11개 전용 템플릿 시드**(vector artwork 그대로 복사 → UP 자연 캡처); 시드 조합은 전용 라우팅 +
  경고 자동 해제, 미시드 조합만 공유 DOWN + 경고. 파라메트릭 엔진도 UP 지원(`schematic_layout`). 남은 것:
  각 시드 템플릿의 **John eyeball 게이트**. hand 미표기 프로젝트 hand 확정 완료(John 2026-07-06):
  **2666 Pembroke HQ DX = LH, 2658 Fitchburg CWC = LH** → 둘 다 기존 시드(dx_lh_header3, cwc_lh)와 중복,
  신규 버킷 없음. **11개가 이 참조 폴더의 완전한 시드 집합.**
  `[[ventum-plus]]` 참고. **OPEN (eyeball 대기).**

## 닫힘 (감사 추적)
- Terra-V 4 케이싱 값 → 채워짐 (D1). · 4HD → 시드됨 (D2). · Terra-V DX/HGRH/water 스페셜 →
  2026-06-28 HIGH 승격 (D3). · Ventum+ → 언블록, 2026-07-03 공유 템플릿으로 도면화 (D4 문서 측).
