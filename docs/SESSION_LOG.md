# CoilForge Session Log

`/checkpoint`가 쌓는 세션 인수인계 로그 (최신순). 각 항목 = 이번 세션 구현 내용 + 다음 스텝.
제조 기록이 아니라 재개용 dev-log다.

<!-- CHECKPOINTS (newest first) -->

## 2026-09-02 (Toronto) · base dd99c8d..ebb3c35 · claude/ambient-supplier
> 이번 세션의 커밋은 `ebb3c35` 하나. 범위 안의 나머지 5개(`8bac658`·`9bfef68`·`2f67dac`·`27d1ef9`·
> `d60bad1`)는 다른 세션의 Terra V HGRH 트랙이며 로드맵 완료 섹션에 이미 기록돼 있다.

### ✅ 구현/결정된 것
- **3179 TWU 검증 → 커버 파서 결함 1건 수정으로 DX 결함 3건 동시 해소** (커밋 `ebb3c35`).
  두 커버 파서가 `qty`에 대해 비대칭이었다: 텍스트 경로는 행 정규식이 `^(?P<qty>\d+)\s+…`로 수량을
  **구조적으로 요구**하지만, 테이블 경로 `_extract_cover_rows_from_table`은 `qty`를 읽어놓고 **검사하지
  않았다**(게이트가 `tag` 유무 + `coil_tag_rejection_reason` 둘뿐). pdfplumber가 여러 줄 Item 셀을 자기
  행으로 쪼개면서 태그를 반복하고 Qty를 비우고 Item에 꼬리(`'Coil)'`)만 남긴 행이 **통째로 코일이 됐다** —
  손이 기본값 LH로 채워진 가짜 도면이 견적 패키지에 삽입됨. 게이트는 **중복 태그 AND qty 없음**의 결합에만
  건다(빈 Qty 단독으로 거부하면 그런 레이아웃의 코일을 통째로 잃는다). 침묵 삭제 금지 — 기존 `rejected`
  채널로 `non_coil_rows_excluded`에 표시.
- **캐스케이드는 가정하지 않고 검증으로 확인했다.** 계획서에 "Phase 1이 ②③을 고칠 것이라고 가정하지
  않는다"고 명시하고 실문서 게이트로 확인한 결과, 유령 행이 DX 상세 블록 바인딩을 밀고 있었음:
  CDXC-3(048)이 100 유닛 치수를 쓰던 것 → **CH 43.25 / FL 33 복구**, CDXC-4 치수 전무 → **54슬롯 복구**.
  (근거: 두 실문서 게이트, 아래 anchors)
- **정본 확정:** `Desktop\3179 - Oxygen8 Submittal - Havtech - 3179 - TWU - Rev0.pdf`
  (sha256 `b76a4e38…`, `Final Working\…Rev0.pdf`와 **바이트 동일**). **정본에는 결함 3건이 원래 없었다** —
  세 결함은 서명본(`Signed Final Submittal\Record Submittal…8-26-2026.pdf`, 235쪽)에서만 재현.
- **오보 1건 철회:** "Right 코일 4개가 LH로 그려진다"는 보고는 **틀렸다.** 브라우저에 넣은 파일과 제가
  헤드리스로 분석한 파일이 **서로 달랐다**(Downloads의 체크리스트 출력 파일명으로 특정). 두 문서 모두
  자기 커버대로 정확히 해석한다. 교훈: 브라우저 실측과 헤드리스를 비교하기 전에 **입력 파일 동일성부터**.
- **RHHGRC 체크리스트 불일치 14건은 CoilForge 결함이 아니다** — 전부 John이 2026-08-04에
  `checklist_wrong`으로 판정한 KD-001~005(체크리스트 시트에 Terra V 분기 없음). `known_defect: 0`.
- **테스트:** 신규 4건(wrap 거부 / wrap 사유 보고 / **첫 등장 qty 없음은 계속 코일** / 정상 8행 커버 무변화).
  전체 **1612 passed, 0 failed**.

### ⏭️ 다음 스텝
- [ ] **[최우선] RHHGRC `X` 치수 — 7개 HGRH 템플릿의 얼어붙은 as-built 값.** 상세는 `.claude/roadmap.md`
  "⬜ 앞으로" 최상단 항목에 전부 적어 뒀다(고정값 7건 목록·선택지 3개·필요한 승인 2건).
  (왜 남음: ⓐ 처리 방식 선택 ⓑ **DO-NOT-TOUCH 편집 승인 범위**가 John 결정)
- [ ] **서명본 vs 정본 핸딩 불일치 자동 검출 (제안만)** — 같은 3179의 두 제출서가 4개 코일의 handing을
  Left↔Right로 다르게 기재한다. CoilForge는 문서 간 대조를 하지 않아 검출 불가. (왜 남음: 별건, 미승인)
- [ ] **Phase 2 DX 블록 바인딩 조사 — 보류(닫지 않음).** 증상은 사라졌지만 바인딩 규칙 자체는 읽지 않았다.
  유령 행 없이 같은 어긋남을 내는 문서가 나오면 재개. (왜 남음: 우선순위 낮아짐)
- [ ] **다른 세션 미커밋 정리 (John)** — `.claude/roadmap.md`(내 항목 포함), `capture/{db,observe}.py`,
  `tests/test_capture_ledger.py`, 미추적 `.agents/ .codex/ pytest.ini scripts/migrate_capture_ledger.py`,
  `tests/test_template_hardcoded_dims.py`. (왜 남음: **내 커밋에 섞으면 안 되는 남의 작업**)

