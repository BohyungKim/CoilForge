# CoilForge 엔지니어링 위키 — 스키마

이 디렉터리는 CoilForge 엔지니어링 도메인을 위한 **LLM이 유지·관리하는 지식 위키**로, Andrej Karpathy의
["LLM Wiki" 패턴](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)을 따른다:
서로 링크된 마크다운 페이지 묶음을 LLM이 *유지*하고(북키핑·교차참조·정합성), John이 *큐레이션*한다
(방향 설정·판단·사인오프).

이것은 실행 가능한 규칙 테이블(`src/coilforge/rules/coil_header_rules.yaml`) **위에 얹히는 사람이 읽는
합성 계층**이다. YAML은 *엔진*에게 무엇을 계산할지 알려주고, 이 위키는 *사람*에게 코일 패밀리가 무엇인지,
왜 그 규칙이 존재하는지, 무엇이 아직 남았는지를 알려준다.

> **이 위키는 리뷰 보조물이지 승인이 아니다.** `[CONFIRMED]` 배지는 엔지니어링이 사실을 사인오프했다는
> 뜻이지, 도면이 릴리스됐다는 뜻이 절대 아니다. `AGENTS.md`의 모든 CoilForge 하드 바운더리가 여기에도
> 그대로 적용된다 — 무엇보다 **엔지니어링 값을 절대 지어내지 않는다.**

---

## 세 계층 (왜 파일 복사가 아니라 포인터로 두는가)

| 계층 | 위치 | 규칙 |
| --- | --- | --- |
| **L1 — 원본 소스** | `[[sources]]` (파일이 아니라 *레지스트리*) | SOP `.docx`, 체크리스트 `.xlsx`, as-built PDF는 설계상 `.gitignore` 대상이다. 위키는 `evidence_ref` 토큰으로 이들을 **인용**할 뿐, 정제되지 않은 원시 값을 복사하지 않는다. 원본과 해석은 분리 유지(`AGENTS.md`). |
| **L2 — 위키** | 여기의 나머지 모든 `*.md` + `[[index]]` + `[[log]]` | LLM이 생성한 합성물. 엔티티 / 개념 / 합성 페이지, 모두 상호 링크. |
| **L3 — 스키마** | 이 파일 + `/wiki-ingest`, `/wiki-query`, `/wiki-lint` | 규칙집 + 운영 커맨드. |

---

## 페이지 유형

- **엔티티 — 카테고리** (`categories/*.md`) — 코일 카테고리 하나: `dx`, `hgrh`, `hwc`, `cwc`.
  무엇인지, 태그 접두사, 헤더 수, 핵심 규칙, 핏 거동.
- **엔티티 — 제품 패밀리** (`products/*.md`) — `nova`, `ventum-h`, `ventum-plus`,
  `terra-h`, `terra-v`. 무엇인지, 사이즈(R-076), 케이싱 출처(R-074), 라우팅/신뢰도, 남은 값.
- **개념 / 합성** (`concepts/*.md`) — 가로지르는 개념: `confidence-gate`,
  `taxonomy`, `multi-header-geometry`, `mechanical-fit`.
- **레지스트리** (`sources.md`) — L1 포인터 목록.
- **원장** (`open-questions.md`) — John에게 남은 항목의 라이브 목록, `docs/MVP_FINALIZATION_CHECKLIST.md`와
  대조/조정.
- **카탈로그 / 로그** (`index.md`, `log.md`) — 두 개의 유지 파일.

시드 상태(2026-07-04): *엔티티/개념* 유형별로 각 한 페이지씩을 워크드 예시로 시드했다
(`categories/hgrh`, `products/terra-v`, `concepts/confidence-gate`). 나머지는 `/wiki-ingest`로
자라난다. 아직 시드 안 됐지만 *참조되는* 페이지는 `[[index]]`에 스텁으로 나열한다.

---

## 규약 (핵심 규칙)

### 1. 자명하지 않은 모든 주장에는 **배지** + **인용**이 붙는다

배지는 CoilForge의 신뢰도 게이트를 그대로 반영한다(`[[confidence-gate]]` 참고):

- **`[CONFIRMED]`** — 엔지니어링/John 사인오프. 근거를 인용: 날짜 있는 `John YYYY-MM-DD:` ref,
  `CHK Sheet!Cell`, `SOP §section`, 또는 `EZC-####` as-built.
