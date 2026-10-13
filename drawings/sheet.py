"""The sheet a diagram is printed on: border, zones, legend, notes,
revisions and title block.

Sheet sizes and margins follow ISO 5457 (A0 to A3 landscape, a 20 mm filing
margin on the left and 10 mm elsewhere, zones of about 50 mm lettered up the
sides and numbered along the top and bottom). The title block sits bottom
right, as ISO 7200 places it, with the fields an Australian drawing register
expects. The diagram is fitted into what is left; a diagram too big for A0 is
scaled down and the sheet says so.
"""
from __future__ import annotations

import textwrap
from typing import Dict, List, Optional, Tuple

from .canvas import Block, Canvas, text_width

SIZES = [("A3", 420.0, 297.0, 8, 6), ("A2", 594.0, 420.0, 12, 8),
         ("A1", 841.0, 594.0, 16, 12), ("A0", 1189.0, 841.0, 24, 16)]
LEFT, MARGIN = 20.0, 10.0
STRIP_H = 64.0          # notes, revisions and title block along the bottom
TITLE_W = 170.0
REV_W = 96.0
LEGEND_W = 66.0
GAP = 6.0               # between the diagram and anything around it

L_BORDER, L_TEXT, L_TITLE = "SHEET-BORDER", "SHEET-TEXT", "SHEET-TITLE"


def drawing_area(size: Tuple[float, float], legend=True):
    """(x0, y0, x1, y1) free for the diagram on a sheet of this size."""
    w, h = size
    x0, y0 = LEFT + GAP, MARGIN + STRIP_H + GAP
    x1 = w - MARGIN - GAP - (LEGEND_W + GAP if legend else 0)
    y1 = h - MARGIN - GAP
    return x0, y0, x1, y1


def _cell(c, x0, y0, x1, y1, label=None, value=None, vh=3.0, align="LEFT"):
    c.rect((x0, y0), (x1, y1), L_BORDER)
    if label:
        c.text((x0 + 1.2, y1 - 1.2), label.upper(), 1.6, L_TEXT,
               align="TOP_LEFT")
    if value not in (None, ""):
        if align == "CENTER":
            c.text(((x0 + x1) / 2, y0 + 1.8), value, vh, L_TITLE,
                   align="BOTTOM_CENTER")
        else:
            c.text((x0 + 1.8, y0 + 1.8), value, vh, L_TITLE,
                   align="BOTTOM_LEFT")


def _fit(value: str, width: float, h: float) -> float:
    """Text height that fits value in width, no bigger than h."""
    w = text_width(value, h)
    return h if w <= width or w == 0 else max(1.6, h * width / w)


def border(c: Canvas, size, zones):
    w, h = size
    c.rect((0, 0), (w, h), L_BORDER)                          # trimmed edge
    fx0, fy0, fx1, fy1 = LEFT, MARGIN, w - MARGIN, h - MARGIN
    c.rect((fx0, fy0), (fx1, fy1), L_BORDER, width=0.7)       # frame
    zx, zy = zones
    sx, sy = (fx1 - fx0) / zx, (fy1 - fy0) / zy
    for i in range(zx + 1):
        x = fx0 + i * sx
        c.line((x, fy1), (x, h), L_BORDER)
        c.line((x, fy0), (x, 0), L_BORDER)
        if i < zx:
            for y in (h - MARGIN / 2, MARGIN / 2):
                c.text((x + sx / 2, y), str(i + 1), 3, L_TEXT,
                       align="MIDDLE_CENTER")
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"          # no I or O, per ISO 5457
    for j in range(zy + 1):
        y = fy1 - j * sy
        c.line((fx0, y), (LEFT - MARGIN, y), L_BORDER)
        c.line((fx1, y), (w, y), L_BORDER)
        if j < zy:
            for x in (LEFT - MARGIN / 2, w - MARGIN / 2):
                c.text((x, y - sy / 2), letters[j], 3, L_TEXT,
                       align="MIDDLE_CENTER")
    # centring marks, for the copy camera and the plotter
    for (a, b) in (((w / 2, 0), (w / 2, fy0)), ((w / 2, h), (w / 2, fy1)),
                   ((0, h / 2), (fx0, h / 2)), ((w, h / 2), (fx1, h / 2))):
        c.line(a, b, L_BORDER, width=0.5)


