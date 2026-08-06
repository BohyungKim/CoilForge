---
description: Run the full test suite, then (only if green) lint the wiki for drift, capture new knowledge (domain facts → wiki / agent-instructions → CLAUDE.md), stage, commit, and push the current branch
allowed-tools: Bash(python -m pytest:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git status:*), Bash(git diff:*), Bash(git branch:*), Bash(git rev-parse:*), Bash(git log:*), Read, Edit, Write, Grep, Glob
---

# /ship — 배포 (test → wiki-lint → 지식 캡처(wiki/CLAUDE.md) → commit → push)

사용자가 `배포` 또는 `ship`을 입력하면 이 워크플로우를 실행한다.
아래 순서를 **반드시 지키고**, 테스트가 실패하면 절대 commit/push 하지 않는다.

## 1. 테스트 실행
- 레포 루트에서 백엔드 테스트 전체 실행: `python -m pytest -q`
  - (참고: 단일 파일은 `python -m pytest tests/<file>.py -q`)

## 2. 테스트 실패 시
- **중단한다.** 실패한 테스트 이름과 핵심 에러 메시지를 그대로 보고한다.
- `git add` / `git commit` / `git push`를 **하지 않는다.**
- 추측으로 수정하지 말고, 사용자에게 다음 행동을 묻는다.

## 3. 테스트 전체 통과 시 — 아래 순서로 실행
1. `git status` + `git diff` 로 변경 내용을 먼저 확인한다.
2. **위키 드리프트 점검 — `/wiki-lint` (리포트만, 비차단).**
   - `/wiki-lint` 스킬을 실행한다. 테스트가 code-vs-code를 검증했다면, lint는 **wiki-vs-code**를 검증한다(위키 주장 ↔ `coil_header_rules.yaml`/enum/문서). `docs/wiki/`가 없으면 이 단계를 건너뛴다.
   - **비차단:** 드리프트가 나와도 commit/push를 **막지 않는다.** 발견 항목은 4단계 요약에 한 줄로 표시한다.
   - 위키를 코드에 억지로 맞추지 않는다. 심각한 드리프트(위키가 이번 diff의 값과 직접 모순 등)는 `docs/wiki/open-questions.md`에 올려 John이 소스(CLAUDE.md/YAML)를 정정하게 한다.
   - lint 로직을 여기 복붙하지 않는다 — 기존 `/wiki-lint` 스킬을 그대로 호출한다.
3. **이번 세션 지식 캡처 — 청중별 2레인** (커밋에 함께 담기 위해 스테이징 *전에* 실행한다).
   먼저 이번 세션에서 얻은 것을 돌아보고, **누구를 위한 지식인지**로 갈라 넣는다:
   - **(a) 도메인 사실 → 위키 (`docs/wiki/`).** 코일/규칙/패밀리 지식, 새 SOP 특례, 태그 스펠링, `John YYYY-MM-DD:` 결정 등. `/wiki-ingest` 규율로 반영한다 — 각 사실에 배지(`[CONFIRMED]`/`[REVIEW-REQUIRED]`/`[BLOCKED]`) + `evidence_ref` 인용 + `[[링크]]`를 붙이고, 관련 페이지 + `index.md` + `log.md`를 갱신. 소스에 없는 값은 지어내지 않고 `open-questions.md`에 올린다.
   - **(b) 에이전트 지시 → CLAUDE.md.** 새로 쓴 bash 명령, 코드 스타일 패턴, 테스트 접근법, 환경/설정 quirk, 겪은 gotcha. `Glob`로 `**/CLAUDE.md`를 찾아 **한 개념당 한 줄**로 간결히. 장황한 설명·뻔한 정보·일회성 수정은 넣지 않는다.
   - **두 레인 공통:** 후보마다 `diff` 형태로 변경안과 **한 줄 이유**를 보여주고, **반드시 사용자 승인을 먼저 받는다.** 승인한 변경만 적용한다(위키는 `Write`/`Edit`, CLAUDE.md는 `Edit`). 승인 없으면 고치지 않는다.
   - 애매하면(도메인이냐 지시냐) 물어본다. 둘 다 없으면 "이번 세션 위키/CLAUDE.md 추가 없음"이라고 알리고 건너뛴다.
4. **스테이징 — `git add -A` 금지. 관련 변경만 경로로 골라 추가한다.**
   - 1단계에서 본 변경 중 **이번 작업과 직접 관련된 파일만** `git add <경로>`로 스테이징한다(3단계에서 승인·적용된 `docs/wiki/*` 위키 변경과 CLAUDE.md 변경을 **코드와 같은 커밋에** 포함 — 위키↔코드 히스토리 동기 유지).
   - 다음은 **절대 스테이징/커밋하지 않는다**(무관·로컬·도구 산출물):
     - `.claude/worktrees/` — git worktree 디렉터리(레포 안에 커밋하면 손상 위험)
     - `.claude/agent-memory/` — 로컬 에이전트 메모리
   - 무엇이 "관련"인지 애매하면 멈추고 사용자에게 포함/제외 목록을 보여준 뒤 확인받는다.
   - 동시 세션이 인덱스를 바꿀 수 있으므로, 스테이징 직후 `git diff --cached --stat`로 **실제로 무엇이 담겼는지 재확인**한다. 위 제외 항목이 끼었으면 `git restore --staged <경로>`로 뺀다.
5. 변경 내용을 분석하여 적절한 커밋 메시지를 자동 작성한다.
   - Conventional Commits 형식(`feat:`, `fix:`, `refactor:`, `docs:` …)을 따른다.
   - 메시지는 영어로 작성한다(이 프로젝트 규칙).
   - 커밋 메시지 끝에 다음 trailer를 추가한다:
     ```
     Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
     ```
6. `git commit` — 위 메시지로 커밋한다.
7. 현재 브랜치를 확인하고(`git rev-parse --abbrev-ref HEAD`) `git push origin <현재브랜치>` 로 푸시한다.
   - **`main`에 직접 커밋/푸시하지 않는다.** 현재 브랜치가 `main`이면 멈추고 사용자에게 알린다.
   - `--force` 푸시 금지. 이미 푸시된 커밋 amend 금지.

## 4. 결과 요약 출력
push 완료 후 다음을 3~6줄로 요약한다:
- 통과한 테스트 수
- **위키 드리프트**: `/wiki-lint` 발견 수(0이면 "드리프트 없음") — 커밋을 막지 않았음을 명시
- **지식 캡처**: 위키 갱신 페이지 수 / CLAUDE.md 갱신 항목 수(각각 없으면 "변경 없음")
- 작성한 커밋 메시지(제목)
- 푸시한 브랜치와 원격
