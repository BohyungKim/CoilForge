---
description: Checkpoint the current session — append what was implemented + next steps to docs/SESSION_LOG.md, or `resume` to re-orient from the last checkpoint
argument-hint: "[empty = write a new checkpoint | resume = read the latest checkpoint]"
allowed-tools: Read, Write, Edit, Bash(git log:*), Bash(git diff:*), Bash(git status:*), Bash(git rev-parse:*), Bash(git branch:*), Bash(git add:*), Bash(git commit:*), Bash(TZ=America/Toronto date:*), Bash(date:*)
---

# /checkpoint — 세션 인수인계 로그 (pause/resume dev-log)

세션을 중간에 멈췄다가 며칠 뒤 돌아와 이어갈 때를 위한 스킬. **이번 세션에서 구현/결정된 것**과
**다음 스텝**을 `docs/SESSION_LOG.md`에 최신순으로 쌓고(write), 돌아왔을 때 가장 최근 체크포인트를
다시 읽어 방향을 잡는다(resume).

- **인자 없음** → 새 체크포인트 기록 (write 모드).
- **`resume`** → 가장 최근 체크포인트를 읽어 화면에 보여주고 "다음 스텝"부터 이어가도록 재-오리엔테이션. **아무것도 쓰지 않는다.**

절대 없는 내용을 지어내지 않는다 — 모든 "구현" 항목은 근거(커밋 해시/파일/테스트/대화 중 결정)에
연결하고, 불확실하면 "미확인"이라 적는다. (`/defer-task`는 이 요약을 Notion 날짜 태스크로 밀어내고,
`/work-review`는 지난 하루를 채점한다. `/checkpoint`는 repo에 커밋되는 로컬 dev-log로, 오직 재개를 위한 것.)

## 고정 좌표

- **로그 파일:** `docs/SESSION_LOG.md` (repo 루트 기준). 없으면 write 모드가 처음 생성한다.
- **최신순(newest-first).** 파일 상단의 `<!-- CHECKPOINTS (newest first) -->` 앵커 **바로 아래**에
  새 항목을 prepend 한다 (`Edit`: old_string = 앵커 줄 → new_string = 앵커 줄 + 새 항목). 전체 재작성 금지.
- **날짜/타임존:** America/Toronto. `TZ=America/Toronto date +%Y-%m-%d`.

---

# ───────── `resume` 모드 (인자가 `resume`일 때) — 읽기 전용 ─────────

## R1. 최근 체크포인트 읽기
1. `docs/SESSION_LOG.md`를 `Read`. 없으면 "아직 체크포인트가 없다"고 알리고, write 모드를 안내한 뒤 종료.
2. **가장 최근(맨 위) 항목 하나**를 화면에 그대로 출력한다 (필요하면 그 위 1개까지, 최대 2개).

## R2. 그 이후 변경 드리프트 확인
- 그 항목 헤더의 `HEAD <hash>`를 읽어 `git log <hash>..HEAD --oneline`을 돌린다.
  체크포인트 이후에 새로 커밋된 게 있으면 "체크포인트 이후 커밋"으로 한 줄씩 보여준다(없으면 "이후 커밋 없음").
- 현재 브랜치(`git rev-parse --abbrev-ref HEAD`)와 항목의 브랜치가 다르면 그 사실을 알린다.

## R3. 재개 안내
- 그 항목의 **"다음 스텝"** 체크리스트를 지금의 즉시 계획으로 다시 제시하고, **첫 항목부터 시작할지 묻는다.**
- **resume 모드에서는 로그 파일을 절대 수정하지 않는다.**

---

# ───────── write 모드 (인자 없음) — Draft → Confirm → Write ─────────

## 1. 기준점(base) 확정 — flaky trailer에 의존하지 않는다
1. `docs/SESSION_LOG.md`가 있으면 `Read` 해서 **가장 최근 항목의 `HEAD <hash>`**를 `LAST`로 잡는다.
2. 커밋 근거 범위: `git log LAST..HEAD --format='%h %s'` + `git diff LAST..HEAD --stat` (지난 체크포인트 이후 커밋).
3. 아직 안 커밋된 작업: `git status --short` + `git diff --stat` (진행 중 변경).
4. **첫 실행(로그 없음)** → `LAST`가 없으니: 이번 세션 커밋 힌트로 `git log --grep=session_<현재세션id> --oneline`
   (커밋 trailer에 있을 때만 잡힘 — 없으면 `git log --oneline -8`)을 쓰고, 항목에 "첫 체크포인트 — 이전 기준점
   없음, 범위는 근사치"라고 **정직하게** 적는다.
   > `Claude-Session:` trailer는 절반 정도의 커밋에만 붙으므로 범위의 유일한 근거로 쓰지 않는다. 진짜 경계는
   > 항목마다 기록하는 `HEAD <hash>`다.