def title_block(c: Canvas, x1: float, y0: float, info: Dict):
    """Title block with its bottom-right corner at (x1, y0)."""
    x0, y1 = x1 - TITLE_W, y0 + STRIP_H
    c.rect((x0, y0), (x1, y1), L_BORDER, width=0.5)
    # owner and status
    top = y1 - 14
    _cell(c, x0, top, x1, y1)
    owner = (info.get("client") or "").upper()
    c.text((x0 + 3, top + 7), owner, _fit(owner, 92, 5), L_TITLE,
           align="MIDDLE_LEFT")
    status = (info.get("status") or "").upper()
    if status:
        c.text((x1 - 3, top + 7), status, _fit(status, 64, 2.5), L_TITLE,
               align="MIDDLE_RIGHT")
    # title
    t0 = top - 20
    _cell(c, x0, t0, x1, top, "Title")
    title = (info.get("title") or "").upper()
    sub = (info.get("subtitle") or "").upper()
    c.text((x0 + 3, t0 + 10.5), title, _fit(title, TITLE_W - 6, 4.5),
           L_TITLE, align="BOTTOM_LEFT")
    c.text((x0 + 3, t0 + 4), sub, _fit(sub, TITLE_W - 6, 3.2), L_TITLE,
           align="BOTTOM_LEFT")
    # people and dates
    r0 = t0 - 13
    cols = [("Drawn", info.get("drawn")), ("Checked", info.get("checked")),
            ("Approved", info.get("approved")), ("Date", info.get("date")),
            ("Project", info.get("project"))]
    widths = [28, 28, 28, 30, TITLE_W - 114]
    x = x0
    for (label, value), wd in zip(cols, widths):
        v = str(value or "")
        _cell(c, x, r0, x + wd, t0, label, v, _fit(v, wd - 3, 2.8))
        x += wd
    # number, revision, sheet, size, scale
    cols = [("Drawing number", info.get("number")),
            ("Rev", info.get("revision")), ("Sheet", info.get("sheet")),
            ("Size", info.get("size")), ("Scale", info.get("scale"))]
    widths = [TITLE_W - 92, 18, 26, 20, 28]
    x = x0
    for (label, value), wd in zip(cols, widths):
        v = str(value or "")
        _cell(c, x, y0, x + wd, r0, label, v,
              _fit(v, wd - 3, 4.0 if label == "Drawing number" else 3.2))
        x += wd


