"""
Google Docs 단락 JSON을 format_full values.json 으로 변환.

목표:
- 공문형 재작성 없이 원문 아젠다/보고 구조를 최대한 보존
- Google Docs 의 HEADING_1/2/3, 리스트 구조를 format_full 슬롯에 매핑

입력:
- codex Google Drive `_get_document_text` 응답 JSON

출력:
- public-doc-to-hwpx `format_full` 용 values.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


ROMANS = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ"]
CHAPTER_TITLE_SLOTS = [f"장{i:02d}_제목" for i in range(1, 7)]
BODY_SLOT_GROUPS = [
    ("본문_절_001", "본문_항목_001", "본문_세부_001", "본문_주석_001"),
    ("본문_절_002", "본문_항목_002", "본문_세부_002", "본문_주석_002"),
    ("본문_절_003", "본문_항목_003", "본문_세부_003", "본문_주석_003"),
    ("본문_절_004", "본문_항목_004", "본문_세부_004", "본문_주석_004"),
    ("본문_절_005", "본문_항목_005", "본문_세부_005", "본문_주석_005"),
    ("본문_절_006", "본문_항목_006", "본문_세부_006", "본문_주석_006"),
    ("본문_절_007", "본문_항목_007", "본문_세부_007", "본문_주석_007"),
    ("본문_절_008", "본문_항목_008", "본문_세부_008", "본문_주석_008"),
    ("본문_절_009", "본문_항목_009", "본문_세부_009", "본문_주석_009"),
    ("본문_절_010", "본문_항목_010", None, "본문_주석_010"),
    ("본문_절_011", "본문_항목_011", "본문_세부_010", "본문_주석_011"),
    ("본문_절_012", "본문_항목_012", "본문_세부_011", "본문_주석_012"),
]
TOC_CHAPTER_SLOTS = ["목차_항목_001", "목차_항목_003", "목차_항목_013",
                     "목차_항목_021", "목차_항목_033", "목차_항목_043"]
TOC_SUBSECTION_SLOTS_BY_CHAPTER = {
    2: ["목차_항목_005", "목차_항목_007", "목차_항목_009", "목차_항목_011"],
    3: ["목차_항목_015", "목차_항목_017", "목차_항목_019"],
    4: ["목차_항목_023", "목차_항목_025", "목차_항목_027", "목차_항목_029", "목차_항목_031"],
    5: ["목차_항목_035", "목차_항목_037", "목차_항목_039", "목차_항목_041"],
    6: ["목차_항목_045", "목차_항목_047", "목차_항목_049", "목차_항목_051"],
}
DATE_RE = re.compile(r"(\d{4}\.\s*\d{1,2}\.\s*\d{1,2})")


@dataclass
class Section:
    title: str
    bullets: list[str] = field(default_factory=list)


@dataclass
class Chapter:
    title: str
    bullets: list[str] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def strip_number_prefix(text: str) -> str:
    text = clean_text(text)
    return re.sub(r"^\d+\.\s*", "", text)


def split_label_value(text: str) -> tuple[str, str]:
    if ":" not in text:
        return clean_text(text), ""
    label, value = text.split(":", 1)
    return clean_text(label), clean_text(value)


def shorten_for_toc(text: str, limit: int = 28) -> str:
    text = clean_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def parse_doc_payload(payload: dict) -> tuple[str, str, str, str, list[Chapter]]:
    paragraphs = payload.get("paragraphs", [])

    pre_title: list[str] = []
    main_title = ""
    meta_line = ""
    chapters: list[Chapter] = []
    current_chapter: Chapter | None = None
    current_section: Section | None = None
    seen_h1 = False

    for para in paragraphs:
        text = clean_text(para.get("text", ""))
        if not text:
            continue
        style = para.get("namedStyleType", "NORMAL_TEXT")

        if style == "HEADING_1":
            main_title = text
            seen_h1 = True
            continue

        if not seen_h1:
            pre_title.append(text)
            continue

        if not meta_line and style == "NORMAL_TEXT" and not para.get("isListItem"):
            meta_line = text
            continue

        if style == "HEADING_2":
            current_chapter = Chapter(title=strip_number_prefix(text))
            chapters.append(current_chapter)
            current_section = None
            continue

        if style == "HEADING_3":
            if current_chapter is None:
                current_chapter = Chapter(title="기타")
                chapters.append(current_chapter)
            current_section = Section(title=clean_text(text))
            current_chapter.sections.append(current_section)
            continue

        if current_chapter is None:
            continue

        target = current_section.bullets if current_section else current_chapter.bullets
        target.append(text)

    pre_title_line = clean_text(" ".join(pre_title))
    full_title_parts = [part for part in [pre_title_line, main_title] if part]
    full_title = " ".join(full_title_parts).strip()

    org_line = meta_line
    date = ""
    match = DATE_RE.search(meta_line)
    if match:
        date = clean_text(match.group(1))
        org_line = clean_text(meta_line[: match.start()]).rstrip(" -")

    if not full_title:
        full_title = clean_text(payload.get("title", "제목 미상 문서"))

    return pre_title_line, main_title, org_line, date, chapters


def build_cover_values(pre_title: str, main_title: str, org_line: str, date: str) -> dict:
    subtitle = f"- {pre_title} -" if pre_title else ""
    return {
        "문서번호": "AGENDA-AUTO",
        "보존기간": "1년",
        "text_001": subtitle,
        "text_002": main_title or pre_title,
        "보고일": date or "",
        "기관명": org_line or "",
        "본부부서명": "",
    }


def build_toc_values(chapters: list[Chapter]) -> dict:
    values: dict[str, str] = {}
    for idx, chapter in enumerate(chapters[: len(ROMANS)]):
        values[TOC_CHAPTER_SLOTS[idx]] = f"{ROMANS[idx]}. {chapter.title}"

        subsection_slots = TOC_SUBSECTION_SLOTS_BY_CHAPTER.get(idx + 1, [])
        subsection_titles: list[str] = []
        if chapter.sections:
            subsection_titles = [section.title for section in chapter.sections]
        else:
            for bullet in chapter.bullets:
                label, value = split_label_value(bullet)
                subsection_titles.append(label if value else bullet)

        for sub_idx, slot in enumerate(subsection_slots):
            if sub_idx >= len(subsection_titles):
                break
            values[slot] = f"{sub_idx + 1}. {shorten_for_toc(subsection_titles[sub_idx])}"
    return values


def format_primary_item(text: str, direct_marker: bool) -> str:
    text = clean_text(text)
    return f"  ◦ {text}" if direct_marker else text


def format_detail(text: str) -> str:
    return f"   - {clean_text(text)}"


def format_note(texts: list[str]) -> str:
    joined = " / ".join(clean_text(text) for text in texts if clean_text(text))
    if not joined:
        return ""
    return f"       ※ {joined}"


def chapter_sections(chapter: Chapter) -> list[Section]:
    if chapter.sections:
        return chapter.sections
    return [Section(title=chapter.title, bullets=chapter.bullets)]


def build_body_values(chapters: list[Chapter]) -> dict:
    values: dict[str, str] = {}
    flat_sections: list[tuple[int, Section]] = []

    for idx, chapter in enumerate(chapters[: len(CHAPTER_TITLE_SLOTS)]):
        values[CHAPTER_TITLE_SLOTS[idx]] = f" {chapter.title}"
        for section in chapter_sections(chapter):
            flat_sections.append((idx, section))

    for slot_idx, (chapter_idx, section) in enumerate(flat_sections[: len(BODY_SLOT_GROUPS)]):
        title_slot, item_slot, detail_slot, note_slot = BODY_SLOT_GROUPS[slot_idx]
        values[title_slot] = f" □ {section.title}"

        bullets = [clean_text(b) for b in section.bullets if clean_text(b)]
        if not bullets:
            continue

        direct_marker = item_slot in {"본문_항목_010", "본문_항목_011", "본문_항목_012"}
        values[item_slot] = format_primary_item(bullets[0], direct_marker)

        if detail_slot and len(bullets) >= 2:
            values[detail_slot] = format_detail(bullets[1])

        overflow = bullets[2:] if detail_slot else bullets[1:]
        if note_slot and overflow:
            values[note_slot] = format_note(overflow)

    return values


def build_schedule_table(chapters: list[Chapter]) -> dict:
    values: dict[str, str] = {}
    overview = next((chapter for chapter in chapters if "미팅 개요" in chapter.title), None)
    if not overview or not overview.bullets:
        return values

    pairs = [split_label_value(bullet) for bullet in overview.bullets]
    cleaned_pairs = [(label, value) for label, value in pairs if label]
    rows = cleaned_pairs[:4]
    if not rows:
        return values

    cells = []
    for label, value in rows:
        cells.extend([label, value or "-", ""])
    while len(cells) < 12:
        cells.append("")

    for idx, text in enumerate(cells[:12], start=1):
        values[f"일정표_셀_{idx:03d}"] = text
    return values


def build_reference_values(chapters: list[Chapter]) -> dict:
    refs: list[str] = []
    for chapter in chapters:
        for section in chapter.sections:
            refs.append(section.title)
    return {f"참고자료_{idx}": f"{idx}. {title}" for idx, title in enumerate(refs[:3], start=1)}


def build_values(payload: dict) -> dict:
    pre_title, main_title, org_line, date, chapters = parse_doc_payload(payload)
    values = {}
    values.update(build_cover_values(pre_title, main_title, org_line, date))
    values.update(build_toc_values(chapters))
    values.update(build_reference_values(chapters))
    values.update(build_body_values(chapters))
    values.update(build_schedule_table(chapters))
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Docs JSON -> format_full values.json")
    parser.add_argument("--input", required=True, help="`_get_document_text` 응답 JSON 경로")
    parser.add_argument("--output", required=True, help="출력 values.json 경로")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    values = build_values(payload)
    Path(args.output).write_text(
        json.dumps(values, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
