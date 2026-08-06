---
description: Answer a question from the CoilForge engineering wiki with citations — and optionally file a valuable answer back as a new page
argument-hint: "[question about coils / rules / families / taxonomy]"
allowed-tools: Read, Grep, Glob, Write, Edit
---

# /wiki-query — 위키에 질문 (Karpathy LLM-Wiki query)

`$ARGUMENTS`로 준 질문을 `docs/wiki/`의 페이지들에서 찾아 **인용과 함께** 답한다. 답이 재사용 가치가
있으면 새 페이지로 위키에 되-저장(file-back)할지 제안한다.

절대 없는 내용을 지어내지 않는다 — 위키에 없으면 `미확인`이라 답하고, 어디를 봐야 할지(규칙 ID/소스)만
가리킨다. 추측 값을 답으로 내지 않는다. (`/wiki-ingest`는 지식을 *들여오고*, `/wiki-lint`는 *일관성*을
점검한다. `/wiki-query`는 위키를 *읽어* 답한다 — 읽기 우선, 되-저장은 확인 후에만.)

## 고정 좌표
- **위키 루트:** `docs/wiki/` (`WIKI.md`가 스키마·배지·인용 규칙). 카탈로그는 `index.md`.
- **인용:** 답의 각 사실에 배지(`[CONFIRMED]`/`[REVIEW-REQUIRED]`/`[BLOCKED]`) + `evidence_ref` +
  가능하면 규칙 ID. 위키 페이지 자체도 `[[stem]]`으로 가리킨다.

## 1. 검색
1. `index.md`로 관련 페이지 후보를 잡고, `Grep`으로 위키 본문에서 키워드/규칙 ID를 찾는다.
2. 필요하면 위키가 가리키는 1차 근거(`coil_header_rules.yaml`, `docs/rules/coil_header_rule_extraction.md`)를
   `Read`로 확인해 인용을 검증한다. **위키에 없는 값을 여기서 새로 만들지 않는다** — 없으면 미확인.

## 2. 답변 합성
- 질문에 직접 답하고, 각 사실에 배지 + 인용을 붙인다. 상충하는 근거가 있으면 숨기지 말고 둘 다 제시한다.
- 위키가 다루지 않는 부분은 명시적으로 `미확인`으로 남기고, 관련 스텁 페이지(`index.md`의 Stubs)를 가리킨다.

## 3. (선택) 되-저장 — Draft → Confirm → Write
- 답이 일반적 재사용 가치가 있으면: **터미널에 새 페이지 draft를 먼저 보여주고**, John의 확인을 받은 뒤에만
  `Write`(새 페이지) + `index.md`/`log.md`(`## <date> · query — <title>`) 갱신. 확인 전에는 쓰지 않는다.

## 4. 결과 요약 (2~4줄)
- 답의 핵심 1~2줄 + 근거로 쓴 페이지/규칙
- `미확인`으로 남긴 부분이 있으면 명시
- 되-저장했으면 새 페이지 경로, 아니면 "되-저장 없음"
