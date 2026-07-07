# CoilForge 위키 — 인덱스

콘텐츠 카탈로그. 페이지당 한 줄, 유형별 그룹. 상태(Status)는 개별 주장이 아니라 그 페이지의 전반적
신뢰도 태세다. 스키마는 `[[WIKI]]` 참고. `/wiki-ingest`가 유지하고 `/wiki-lint`가 감사한다.

## 메타
- [[WIKI]] — 스키마 / 규칙집: 계층, 페이지 유형, 배지 + 인용 규약.
- [[log]] — append-only 연산 로그 (ingest / query / lint).
- [[sources]] — L1 원본 소스 레지스트리 (외부·gitignored — 인용하되 복사하지 않음).
- [[open-questions]] — John에게 남은 항목 라이브 원장, `docs/MVP_FINALIZATION_CHECKLIST.md`와 대조.

## 카테고리 (코일 타입)
- [[hgrh]] `[CONFIRMED core]` — Hot-Gas Reheat: 태그 별칭, 1–4 HD, 서플라이/리턴 지오메트리, 카퍼 스트랩.

## 제품 (패밀리)
- [[terra-v]] `[REVIEW-REQUIRED core]` — Terra Vertical: 13 사이즈, 전용 (키 큰) 케이싱, SOP-confirmed 스페셜.
- [[ventum-plus]] `[CONFIRMED core]` — Ventum Plus: 자체 상수 세트, distributor orientation UP (R-032), 11개 전용 템플릿 시드 (product_family fork, 2026-07-06).

## 개념
- [[confidence-gate]] `[CONFIRMED]` — HIGH→values / MEDIUM→suggestions / LOW·CONFLICT→blocked; 중심 불변식.

## 스텁 (참조되지만 아직 시드 안 됨 — `/wiki-ingest`로 자라남)
- `[[dx]]`, `[[hwc]]`, `[[cwc]]` — 나머지 세 카테고리.
- `[[nova]]`, `[[ventum-h]]`, `[[terra-h]]` — 나머지 세 패밀리.
- `[[taxonomy]]` — 4단계 결정 트리 (카테고리 → 패밀리 → 헤더 수 → 도면).
- `[[multi-header-geometry]]` — circuits/feeds → I2/S2/R2… (R-022/R-034/R-048/R-052/R-072/R-073).
- `[[mechanical-fit]]` — WIDTH/HEIGHT/INSTALL 핏 (R-077/R-078, `compatibility/mechanical_fit.py`).
