"""
tidy_full_agenda.py

format_full 결과물을 아젠다/회의안 용도로 다듬는 후처리.

- 표지의 결재/문서메타 대형 표 제거
- 제거 과정에서 결재제목 셀 안의 부제/제목은 표 밖 단락으로 재구성
- 회사명은 한 번만, 작은 줄로 제목 아래 배치
- 목차의 빈 행(제목 없는 1x3 테이블) 제거
"""

import argparse
import re
import shutil
import tempfile
import zipfile
from pathlib import Path


TABLE_RE = re.compile(r"<hp:tbl\b.*?</hp:tbl>", re.DOTALL)
PARA_RE = re.compile(r"<hp:p\b.*?</hp:p>", re.DOTALL)


def extract_table_text(block: str) -> list[str]:
    return [text.strip() for text in re.findall(r"<hp:t>(.*?)</hp:t>", block) if text.strip()]


def is_cover_approval_table(block: str) -> bool:
    return 'rowCnt="20"' in block and 'colCnt="13"' in block and "문서번호" in block and "협" in block and "조" in block


def is_empty_toc_row(block: str) -> bool:
    if 'rowCnt="1"' not in block or 'colCnt="3"' not in block:
        return False
    texts = extract_table_text(block)
    if not texts:
        return False
    if texts[0] not in {"Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ"}:
        return False
    return len(texts) == 1


def remove_table_and_host_paragraph(xml: str, match: re.Match) -> str:
    start, end = match.span()
    p_start = xml.rfind("<hp:p ", 0, start)
    p_end = xml.find("</hp:p>", end)
    if p_start != -1 and p_end != -1:
        p_end += len("</hp:p>")
        return xml[:p_start] + xml[p_end:]
    return xml[:start] + xml[end:]


def extract_cover_title_paragraphs(block: str) -> list[str]:
    title_cell = re.search(
        r'<hp:tc name="결재제목".*?<hp:subList\b[^>]*>(.*?)</hp:subList>',
        block,
        re.DOTALL,
    )
    if not title_cell:
        return []
    inner = title_cell.group(1)
    paragraphs = []
    for para in PARA_RE.findall(inner):
        texts = extract_table_text(para)
        if texts:
            paragraphs.append(para)
    return paragraphs


def replace_first_text(block: str, new_text: str) -> str:
    return re.sub(r'(<hp:t\b[^>]*>)(.*?)(</hp:t>)', rf'\1{new_text}\3', block, count=1, flags=re.DOTALL)


def find_paragraphs_by_text(xml: str, text: str) -> list[re.Match]:
    matches = []
    for match in PARA_RE.finditer(xml):
        texts = [t.strip() for t in re.findall(r"<hp:t>(.*?)</hp:t>", match.group(0)) if t.strip()]
        if any(t == text for t in texts):
            matches.append(match)
    return matches


def remove_paragraph_at(xml: str, match: re.Match) -> str:
    return xml[:match.start()] + xml[match.end():]


def remove_extra_leading_empty_paragraphs(xml: str) -> tuple[str, int]:
    matches = list(PARA_RE.finditer(xml))
    if len(matches) < 3:
        return xml, 0

    first_content_idx = None
    for idx, match in enumerate(matches):
        texts = extract_table_text(match.group(0))
        if texts:
            first_content_idx = idx
            break

    if first_content_idx is None or first_content_idx <= 1:
        return xml, 0

    to_remove = []
    for idx in range(1, first_content_idx):
        texts = extract_table_text(matches[idx].group(0))
        if not texts:
            to_remove.append(matches[idx])

    for match in reversed(to_remove):
        xml = remove_paragraph_at(xml, match)
    return xml, len(to_remove)


def remove_linesegarray_from_paragraph(block: str) -> str:
    return re.sub(r'<hp:linesegarray\b[^>]*>.*?</hp:linesegarray>', '', block, flags=re.DOTALL)


def refresh_agenda_linesegs(xml: str) -> tuple[str, int]:
    updated = []
    count = 0
    for match in PARA_RE.finditer(xml):
        block = match.group(0)
        texts = extract_table_text(block)
        text = " ".join(texts)
        if not text:
            updated.append(block)
            continue
        if any(marker in text for marker in ["※", "◦", "○", "-", ":", "개발팀", "미팅", "한국퍼실리테이터연합회"]):
            new_block = remove_linesegarray_from_paragraph(block)
            if new_block != block:
                count += 1
            updated.append(new_block)
        else:
            updated.append(block)
    rebuilt = []
    last = 0
    for match, replacement in zip(PARA_RE.finditer(xml), updated):
        rebuilt.append(xml[last:match.start()])
        rebuilt.append(replacement)
        last = match.end()
    rebuilt.append(xml[last:])
    return "".join(rebuilt), count