### 🔎 Resume anchors
- branch: claude/ambient-supplier · HEAD: `ebb3c351ac97efbd6160eb9c246430bfc5e259f8` (pushed)
- **⚠️ 로드맵 항목은 커밋되지 않았다** — `.claude/roadmap.md`에 다른 세션의 미커밋 변경(+18줄)이 함께
  있어, 그 파일을 커밋하면 남의 작업이 딸려간다. 내 항목은 워킹트리에만 있으며 이 로그가 백업이다.
- 핵심 경로: `src/coilforge/submittal/pdf_intake.py::_extract_cover_rows_from_table` (게이트) ·
  `tests/test_phase2e_pdf_coil_intake.py` (신규 4건) ·
  `tests/test_template_hardcoded_dims.py::_KNOWN_OPEN` (X 7건이 **등식**으로 고정, untracked)
- 롤백: `git revert ebb3c35`, 또는 `if qty is None and tag in seen_tags:` 블록 + `seen_tags` 두 줄 제거
- 실문서(저장소 밖, gitignore 대상): 정본 `C:\Users\JohnKim\Desktop\3179 - Oxygen8 Submittal - Havtech -
  3179 - TWU - Rev0.pdf` · 서명본 `…\02 - POs\3179 - Havtech - TWU\Signed Final Submittal\Record
  Submittal - TWU Alumnae Hall Renovation Oxygen8 VRV CU - 8-26-2026.pdf`
- 게이트 수치 — 정본: 8코일, CDXC-3 `CH 43.25/FL 33`, CDXC-4 54슬롯, 게이트 **미발동** ·
  서명본: **9→8**, 유령 소멸(`wrapped continuation of the row above (tag repeated, no Qty)`),
  CDXC-3·CDXC-4 복구
- 관련: plan `C:\Users\JohnKim\.claude\plans\ccs-ia-quatt-peaceful-parnas.md` · `.claude/roadmap.md` ⬜앞으로 최상단

## 2026-08-31 (Toronto) · base c6c702c..71514a1 · claude/ambient-supplier
> 참고: 로그의 직전 기준점은 7/23(`c6c702c`)이고 그 사이 83커밋이 쌓였으나 82개는 다른 세션/트랙
> (Stage 4 Observatory, review-convergence, sl1-tagfilter, Omnia)으로 로드맵 완료 섹션에 이미 기록됨.
> **이번 대화 세션의 실제 경계는 `c43d9d7..71514a1` — 커밋 1개.**
> 로드맵 트랙: **견적 납품 워크플로 압축 4단계 "원클릭 납품 정리"** (코드 완료, 눈검증 대기).

### ✅ 구현/결정된 것
- **탐색 결과가 요청을 뒤집었다: 기능은 이미 90% 있었다.** `POST /api/deliverable/finalize` +
  `#finalize-deliverable` 버튼이 이미 프로젝트 번호로 `02 - POs/<번호>/Accessory Order Forms/DirectCoil`을
  찾아 세 파일을 넣고 있었음. 따라서 이번 작업은 신규 구현이 아니라 **기존 finalize 경로의 정책 4가지 변경**.
  (근거: 탐색 2건, `deliverable/finalize.py` 기존 65-136행)
- **Build 한 번 = 패키지 + 파일 정리** (커밋 `71514a1`) — `buildQuotePackage()` 끝에서
  `fileDeliverable({skipDraft:true})` 호출. 두 번째 버튼은 **"Open Outlook draft"** 전용으로 라벨 변경.
  (근거: web/app.js:4829, web/index.html:280)
- **복사 → 이동.** 체크리스트는 서버가 경로를 아는 유일한 파일이라 진짜 move. PDF 2개는 **바이트로만**
  도달하므로(브라우저는 경로를 안 줌) `~/Downloads/<이름>` + Chrome의 `<stem> (1)<ext>`를 재구성하되
  **sha256이 방금 기록한 내용과 일치할 때만 삭제**(`retire_download`). 이름 일치만으로는 절대 안 지움 =
  경로 추측이 안전해지는 이유. revised PDF는 브라우저가 비동기 저장하므로 5초 바운디드 폴링.
  (근거: `deliverable/finalize.py::retire_download`, 신규 테스트 4건)
- **충돌 = 같은 이름 AND 다른 내용, 그리고 전부 중단.** `plan_placements`가 세 목적지를 먼저 판정하고
  `commit_placements`가 쓰므로 **반쯤 채워진 폴더**(완료된 것처럼 보여서 더 나쁨)가 도달 불가.
  응답은 **HTTP 200 + `status:"conflict"`** — 충돌은 에러가 아니라 John의 결정 대기(폴더 부재는 계속 400/409).
  `overwrite:true`가 답. (근거: web_app.py:1539-1567, 신규 테스트 3건)
- **동일 내용 = `already_filed`, 충돌 아님.** 이 한 줄 정의가 버튼 두 개를 살림 — Build가 정리한 뒤
  초안 버튼이 같은 세 파일 위로 다시 돌아도 통과하므로 **초안 전용 엔드포인트를 안 만들었다.**
  대신 Outlook 첨부를 `files_written[1]` 인덱스가 아니라 **이름으로** 조회(리스트 구성이 달라지므로).
- **폴더명은 접어서 매칭**(소문자화 + 공백/`_`/`-` 제거). `Direct Coil`은 **`DirectCoil`로 rename 후 재사용**
  (안에 있던 파일 이력 보존, 빈 폴더를 옆에 안 만듦). `Accessory Order Forms`는 느슨히 찾되 **rename 안 함** —
  AOF 부재 = 프로젝트 폴더 오인식 신호인데, 철자 변형이 그 에러를 유발하면 의미가 사라지므로.
  두 철자 공존 시 추측하지 않고 raise. (근거: `_child_by_normalized`, `_rename_to_canonical`, 신규 테스트 5건)
