# Step 1: identity-header (R12c)

PO Release Case 백로그 **R12c** — 오늘 CoilForge 요청 헤더 `x-coilforge-*`는 전부 **content-hint**
(source-id/filename/product/size/cover-page)뿐, **누가 개시했는지(요청 identity)**는 기록되지 않는다.
`X-CoilForge-Identity` 헤더를 받아 마일스톤 저널에 남겨 추적성을 준다.

## 읽어야 할 파일

먼저 이전 step(sha1 캐시)에서 바뀐 `submittal_to_drawing.py`/`web_app.py`를 읽고 일관성을 유지하라.

- `src/coilforge/web_app.py`:
  - `_journal_milestone`(L51) — 마일스톤 저널 기록 함수(여기에 identity를 실어야 함).
  - 기존 헤더 읽기 패턴: `x-coilforge-source-id`(L298·325·342·456·695), `x-coilforge-filename`,
    `x-coilforge-product`(L473), `x-coilforge-cover-page`(L85). **이 패턴을 그대로 미러**.
  - `_journal_milestone` 호출부들(예: `case-to-drawing` L415).
- `src/coilforge/brain_case.py` — `case_identity()`(프로젝트 식별). **이것과 혼동 금지**: 요청 identity(개시자)와 프로젝트 identity는 다른 개념.
- `AGENTS.md` — 하드 경계.

## 작업

`X-CoilForge-Identity` 요청 헤더(개시자/호출 출처 문자열)를 읽어 `_journal_milestone`(L51)에 전달,
마일스톤 저널 레코드에 `identity`(또는 유사 키)로 남긴다.

규칙:
- 기존 `request.headers.get("x-coilforge-...")` 패턴을 그대로 따른다(대소문자·기본값 처리 일관).
- 헤더 미제공 시 안전한 기본값(예: `None`/`"unknown"`)으로 degrade — 요청을 실패시키지 마라.
- `_journal_milestone` 시그니처에 identity를 additive로 추가(기존 호출부가 깨지지 않게 기본값).
- `brain_case.case_identity()`(프로젝트 번호/이름)와 섞지 마라. 이건 **요청 개시자** 식별이다.

## Acceptance Criteria

```bash
python -m pytest -q
```

신규 테스트:
- `X-CoilForge-Identity`를 실은 요청 → 기록된 마일스톤 저널에 그 identity가 포함됨을 단언
  (기존 저널/마일스톤 테스트 패턴 재사용; FastAPI 테스트는 `pytest.importorskip("fastapi")` 관례 준수).
- 헤더 미제공 요청도 정상 처리(크래시 없음)됨을 단언.

## 검증 절차

1. 위 AC 실행(기존 78파일 무회귀 포함).
2. 하드룰 체크: 프로젝트 identity와 혼동 없음? 헤더 부재 시 degrade? raw JSON/PDF 무변경?
3. `phases/1-r12-operability/index.json` step 1 갱신(통과→completed+summary / 3회 실패→error).

## 금지사항

- 요청 identity를 `brain_case.case_identity()`(프로젝트 식별)와 섞지 마라. 이유: 다른 개념.
- 헤더 부재를 에러로 만들지 마라. 이유: 기존 호출부 회귀.
- raw JSON/PDF 수정·engineering 값 발명·Brain 레포 편집 금지.