def remove_empty_toc_tab_paragraphs(xml: str) -> tuple[str, int]:
    removed = 0
    while True:
        changed = False
        for match in PARA_RE.finditer(xml):
            block = match.group(0)
            texts = [t.strip() for t in re.findall(r"<hp:t>(.*?)</hp:t>", block) if t.strip()]
            if len(texts) == 1 and re.fullmatch(r'<hp:tab width="\d+" leader="3" type="2"/>', texts[0]):
                xml = remove_paragraph_at(xml, match)
                removed += 1
                changed = True
                break
        if not changed:
            break
    return xml, removed


def tidy_agenda_hwpx(hwpx_path: Path) -> dict:
    workdir = Path(tempfile.mkdtemp(prefix="tidy_agenda_"))
    try:
        with zipfile.ZipFile(hwpx_path, "r") as zf:
            zf.extractall(workdir)

        sec_path = workdir / "Contents" / "section0.xml"
        xml = sec_path.read_text(encoding="utf-8")

        cover_removed = 0
        empty_toc_removed = 0
        cover_title_restored = 0
        org_deduped = 0
        leading_empty_removed = 0
        linesegs_removed = 0
        empty_toc_tab_paragraphs_removed = 0

        while True:
            changed = False
            for match in list(TABLE_RE.finditer(xml)):
                block = match.group(0)
                if is_cover_approval_table(block):
                    title_paragraphs = extract_cover_title_paragraphs(block)
                    xml = remove_table_and_host_paragraph(xml, match)
                    cover_removed += 1

                    date_matches = find_paragraphs_by_text(xml, "2026.5.6")
                    org_matches = find_paragraphs_by_text(xml, "fKF 한국퍼실리테이터연합회 숙의리서치센터")

                    insert_at = date_matches[0].start() if date_matches else 0
                    if title_paragraphs:
                        meta_para = ""
                        if date_matches:
                            meta_para = replace_first_text(
                                date_matches[0].group(0),
                                "fKF 한국퍼실리테이터연합회 숙의리서치센터  2026.5.6"
                            )
                        rebuilt = "".join(title_paragraphs)
                        if meta_para:
                            rebuilt += meta_para
                        xml = xml[:insert_at] + rebuilt + xml[insert_at:]
                        cover_title_restored += len(title_paragraphs)

                    # 기존 기관명/날짜 단락 제거
                    for target in ["fKF 한국퍼실리테이터연합회 숙의리서치센터", "2026.5.6"]:
                        extra_matches = find_paragraphs_by_text(xml, target)
                        for extra in reversed(extra_matches):
                            xml = remove_paragraph_at(xml, extra)
                            org_deduped += 1

                    changed = True
                    break
                if is_empty_toc_row(block):
                    xml = remove_table_and_host_paragraph(xml, match)
                    empty_toc_removed += 1
                    changed = True
                    break
            if not changed:
                break

        xml, leading_empty_removed = remove_extra_leading_empty_paragraphs(xml)
        xml, linesegs_removed = refresh_agenda_linesegs(xml)
        xml, empty_toc_tab_paragraphs_removed = remove_empty_toc_tab_paragraphs(xml)

        sec_path.write_text(xml, encoding="utf-8")

        tmp_out = hwpx_path.with_suffix(".hwpx.tmp")
        if tmp_out.exists():
            tmp_out.unlink()
        with zipfile.ZipFile(tmp_out, "w", zipfile.ZIP_DEFLATED) as zf:
            mt = workdir / "mimetype"
            zf.write(mt, "mimetype", compress_type=zipfile.ZIP_STORED)
            for f in sorted(workdir.rglob("*")):
                if f.is_file() and f.name != "mimetype":
                    zf.write(f, f.relative_to(workdir).as_posix())
        shutil.move(str(tmp_out), str(hwpx_path))

        return {
            "ok": True,
            "cover_tables_removed": cover_removed,
            "empty_toc_rows_removed": empty_toc_removed,
            "cover_title_restored": cover_title_restored,
            "org_paragraphs_removed": org_deduped,
            "leading_empty_removed": leading_empty_removed,
            "linesegs_removed": linesegs_removed,
            "empty_toc_tab_paragraphs_removed": empty_toc_tab_paragraphs_removed,
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="format_full 결과를 agenda 스타일로 정리")
    parser.add_argument("hwpx")
    args = parser.parse_args()
    result = tidy_agenda_hwpx(Path(args.hwpx).resolve())
    print(result)


if __name__ == "__main__":
    main()
