"""Copy parser geometry while the PDF is open; tables never become shared prose."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

import fitz

from .types import Cell, EvidenceWindow, Table


@dataclass
class PageLayout:
    windows: list[EvidenceWindow] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    parents: dict[str, str | None] = field(default_factory=dict)
    headings: list[str] = field(default_factory=list)
    image_boxes: list[tuple[float, ...]] = field(default_factory=list)
    words: list[tuple[Any, ...]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def native_layout(page: fitz.Page, number: int) -> PageLayout:
    page_id = f"p{number}"
    result = PageLayout(parents={"document": None, page_id: "document"})
    blocks = [b for b in page.get_text("blocks", sort=True) if b[6] == 0]
    result.words = [tuple(w) for w in page.get_text("words", sort=True)]
    result.image_boxes = [tuple(i["bbox"]) for i in page.get_image_info()]
    diagram_like = len(page.get_drawings()) > 50
    # Headings are geometric candidates, not inferred semantic section titles.
    text_dict = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)
    spans = [s for b in text_dict["blocks"] if "lines" in b for line in b["lines"] for s in line["spans"]]
    sizes = sorted(s["size"] for s in spans)
    median = sizes[len(sizes) // 2] if sizes else 0
    heading_spans = [s for s in spans if s["size"] > median * 1.15 and s["text"].strip()]
    result.headings = [s["text"].strip() for s in heading_spans]

    def section_at(box):
        preceding = [(i, s) for i, s in enumerate(heading_spans) if s["bbox"][3] <= box[1]
                     and s["bbox"][0] < box[2] and s["bbox"][2] > box[0]]
        if not preceding:
            return page_id, ""
        i, span = max(preceding, key=lambda x: x[1]["bbox"][3])
        sid = f"{page_id}:s{i}"
        result.parents[sid] = page_id
        return sid, span["text"].strip()

    try:
        detected = list(page.find_tables().tables)
    except Exception:
        detected = []
        result.issues.append("table_detection_failed")
    for index, table in enumerate(detected):
        tid = f"{page_id}:t{index}"
        parent, heading = section_at(table.bbox)
        result.parents[tid] = parent
        rows = []
        for r, values in enumerate(table.extract()):
            cells = []
            for c, raw in enumerate(values):
                box = table.rows[r].cells[c]
                # Preserve null cells. The parser doesn't supply an authoritative merge owner.
                cells.append(Cell(c, raw, tuple(box) if box else None))
            rows.append(cells)
        for r, cells in enumerate(rows):
            for c, cell in enumerate(cells):
                if cell.bbox is not None:
                    continue
                examples = [row[c].bbox for row in rows if c < len(row) and row[c].bbox]
                if not examples:
                    continue
                narrow = min(examples, key=lambda box: box[2] - box[0])
                point = fitz.Point((narrow[0] + narrow[2]) / 2, (table.rows[r].bbox[1] + table.rows[r].bbox[3]) / 2)
                owners = [(rr, cc) for rr, row in enumerate(rows) for cc, owner in enumerate(row)
                          if owner.bbox and fitz.Rect(owner.bbox).contains(point)]
                if len(owners) == 1:
                    rr, cc = owners[0]
                    cells[c] = replace(cell, merged_with=f"{tid}:r{rr}:c{cc}")
        columns = [name or "" for name in table.header.names]
        near = "\n".join(b[4].strip() for b in blocks if 0 <= table.bbox[1] - b[3] <= 60
                         and b[0] < table.bbox[2] and b[2] > table.bbox[0])
        result.tables.append(Table(tid, number, tuple(table.bbox), heading, columns, rows, parent, near))
        for r, cells in enumerate(rows):
            rid = f"{tid}:r{r}"
            result.parents[rid] = tid
            result.windows.append(EvidenceWindow(
                rid, number, "\t".join(cell.raw or "" for cell in cells), rid, tid,
                heading, tid, rid, tuple(table.rows[r].bbox), cells, columns, "pymupdf", 1.0,
                table_context=[[c.raw for c in row] for row in rows[:5]],
            ))

    # Words intersecting table geometry must not re-enter extraction through a text block.
    for index, block in enumerate(blocks):
        words = [w for w in result.words if w[5] == block[5]
                 and not any(fitz.Rect(w[:4]).intersects(fitz.Rect(t.bbox)) for t in result.tables)]
        lines: dict[tuple[int, int], list[tuple]] = {}
        for word in words:
            lines.setdefault((word[5], word[6]), []).append(word)
        groups: list[list[list[tuple]]] = []
        for line in lines.values():
            matching = next((g for g in groups if abs(g[0][0][0] - line[0][0]) < page.rect.width * 0.2), None)
            if matching is None:
                groups.append([line])
            else:
                matching.append(line)
        for g, group in enumerate(groups):
            text = "\n".join(" ".join(w[4] for w in line) for line in group).strip()
            if not text:
                continue
            box = fitz.Rect(group[0][0][:4])
            for line in group:
                for word in line:
                    box |= fitz.Rect(word[:4])
            parent, heading = section_at(box)
            bid = f"{page_id}:b{index}" + (f":g{g}" if len(groups) > 1 else "")
            result.parents[bid] = parent
            result.windows.append(EvidenceWindow(bid, number, text, bid, parent, heading,
                                                  bbox=tuple(box), parser="pymupdf",
                                                  quality=0.45 if "\ufffd" in text else 1.0,
                                                  visual_required=bool(result.issues)))
    if result.image_boxes or diagram_like:
        result.windows = [replace(w, visual_required=True) for w in result.windows]
    return result


def transcribed_layout(text: str, number: int, parser: str) -> PageLayout:
    """Markdown tables are isolated; visual verification is mandatory without native geometry."""
    page_id = f"p{number}"
    result = PageLayout(parents={"document": None, page_id: "document"})
    lines = text.splitlines()
    section = ""
    parent = page_id
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("#"):
            section = line.lstrip("# ")
            parent = f"{page_id}:{parser}:s{index}"
            result.parents[parent] = page_id
            result.headings.append(section)
        if index + 1 < len(lines) and "|" in line and re.fullmatch(r"[\s|:\-]+", lines[index + 1]) and "---" in lines[index + 1]:
            columns = [c.strip() for c in line.strip().strip("|").split("|")]
            tid = f"{page_id}:{parser}:t{index}"
            result.parents[tid] = parent
            rows = []
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                values = [c.strip() for c in lines[index].strip().strip("|").split("|")]
                cells = [Cell(c, value) for c, value in enumerate(values)]
                rid = f"{tid}:r{len(rows)}"
                result.parents[rid] = tid
                result.windows.append(EvidenceWindow(rid, number, lines[index], rid, tid, section,
                    tid, rid, cells=cells, columns=columns, parser=parser, quality=0.65, visual_required=True))
                rows.append(cells)
                index += 1
            result.tables.append(Table(tid, number, None, section, columns, rows, parent))
            continue
        if line.strip():
            bid = f"{page_id}:{parser}:b{index}"
            result.parents[bid] = parent
            result.windows.append(EvidenceWindow(bid, number, line.strip(), bid, parent, section,
                parser=parser, quality=0.65, visual_required=True))
        index += 1
    return result
