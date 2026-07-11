# CoilForge 하네스 배치 — R12 운영성

PO Release Case의 병행 배치 일부. R1(브레인 라이브 릴리즈)이 별도 세션에서 진행 중이며, 이 작업은
**CoilForge 레포 안에서 끝나 브레인/R1과 무충돌**이다.

계획 근거: `..\PO_Release_Case\.claude\plans\r1-roadmap-md-radiant-storm.md` (CoilForge R12 섹션).

## 부트스트랩된 하네스

`scripts/execute.py`는 PO Release Case에서 이식한 하네스다. 이식 조정:
- 가드레일 주입 = **`CLAUDE.md` + `AGENTS.md`** (docs/는 파일이 많아 glob 제외; 필요 doc은 step이 개별 지시).

## Phase

| phase | 항목 | 내용 |
|---|---|---|
| `0-harness-smoke` | R12a | `run_server_dev.bat`(--reload) 추가 — 하네스 스모크 겸(기본 `run_server.bat`은 불변) |
| `1-r12-operability` | R12b·R12c | step0 = prefill **sha1 캐시**⭐(30~60초 분석 캐시, 오염방지 규칙) · step1 = `X-CoilForge-Identity` 헤더→마일스톤 저널 |

## 실행 (사용자 트리거)

```bash
cd C:\Users\JohnKim\Desktop\Bins\Projects\CoilForge
git checkout main          # 배치 베이스(현재 claude/ccsi-autofill이면 전환)
python scripts/execute.py 0-harness-smoke      # feat-0-harness-smoke 브랜치 자동 생성
git checkout main
python scripts/execute.py 1-r12-operability    # feat-1-r12-operability
```

`execute.py`가 `feat-{phase}` 브랜치 생성/checkout + 가드레일 주입 + 2단계 커밋 + 자가교정(3회)을 처리.
AC는 각 step의 `python -m pytest -q`(기존 78파일 무회귀 포함). 별도 레포라 `main`에서 독립 병합.

## 하드 경계 (AGENTS.md/CLAUDE.md)

raw JSON/PDF 수정 금지 · engineering 값 발명 금지 · inferred 매핑 review-required · production export 불가.