- **John이 확정한 정책 6건** (AskUserQuestion 2회): 이동 / 충돌 시 멈추고 묻기 / 변형 폴더는 rename 후 사용 /
  AOF 없으면 에러 중단 / FULL CHECKLIST = 자동생성 `<제출서명> - Coil Checklist.xlsx` / Build는 정리까지만
  (Outlook 초안은 별도 버튼).
- **의도적으로 버린 커버리지:** `test_place_bytes_never_clobbers` — 동명 파일이 조용히 ` (2).pdf`가 되던 동작.
  "멈추고 물어보기"가 이를 대체하므로 충돌/동일내용/덮어쓰기 3건으로 교체. `checklist/excel_writer.py`의
  별도 `(2)` 폴백(Downloads 쓰기 경로)은 무접촉.
- **테스트:** `tests/test_deliverable_finalize.py` 10→33건, 전체 **1608 passed, 0 failed** (커밋 직전 측정).
- **문서:** `CLAUDE.md`에 4개 규칙 기록(252-279행) — 이 파일이 프로젝트 계약서라 drift 방지.

### ⏭️ 다음 스텝
- [ ] **[Phase Gate] John 브라우저 눈검증 1회** — `run_server.bat` 재시작(--reload 없음) → 제출서 분석 →
  Quote PDF 드롭 → Build quote package. 합격: DirectCoil에 세 파일 존재 **AND** Downloads에서 셋 다 사라짐.
  (왜 남음: 실제 OneDrive/SharePoint 폴더에 쓰는 동작이라 사람 확인이 Phase Gate 조건)
- [ ] **충돌 케이스는 테스트용 사본 폴더에서 먼저** — Quote PDF를 다른 걸로 바꿔 같은 프로젝트에 Build →
  프롬프트가 뜨고 기존 파일이 안 바뀌는지. (왜 남음: 실제 파일을 대체할 수 있는 유일한 경로)
- [ ] **로드맵 미기재** — `.claude/roadmap.md`에 4단계 "원클릭 납품 정리" 항목이 없다. (왜 남음: 그 파일을
  다른 세션이 수정 중이라 충돌 회피를 위해 손대지 않음. 그 세션 커밋 후 추가 필요)
- [ ] **`DEFAULT_PO_BASE` 하드코딩 유지** — 설정화는 범위 밖으로 확정. (왜 남음: John이 필요하다고 하기 전엔 불필요)
- [ ] **한계 1건(Confirmed):** 원본 Quote를 Downloads가 **아닌** 곳에서 골랐다면 그 원본은 안 지워지고
  `not found — left in place`로 보고됨. CCSI export가 Downloads로 떨어지는 워크플로에선 무해.

### 🔎 Resume anchors
- branch: claude/ambient-supplier · HEAD: `71514a115add14d22d4b1fa4703b0248f9fae3ab` (pushed)
- 미커밋(**이번 세션 아님 — 다른 세션 진행 중, 건드리지 말 것**): `.claude/roadmap.md`,
  `capture/{db,observe}.py`, `services/{direct_coil_drawing_pipeline,drawing_param_resolver}.py`,
  `workflows/submittal_to_drawing.py`, HGRH 템플릿 4쌍(slot_map.json + template.svg),
  `tests/{test_capture_ledger,test_template_clean}.py`, 미추적 `.agents/ .codex/ pytest.ini`
  `scripts/migrate_capture_ledger.py` + 테스트 3개
- 핵심 경로: `src/coilforge/deliverable/finalize.py` (plan/commit_placements, retire_download,
  _child_by_normalized) · `src/coilforge/web_app.py:1418-1650` · `web/app.js::fileDeliverable`
  (4840-) · `web/index.html:280-285`
- 롤백: `web/app.js:4829`의 `await fileDeliverable({ skipDraft: true });` 한 줄 삭제 → 이전 2버튼 흐름 복귀
- 관련: plan `C:\Users\JohnKim\.claude\plans\ccs-ia-quatt-peaceful-parnas.md` · CLAUDE.md:252-279

## 2026-07-23 (Toronto) · base e30c36f..c6c702c · claude/ambient-supplier
> 참고: 이 base 범위엔 중간에 다른 세션 커밋(af3b4fc Stage 3.0 등)이 섞여 있으나 그건 로드맵 완료 섹션에
> 이미 기록됨. 아래는 **이번 대화 세션(2026-07-23)**에서 실제로 한 작업만.
### ✅ 구현/결정된 것
- **quote-package 삽입 도면에 coil tag 표시** (커밋 `15bcd55`) — cdf6fc3의 SVG 태그 주입은 정상이었고,
  어셈블러의 불투명 배너(페이지 y0~16)가 라벨(페이지 y2.2~18.7)을 덮어 디센더 조각만 남던 게 근본원인.
  `_stamp_watermark_banner`가 tag를 받아 배너 위 우측에 재인쇄 + `_BANNER_HEIGHT` 16→20(묻힌 라벨 완전 덮음).
  SVG 라벨 하향 이전 안은 33개 시드 템플릿 좌상단 래스터 스캔으로 기각(y≈20부터 지오메트리=안전지대 없음).
  라이브 `/api/package/quote` 실증(양 페이지 자기 태그·export_allowed False). (근거: `15bcd55`,
  package/assembler.py, tests/test_package_assembler.py, 신규 3테스트, 1081 green)
