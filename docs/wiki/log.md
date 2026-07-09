# CoilForge 위키 — 연산 로그

위키 연산의 append-only 기록, 최신순. 각 항목: 날짜 · 연산(`ingest` | `query` | `lint`) · 제목 ·
바뀐 것. 날짜는 America/Toronto이며 기록 시점에 확인된 값만 쓰고 지어내지 않는다. 이것은 *지식*-연산
로그로 — `docs/SESSION_LOG.md`(dev 인수인계 로그)와 구별된다.

<!-- LOG (newest first) -->

## 2026-07-08 · ingest — R-074 2차 출처 판정 + R-048/R-085 조건부 발화 검증
로드맵 후속 두 항목 처리 결과를 원장에 반영. **R-074**(casing dims): 코드베이스 내부에 독립 2차
출처 없음 판정(`mechanical_fit`/`checklist`는 R-074 소비=순환; slot `casing_height`는 다른 물리량;
SOP 등가 테이블 없음) → MEDIUM 유지 확정, 승격 트리거 = 외부 2차 출처 확보. **R-048**: 조건부 발화
(circuits+conn_size+rows) HIGH 검증 + **supply≠return 공식 결함** 발견(엔진이 supply에 return과 동일
리스트; YAML 공식은 supply=CD−[...]) → `[REVIEW-REQUIRED]` 별도 처리 등재. **R-085**: back_to_back
HIGH 발화 검증 + **실 경로 미배선**(입력이 `build_header_request`에 없음) 판정 등재. 신규 유닛테스트
4건(`test_header_prepopulate_engine.py`), R-048 YAML confidence stale(MEDIUM→HIGH) 정정. `src/` 값
변경 없음(엔지니어링 값 무발명). `[[open-questions]]`·`[[hgrh]]` 조정, 근거
`docs/mvp_promotion_decisions.md` §후속.

## 2026-07-07 · lint — MEDIUM→HIGH 승격 원장 정정
`open-questions.md`의 "AWAITING SIGN-OFF"(R-044a/c·R-048·R-066·R-002b·R-073·R-074·R-077·R-085·R-086)를
John 2026-07-07 판정 결과로 갱신: 승격 5(R-066/R-002b/R-085/R-044c/R-048)·검토유지 2(R-044a/R-074)·
재분류 3(R-073/R-077/R-086). 근거 `docs/mvp_promotion_decisions.md` + `coil_header_rules.yaml`.

## 2026-07-06 · ingest — Ventum+ 전용 템플릿 시드 (product_family fork)
R-032 UP 갭 근본 해결: catalog에 `product_family` 축(2-pass: 전용 우선→공유 fallback) 추가 후, 실제
Ventum+ 선정 도면(2폴더·69페이지 스윕, `scripts/inventory_ventum_selection.py`)에서 **11개 전용 템플릿
시드** — DX 5·HGRH 3·HWC 2·CWC 1. 시더는 vector artwork를 그대로 복사하므로 distributor UP이 자연
캡처됨(eyeball로 hgrh_lh/cwc_lh 모델번호 `-L` 확인). 미시드 조합·타 라인은 공유 22버킷 그대로(무회귀,
776 tests green). `[[ventum-plus]]` 템플릿 섹션 갱신, `[[index]]`·`[[open-questions]]` 조정. John eyeball
게이트 대기.

## 2026-07-06 · query+ingest — Ventum+ distributor orientation (R-032 UP)
질의: "Ventum+ 전용 template을 이미 시딩했나?" → **아니오.** 2026-07-03은 전용 시드가 아니라 공유
템플릿 재사용 un-block(`[[open-questions]]` D4). 조사 중 로드-베어링 갭 발견: R-032가 Ventum+ DX
distributor를 `ConnectionUp`으로 `HIGH` 계산하지만 도면 경로가 `dist_orientation`을 소비하지 않아
distributor를 `DOWN`으로 오도(誤導). 처리(2026-07-06): 프로즌 경로 loud 경고
(`_flag_distributor_orientation_review`) + 파라메트릭 엔진이 `slot.DIST_ORIENTATION`→
`HeaderSpec.orientation`→UP top-edge 배치로 소비. 새 페이지 `[[ventum-plus]]` 생성(스텁 승격),
`[[index]]` 제품 섹션 추가, `[[open-questions]]`에 eyeball-대기 항목 추가. 771 테스트 그린.

