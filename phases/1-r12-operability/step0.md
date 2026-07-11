# Step 0: prefill-sha1-cache (R12b) ⭐

PO Release Case 백로그 **R12b** — 케이스 딥링크/재분석 흐름에서 **같은 submittal PDF를 반복
분석**하면서 매번 30~60초 OCR/분석을 재실행한다. `sha1(pdf_bytes)` 기반 메모이즈로 반복 분석을
캐시 히트로 만든다. **이 phase의 핵심 가치.**

## 읽어야 할 파일

- `src/coilforge/workflows/submittal_to_drawing.py` — `run_pdf_to_drawing_workflow`(L269) **정의 전체**.
  시그니처: `(pdf_bytes, *, source_id, source_filename, cover_page_hint, preview_defaults, title_block)`.
  내부는 `extract_coil_candidate_from_pdf_bytes(...)`(L278~, 여기가 비싼 OCR/분석) → 후처리.
- `src/coilforge/web_app.py` — 이 함수를 부르는 7+ 엔드포인트(L296·340·392·454·581·693·814).
  특히 케이스 딥링크 `case-to-drawing`(L375-418, 주석 L390 "analysis blocks 30-60s")와
  재분석 재-POST 흐름(`case_submittal_pdf` L421-425 주석: checklist/quote/cover-page 재분석이 원본 bytes 재전송).
- `src/coilforge/phase2a/snapshot.py` L20 — `hashlib.sha256(...)[:12]` **해시 선례**(패턴 재사용).
- `AGENTS.md` — 하드 경계.

## 작업

`run_pdf_to_drawing_workflow` 결과를 **입력에 대해 메모이즈**한다(모듈 레벨 바운디드 캐시).

**핵심 규칙(하드) — 캐시 정확성:**
- 결과는 `pdf_bytes` **뿐 아니라** `source_id`·`source_filename`·`cover_page_hint`·`preview_defaults`·
  `title_block` **전부에 의존**한다(source_id 등은 결과에 임베드됨). 따라서 캐시 키는
  **`sha1(pdf_bytes)` + 나머지 인자 전체의 안정 해시**여야 한다.
  **순수 `sha1(pdf_bytes)`만 키로 쓰지 마라. 이유: 같은 PDF라도 호출부마다 source_id가 달라,
  캐시가 엉뚱한 source_id가 박힌 결과를 돌려준다(조용한 오염).**
- (선택 최적화) 비싼 부분은 OCR(`extract_coil_candidate_from_pdf_bytes`)이다. 분석부만
  `(sha1(pdf_bytes), cover_page_hint)`로 캐시하고 메타(source_id 등)는 매 호출 재적용하면 더 큰
  히트율을 얻는다 — 단 분석/메타 분리가 확실할 때만. 자신 없으면 위의 **전체-입력 키**(안전)로 가라.
- 캐시는 **바운디드**(예: `functools.lru_cache` 또는 크기상한 dict)로 무한 증가를 막아라.
- 반환값은 호출자가 변형할 수 있으니, 캐시가 공유 가변객체를 노출해 오염되지 않도록 하라
  (깊은 복사 반환 또는 불변 취급 — 기존 코드의 소비 방식을 보고 판단).

## Acceptance Criteria

```bash
python -m pytest -q
```

신규 테스트:
- 비싼 내부 호출(`extract_coil_candidate_from_pdf_bytes` 또는 그 하위)을 monkeypatch로 카운트 →
  **동일 입력 2회 호출 시 실제 분석은 1회**(2번째는 캐시 히트)임을 단언.
- **오염 방지**: 같은 `pdf_bytes`, 다른 `source_id` 2회 → 각기 올바른 source_id 결과 반환(캐시 교차오염 없음).

## 검증 절차

1. 위 AC 실행(기존 78파일 무회귀 포함).
2. 하드룰 체크: 캐시 키에 전체 입력 반영? 캐시 바운디드? raw PDF/JSON 무변경?
3. `phases/1-r12-operability/index.json` step 0 갱신(통과→completed+summary / 3회 실패→error).

## 금지사항

- 순수 `sha1(pdf_bytes)`만으로 캐싱하지 마라. 이유: source_id 오염.
- raw submittal PDF/JSON을 수정하거나 engineering 값을 발명하지 마라(AGENTS.md 하드룰).
- Brain 레포를 건드리지 마라. 기존 테스트를 깨뜨리지 마라.