- **DX 분배기 S를 체크리스트처럼 1/8" 반올림** (커밋 `1dbbf74`) — 체크리스트 `ROUND(k·CD/(n+1)·8,0)/8`(1/8 스냅)과
  달리 세 곳에 각기 다르게 틀림(엔진 R-034=정수인치, 슬롯레이어·패널=반올림 없음). 신규 `round_eighth()`(기존
  `_excel_round` 재사용=Excel half-away-from-zero)로 통일. DX 한정(CWC/HWC 시트엔 S행 없음=무발명, Terra V CD−Rn
  분기 불변). CD=5.5,n=2 → S1=1.875/S3=3.625(John 체크리스트 스크린샷 일치). 1/8은 비례 안 함=k마다 개별 반올림.
  (근거: `1dbbf74`, header_prepopulate_engine.py·direct_coil_drawing_pipeline.py·drawing_param_resolver.py·
  coil_header_rules.yaml, 기존 단언 4건 갱신+신규 1건, 1082 green)
- **로드맵 갱신** (커밋 `c6c702c`) — 헤더 최신-갱신 블록 + 완료 2항목 + TR-4 추가.
- **결정:** 두 수정 모두 DX 범위 한정 확정. CWC/HWC S는 근거 수식 부재로 미변경(무발명 원칙).

### ⏭️ 다음 스텝
- [ ] **[TR-4] John 브라우저 눈확인** — DX quote PDF 재분석(pdfCoilPages 캐시라 필수)→Build quote package→
  ①배너 우측 Tag ②DX S 1/8 단위 ③체크리스트 비교표 S 행 green. (왜 남음: 실 렌더 사람 눈 확인은 John 몫)
- [ ] **세 커밋 push 여부 결정** (왜 남음: 트리에 Stage 2.1/3.0 미커밋 공존 → push 범위 John 판단)
- [ ] **CWC/HWC S 반올림 보류** (왜 남음: 체크리스트 시트에 S행 없음 — 필요 시 John이 공식 제공)

### 🔎 Resume anchors
- branch: claude/ambient-supplier · HEAD: `c6c702c` · 미커밋: Stage 2.1/3.0 트랙(capture/retrieve.py,
  workflows/submittal_to_drawing.py, web/app.js·style.css, capture/tuning.py, scripts/tune_case_weights.py,
  tests/test_case_tuning.py, tests/test_capture_retrieve.py — **이번 세션 아님**, John eyeball 대기)
- 핵심 경로: src/coilforge/package/assembler.py · src/coilforge/services/{header_prepopulate_engine,
  direct_coil_drawing_pipeline,drawing_param_resolver}.py · 체크리스트 원본 수식 = CHK DX!C46:C49
- 관련: 로드맵 TR-4 · 체크리스트 DX 시트 S1/S3/S5/S7 수식

## 2026-07-16 (Toronto) · base 5573f05..e30c36f · claude/ambient-supplier
### ✅ 구현/결정된 것
- **Ambient Dynamics quick-ship 서플라이어 확장** — Direct Coil(기본) vs Ambient 선택 축. Ambient는 성능 검증 워크플로: Ambient 회신 Performance PDF를 파싱해 baseline submittal과 coil별 비교, capacity/coil-volume을 Coil Utilities acceptance 밴드로 판정. Direct Coil 경로 byte-identical. (커밋 `e30c36f`, 25 files +2251, 963 tests pass — 929→963 +34)
- **`coil_utilities/` 재사용 내부 테이블** — `Coil Utilities - HWC DX.xlsx`에서 이식: R32 14-킷 capacity/coil-volume 밴드(EKEXVA 킷→tonnage, circuits 스케일), geometry 엔진(volume/passes/drop-tubes/face-area), heating 용량식, Allowable Ranges 기준. R410a는 상수 미확보 → **빈 TODO(invent 금지)**. (`charts.py`/`geometry.py`/`ranges.py`, `test_coil_utilities.py`)
- **`ambient/`** — `pdf_intake`(DX/Condensing Report 파서, Btu/hr→MBH 단위 감지, degraded-OCR 방어), `model`/`mapping`/`compare`(태그 페어링, category-keyed, whole-coil 불일치 `not_compared_reason`), `range_provider`(baseline 용량→킷, 없으면 Ambient 폴백), `rfq`(성능 타깃 요약).
- web: `POST /api/ambient/compare`(multipart baseline+ambient), `/api/ambient/rfq`, `COILFORGE_AMBIENT` kill-switch; supplier 토글 + green/red/grey 패널.
- `checklist/compare._match` 확장(keyword-only `tol`/`rel_tol`, 기존 positional 호출 byte-safe).
- **실제 2975 데이터 브라우저 눈 확인**: FPI 10 vs 9 mismatch 포착, Capacity Range 171.5∈[169,189]·Coil Volume Range 363.6∈[287,778] green match.
- 독립 재검토 게이트 통과(HIGH-1 multipart·HIGH-2 OCR·MEDIUM-1 단위감지·MEDIUM-2 whole-coil·MEDIUM-3 kill-switch·LOW-2 category-keyed 전부 반영).

