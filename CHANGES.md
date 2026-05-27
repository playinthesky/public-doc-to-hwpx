# 변경 이력

> 상세 내용은 `SKILL.md` 안의 변경이력 표를 참고. 이 파일은 사용자 친화적 요약.

## 최신 버전: v3.6.13 (2026-05-27)

### v3.6.13 — Agenda mode 표지/목차 정리

**문제**: `format_full`을 아젠다/회의안으로 쓸 때
- 표지 결재표를 제거하면 제목까지 사라질 수 있었고
- 회사명이 두 번 들어가거나 너무 크게 강조되었고
- 빈 목차 줄/탭-only 단락 때문에 페이지번호와 점선이 어색하게 보였음
- 일부 본문은 lineseg 캐시 때문에 자간이 비정상적으로 붙어 보였음

**해결**:
- `scripts/tidy_full_agenda.py` 신규 후처리 강화
  - 결재표 제거
  - `결재제목` 셀 안 부제/제목 복원
  - 회사명 + 날짜를 일반 메타 한 줄로 재배치
  - 빈 목차 행 제거
  - 탭만 남은 목차 단락 제거
  - agenda 문단 `linesegarray` 제거로 자간 재계산 유도
- `scripts/build_full.py --agenda-mode` 추가
- `scripts/simulate_pages.py` 수정: 제목 없는 목차 줄에는 페이지번호 미배정
- `scripts/fix_toc_dots.py` 조정: 탭 폭 `42000 -> 39000`

즉, 이제 `format_full`은 **공문 잔재 없이 회의안/아젠다 표지 + 목차** 쪽으로
한 단계 더 안정화되었습니다.

## 이전 최신 버전: v3.6.12 (2026-05-27)
### v3.6.12 — Google Docs 아젠다/보고 구조 보존 매퍼

**문제**: Google Docs 원문이 `HEADING_2/3 + 리스트` 구조인데도 공문형 values로
억지 재작성되면서, 미팅 아젠다·내부 회의안이 시행문처럼 변형됨.

**해결**: `scripts/map_google_doc_to_full_values.py` 신규.
- Codex Google Drive `_get_document_text` 응답 JSON을 직접 입력으로 사용
- `HEADING_1` → 표지 제목
- `HEADING_2` → 장(章) / 본문 절
- `HEADING_3` → 하위 섹션
- 리스트 항목 → 본문 항목·세부·주석 / 일정표 셀로 매핑

**회귀 예시 추가**:
- `examples/google_doc_jejuda_agenda.json`
- `examples/example_values_full_jejuda_agenda.json`

즉, 공문이 아닌 **아젠다·내부 보고용 HWPX** 는 이제 공문 빌더가 아니라
`format_full` 기반 구조 보존 매퍼로 시작하는 것이 기본 경로입니다.

## 이전 최신 버전: v3.6.11 (2026-05-13)

### v3.6.11 — 1p 보고서 마커 자동 정규화

**문제**: 1p 양식의 ◦ 위계(paraPr=31) 는 자동 마커 없는데 사용자가 ◦ 미입력 → 누락.
- 위계(paraPr=27) 는 자동 BULLET 마커 있는데 사용자가 "- " 직접 입력 → 중복.

**해결**: `scripts/normalize_1p_markers.py` 신규 — fill_skeleton 이 1p 양식 자동
감지 시 placeholder 별 마커 규칙 적용. 사용자가 어떤 형식으로 입력하든 양식과
충돌 없는 결과 자동 생성.

| placeholder | 처리 |
|---|---|
| ◦ 자리 (12개) | 사용자 입력 앞에 `◦ ` 자동 추가, 기존 변형 마커(○/◇)는 표준 `◦`로 치환 |
| - 자리 (6개) | 사용자 입력 시작의 `-/–/−` 자동 제거 |
| * 자리 | 사용자 입력 앞에 `* ` 자동 추가 |

**부가 개선**: 변경 이력 파일 자체의 갱신 누락 방지를 위해 파일명을
`CHANGES_v[N].md` → `CHANGES.md` 로 안정화 + 버전 업데이트 체크리스트
(`RELEASE_CHECKLIST.md` 신규) 추가.

## 사용법 변경 (v3.6.10 이후)

공문 빌드 시 `examples/example_values_gongmun.json` 참고:

```json
{
  "수신자": "내부 임직원",
  "text_005": "(경유)",
  "text_006": "제목",
  "본문":      ["1. ...", "2. ...", "3. ...", "4. ..."],
  "본문_가나": ["가. ...", "나. ...", "다. ..."],
  "본문_1)":  ["1) ...", "2) ..."],
  "본문_①":   ["① ...", "② ..."],
  "붙임":      ["붙임 1. ...", "2. ...", "3. ..."]
}
```

- 각 위계 배열의 항목 수에 따라 단락이 자동 확장
- 빈 배열 또는 미입력 시 해당 위계 단락 자체가 출력에서 사라짐
- 표 구조(헤더/발신부) 단락은 hp:tbl 보존 예외로 무조건 유지
- `수신자` 키만 입력하면 "수신" 라벨은 자동 부여

1p 빌드 시 `examples/example_values_1p.json` 참고 — 마커 입력은 자유롭게.

## 누적 변경표 (v3.6.x)

| 버전 | 변경 |
|---|---|
| v3.6.0 | 표지·공문 제목 자간 압축 자동 해소 (`wrap_long_titles.py`) |
| v3.6.1 | 풀버전 목차 점선 깨짐 자동 해소 (단계 A: width 통일) |
| v3.6.2 | 목차 점선 width 미세 조정 45000 → 42000 |
| v3.6.3 | 공문 본문 자간 압축 자동 해소 (`fix_gongmun_body.py`) |
| v3.6.4 | 풀버전 안 열림 + 공문 단락 합쳐짐 핫픽스 |
| v3.6.5 | 목차 점선 lineseg 캐시 무효화 (단계 B) |
| v3.6.6 | Skeleton 양식 결함 자동 보정 (Ⅳ장 들여쓰기) + 공문 양식 의도 명세 확정 |
| v3.6.7 | 공문 본문 단락 동적 확장 — 양식 한계 돌파 |
| v3.6.8 | 본문 모든 위계 동적 확장 + 빈 placeholder 단락 자동 제거 |
| v3.6.9 | 위계별 들여쓰기 통일 (양식 슬롯 ↔ 동적 단락) |
| v3.6.10 | 수신자 라벨/입력 분리 양식 결함 보정 + 들여쓰기 미세 차이 해결 (raw XML `<hp:fwSpace/>`) |
| **v3.6.11** | **1p 보고서 마커 자동 정규화 + 변경 이력 갱신 프로세스 정착** |

상세 내용은 `SKILL.md` 변경이력 표 참고.

## 디렉토리 구조

```
public-doc-to-hwpx/
├── SKILL.md                  메인 가이드 + 변경이력 표 + Critical Rules 23개
├── CHANGES.md                ← 이 파일 (사용자용 요약)
├── RELEASE_CHECKLIST.md      ★ v3.6.11 신규 — 버전 업데이트 시 갱신 파일 체크리스트
├── README.md
├── LICENSE
├── PUSH_GUIDE.md             GitHub 푸시용 일회성 가이드
├── scripts/                  빌더 스크립트
├── templates/                4개 양식 빈 골격
├── references/               양식별 상세 가이드
└── examples/                 예시 values.json
    ├── example_values_gongmun.json   시행문 (모든 위계 활용)
    ├── example_values_full.json      풀버전 보고서 (127슬롯)
    └── example_values_1p.json        ★ v3.6.11 신규 — 1p 보고서
```
