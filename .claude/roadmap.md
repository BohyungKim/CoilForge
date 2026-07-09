# 🗺️ CoilForge 로드맵
> 목표: 코일 입력(Direct Coil 폼 / submittal / 스캔 PDF) → 검토용 도면 + 붙여넣기용 필드셋 + 검증·호환 리포트
> 마지막 갱신: 2026-07-09

## ✅ 완료
- [x] Phase 2A MVP 코어 — YAML 룰 엔진 + 템플릿-우선 SVG 도면 파이프라인 동작
- [x] 22개 템플릿 시드 완료 — per-hand 실참조 + 4HD(DX/HGRH LH+RH), 미러 생성 없음
- [x] Terra V SOP 확정 — 10개 델타값 LOW→HIGH 승격, 13개 사이즈·케이싱 전부 해소
- [x] Ventum+ 포크 (2026-07-06) — catalog.py product_family 축(2-pass) + 전용 11템플릿(R-032 UP 분배기 실물 포착); hand 미표기 2666/2658=LH 확정 → 11이 참조 폴더의 완전한 시드 집합; /verify 런타임 PASS(2026-07-07: 실서버 /api/coil-drawing/derive → 전용 라우팅+경고드롭+Nova 게이트 무회귀 6드라이브)
- [x] Mechanical Fit + Coil Checklist 자동채움 — WIDTH/HEIGHT/INSTALL 판정, xlsx 복사본 채움+역검증
- [x] Engineering Wiki — LLM 유지 지식베이스(뱃지+인용), /wiki-ingest·query·lint 드리프트 점검
- [x] CCSI Tier 0/1 — 25키 push + green/red 대조 + 5개 Claude-in-Chrome 스킬(fill/compare/sync/rfo/revise)
- [x] Exceptions-first 프로젝트 검토 게이트 (0cbb391) — K∝문제수, 상수시간 코일 검토
- [x] 원클릭 deliverable + 자동 이메일 초안 + 다회로 S 리포트 반영 (882d468)
- [x] 폰트 추출불가 submittal 자동 OCR + OCR-blocked(토큰/쿼터) 경고 배너 (c007b75) 🆕 이번 세션
- [x] Submittal 제품/사이즈 오검지 수정 (556b366) — 텍스트경로 커버행 model코드 포착 → TERRA H/015 라이브 검증 🆕 이번 세션
- [x] Header 2 = circuit수 확정 (John 2026-07-06) + wiki multi-header-geometry 시드 (b7f71a2) 🆕 이번 세션
- [x] PR #3 생성 (2026-07-07) — claude/ccsi-autofill → main, 73커밋(브랜치 누적 작업 전부)
- [x] 저위험 SOP 승격 5개 (R-066/R-002b/R-085/R-044c/R-048 MEDIUM→HIGH, 790 green) + eyeball 사인오프(John 2026-07-07) + 결정표·재분류(R-073/R-077/R-086) + /ship(hunk격리로 R-006 등 무관작업 제외)
- [x] R-074 2차 출처 판정 + R-048/R-085 조건부 발화 검증 (fc7037c, 794 green) — R-074 내부 2차출처 부재→MEDIUM 유지 확정(외부 출처 대기); R-048/R-085 유닛테스트 4건으로 HIGH 발화 검증; 검증 중 발견한 R-048 supply≠return 공식 결함·R-085 back_to_back 실경로 미배선을 [REVIEW-REQUIRED]로 등재(hunk격리로 R-006 재배제) 🆕 이번 세션

## ▶️ 지금
- [ ] MVP 사인오프 마무리 — 파라미터 완전성 감사(Stage 2b) — 다음 걸음:
  승격 판정 전부 해소(승격5·유지2·재분류3, R-074/R-048/R-085 후속까지 확정 기록). 이제 남은 것은
  **템플릿 eyeball 사인오프**(Ventum+ 11 + 공용 10) + John 판정 대기 3건(R-048 supply 공식 수정 ·
  R-085 back_to_back 실경로 배선 · R-074 외부 2차 출처 확보). 결정 기록은 docs/mvp_promotion_decisions.md.

## ⬜ 앞으로
- [ ] 템플릿 eyeball 사인오프 — Ventum+ 11 + 공용 10, 실제 프로젝트 진행하며 확인 (MVP §1·§4)
- [ ] PR #3 리뷰·머지 (claude/ccsi-autofill → main) — ⚠️ 2026-07-07 병합 시도 = CONFLICTING: drawing engine 5파일 충돌(main Phase 2.6–4b 라벨/V3 vs ccsi 병렬 피처 S1·R2·HDx1·AIRFLOW·Terra V·Ventum+, 양쪽 고유). 통합 병합은 크고 위험 → **drawing 세션과 조율 후 진행 (보류)**
- [ ] CCSI Tier 1 실 mutation 라이브 end-to-end 1회 (미완) — 2026-07-05 이후 우선순위 하향
- [ ] Terra 스플릿 [EXT] — TERRA → TERRA_H + TERRA_V (Terra H C = 하위변형), ~15룰 리키
- [ ] 커버리지 대시보드 생성기 [EXT] — 수기 HTML → catalog.list_template_entries() 자동생성
- [ ] (DEFER) 파라메트릭 도면엔진 SVG/DXF/PDF — MVP는 템플릿-우선, 명시 승인 전까지 보류