### ⏭️ 다음 스텝
- [ ] **Material 문자열 false-positive 정규화** — baseline이 `"Copper - 0.016 Plain"`/`"Aluminum 0.008"`처럼 재질+두께+표면을 한 문자열로 저장 → Ambient `"Copper"`/`"Aluminum"`과 `differ`로 뜸. **정직한 차이지만 노이즈** — 재질 토큰만 비교하도록 정규화 필요(John 확인: 어디까지 무시할지). 위치: `ambient/compare.py` 또는 `mapping.py` string 필드 처리.
- [ ] **Phase 6 엑셀 write-back** (`ambient/excel_writer.py`) — 실제 `<proj> - Coilmaster-Ambiant Dynamics Coil Comparison.xlsx` 템플릿의 라벨/열 전사 필요(**John 제공 대기**). `checklist/excel_writer.py` 미러(DispatchEx 격리, SaveCopyAs Downloads, C열 baseline/D열 Ambient, Range·Volume 공식 셀 미변경).
- [ ] **circuits 검출** — 현재 기본 1. Ambient `System Type Intertwined (x2)` 파싱 미구현 → 멀티서킷 밴드 스케일 부정확 가능.
- [ ] **baseline 용량 소스 결정** — Oxygen8 submittal은 per-coil 용량 미파싱 → 킷 선택이 Ambient 폴백. Coilmaster EZ-Coil PDF를 baseline으로 쓸지 / 파싱 확장할지 John 결정.
- [ ] **% 허용오차 확정** — 현재 review-only 기본값(capacity ±2%, PD ±5%, temp ±0.5°F). John 확정 필요.
- [ ] **R410a 차트 전 컬럼 전사** — 필요 시(현재 R32만; R410a 빈 TODO).
- [ ] **다음 리뷰 포인트**: `coilforge-invariant-guard`로 이 diff 재검토 권장(three-layer/never-invent/gated-slot 확인). 커밋은 됐으니 리뷰는 사후.

### 🔎 Resume anchors
- branch: `claude/ambient-supplier` · HEAD: `e30c36f7e90e9b8bdb5c873329991b7c89a6ae40` · 미커밋: 없음(내 파일)
- ⚠️ 워킹트리 나머지(`services/direct_coil_drawing_pipeline.py`의 HGRH 파라미터, `.agents/`, `.codex/`)는 **동시세션/기존 소유 — 내 것 아님**, 커밋에서 제외함.
- 핵심 경로: `src/coilforge/coil_utilities/`, `src/coilforge/ambient/`, `web/{index.html,app.js,style.css}`, `web_app.py` `/api/ambient/*`
- 관련: plan `C:\Users\JohnKim\.claude\plans\ambient-cozy-barto.md` · 소스 워크북 `Coil Utilities - HWC DX.xlsx` · 예시 프로젝트 2975(baseline=DirectCoil REV1, ambient=Downloads Ambient PDF)

## 2026-07-04 (Toronto) · Tier 1 BUILT (T1+T2+T3, CCSI quote-revision workflow) · base `11d1c7b..4d46013` · claude/ccsi-autofill
### ✅ 구현/결정된 것
- **Tier 1 전체 빌드 — John의 CCSI 견적-리비전 워크플로우를 confirm-gated 스킬 체인으로.** 5개 스킬: `/ccsi-fill`(push) · `/ccsi-compare`(compare) · `/ccsi-sync-all`(T1 멀티코일) · `/ccsi-rfo`(T2 프로젝트 nav) · `/ccsi-revise`(T3 마무리).
- **T1 (`a25b801`) — 멀티코일 sync 루프.** `window.coilforgeCoils()`/`coilforgeSelectCoil(i)` 훅(app.js, 모듈 스코프 우회) + `/ccsi-sync-all`(태그 매칭, 코일당 push+compare). **라이브 검증:** 3025 5코일 로드 → CDXC-1 매칭·활성화 → compare **22 match / 3 red(R 계열)**, 패널 초록/빨강 실렌더(앞선 픽셀-미확인 caveat 해소).
- **T2 (`99f2650`) — CCSI 프로젝트 nav.** T2.0 라이브 셀렉터 캡처(읽기 전용, 클릭 0) → `web/ccsi/ccsi_nav_map.json`(8 액션/3 mutating): `CopyRevision`(복제)·`RevisionNoteUpdate`(RFO)·`retrieveReport`(export)·`RetrieveProductsForRevision`(코일 로드)·`editProduct(id,'DXCoil')`(코일 열기). 구조: **Project→Revisions→Products**. + `/ccsi-rfo` 오케스트레이션(각 mutation STOP-확인).
- **T3 (`4d46013`) — export→revise→email.** `/ccsi-revise` 오케스트레이션 + **"Prepare email draft" 버튼**(app.js/index.html, quote 빌드 후 노출, mailto 초안, **발송 안 함·첨부 John**). revise는 기존 `/api/package/quote` 재사용(신규 코드 최소).
- **결정(재확인):** login=John, 되돌리기-어려운 CCSI 클릭(복제/RFO/저장/export)·이메일 발송은 전부 John의 클릭별 확인. review_aid_only / export_allowed:false 유지. 값 창작 0.
- **검증:** 각 단계 커밋 전 **737 passed** 유지(멀티코일 훅·이메일 로직은 node/격리 검증).

### ⏭️ 다음 스텝
- [ ] **Tier 1 전체 체인 라이브 실증** — throwaway/테스트 리비전에서 `/ccsi-rfo`→`/ccsi-revise`를 각 mutation 확인하며 끝까지(실제 복제/RFO/export/revise/email 초안). **왜 남음:** 실제 CCSI 레코드 변경이라 John-in-the-loop 필요; T2.1/T3 실행 경로 미실행(빌드만).
- [ ] **(사소) "Copy CCSI autofill payload" 버튼 문구 "13" → 멀티헤더 반영** (app.js, command·map은 이미 정리됨).
- [ ] **(선택) Track B 복귀** — 최종 제품 파라메트릭 드로잉 엔진: 레이아웃/뷰 마무리 → feature 라이브러리 → DXF(ezdxf 설치) → PDF+export 게이트. 별도 브랜치 `claude/phase2-drawing-engine`.

