---
description: Run the full test suite, then (only if green) revise CLAUDE.md, stage, commit, and push the current branch
allowed-tools: Bash(python -m pytest:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git status:*), Bash(git diff:*), Bash(git branch:*), Bash(git rev-parse:*), Bash(git log:*), Read, Edit, Glob
---

# /ship — 배포 (test → revise CLAUDE.md → commit → push)

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
2. **CLAUDE.md 갱신 (revise-claude-md 워크플로우)** — 커밋에 함께 담기 위해 스테이징 *전에* 실행한다.
   - 이번 세션에서 얻은 학습(새로 쓴 bash 명령, 코드 스타일 패턴, 테스트 접근법, 환경/설정 quirk, 겪은 gotcha)을 돌아본다.
   - `CLAUDE.md` 파일들을 찾는다(`Glob`로 `**/CLAUDE.md`).
   - 추가할 내용을 **한 개념당 한 줄**로 간결히 초안 작성한다. 장황한 설명·뻔한 정보·재발 가능성 낮은 일회성 수정은 넣지 않는다.
   - 추가 후보마다 `diff` 형태로 변경안과 **한 줄 이유**를 보여준다.
   - **반드시 사용자 승인을 먼저 받는다.** 승인한 변경만 `Edit`으로 적용하고, 승인 없으면 CLAUDE.md를 고치지 않는다.
   - 추가할 학습이 없으면 "이번 세션에서 CLAUDE.md에 추가할 내용 없음"이라고 알리고 이 단계를 건너뛴다.
3. `git add -A` — 변경된 파일 전체 스테이징(승인되어 적용된 CLAUDE.md 변경 포함).
4. 변경 내용을 분석하여 적절한 커밋 메시지를 자동 작성한다.
   - Conventional Commits 형식(`feat:`, `fix:`, `refactor:`, `docs:` …)을 따른다.
   - 메시지는 영어로 작성한다(이 프로젝트 규칙).
   - 커밋 메시지 끝에 다음 trailer를 추가한다:
     ```
     Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
     ```
5. `git commit` — 위 메시지로 커밋한다.
6. 현재 브랜치를 확인하고(`git rev-parse --abbrev-ref HEAD`) `git push origin <현재브랜치>` 로 푸시한다.
   - **`main`에 직접 커밋/푸시하지 않는다.** 현재 브랜치가 `main`이면 멈추고 사용자에게 알린다.
   - `--force` 푸시 금지. 이미 푸시된 커밋 amend 금지.

## 4. 결과 요약 출력
push 완료 후 다음을 3~5줄로 요약한다:
- 통과한 테스트 수
- CLAUDE.md 갱신 여부(적용한 항목 수 또는 "변경 없음")
- 작성한 커밋 메시지(제목)
- 푸시한 브랜치와 원격
