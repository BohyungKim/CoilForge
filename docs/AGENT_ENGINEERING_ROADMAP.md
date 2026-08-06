# Agent Engineering 성장 로드맵 (John — 2026-07)

> 평일 저녁 1~1.5시간 × 10주. CoilForge를 실습장으로 삼아, "Claude Code 파워유저"에서
> "에이전트 엔지니어"로 올라가기 위한 실전형 커리큘럼.
>
> 근거: `/deep-research` 실행 결과 — Anthropic 공식 엔지니어링 블로그 6편, Claude Code /
> Agent SDK 공식 문서, `anthropics/skills` 레포 등 1차 소스 14개에서 추출한 70개 주장.
> (적대적 검증 패스는 세션 한도로 실패 — 모든 인용은 1차 소스 URL 직접 인용이며,
> 수치 주장은 해당 원문에서 재확인 후 사용할 것.)

---

## 1. 현재 수준 진단 — CoilForge 코드베이스 근거

| 축 | 수준 | 이미 갖춘 것 (근거) | 갭 |
|---|---|---|---|
| **1. Agent & Sub-agent** | 중상 | 커스텀 에이전트 2개(`coilforge-invariant-guard`, `coilforge-render-verifier`) — 공식 권장 패턴("검증 서브에이전트는 메인 세션의 가정을 물려받지 않아 효과적")을 이미 실천 중 | 에이전트를 **검증자**로만 사용. orchestrator-workers, 병렬 fan-out, judge panel 등 **오케스트레이션 패턴** 미경험. Agent SDK 미사용 |
| **2. Context Engineering** | 상 | 500줄급 CLAUDE.md(gotcha 축적), 메모리 시스템, LLM 위키, `/checkpoint` 세션 로그, worktree 병렬 세션 | CLAUDE.md가 공식 권장(200줄 이하)의 2.5배 — "절차는 skill로, 규칙은 rules로" 분리 미적용. compaction/메모리 툴의 **측정 기반** 운영 미경험 |
| **3. Tool & MCP** | 중 | 자체 Python MCP 서버 1개(`plan-review`), Claude-in-Chrome 실전 활용 | **ACI(Agent-Computer Interface) 설계 이론** 부재 — 툴 설명 품질이 에이전트 성능을 직접 좌우한다는 관점(툴 설명 개선만으로 작업시간 40% 단축 사례)이 빈 곳. "언제 MCP를 안 쓰는 게 맞는가" 판단 기준 없음 |
| **4. Hook & Skill** | 중상 | PostToolUse 타깃 테스트 훅, Stop/Notification 알림 훅, 커스텀 스킬 10+개(ccsi-* 5종 포함) | 훅이 **사후 반응형**(PostToolUse)에 머묾. "절대 일어나면 안 되는 일은 지시문이 아니라 PreToolUse 차단 훅으로" 원칙 미적용. 훅 이벤트 표면(~30종: SubagentStop, PreCompact, SessionStart 등) 미탐사. 스킬은 eval 없이 작성 |
| **5. Planning & HITL** | 상 | Phase Gate 워크플로우, confidence gate 3단(HIGH/MEDIUM/LOW), plan-review MCP 외부 크로스체크 | **eval-driven development** — "자율성 승격을 측정으로 결정"하는 단계가 없음. 20케이스 + LLM-judge 수준의 경량 eval도 미보유 |

**종합:** 갭이 가장 큰 곳은 **축 1(오케스트레이션)과 축 3(툴 인터페이스 설계)**.
축 2·5는 이미 상급이므로 "심화 + 측정" 위주로 짧게 배정한다.

---

## 2. 갈고닦아야 할 항목 (우선순위순)