### 🔎 Resume anchors
- branch: `claude/ccsi-autofill` · HEAD: `4d46013f96b5d1535e05db7b89c7f67fe96aacbc` · 미커밋: 없음(내 Tier 1) — 워킹트리 나머지는 동시세션 소유
- 스킬/명령: `.claude/commands/{ccsi-fill,ccsi-compare,ccsi-sync-all,ccsi-rfo,ccsi-revise}.md`
- 핵심 경로: `web/ccsi/ccsi_dx_field_map.json`(25키) + `ccsi_nav_map.json`(nav), `src/coilforge/ccsi/compare.py`+`/api/ccsi-compare`, `web/app.js`(`coilforgeCoils`/`prepareQuoteEmail`), `package/assembler.py`+`/api/package/quote`
- 상태차트 Artifact: https://claude.ai/code/artifact/64d4f7b4-14de-4463-a5f3-e0117e2f766d · plan `C:\Users\JohnKim\.claude\plans\this-is-a-substantial-compressed-castle.md`

## 2026-07-04 (Toronto) · Tier 0 CLOSED (Phase 2.0 + 3.1, live-verified) · base `bc9bbfe..11d1c7b` · claude/ccsi-autofill
### ✅ 구현/결정된 것
- **Tier 0 전부 커밋·푸시 완료 — CCSI 양방향 통합 3겹(mirror→push→compare) 완성.** 커밋 4개: `7a41933`(3.0 백엔드+2.1 payload+3.2/3.3 UI), `f6c1a8a`(session-log), `f374fc3`(2.0 셀렉터), `11d1c7b`(3.1 read-back 명령).
- **Phase 2.0 — 멀티헤더 셀렉터 라이브 캡처** (`f374fc3`): 실제 CCSI 편집기(`coil.ccsi.ie/Coils/Edit/8182979`, 3-header DX 코일 3025 Bauducco)에서 12개 id 덤프 → `ccsi_dx_field_map.json` v`2026-07-04`(25키). 패턴 **`DX_<stem><N>`**(I2→`#DX_HS2`, S2→`#DX_VS2`…), 전부 편집가능. 값 창작 0. `test_ccsi_field_map.py` exact-13 완화 + 고유-id 검증. 근거: **737 passed**.
- **Phase 2.1b** (`f374fc3`): userscript·`/ccsi-fill` 스니펫 둘 다 이미 `Object.keys(map.fields)` 동적 → **코드 무변경**, stale "13" 문구만 정정.
- **Phase 3.1 — `/ccsi-compare` read-back 명령** (`11d1c7b`): CCSI 값을 map 셀렉터로 읽어 `window.coilforgeCcsiCompare()` 호출 → 패널 초록/빨강. CCSI가 localhost에 cross-origin이라 selector를 CCSI-탭 JS에 embed. **라이브 검증: 25/25 값 읽힘(not-found 0), entrypoint 실행됨.**
- **실데이터 안전망 실증:** 3025 CDXC-1을 서버사이드 분석(`/api/workflow/pdf-to-drawing`, 84p/126s) → CoilForge 계산값 vs CCSI 라이브값 25필드 대조 = **22 match / 3 mismatch(R 계열 return-spacing)**. tolerance(0.01) 정상.
- **결정(John):** R 계열 불일치는 **무시** — 최종 quote는 CoilForge가 그린 값으로 요청되므로 CCSI R 차이는 이 워크플로우를 막지 않음. (안전망은 정상 작동, 발견은 내려둠.)
- **부수 관측(미변경):** 라이브 DOM에서 base `CD`가 편집가능(기존 map은 readonly 표기) — base-13 사안이라 손 안 대고 플래그만.

### ⏭️ 다음 스텝
- [ ] **Tier 0 이후 로드맵 상위 티어 착수** — 파라메트릭 드로잉 엔진 백엔드(**DXF** via ezdxf 1:1, **PDF** 제출용 title-block/scale), 커버리지 대시보드 생성기(현재 hand-authored `docs/coverage_dashboard.html`). (왜 남음: Tier 0가 CCSI 스레드였고, 제품 최종형은 3-backend 드로잉 엔진)
- [ ] **(선택) 브라우저 내 초록/빨강 실사용 확인** — John이 코일 드래그(업로드 캡 없음) 후 `/ccsi-compare` → 패널 색 eyeball. (오늘은 데모 코일 state로 entrypoint만 확인, 패널은 `is-init-stage`라 숨김)
- [ ] **(선택) base CD readonly 정정** — 라이브에서 편집가능 관측; John 확인 후 `ccsi_dx_field_map.json`의 `CD.ccsi_readonly` 조정 여부 결정.
- [ ] **(선택) 4HD 셀렉터** — 실제 4-header DX 코일 열면 `DX_HS4…` 캡처(패턴상 예측되나 창작 금지).

### 🔎 Resume anchors
- branch: `claude/ccsi-autofill` · HEAD: `11d1c7bf6309c5481d7b224918f43a47abce84dc` · 미커밋: 없음(내 Tier 0) — 워킹트리 21개 변경은 전부 동시세션 소유(`direct_coil_drawing_pipeline.py`, checklist, YAML, HWC 템플릿 등)
- 핵심 경로: `web/ccsi/ccsi_dx_field_map.json`(25키), `src/coilforge/ccsi/compare.py`+`/api/ccsi-compare`, `web/app.js`(`compareCcsi`/`ccsiFillKeys`), `.claude/commands/{ccsi-fill,ccsi-compare}.md`, CCSI 편집기 `coil.ccsi.ie/Coils/Edit`
- 관련: plan `C:\Users\JohnKim\.claude\plans\this-is-a-substantial-compressed-castle.md`(STATUS 섹션이 shipped/remaining 반영) · 서버 `:8011` 실행 중