## 2. 두 섹션 작성 (근거 기반, 지어내지 않음)
가장 풍부한 근거는 **이번 대화 세션 자체**(무엇을 했고 무엇을 결정했는지). git은 그 교차검증.

- **① 구현/결정된 것** *(결과 중심 bullets)* — "무엇을 했다"가 아니라 **"무엇이 바뀌었다"**. 각 항목에
  근거(커밋 해시 / 파일 / 통과 테스트 수 / 대화 중 확정된 결정)를 붙인다.
- **② 다음 스텝** *(`- [ ]` 체크리스트, 착수 순서대로)* — 아직 안 끝났거나 이월되는 것. 각 항목에 **왜 남았는지 /
  무엇이 필요한지**(예: "John이 값 제공 필요", "공식 미확정")를 한 줄로. 열린 질문/블로커 포함.
- **③ Resume anchors** — 브랜치 · `HEAD <풀 or 짧은 hash>` · 미커밋 파일 목록 · 핵심 파일/경로 · 관련 plan
  파일이나 `/defer-task`/이슈 링크.

## 3. 항목 포맷 (최신순 prepend용)
```
## <YYYY-MM-DD> (Toronto) · base <LAST_short>..<HEAD_short> · <branch> · <session-id 있으면>
### ✅ 구현/결정된 것
- ...  (근거: <hash>/<file>/<tests>)
### ⏭️ 다음 스텝
- [ ] ...  (왜 남음 / 필요한 것)
### 🔎 Resume anchors
- branch: <branch> · HEAD: <full hash> · 미커밋: <files or "none">
- 핵심 경로: ... · 관련: <plan/defer-task/링크>
```

## 4. Draft → Confirm → Write (절대 먼저 쓰지 않는다)
1. **터미널에 먼저 출력**: 확정한 `LAST..HEAD` 범위, 그리고 위 3섹션 항목 전체(draft).
2. **John의 확인을 받는다. 확인 전에는 파일에 아무것도 쓰지 않는다.**
3. 확인되면:
   - `docs/SESSION_LOG.md`가 **없으면** `Write`로 생성한다 — 헤더 + 앵커 + 첫 항목:
     ```
     # CoilForge Session Log

     `/checkpoint`가 쌓는 세션 인수인계 로그 (최신순). 각 항목 = 이번 세션 구현 내용 + 다음 스텝.
     제조 기록이 아니라 재개용 dev-log다.

     <!-- CHECKPOINTS (newest first) -->

     <첫 항목>
     ```
   - **있으면** `Edit`로 앵커 줄(`<!-- CHECKPOINTS (newest first) -->`) 바로 아래에 새 항목을 prepend.

## 5. (선택) 로그만 커밋 — 물어본 뒤에만
- "이 로그 항목을 지금 커밋할까요?"라고 **묻는다.** 예이면 **`docs/SESSION_LOG.md` 한 파일만**:
  `git add docs/SESSION_LOG.md` → `git commit -m "docs(session-log): checkpoint <date>"`.
- **`main`에는 커밋하지 않는다** (`git rev-parse --abbrev-ref HEAD`가 `main`이면 멈추고 알린다).
  `git add -A` 금지 — 로그 파일 외 스테이징 금지. 아니오면 워킹트리에만 두고 다음 커밋/`/ship`에 딸려가게 둔다.

## 6. 결과 요약 (3~5줄)
- 기록한 날짜 + `LAST..HEAD` 범위 · 로그 파일 경로
- ✅ 구현 항목 수 · ⏭️ 다음 스텝 수
- 커밋했으면 커밋 해시, 아니면 "미커밋 (다음 /ship에 포함)"
- git 범위 밖(대화에만 있는) 항목이 있으면 정직하게 한 줄