1. **오케스트레이션 어휘 습득** — prompt chaining / routing / parallelization / orchestrator-workers / evaluator-optimizer 5대 패턴을 이름으로 알고, 언제 쓰고 언제 안 쓰는지(멀티에이전트는 토큰 3~15배 — 고가치 작업에만) 판단하기.
2. **서브에이전트 위임 기준의 정량화** — "10개 이상 파일 탐색 or 3개 이상 독립 작업이면 위임", "분해는 문제 유형이 아니라 **컨텍스트 격리** 기준으로". 안티패턴(순차 의존 작업, 같은 파일 동시 편집, 전문 에이전트 남발) 회피.
3. **ACI 설계** — 툴 정의에 메인 프롬프트만큼의 공을 들이기: 예시 포함, 자연어 결과 반환, poka-yoke(실수 방지) 인터페이스.
4. **PreToolUse 차단형 가드레일** — "지시문은 확률적 요청, 훅은 결정적 보장". CoilForge의 DO-NOT-TOUCH 경로를 훅으로 강제.
5. **Eval-first 습관** — 스킬/에이전트를 만들기 **전에** 평가 3개부터. 실사용 쿼리 ~20개 + LLM-as-judge(0.0–1.0 점수)로 시작.
6. **Agent SDK** — CLI 워크플로우를 프로그래밍 가능한 프로덕션 에이전트로 옮기는 다리. "CLI는 일상 개발, SDK는 프로덕션 자동화."
7. **컨텍스트 다이어트의 측정화** — context rot(길수록 recall 저하)을 전제로, CLAUDE.md 200줄 목표·`.claude/rules/` paths 분리·just-in-time 로딩을 토큰 수치로 확인.

---

## 3. 10주 로드맵

각 주는 **[읽기 30분 → 실습 45분 → 완료 기준 확인]** 리듬. 완료 기준은 전부
CoilForge 안에서 눈으로 확인 가능한 산출물이다 (Phase Gate 문화 그대로).

### Week 1 — 패턴 어휘: Workflow vs Agent 분류법
- **읽기:** [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) — workflows(코드가 경로 결정) vs agents(모델이 경로 결정) 구분 + 5대 패턴.
- **실습:** CoilForge의 자동화 전부(rule engine, 2개 서브에이전트, ccsi-* 스킬, ship 커맨드, 훅)를 5대 패턴에 매핑한 한 장짜리 표 작성 → `docs/wiki/`에 페이지로.
- **완료 기준:** "CoilForge에서 진짜 agent인 것"과 "사실은 workflow인 것"을 구분한 위키 페이지 1개. (힌트: rule engine은 agent가 아니라 잘 만든 workflow — 그게 장점이다. "단순한 해법과 eval을 소진한 뒤에만 에이전틱 복잡도를 추가하라"가 공식 권고.)