## 2026-07-04 (Toronto) · Tier 0 CCSI push + compare · base 근사 `be05fd2..bc9bbfe` + 미커밋 · claude/ccsi-autofill
### ✅ 구현/결정된 것
- **Tier 0 Phase 3.0 — CCSI↔CoilForge 비교 백엔드** (미커밋): `src/coilforge/ccsi/compare.py`(신규, `checklist/compare.py::_match` tol=0.01 재사용) + `POST /api/ccsi-compare`(`web_app.py`). 안전 플래그 스탬프(`review_aid_only:true`/`export_allowed:false`). 근거: `tests/test_ccsi_compare.py` 7개 통과, 전체 **736 passed**.
- **Tier 0 Phase 2.1 — 멀티헤더 payload** (미커밋): `web/app.js`에 `ccsiFillKeys` 추가 → `buildCcsiAutofillPayload`가 `parameters`에 있고 field-map에도 있는 I2/S2/O2/R2/HD2/ZD2… 키까지 방출(1HD는 base 13로 degrade). 근거: `web/app.js` diff, node --check.
- **Tier 0 Phase 3.2/3.3 — 초록/빨강 안전 비교 UI** (미커밋): `renderParameterRow`에 verdict 컬러(초록 match / 빨강 mismatch + ⚠뱃지), `compareCcsi`/`window.coilforgeCcsiCompare`, `#ccsi-compare-banner`, `web/style.css` 클래스. 근거: computed-style 육안 검증(빨강 엣지 rgb(224,107,107)+danger-bg, 초록 엣지 rgb(77,138,44)).
- **결정:** 비교를 JS 포팅 대신 **백엔드 엔드포인트로** — compare.py 단일 소스, pytest 가능, CCSI DOM 문자열값도 `_norm`이 강제변환. (대화 중 확정)
- **결정:** 전달 경로는 **Claude-in-Chrome `/ccsi-fill` 우선**(오늘 동작), Tampermonkey 역방향 브리지는 선택적 후속. (John 확인)
- **문서↔코드 드리프트 발견(미수정):** CLAUDE.md "10 of 22 templates" · "4HD placeholder_blocked" stale(코드는 22/22 active); mechanical_fit docstring stale; `coverage_dashboard.html` stale.

### ⏭️ 다음 스텝
- [ ] **Tier 0 커밋** — 검증된 7파일(`ccsi/compare.py`·`__init__.py`, `web_app.py` 라우트, `test_ccsi_compare.py`, `web/app.js`·`index.html`·`style.css`)을 `/ship`. **진행 중:** ship 실행함(736 green), surgical 스테이징 7파일 확정, CLAUDE.md 한 줄 추가 승인 대기.
- [ ] **Phase 2.0 라이브 셀렉터 캡처** — `coil.ccsi.ie/Coils/Edit`(3-circuit CDXC-1)에서 I2/I3/S2/S3… input id + readOnly 덤프 → `ccsi_dx_field_map.json` 확장. **필요:** 코일 편집기 URL/이동(문서 뷰에서 도달 실패), 브라우저 게이트. 값 절대 지어내지 않음.
- [ ] **Phase 2 테스트 갱신** — `tests/test_ccsi_field_map.py`에서 "exactly 13" 바운드 제거 (2.0이 키 추가한 뒤에만).
- [ ] **Phase 3.1 read-back 배선** — `.claude/commands/ccsi-fill.md`가 CCSI 값을 셀렉터로 읽어 `window.coilforgeCcsiCompare(...)` 호출하도록. **필요:** 2.0 완료 후.
- [ ] **라이브 확인** — `run_server.bat` 재시작(no --reload) 후 `/api/ccsi-compare` end-to-end + CDXC-1 R 3.317 vs 1.3125 빨강 시연.

### 🔎 Resume anchors
- branch: `claude/ccsi-autofill` · HEAD: `bc9bbfef7357cf89ae5d95eb839b65edb83e7b7b` · 미커밋 Tier 0: `src/coilforge/ccsi/{__init__,compare}.py`, `tests/test_ccsi_compare.py`, `src/coilforge/web_app.py`(+15), `web/app.js`(+109), `web/index.html`(+5), `web/style.css`(+42)
- **워킹트리 엉킴(이 세션 소관 아님, 커밋 시 제외):** `services/direct_coil_drawing_pipeline.py`(1058줄 churn), `checklist/from_workflow.py`·`mapping.py`, `rules/coil_header_rules.yaml`, `templates/.../hwc/*.svg`, 관련 test들
- 핵심 경로: `web/ccsi/ccsi_dx_field_map.json`(13키+8 remap), `src/coilforge/checklist/compare.py`(재사용 코어), CCSI 편집기 `coil.ccsi.ie/Coils/Edit`, payload schema `coilforge.ccsi.autofill/1`
- 관련: plan `C:\Users\JohnKim\.claude\plans\this-is-a-substantial-compressed-castle.md`

