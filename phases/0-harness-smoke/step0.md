# Step 0: reload-dev-launcher (R12a)

PO Release Case 백로그 **R12a** — 개발 중 `src/` 편집 후 매번 서버를 수동 재시작해야 하는 마찰
제거. uvicorn `--reload` 개발 런처를 제공한다. 이 step은 **부트스트랩된 하네스가 CoilForge에서
end-to-end로 도는지 실증하는 스모크**를 겸한다(작고 안전한 실변경).

## 읽어야 할 파일

- `CLAUDE.md` — "Commands" 섹션(약 L22-35): `run_server.bat`은 **의도적으로 `--reload` 없이** 실행
  한다는 설명과, 수동 auto-reload 커맨드(`python -m uvicorn coilforge.web_app:app --app-dir src --reload`).
- `run_server.bat` — 현재 런처(L22: `--reload` 없음).
- `AGENTS.md` — 프로젝트 하드 경계.

## 작업

**신규 개발 런처** `run_server_dev.bat` 를 추가한다. `run_server.bat`을 미러하되 uvicorn을 **`--reload`
포함**으로 실행한다(= CLAUDE.md L34의 수동 커맨드를 더블클릭 가능한 .bat로).

규칙:
- **`run_server.bat`(기본 런처)의 동작은 바꾸지 마라.** 이유: CLAUDE.md가 기본 non-reload를
  의도적으로 문서화했다(브라우저의 `pdfCoilPages` 클라이언트 캐시 때문에 리로드가 오해를 부를 수 있음).
  `--reload`는 **별도 dev 런처**로만 제공한다.
- 새 .bat 주석에 "개발용: src 편집 시 자동 리로드. pdfCoilPages는 클라이언트 캐시라 브라우저에서
  PDF 재분석 필요"를 한 줄 남긴다(CLAUDE.md 취지 반영).

## Acceptance Criteria

```bash
python -m pytest -q                          # 기존 78파일 무회귀 (로직 무변경)
grep -q -- "--reload" run_server_dev.bat     # 새 dev 런처에 --reload 존재
```

## 검증 절차

1. 위 AC 실행.
2. `run_server.bat`이 변경되지 않았는지 확인(기본 런처 보존).
3. `phases/0-harness-smoke/index.json` step 0 갱신(통과→completed+summary / 3회 실패→error).

## 금지사항

- `run_server.bat` 기본 동작 변경 금지. 이유: 의도된 non-reload 기본값(CLAUDE.md).
- 제품 코드(`src/coilforge/**`)를 건드리지 마라. 이 step은 런처 파일만 추가한다.
- raw JSON/PDF 수정·engineering 값 발명 금지(AGENTS.md/CLAUDE.md 하드룰).