### Week 2 — 서브에이전트 위임 기준과 안티패턴
- **읽기:** [Subagents in Claude Code](https://claude.com/blog/subagents-in-claude-code) + [When and how to use multi-agent](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them).
- **실습:** 기존 2개 에이전트(`.claude/agents/*.md`)를 위임 기준(컨텍스트 격리? 최소 컨텍스트 전달?)으로 감사(audit)하고 프롬프트 개선. 이어서 3번째 에이전트 1개 신설 — 예: 멀티코일 견적 패키지에서 **코일별 병렬 검증** 리더(탐색형, 읽기 전용).
- **완료 기준:** 새 에이전트가 실제 견적 PDF 1건에서 유의미한 리포트를 반환. 에이전트 정의에 objective / output format / task boundary가 명시돼 있을 것 ("모호한 지시 = 중복·누락 작업"이 공식 실패 모드).

### Week 3 — 오케스트레이션: orchestrator-workers 실전
- **읽기:** [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) — 리드 에이전트가 분해→병렬 위임하는 구조, 토큰 경제학(멀티에이전트 ≈ 채팅의 15배).
- **실습:** Claude Code의 Workflow/Agent 병렬 실행으로 "견적 패키지 전 코일 fan-out 검토 → 결과 종합" 오케스트레이션을 1회 설계·실행. 단일 세션으로 했을 때와 비용·품질 비교 메모.
- **완료 기준:** 병렬 실행 로그 + "이 작업엔 멀티에이전트가 (안)맞았다"는 1문단 판정. 판정 근거가 3대 조건(컨텍스트 오염 / 병렬성 / 전문화) 중 어느 것인지 명시.

### Week 4 — Claude Agent SDK 입문
- **읽기:** [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview) — Claude Code와 동일한 툴·루프·컨텍스트 관리를 Python 라이브러리로. SDK는 `.claude/skills/`, CLAUDE.md를 그대로 로드하므로 기존 자산 재사용 가능.
- **실습:** `invariant-guard`를 SDK 스크립트로 포팅 — `AgentDefinition`(prompt + 제한된 툴 목록)으로 정의하고, diff를 입력받아 위반 리포트를 출력하는 단독 실행 파일. `parent_tool_use_id`로 서브에이전트 메시지 추적 로그 남기기.
- **완료 기준:** `python check_invariants.py` 한 방으로 커밋 전 감사가 도는 것. (이게 Week 10의 CI 훅 재료가 된다 — "CLI는 개발, SDK는 자동화.")

### Week 5 — ACI: 툴 인터페이스 설계
- **읽기:** [Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) + Building Effective Agents의 ACI 절 — 적은 수의 고레버리지 툴, 네임스페이스, **자연어 컨텍스트를 반환하는 툴 결과**, poka-yoke.
- **실습:** `mcp_servers/plan_review/server.py`의 툴 정의를 ACI 기준으로 리라이트: 설명에 사용 예시 추가, 에러를 "다음에 뭘 하면 되는지" 알려주는 자연어로, 잘못 쓰기 어려운 파라미터 구조로. Claude에게 개선 전/후 툴을 각각 쓰게 해 비교(공식 사례: 툴 설명 개선만으로 작업 완료 시간 40% 단축).
- **완료 기준:** 개선 전/후 같은 플랜 리뷰 태스크의 turn 수·오호출 횟수 비교 메모 1개.

### Week 6 — MCP 서버 2호기 + "MCP를 안 쓰는 판단"
- **읽기:** MCP 공식 문서의 서버 개발 가이드 + Week 5 소스 재독.
- **실습:** 2호 MCP 서버 후보 두 개를 놓고 **먼저 판정**: (a) `coil_header_rules.yaml`을 질의하는 rule-query 서버 vs (b) 그냥 CLI 스크립트 + Bash 허용. "에이전트가 세션 중 반복 호출하는가? 구조화된 결과가 필요한가?"로 결정하고, MCP가 정답인 쪽만 구현.
- **완료 기준:** 판정 근거 문서 + (구현했다면) `.mcp.json`에 등록된 서버가 실제 질의에 응답. 툴이 15~20개를 넘으면 모델이 선택에 컨텍스트를 낭비한다는 임계값을 기억할 것 — 서버를 늘리는 게 항상 이득이 아니다.

### Week 7 — Hooks 심화: 사후 반응 → 사전 차단
- **읽기:** [Hooks guide](https://code.claude.com/docs/en/hooks-guide) + [Steering Claude Code](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more) — "절대 금지는 지시문이 아니라 훅으로". 훅 프로토콜: stdin JSON, exit 2 = 차단(stderr가 Claude에게 피드백), PreToolUse deny는 permission mode보다 우선.
- **실습:** CoilForge의 DO-NOT-TOUCH 경로(`pdf_to_template_drawing.py`, 시드된 `template.svg` 4종 아티팩트, raw JSON/PDF)를 편집하려는 Edit/Write를 **PreToolUse 훅으로 차단**하는 `guard_do_not_touch.py` 작성. 보너스: SessionStart 훅의 stdout이 컨텍스트에 주입되는 것을 이용해 `docs/SESSION_LOG.md` 최근 체크포인트 자동 로드.
- **완료 기준:** 금지 파일 편집 시도가 실제로 exit 2로 막히고, Claude가 stderr 사유를 읽고 우회하지 않고 물러나는 것을 라이브로 확인.

### Week 8 — Skills 심화 + CLAUDE.md 다이어트
- **읽기:** [Equipping agents with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) + [anthropics/skills](https://github.com/anthropics/skills)의 `docx`/`pdf` 스킬 소스 정독 — 3단 progressive disclosure(name+description → SKILL.md → 참조 파일), description이 트리거 표면(name ≤64자, description ≤1024자, 3인칭), 본문 500줄 이하.
- **실습 A:** ccsi-* 스킬 중 1개를 기준에 맞게 리팩터(트리거 설명 개선, 긴 본문을 참조 파일로 분리, "결정적이어야 하는 부분은 스크립트로").
- **실습 B:** CLAUDE.md 다이어트 — 절차성 내용(서버 재시작 워크플로우 등)은 skill로, 경로 조건부 규칙은 `.claude/rules/` + `paths` frontmatter로 이관해 200줄 방향으로. (@import는 정리는 되지만 **컨텍스트 절감은 안 된다** — 시작 시 전부 로드됨.)
- **완료 기준:** CLAUDE.md 줄 수 감소 수치 + 이관된 rules/skill이 해당 파일 작업 시에만 로드되는 것 확인.

### Week 9 — Context Engineering 심화: 측정 기반 운영
- **읽기:** [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) + [컨텍스트 관리 쿡북](https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools) — context rot, "적절한 고도(altitude)"의 시스템 프롬프트, just-in-time 로딩(식별자만 들고 있다가 툴로 가져오기), 장기 작업 3기법(compaction / 구조화 노트 / 서브에이전트).
- **실습:** 긴 CoilForge 세션 1개를 골라 `/context`로 토큰 구성 확인 → 가장 큰 소비원(위키? 규칙? 훅 출력?)을 just-in-time으로 전환. `/compact` 후 루트 CLAUDE.md만 자동 재주입된다는 사실을 확인하고, 컴팩션에서 살아남아야 할 내용을 메모리/SessionStart 훅으로 옮기기.
- **완료 기준:** 전/후 컨텍스트 토큰 비교 수치 1개 + "컴팩션 생존 전략" 위키 페이지.

### Week 10 — Eval-driven autonomy: 자율성의 승격 게이트
- **읽기:** [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) + multi-agent 포스트의 eval 절 — 실사용 쿼리 ~20개 + 단일 호출 LLM-as-judge(0.0–1.0 + pass/fail)로 시작; 능력을 만들기 전에 eval부터.
- **실습:** CoilForge 드로잉 파이프라인 eval 세트 구축 — 과거 실제 견적 PDF 20건(sanitized) × "엔진 슬롯이 기대값과 일치하는가"를 pytest + 스코어 리포트로. 이걸 **Claude의 자율성 게이트**로 재사용: eval 통과율이 기준을 넘는 작업 유형만 사전 승인 확대 (MEDIUM→HIGH 승격 로직을 사람이 아니라 Claude에게 적용하는 것).
- **완료 기준:** `python -m pytest tests/eval_drawing_accuracy.py` 스코어 리포트 + "이 유형은 이제 Claude에게 맡긴다/아직 아니다" 판정 문서. Week 4의 SDK 스크립트를 여기에 연결하면 커밋 전 자동 감사 루프 완성.

---

## 4. 10주 이후 (선택 심화)

- **Agent Teams / 중첩 서브에이전트(최대 5단)** — Week 3 오케스트레이션이 손에 붙은 뒤.
- **prompt/agent 타입 훅** — 셸 훅으로 판정 불가한 것(diff의 의미적 위험도 등)을 Haiku 단일 호출 훅으로.
- **서버사이드 compaction / memory tool API** — SDK 에이전트가 장기 실행형이 될 때.
- **스킬 eval 자동화** — skill-creator의 벤치마크 기능으로 ccsi-* 스킬 회귀 테스트.

## 5. 소스 목록 (전부 1차 소스)

| 축 | 소스 |
|---|---|
| 1 | [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) · [Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) · [Subagents in Claude Code](https://claude.com/blog/subagents-in-claude-code) · [When/how multi-agent](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them) · [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview) |
| 2 | [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) · [Context management cookbook](https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools) · [Memory docs](https://code.claude.com/docs/en/memory) |
| 3 | [Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents) · Building Effective Agents (ACI 절) |
| 4 | [Hooks guide](https://code.claude.com/docs/en/hooks-guide) · [Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) · [anthropics/skills](https://github.com/anthropics/skills) · [Steering Claude Code](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more) |
| 5 | [Demystifying evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) · Multi-agent research system (eval 절) |

> ⚠️ 리서치의 적대적 검증 단계가 세션 한도로 전부 실패했으므로, 본문 수치(90.2%, 15x,
> 40%, 200줄, 20쿼리 등)는 위 원문에서 읽으며 직접 재확인할 것 — 그 재확인 자체가
> Week 1~10 읽기 과제에 포함돼 있다.