## 2026-07-04 (Toronto) · investigation session (Ventum+ status) · claude/ccsi-autofill
### ✅ 구현/결정된 것
- (코드 변경 0건 — 순수 조사 세션, plan mode) Ventum+ 데이터 매핑 + 드로잉 생성 현재 구현 상태 조사.
- 데이터 매핑: 완전 구현 확인. 탐지(V20–V150 토큰, coilmaster_drawing_extract.detect_product_and_size)
  → ProductFamily.VENTUM_PLUS(schemas/header_prepopulate.py:42) → 룰엔진 전용 룰 11개+
  (R-011 플랜지 1", R-029 dist_i=12, R-032 방향 UP, R-052/R-063b 제품 분기) → canonical record, 막힘 없음.
- ★정정: 드로잉 생성은 "하드블록"이 아니다. 실제 코드
  workflows/submittal_to_drawing.py:482 = `_UNREGISTERED_PRODUCT_LINES: set[str] = set()` (비어 있음).
  Ventum+는 2026-07-03(커밋 bc9bbfe)에 un-block되어 공유 CoilMaster 템플릿으로 그려짐. 게이트는
  남아 있으나 이제 Terra V CWC/HWC만 omit. (근거: grep + 주석 submittal_to_drawing.py:500-502)
- 세션 중 Explore 에이전트가 stale하게 `= {"VENTUM_PLUS"}` + test_ventum_plus_is_unregistered로
  보고 → 파일 직접 확인으로 반증. 사용자에게 전달한 초기 보고서의 "차단" 결론은 오류였고 정정 완료.
### ⏭️ 다음 스텝
- [ ] (선택) Ventum+ 엔드투엔드 렌더 실물 확인 — run_server.bat 재시작(--reload 없음) + V-tag
      제출문서 재분석해 SVG가 실제로 나오는지 eyeball. (왜 남음: 코드상 un-block만 확인, 실행 검증 미완)
- [ ] 미커밋 워킹트리 정리 — 이번 세션과 무관한 대량 변경 다수(ccsi/, checklist,
      direct_coil_drawing_pipeline.py 1058줄, coil_header_rules.yaml 등). 다음 /ship 또는 별도 커밋으로.
      (왜 남음: 선행/동시 세션 작업이 스테이징 안 됨)
### 🔎 Resume anchors
- branch: claude/ccsi-autofill · HEAD: bc9bbfef7357cf89ae5d95eb839b65edb83e7b7b · 미커밋: 대량(위 참조)
- 핵심 경로: src/coilforge/workflows/submittal_to_drawing.py (게이트 :482),
  services/header_prepopulate_engine.py (R-052/R-063b 분기), rules/coil_header_rules.yaml (R-074/R-076),
  template_population/catalog.py (공유 버킷 — product_family 디스크리미네이터 없음)
- 관련: CLAUDE.md "Current code state vs confirmed target" 표 · plan 파일
  C:\Users\JohnKim\.claude\plans\ventum-data-mapping-recursive-curry.md (미작성 상태로 남음)

## 2026-07-04 (Toronto) · first checkpoint (no prior base) · claude/ccsi-autofill
### ✅ 구현/결정된 것
- CDXC-3 "needs coil type + product line + unit size to evaluate fit" 원인 규명 + 수정.
  근본원인: cover schedule가 2페이지로 넘어갈 때 continuation 행을 text-line 파서로만
  읽어 `model` 컬럼을 버려서 `TV_B_024`가 detect_product_and_size에 도달 못함 →
  product_type/unit_size=None → R-074 casing 조회 불가 → fit note. (근거: 실 PDF 진단
  로그 pg2 model='' , detect=(None,None))
- 수정: `_with_continuation_cover_rows`를 table-first로 변경 — continuation 페이지에도
  `_detect_cover_page_from_tables`(header-less positional fallback `_find_cover_coil_table`,
  전 컬럼+model 읽음) 적용, table 없을 때만 text 파서로 폴백. break-guard + (page,row,tag)
  dedup + review_note 보존. (근거: commit 0db7ee3, src/coilforge/submittal/pdf_intake.py)
- 회귀 테스트 추가: 합성 2페이지 cover(_TextPage, 고객데이터 없음)로 continuation 행
  model=='TV_B_024' → ('TERRA V','024') 검증. 전체 스위트 726 passed. (근거: 0db7ee3,
  tests/test_phase2e_pdf_coil_intake.py)
- CLAUDE.md에 continuation-page table-first gotcha 문서화. (근거: 0db7ee3)
- 실 PDF 재진단: 5개 coil 전부 해석 — CDXC-3 → DX / TERRA V / 024. positional 매핑은
  MEDIUM(review-required) 유지, confidence 부풀림 없음.
- /defer-task로 2026-07-04 태스크 생성(Work + Daily 캘린더, URL 상호참조). Notion만 변경,
  로컬 파일 변경 없음.
### ⏭️ 다음 스텝
- [ ] 브라우저 eyeball 검증: run_server.bat 재시작(--reload 없음) + PDF 재분석 후 CDXC-3
      fit 카드가 DX/TERRA/024 + width/height verdict로 뜨는지 확인 (아직 코드-레벨만 검증)
- [ ] John의 HWC/CWC signal→application 매핑 확보 (값 없이는 아래 인코딩 불가)
- [ ] mechanical_fit.py에 HWC application 유도 인코딩 (위 매핑 필요)
- [ ] partner 존재 시 drain-pan 자동 활성화 — refreshMechanicalFit의 하드코딩
      installed_on_drain_pan:true 제거 (설계 결정 필요)
- [ ] Terra drain_pan_option D1/D2/D3 출처 결정 (John 확인 필요)
- [ ] 멀티코일 검증 테스트 추가 (case_006/case_003)
- [ ] manual-flow polish: finned-height/length 편집 시 fit 재실행
### 🔎 Resume anchors
- branch: claude/ccsi-autofill · HEAD(내 커밋): 0db7ee3 · 미커밋: 없음(내 것) — 워킹트리
  변경은 전부 동시 세션 소유
- 주의: 현재 실제 HEAD=bc9bbfe (동시 세션이 0db7ee3 위에 4커밋 스택). 내 작업 경계는 0db7ee3.
- 핵심 경로: src/coilforge/submittal/pdf_intake.py::_with_continuation_cover_rows,
  tests/test_phase2e_pdf_coil_intake.py, compatibility/mechanical_fit.py:454
- 관련: plan c-users-johnkim-desktop-coil-checklist-jaunty-bunny.md · defer-task Notion
  2026-07-04 "CoilForge — verify continuation-page fix + mechanical-fit follow-ups"