def revisions(c: Canvas, x1: float, y0: float, revs: List[Dict]):
    x0, y1 = x1 - REV_W, y0 + STRIP_H
    c.rect((x0, y0), (x1, y1), L_BORDER, width=0.5)
    cols = [("Rev", 10), ("Date", 18), ("Description", REV_W - 48),
            ("By", 10), ("Chk", 10)]
    row = 5.5
    # header along the bottom, rows stacking upwards: the latest is on top
    x = x0
    for name, wd in cols:
        c.rect((x, y0), (x + wd, y0 + row), L_BORDER)
        c.text((x + wd / 2, y0 + row / 2), name.upper(), 1.8, L_TEXT,
               align="MIDDLE_CENTER")
        x += wd
    shown = list(revs)[-int((STRIP_H - row) // row):]
    for i, r in enumerate(shown):
        yb = y0 + row * (i + 1)
        x = x0
        for (name, wd), key in zip(cols, ("rev", "date", "description", "by",
                                          "chk")):
            c.rect((x, yb), (x + wd, yb + row), L_BORDER)
            v = str(r.get(key) or "")
            c.text((x + 1.2, yb + row / 2), v, _fit(v, wd - 2.4, 2.0), L_TEXT,
                   align="MIDDLE_LEFT")
            x += wd


def notes(c: Canvas, x0: float, x1: float, y0: float, lines: List[str]):
    y1 = y0 + STRIP_H
    c.rect((x0, y0), (x1, y1), L_BORDER, width=0.5)
    c.text((x0 + 2, y1 - 2), "NOTES", 2.5, L_TITLE, align="TOP_LEFT")
    h = 2.0
    chars = max(20, int((x1 - x0 - 10) / (h * 0.62)))
    y = y1 - 7.5
    for i, line in enumerate(lines, 1):
        wrapped = textwrap.wrap(line, chars - 4) or [""]
        for j, part in enumerate(wrapped):
            if y < y0 + 2:
                return
            if j == 0:
                c.text((x0 + 2, y), f"{i}.", h, L_TEXT, align="TOP_LEFT")
            c.text((x0 + 7, y), part, h, L_TEXT, align="TOP_LEFT")
            y -= h * 1.55


def legend(c: Canvas, x0: float, y1: float, y_min: float,
           items: List[Tuple[str, Optional[str], dict]],
           blocks: Dict[str, Block]):
    """A column of symbols and line styles, top-left at (x0, y1).

    items: (description, block name or None, line style) where a line style
    is {"layer": .., "width": ..} drawn as a short sample.
    """
    row = 8.0
    x1 = x0 + LEGEND_W
    rows = len(items)
    y_bot = max(y_min, y1 - 8 - rows * row - 2)
    c.rect((x0, y_bot), (x1, y1), L_BORDER, width=0.5)
    c.text((x0 + 2, y1 - 2), "LEGEND", 2.5, L_TITLE, align="TOP_LEFT")
    y = y1 - 8 - row / 2
    for desc, block, style in items:
        if y < y_bot + row / 2:
            break
        if block:
            b = blocks[block]
            k = min(1.0, 9 / max(b.size), 7 / max(b.size[1], 1))
            c.insert(block, (x0 + 8, y), style.get("layer", L_TEXT),
                     scale=k, attribs={})
        else:
            c.line((x0 + 3, y), (x0 + 13, y), style.get("layer", L_TEXT),
                   width=style.get("width", 0.0),
                   linetype=style.get("linetype"))
        lines = textwrap.wrap(desc, 30)[:2]
        for i, part in enumerate(lines):
            c.text((x0 + 16, y + (len(lines) - 1) * 1.4 - i * 2.8), part, 2.0,
                   L_TEXT, align="MIDDLE_LEFT")
        y -= row
    return y_bot


def compose(diagram: Canvas, blocks: Dict[str, Block], info: Dict,
            legend_items, note_lines: List[str], minimum="A3"):
    """Put a diagram on the smallest sheet it fits. Returns (canvas, meta)."""
    bx0, by0, bx1, by1 = diagram.bounds(blocks)
    ew, eh = max(bx1 - bx0, 1.0), max(by1 - by0, 1.0)
    legend_h = 8.0 * len(legend_items) + 12
    names = [s[0] for s in SIZES]
    start = names.index(minimum) if minimum in names else 0
    for name, w, h, zx, zy in SIZES[start:]:
        x0, y0, x1, y1 = drawing_area((w, h))
        if ew <= x1 - x0 and eh <= y1 - y0 and legend_h <= y1 - y0 + GAP:
            k = 1.0
            break
    else:
        k = min((x1 - x0) / ew, (y1 - y0) / eh)
    size, zones = (w, h), (zx, zy)
    w, h = size
    x0, y0, x1, y1 = drawing_area(size)
    # centre the diagram in its area
    dw, dh = (bx1 - bx0) * k, (by1 - by0) * k
    dx = x0 + ((x1 - x0) - dw) / 2 - bx0 * k
    dy = y0 + ((y1 - y0) - dh) / 2 - by0 * k
    out = Canvas()
    border(out, size, zones)
    fx1, fy0 = w - MARGIN, MARGIN
    info = dict(info)
    info.setdefault("size", name)
    info["scale"] = "NTS" if k == 1 else f"NTS ({k:.2f})"
    title_block(out, fx1, fy0, info)
    revisions(out, fx1 - TITLE_W, fy0, info.get("revisions") or [])
    notes(out, LEFT, fx1 - TITLE_W - REV_W, fy0, note_lines)
    legend(out, w - MARGIN - LEGEND_W, h - MARGIN, MARGIN + STRIP_H + GAP,
           legend_items, blocks)
    out.extend(diagram.transformed(dx, dy, k))
    return out, {"size": name, "paper_mm": [w, h], "scale": k}
