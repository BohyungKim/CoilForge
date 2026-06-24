---
description: Evaluate one day of Notion work (Work Calendar + Daily Tasks) and write a research-backed efficiency review into that day's "Work" row
argument-hint: "[YYYY-MM-DD | today | yesterday]  (default: today, Toronto)"
allowed-tools: mcp__notion__notion-search, mcp__notion__notion-fetch, mcp__notion__notion-update-page, mcp__notion__notion-create-pages, Bash(TZ=America/Toronto date:*), Bash(date:*)
---

# /work-review — 업무 효율 리뷰 (Notion daily work evaluation)

입력은 **평가할 날짜 하나**뿐이다 (`$ARGUMENTS`). 그 날의 Notion 작업을 읽어
**연구 기반 Daily Work Review**를 작성하고, 그 날 **Daily Tasks의 "Work" 행 본문**에
붙여 넣는다. 절대 값을 지어내지 않는다 — 근거가 약하면 "추정/미확인"이라고 적는다.

> Notion MCP 도구가 deferred 상태면 먼저 한 번에 로드한다:
> `ToolSearch("select:mcp__notion__notion-search,mcp__notion__notion-fetch,mcp__notion__notion-update-page,mcp__notion__notion-create-pages")`

## 고정 좌표 (Notion architecture — verified)

- **Work Tasks** (Work Calendar / Parking Lot): `collection://d35b1602-d881-4925-8672-cd643bab375d`
  - props: Name, Date, Due Date, Status(Not Started/In Progress/Blocked/Done), Impact, Priority
- **Daily Tasks** (the "Work" row lives here): `collection://08ef144c-aa66-4ebb-b213-b495e1621d9c`
  - props: Name, Date, Status(Not started/In progress/Done), Impact, Priority, Projects, Tasks Table
- Daily page: `92806ef1-9f5f-4929-a9a3-8a3739346465` · Work hub: `1f3d2b09-cc4d-4a09-8567-6cc46b27ba73`

## 1. 날짜 확정 (America/Toronto)

1. `$ARGUMENTS`가 비었거나 `today`면 → 오늘. `yesterday`면 → 어제. 그 외엔 그 날짜.
2. Toronto 기준으로 확정한다: `TZ=America/Toronto date +%Y-%m-%d` (필요시 `-d` 로 오프셋).
   - 대상일 `D`, 직전일 `D-1` 둘 다 구한다.
3. **Notion timestamp는 UTC라 다음날처럼 보일 수 있다.** 행의 `Date`를 Toronto 로컬
   날짜로 환산해서 `D`/`D-1`과 비교한다. 애매하면 행 제목·본문·생성시각을 함께 본다.

## 2. 그 날의 작업 수집 (두 DB 모두, D + 컨텍스트용 D-1)

깔끔한 "날짜 필터 쿼리" 도구는 없다. 다음으로 수집한다:
1. `notion-search`를 **각 data source로 스코프**해서 (`data_source_url`) 호출한다.
   - Work Tasks(`collection://d35b1602…`)와 Daily Tasks(`collection://08ef144c…`) 둘 다.
   - 쿼리는 그 날짜(예: `June 9` / `2026-06-09`)와 보일 법한 작업/회의 키워드를 섞는다.
2. 후보 행마다 `notion-fetch`로 열어 **`Date`가 `D`(또는 `D-1`)에 속하는지 확인**하고,
   아닌 것은 버린다. 본문에서 상태·메모·시간블록(Date start/end)·근거를 읽는다.
3. 각 작업에 대해 기록: Name, Status, Priority/Impact, 시간블록, 핵심 메모/산출 근거.
4. **완전성 정직성:** 검색으로 못 잡았을 수 있는 알려진 블록이 빠졌다고 의심되면
   리뷰에 "검색에 안 잡힌 항목이 있을 수 있음"이라고 명시한다. 없는 일을 만들지 않는다.

## 3. 평가 작성 — 승인된 Daily Work Review 템플릿

원칙(연구 기반): **활동량이 아니라 성과(outcome)**, deep work/flow, plan-vs-actual,
막힌 일(Problems)까지. **한 화면**에 들어오게, 표는 5행 이내. 근거 약하면 "추정"이라 표기.

아래 순서·구조로 작성한다 (Notion-flavored markdown; 표 작성 전
`notion://docs/enhanced-markdown-spec` 리소스를 한 번 확인해 표 문법을 맞춘다):

