---
description: Send an implementation plan to the plan-review MCP server (OpenAI) for a critical pre-build review
argument-hint: "[plan text | file path | empty = use the plan in the current conversation]"
allowed-tools: mcp__plan-review__review_plan, Read
---

# /plan-review — 플랜 외부 검토 (plan-review MCP)

사용자가 `/plan-review` 를 입력하면, 구현 플랜을 `plan-review` MCP 서버
(`mcp__plan-review__review_plan`, OpenAI 백엔드)로 보내 누락/리스크 검토를 받는다.

## 1. 검토할 플랜 텍스트(`plan` 인자)를 결정한다

`$ARGUMENTS` 값에 따라 플랜 소스를 고른다:

- **인자가 파일 경로이면** (`.md` / `.txt` 등 실제 존재하는 경로): `Read`로 파일을
  읽고 그 내용을 플랜으로 사용한다.
- **인자가 일반 텍스트이면**: 그 텍스트를 그대로 플랜으로 사용한다.
- **인자가 비어 있으면**: 현재 대화에서 가장 최근에 제시/작성된 구현 플랜을
  플랜으로 사용한다. 대화에 명확한 플랜이 없으면 **호출하지 말고**, 어떤 플랜을
  검토할지 사용자에게 되묻는다.

## 2. MCP 도구 호출

위에서 결정한 텍스트를 `plan` 인자로 하여 `mcp__plan-review__review_plan` 를
**한 번** 호출한다. 플랜 텍스트를 임의로 요약/축약하지 말고 그대로 전달한다.

## 3. 결과 처리

- 반환값이 `ERROR: ...` 로 시작하면(예: `OPENAI_API_KEY` 누락), 그 에러를 그대로
  보고하고 원인/해결책을 1~2줄로 안내한다. 검토가 된 것처럼 꾸미지 않는다.
- 정상 반환이면 검토 내용을 사용자에게 전달하고, 마지막에 가장 중요한 1~3개
  지적사항을 짧게 요약한다.

## 참고

- 이 검토는 **외부(OpenAI) 유료 호출** 1회를 발생시킨다. 사소한 한 줄짜리 플랜보다
  멀티파일/스키마 변경 같은 실제 플랜에 사용한다.
- 이 도구는 플랜을 **검토만** 한다. 플랜을 대신 작성하거나 코드를 구현하지 않는다.
  CoilForge의 Phase Gate("플랜 먼저, 승인 후 구현")에서 승인 전 2차 점검용이다.
