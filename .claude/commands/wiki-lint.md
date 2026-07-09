---
description: Health-check the CoilForge engineering wiki — wiki-vs-code drift, contradictions, stale review-required claims, orphans, checklist drift, index/log integrity
argument-hint: "[empty = full lint | page path/stem = lint just that page]"
allowed-tools: Read, Grep, Glob, Edit, Write
---

# /wiki-lint — 위키 정합성 점검 (Karpathy LLM-Wiki lint)

`docs/wiki/`를 훑어 모순·낡음·고아·드리프트를 찾아 **보고**한다. CoilForge 고유의 핵심은 **위키↔코드
드리프트** — 위키가 인용한 규칙 ID/값을 `coil_header_rules.yaml`·enum·catalog와 실제로 대조한다.

절대 없는 내용을 지어내지 않는다 — 확인 못 한 항목은 "판정 보류"로 남긴다. **읽기 우선. 수정은
Draft → Confirm → Write로만** 하고, 확인 전에는 어떤 파일도 고치지 않는다. (`/wiki-ingest`는 지식을
*들여오고* `/wiki-query`는 *읽어* 답한다. `/wiki-lint`는 이미 있는 위키의 *건강*을 점검한다.)

## 고정 좌표
- **위키 루트:** `docs/wiki/` (스키마 `WIKI.md`). 원장 `open-questions.md`, 로그 `log.md`, 카탈로그 `index.md`.
- **대조 대상(코드/문서):** `src/coilforge/rules/coil_header_rules.yaml`,
  `src/coilforge/schemas/header_prepopulate.py`(enum), `src/coilforge/template_population/catalog.py`,
  `docs/MVP_FINALIZATION_CHECKLIST.md`, `CLAUDE.md`.
- 인자로 페이지(경로/stem)를 주면 그 페이지만, 없으면 전체를 점검한다.

## 여섯 가지 검사
1. **위키↔코드 드리프트 (핵심):** 각 페이지에서 규칙 ID·값·enum·크기셋을 뽑아 `Grep`/`Read`로
   `coil_header_rules.yaml`/enum/catalog와 대조. 값 불일치·신뢰도 불일치(`HIGH`인데 위키는 `[BLOCKED]`
   라 적음 등)·존재하지 않는 규칙 인용을 잡는다.
2. **페이지↔페이지 모순:** 같은 사실을 다르게 적은 두 페이지.
3. **낡은 `[REVIEW-REQUIRED]`:** 이미 `HIGH`로 승격됐는데 위키는 아직 review-required로 둔 주장.
4. **고아/끊긴 링크:** `index.md`에 없는 페이지, `[[link]]` 대상이 실제 파일도 없고 Stubs에도 없는 경우.
5. **원장 드리프트:** `open-questions.md` ↔ `docs/MVP_FINALIZATION_CHECKLIST.md`의 상태 불일치
   (예: 위키는 owed인데 체크리스트는 `[x]`), 그리고 문서↔문서 모순(예: MVP 체크리스트 vs CLAUDE.md).
6. **index/log 무결성:** `index.md`가 실제 페이지 집합과 일치하는지, `log.md`가 최신순 append-only인지.

## 보고 & (선택) 수정 — Draft → Confirm → Write
1. 심각도 순으로 발견 목록을 **터미널에 출력**한다. 각 항목: 무엇이/어디서(파일·페이지) 어긋났는지 +
   근거(대조한 규칙/셀/커밋). 판정 못 한 건 "보류"로.
2. 고칠 게 있으면 **제안 수정(diff)만 먼저 보여주고**, John의 확인 후에만 `Edit`/`Write`로 반영하고
   `log.md`에 `## <date> · lint — <title>` 항목을 prepend. 확인 전에는 쓰지 않는다.
3. 드리프트가 코드/문서 쪽 문제면(위키가 맞고 CLAUDE.md가 낡음 등) 위키를 바꾸지 말고
   `open-questions.md`에 올려 John이 소스를 고치게 한다.

## 결과 요약 (3~5줄)
- 점검 범위(전체/페이지) · 검사한 페이지 수
- 발견 수를 유형별로: 드리프트 / 모순 / 낡음 / 고아 / 원장 / 무결성
- 가장 중요한 1~3건 한 줄 요약
- 수정했으면 무엇을, 아니면 "보고만 — 수정은 확인 대기"