**1) TL;DR (3 lines)** — 하루 한줄 평가 · 점수 `NN/100` · 가장 중요한 다음 액션 하나.

**2) Plan vs Actual** *(≤5 rows)* — 계획/타임블록 대비 실제.
`Planned block | Actual | Variance / note` — 미기록·버퍼 시간도 숨기지 말고 한 행으로.

**3) Progress · Plans · Problems** *(각 ≤3 bullets)*
- **Progress** — 오늘 전진시킨 성과(결과 중심; "회의 참석"이 아니라 결과)
- **Plans** — 내일 top 1–3
- **Problems** — 막힌 일 / 남의 도움·결정이 필요한 항목

**4) Efficiency Score /100** — 아래 루브릭, 각 항목 한줄 근거.

| Dimension | Weight | Measures |
| --- | ---: | --- |
| Outcome & Strategic Alignment | 30 | 실제 결과/목표를 움직였나 (작업 수가 아니라) |
| Deep Work & Flow | 25 | 보호된 집중시간, 낮은 컨텍스트 스위칭/단편화 |
| Execution & Closure | 20 | plan-vs-actual 완료 + 실제로 닫힌 항목 |
| Coordination Leverage | 15 | 남을 unblock한 1:1/결정 |
| Follow-up Clarity & Sustainability | 10 | 다음 액션(owner+due) 포착 · 지속가능한 페이스 |

**5) Outcomes & Closure** *(≤5 rows)* — `Output | Outcome (the result, not "done") | Next action + owner/due`

**6) Notion-ready summary** — 3–4문장 붙여넣기용 단락 + 직전일 대비 **two-day pattern** 한 줄.

## 4. "Work" 행 찾기 / 생성 (Daily Tasks)

- Daily Tasks(`collection://08ef144c…`)에서 `Name == "Work"`이고 `Date == D`(Toronto)인 행을 찾는다.
- **없으면**: `notion-create-pages`로 그 DB에 행 생성. **Date는 9:00 AM–5:00 PM 근무
  블록(datetime range)으로 박는다** — 빈 날짜가 아니라 시간블록으로:
  - `Name` = `Work`, `Status` = 평가 시점 기준(보통 `Done`), `Impact`/`Priority` = `High` (기존 관례).
  - `date:Date:is_datetime` = `1`  *(0이 아니라 1 — 시간 포함이라는 뜻)*
  - `date:Date:start` = `{D}T09:00:00{OFF}`  (예: `2026-06-23T09:00:00-04:00`)
  - `date:Date:end`   = `{D}T17:00:00{OFF}`  (예: `2026-06-23T17:00:00-04:00`)
  - `{OFF}` = **그 날 D의 America/Toronto UTC 오프셋**. 한 번 계산해서 두 값에 같이 쓴다:
    `TZ=America/Toronto date -d "{D} 09:00" +%:z` → 여름 EDT `-04:00`, 겨울 EST `-05:00`.
    오프셋을 명시해야 Notion이 UTC로 정규화할 때 John 캘린더에 **항상 9 AM–5 PM**으로
    뜬다 (naive 문자열은 UTC로 오해되니 금지). DST는 이 계산이 자동 처리한다.
    *(검증: `…T09:00:00-04:00` == `…T13:00:00Z`, 기존 6월 행과 동일.)*
- 여러 후보가 애매하면 만들지 말고 John에게 어느 행인지 묻는다.

## 5. Draft → Confirm → Write (절대 먼저 쓰지 않는다)

1. 완성된 리뷰 전체를 **터미널에 먼저 출력**한다.
2. John의 확인을 받는다. **확인 전에는 Notion에 아무것도 쓰지 않는다.**
3. 확인되면 `notion-update-page`로 "Work" 행 본문에 추가:
   `command: "insert_content"`, `position: { "type": "end" }`, `content`: 리뷰 markdown.
   (기존 본문은 보존 — append만. replace 금지.)

## 6. 결과 요약 (3~5줄)

- 평가한 날짜 (Toronto)
- 최종 점수 `NN/100`
- 작성 위치: "Work" 행 페이지 URL
- 새로 만든/누락된 행이 있으면 명시
- 검색으로 못 잡았을 수 있는 항목에 대한 정직한 한 줄