- **`[REVIEW-REQUIRED]`** — 추론 / 단일 출처 / MEDIUM. 드러내되 확정으로 취급하지 않는다. 명시적으로
  사인오프되지 않은 모든 것의 **기본값**이다.
- **`[BLOCKED]`** — 엔진에서 `LOW`/`CONFLICT`인 값, `blocked_reason`과 함께.

인용 없는 주장은 결함이다 — 인용하거나 `[REVIEW-REQUIRED]`로 표시하라.

### 2. 인용 문법 = 엔진의 `evidence_ref` 어휘(그대로)

YAML이 쓰는 토큰을 정확히 그대로 써서, 주장이 그 규칙까지 추적되게 한다:
`SOP §DX-TNVH` · `SOP 2024018 §HGRH-TNVH SPECIAL CASE …` · `CHK DX!C24` · `SOP-OLE1..5` ·
`EZC-0001` · `John 2026-06-28 (SOP-confirmed)`. 특정 규칙에서 온 주장이면 규칙 ID(`R-074`)를 함께
적어 `/wiki-lint`이 YAML과 대조할 수 있게 한다.

### 3. `[[wiki-links]]`로 교차링크

메모리 노트와 같은 문법: `[[terra-v]]`, `[[confidence-gate]]` (파일명 stem, `.md` 없음, 경로 없음).
링크는 아낌없이 — 아직 안 쓴 페이지로의 링크는 오류가 아니라 *스텁 마커*다. `[[index]]`의 "스텁"에 기록한다.

### 4. 지어내지 않는다; 빈칸을 표시한다

위키가 어떤 값을 모르면 `미확인` 또는 `[REVIEW-REQUIRED] — owed by John`이라 쓰고 `[[open-questions]]`에
올린다. 사내 소스에 없는 엔지니어링 숫자를 절대 채우지 않는다. (`AGENTS.md`: *엔지니어링 값을 지어내지 않는다*.)

### 5. 커밋되는 페이지는 정제(sanitized)돼 있다

규칙 번호, 공식, 분류, 이미 사내에 있는 케이싱 테이블만 여기 속한다 — 원시 고객 PDF/xlsx 값이나 고객
식별 데이터는 절대 안 된다. 고객/견적별 페이지는 별도 게이트를 거치는 후속 단계로 미룬다.

---

## 세 가지 연산 (전체 절차는 슬래시 커맨드에)

- **`/wiki-ingest <source>`** — 새 소스(제출물 / SOP 섹션 / 세션 발견 / 확정된 결정)를 읽고, 사실을
  추출하고, 페이지 + `[[index]]` + `[[log]]` 편집을 제안한 뒤, **John의 확인을 받고 나서 쓴다.** 소스는
  절대 수정하지 않는다.
- **`/wiki-query <question>`** — 위키를 검색해 인용과 함께 답하고, 가치 있는 답은 새 페이지로 되-저장할지
  제안한다. 다루지 않는 부분은 `미확인`.
- **`/wiki-lint`** — 건강 점검: 위키↔코드 드리프트, 페이지 간 모순, 낡은 `[REVIEW-REQUIRED]`, 고아
  페이지, `[[open-questions]]` ⇄ MVP 체크리스트 드리프트, index/log 무결성. 보고만 하고, 수정은
  Draft → Confirm → Write로만.

## 리포지토리의 나머지와의 관계 (중복 금지)

- **메모리 노트** (`~/.claude/.../memory/`) = *우리가 무엇을 왜 했는가* (협업/결정 로그).
  이 위키 = *도메인에 대해 무엇이 참인가* (레퍼런스). 교차링크하되 합치지 않는다.
- **`docs/rules/coil_header_rule_extraction.md`** = 셀 단위 규칙→근거 사전. 위키는 **여기로 링크**할 뿐,
  이를 다시 옮겨 적지 않는다.
- **`docs/SESSION_LOG.md`** = dev 인수인계. `[[log]]` = 지식-연산 로그. 서로 다른 로그다.
- **`docs/MVP_FINALIZATION_CHECKLIST.md`** = 권위 있는 남은-작업 원장. `[[open-questions]]`는 이와
  대조/조정할 뿐, 대체하지 않는다.
