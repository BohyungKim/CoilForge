---
description: Ingest a source into the CoilForge engineering wiki — extract facts, update the relevant pages + index + log, all confidence-badged and cited
argument-hint: "[source: submittal/SOP-section/session-finding/decision text | file path]"
allowed-tools: Read, Write, Edit, Grep, Glob
---

# /wiki-ingest — 위키에 소스 반영 (Karpathy LLM-Wiki ingest)

`$ARGUMENTS`로 준 소스(제출물 텍스트, SOP 섹션 요약, 이번 세션에서 확정된 발견/결정, 또는 파일 경로)를
읽고, `docs/wiki/`의 **관련 페이지들**에 사실을 통합한다. 새 사실마다 신뢰도 배지(`[CONFIRMED]`/
`[REVIEW-REQUIRED]`/`[BLOCKED]`)와 `evidence_ref` 인용을 붙이고, `index.md`·`log.md`를 갱신한다.

절대 없는 내용을 지어내지 않는다 — 소스에 없는 엔지니어링 값은 채우지 않고 `미확인` 또는
`[REVIEW-REQUIRED] — owed by John`으로 표시하고 `open-questions.md`에 올린다. (`/wiki-query`는 위키를
*읽어* 답하고, `/wiki-lint`는 위키의 *일관성*을 점검한다. `/wiki-ingest`는 새 지식을 *들여온다* — 방향이 안쪽.)

**원본은 절대 수정하지 않는다** (`AGENTS.md`: raw JSON/PDF 수정 금지). 소스는 읽기만 한다.

## 고정 좌표

- **위키 루트:** `docs/wiki/` — 스키마 `WIKI.md`, 카탈로그 `index.md`, 로그 `log.md`, 소스 레지스트리
  `sources.md`, 원장 `open-questions.md`, 그리고 `categories/` · `products/` · `concepts/`.
- **인용 문법 = 엔진의 `evidence_ref` 어휘 그대로:** `SOP §…`, `CHK <Sheet>!<Cell>`, `SOP-OLE1..5`,
  `EZC-####`, `John YYYY-MM-DD:`. 규칙에서 온 사실이면 규칙 ID(`R-074`)를 함께 적는다(→ lint가 대조).
- **교차링크:** `[[stem]]` (확장자·경로 없이 파일명 stem). 아직 없는 페이지 링크 = 스텁 마커 → `index.md`.
- **날짜:** America/Toronto. 날짜는 소스/대화에서 확인된 값만 쓰고, 지어내지 않는다.

## 1. 소스 확정
- `$ARGUMENTS`가 실제 파일 경로면 `Read`로 읽는다. 아니면 인자 텍스트를 소스로 쓴다.
- 비어 있으면 호출하지 말고, 무엇을 반영할지 되묻는다.

## 2. 추출 & 대상 페이지 식별
1. 소스에서 **사실 단위**로 뽑는다(값/공식/규칙/분류/결정). 각 사실에 배지 + 인용 근거를 정한다.
2. 근거가 소스에 없으면 그 사실은 `[REVIEW-REQUIRED]`. 엔진 규칙과 연결되면 `Grep`으로
   `coil_header_rules.yaml`에서 규칙 ID/값을 대조해 인용을 정확히 맞춘다(값을 새로 만들지 않는다).
3. 영향받는 페이지를 고른다. 없으면 `WIKI.md`의 page-type에 맞춰 새 페이지 경로를 정한다
   (예: 새 카테고리 → `categories/<x>.md`).

## 3. Draft → Confirm → Write (절대 먼저 쓰지 않는다)
1. **터미널에 먼저 출력**: (a) 페이지별 제안 변경(diff 수준으로), (b) `index.md` 추가/변경 줄,
   (c) `log.md`에 넣을 항목(`## <date> · ingest — <title>`), (d) `open-questions.md`에 올릴 미확인/owed 항목.
2. **John의 확인을 받는다. 확인 전에는 어떤 파일도 쓰지 않는다.**
3. 확인되면 `Write`/`Edit`로: 대상 페이지 갱신 → `index.md` 갱신 → `log.md` 앵커
   (`<!-- LOG (newest first) -->`) 바로 아래 prepend → 필요 시 `open-questions.md` 갱신.

## 4. 결과 요약 (3~5줄)
- 반영한 소스 · 갱신/생성한 페이지 수와 경로
- 추가된 `[CONFIRMED]` / `[REVIEW-REQUIRED]` / `[BLOCKED]` 사실 수
- `open-questions.md`에 새로 올린 owed/미확인 항목 수
- 지어내지 않고 남겨둔(미확인) 값이 있으면 정직하게 한 줄
