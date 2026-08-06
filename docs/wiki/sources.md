# CoilForge 위키 — 소스 레지스트리 (계층 1)

CoilForge의 엔지니어링 지식이 파생되는 원본 그라운드-트루스 문서들. 이들은 **의도적으로 리포지토리
밖**에 있다(`.gitignore`가 `*.pdf` / `*.xlsx` / `Case/` / 원시 JSON을 차단) — 그래서 이 페이지는 파일이
아니라 **포인터 레지스트리**다. 위키 주장은 이들을 `evidence_ref` 토큰으로 인용하고, 원시 값은 옮겨
적어 정제된 사내 테이블(`coil_header_rules.yaml` R-074/R-077/R-078 및
`docs/rules/coil_header_rule_extraction.md`)에만 존재한다.

> `AGENTS.md` 기준: 원본과 정규화된 해석은 분리 유지. 위키는 이 원본들이 별도로 제공되지 않는 한
> 이들로부터 스스로를 재생성할 수 없다.

| 소스 | `evidence_ref` 토큰 | 상태 | 비고 |
| --- | --- | --- | --- |
| **EZ Coil Selection SOP** `2024018 Rev I` (2026-02-10) | `SOP §…`, `SOP 2024018 §… SPECIAL CASE …`, `SOP-OLE1..5` | 외부 / gitignored | 1차 엔지니어링 소스. `§` 섹션: `§GEN`, `§DX-TNVH`, `§DX-VP`, `§HGRH-TNVH`, `§HGRH-VP`, `§CWC/HWC`. `SOP-OLE1..5` = 내장 케이싱-깊이 테이블. Terra-V 규칙은 이 SPECIAL CASE 섹션을 인용. Rev H(John Kim, 2025-12)는 R-080/R-081이 인용. |
| **Coil Checklist Template** `.xlsx` | `CHK <Sheet>!<Cell>` (예: `CHK DX!C24`) | 외부 / gitignored | 시트: `CWC`, `HWC`, `DX`, `HGRH`, `Units`, `Install \| Drain Pan Width`. `Units` 시트 → R-074 케이싱 dim; WIDTH/HEIGHT FIT 공식 → R-078; 드레인-팬 시트 → R-077. 하위 dim은 Excel 공식(체크리스트 오토필 기능 참고). |
| **as-built EZ Coil / CoilMaster 도면** | `EZC-####` (예: `EZC-0001`), `FEED-*` | 외부 / gitignored (`Case/feed/`) | 리댁션·슬롯화된 `template.svg` 파일을 시드한 레퍼런스 도면. 슬롯화된 템플릿만 커밋됨. DX 지오메트리의 도면 프로비넌스로 인용(`SOP-OLE`, as-built refs). |
| **Oxygen8 Final Submittal PDF** (프로젝트별) | `Submittal #<project>` (예: `Submittal #2910`) | 외부 / gitignored | 커버 스케줄 + 코일 상세 + as-built 도면이 한 문서에. 커버의 라인 아이템이 프로젝트 단위 옵션을 진술 — 예: `#2910` p.2/p.11 `660024-001 HGBP VALVE - DANFOSS AXV-H and hot-gas bypass stub-out on coils adder` → `[[hot-gas-bypass]]`의 패키지 감지 근거. |
| **CoilMaster QUOTATION PDF** (Accessory Order Forms) | `Coilmaster Quote <number>` (예: `Coilmaster Quote 183347-002`) | 외부 / gitignored | p.1 견적, p.2 = 실제 코일 도면(템플릿 시드와 동일 포맷). `[[hot-gas-bypass]]` 참조 대조에 사용: `#2910` LH `DXM05C13-12.00x15.00L`, `#2720` RH `DXM05C14-12.00x15.00R` — 둘 다 `(1 ASC)` / `HDx1`. **주의:** EZ-Coil 5.5.0.0은 모델 문자열을 `DXM05C14-…`로 쓰고 구 포맷은 `DX-F-F-05-14-…` — 같은 코일이어도 문자열이 다르므로 Coil ID로 대조할 것. |
| **날짜 있는 엔지니어링 결정** | `John YYYY-MM-DD:` | 사내 (YAML에 내장) | 문서가 아니라 — `evidence_refs` 안에 인라인으로 기록된 John의 엔지니어링 판단. 사실상 확정의 체인지로그(예: `John 2026-06-28 (SOP-confirmed)`가 Terra-V 스페셜을 LOW→HIGH로 승격). 전부 사내·정제됨. |

## 사내 정제 파생물 (자유롭게 인용 가능)
- `src/coilforge/rules/coil_header_rules.yaml` — 87-규칙 테이블; R-074/R-077/R-078이 옮겨 적은
  케이싱 / 드레인-팬 / 핏 테이블을 담음.
- `docs/rules/coil_header_rule_extraction.md` — 사람이 읽는 규칙→근거 사전.
- `examples/sanitized/`, `examples/mapping_lab/case_00*/` — 규칙-형태 검증만을 위한 목(mock,
  엔지니어 입력) 케이스; 명시적으로 원시 고객 데이터가 *아님*.