## 2026-07-06 · lint — 2차 드리프트 재확인 패스
전체 위키 8파일 점검. 위키↔코드: 15 규칙 ID + enum 2 전부 일치 (드리프트 0). D2/D3/D4는 여전히
활성 — `CLAUDE.md`가 Terra V를 "LOW/blocked (R-023/R-046/R-067)"라 하지만 셋 다 `HIGH`(D3);
target-vs-code 표는 4HD를 `placeholder_blocked`라 하나 `catalog.py`는 4버킷 `_SEEDED`(D2);
Ventum+ 모순(D4) 미조정. 소스 수정은 John에게 (엄격 프로토콜). D1은 `CLAUDE.md`가 이미 수정됨
(L88/92) → `[[open-questions]]` D1을 CLOSED로 조정; 잔여 낡음은 메모리 파일뿐(위키 범위 밖).

## 2026-07-04 · ingest — 위키 부트스트랩 (Karpathy LLM-Wiki 패턴)
사내 정제 소스로부터 위키를 시드함. `[[WIKI]]`(스키마), `[[index]]`, `[[sources]]`,
`[[open-questions]]`, 그리고 엔티티/개념 유형별 워크드 예시 한 개씩 생성:
`[[hgrh]]`, `[[terra-v]]`, `[[confidence-gate]]`. 모든 주장은 배지 + `coil_header_rules.yaml`까지
추적 가능한 `evidence_ref`를 지닌다. 원본 소스는 읽거나 수정하지 않음; `src/` 변경 없음. 사실 출처:
R-021v/R-023/R-040b/R-046/R-052/R-067/R-070/R-074/R-076/R-090 및 `schemas/header_prepopulate.py`의 enum.

## 2026-07-04 · lint — 첫 드리프트 패스 (기록만, 아직 조정 전)
John을 위해 라이브 위키↔코드 / 문서↔문서 드리프트 3건을 플래그함(상세는 `[[open-questions]]`):
1. **Terra-V 케이싱 값** 060/072/084/100 이 `R-074`(`TERRA_V|INTEGRATED|*`)에 **존재**하는데,
   메모리/CLAUDE.md는 아직 "owed by John"이라 설명함. → 남은 항목 CLOSED.
2. **4HD** DX/HGRH가 시드됨(`MVP_FINALIZATION_CHECKLIST.md` L41 `[x]`)인데, CLAUDE.md의
   target-vs-code 표는 여전히 4HD 버킷을 `placeholder_blocked` 데드엔드라 부름. → 낡음.
3. **Terra-V 라우팅**: CLAUDE.md는 Terra V가 "LOW/blocked로 라우팅(R-023/R-046/R-067)"이라 하지만,
   셋 다 지금 `HIGH`(SOP-confirmed, 2026-06-28 승격). → 낡음.
추가로 문서↔문서 모순: **Ventum+ fork**가 MVP 체크리스트(L43)에선 `[ ]` 열림인데 CLAUDE.md에선
"불필요로 폐기됨". → 조정 필요.

## 2026-07-07 · ingest — multi-header-geometry 스텁 시드
`[[multi-header-geometry]]` 스텁을 시드함(circuits/feeds → Nth 헤더). 핵심 `[CONFIRMED]` 사실:
**John 2026-07-06 — N interlaced circuits = N 공급 헤더 (DX/HGRH)**, 따라서 `circuits`가
`submittal_to_drawing.py`에서 "Header N" 템플릿 키를 옳게 이끈다(버그 아님). 근거: 세션 라이브 확인
(ALS Palmetto `CDXC-1` "Interlaced 2 Circuits" → circuits=2 → Header 2). 인덱스: 스텁 → 개념 섹션으로
이동. `src/` 변경 없음. 관련 공식 규칙 R-022/R-034/R-048/R-052/R-072/R-073 참조.
