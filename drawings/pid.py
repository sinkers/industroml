"""Piping and instrumentation diagram from an IndustroML model.

Every pipe connection in the model is a line on the diagram. Equipment
(pumps, chillers, CDUs, tanks, heat exchangers, headers) is laid out in
columns in the direction of flow, left to right. Valves, strainers, filters
and orifice plates that sit between two pipes are drawn inline on the line
that joins the equipment either side, in the order the model connects them.
Instruments are ISA-5.1 bubbles.

A closed loop has no start, so the loop is cut where it returns to the
equipment the walk began from (a chiller, tank or dry cooler by preference),
and that return line is drawn along the bottom of the sheet, as P&IDs
usually draw a return. Lines that jump more than one column run along the
top.

Lines are labelled with a line number (DN-service-id-spec) and a flow arrow,
and drawn on a layer per service, P-LINE-CHWS and so on.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .canvas import Canvas, text_width
from .dxf import layer_for_service
from .model import Model, pipe_line_number, rating
from .symbols import INSTRUMENT_LETTERS, PID_EQUIPMENT, PID_INLINE, VALVE_TYPES

TXT = 2.0
TAG = 2.8
ROW_GAP = 34.0          # clear space between rows of equipment
INLINE_GAP = 5.0        # line between inline items
LANE = 16.0             # spacing of return and jump lanes, room for tags
START_KINDS = ("chiller", "dry_cooler", "cooling_tower", "tank",
               "pressure_vessel", "heat_exchanger", "heat_exchanger_plate",
               "cdu", "pump")


@dataclass
class Line:
    src: str
    dst: str
    src_port: str
    dst_port: str
    items: List[str]
    pipes: List[dict]
    kind: str = "forward"           # forward, jump, return
    track: int = 0


@dataclass
class Plan:
    nodes: Dict[str, dict] = field(default_factory=dict)
    lines: List[Line] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _inline_block(m: Model, asset: str) -> Optional[str]:
    k = m.kind(asset)
    if k == "valve":
        vt = str(m.attrs(asset).get("valve_type", "gate")).lower()
        return VALVE_TYPES.get(vt, "P-GATE")
    return PID_INLINE.get(k)


def _equip_block(m: Model, asset: str) -> str:
    k = m.kind(asset)
    if k in INSTRUMENT_LETTERS:
        return "P-INST"
    return PID_EQUIPMENT.get(k, "P-EQUIP")


def collect(m: Model) -> (List[Line], set):
    pipes = [c for c in m.connections if c.get("type") == "pipe"]
    outs, ins = defaultdict(list), defaultdict(list)
    for c in pipes:
        a, b = m.asset_of(c.get("from", "")), m.asset_of(c.get("to", ""))
        if not a or not b or a == b:
            continue
        outs[a].append(c)
        ins[b].append(c)
    nodes = set(outs) | set(ins)
    inline = {n for n in nodes if _inline_block(m, n)
              and len(ins[n]) == 1 and len(outs[n]) == 1}
    # an instrument with a pipe in and out (a flow meter) is inline too
    inline |= {n for n in nodes if m.kind(n) in INSTRUMENT_LETTERS
               and len(ins[n]) == 1 and len(outs[n]) == 1}
    lines = []
    for c in pipes:
        a, b = m.asset_of(c.get("from", "")), m.asset_of(c.get("to", ""))
        if not a or not b or a == b or a in inline:
            continue
        items, chain, cur, seen = [], [c], b, set()
        while cur in inline and cur not in seen:
            seen.add(cur)
            items.append(cur)
            nxt = outs[cur][0]
            chain.append(nxt)
            cur = m.asset_of(nxt["to"])
        lines.append(Line(a, cur, c["from"], chain[-1]["to"], items, chain))
    equipment = {n for ln in lines for n in (ln.src, ln.dst)}
    return lines, equipment


def _rank(m: Model, lines: List[Line], equipment):
    outs, indeg = defaultdict(list), defaultdict(int)
    for ln in lines:
        outs[ln.src].append(ln)
        indeg[ln.dst] += 1

    def prio(n):
        k = m.kind(n)
        return (START_KINDS.index(k) if k in START_KINDS else 99,
                m.order.get(n, 1e9))

    nodes = sorted(equipment, key=lambda n: m.order.get(n, 1e9))
    state = {}

    def walk(n):
        state[n] = 1
        for ln in outs[n]:
            s = state.get(ln.dst)
            if s == 1:
                ln.kind = "return"
            elif s is None:
                walk(ln.dst)
        state[n] = 2

    for n in nodes:
        if indeg[n] == 0 and n not in state:
            walk(n)
    # a closed loop: start from every piece of the preferred kind at once
    # (both chillers, say), so a line back into any of them is the return
    while any(n not in state for n in nodes):
        rest = sorted((n for n in nodes if n not in state), key=prio)
        best = prio(rest[0])[0]
        starts = [n for n in rest if prio(n)[0] == best] if best < 99 \
            else rest[:1]
        for n in starts:
            state[n] = 1
        for n in starts:
            state[n] = 0
            walk(n)
    rank = {n: 0 for n in nodes}
    fwd = [ln for ln in lines if ln.kind != "return"]
    for _ in range(len(nodes) + 1):
        moved = False
        for ln in fwd:
            if rank[ln.dst] < rank[ln.src] + 1:
                rank[ln.dst] = rank[ln.src] + 1
                moved = True
        if not moved:
            break
    for ln in fwd:
        if rank[ln.dst] - rank[ln.src] > 1:
            ln.kind = "jump"
    return rank


def _order(m, lines, rank):
    cols = defaultdict(list)
    for n in sorted(rank, key=lambda n: m.order.get(n, 1e9)):
        cols[rank[n]].append(n)
    nbrs = defaultdict(list)
    for ln in lines:
        nbrs[ln.src].append(ln.dst)
        nbrs[ln.dst].append(ln.src)
    pos = {n: i for c in cols.values() for i, n in enumerate(c)}
    for sweep in range(6):
        rng = sorted(cols) if sweep % 2 == 0 else sorted(cols, reverse=True)
        for r in rng:
            def key(n):
                ps = [pos[k] for k in nbrs[n] if rank[k] != r]
                return (sum(ps) / len(ps)) if ps else pos[n]
            cols[r].sort(key=key)
            for i, n in enumerate(cols[r]):
                pos[n] = i
    return cols


def _items_len(m, blocks, items):
    return sum(blocks[_inline_block(m, i) or "P-INST"].size[0] + INLINE_GAP
               for i in items)


def _letters(m: Model, asset: str):
    tag = m.tag(asset)
    mm = re.match(r"^([A-Za-z]+)[-_ ]?(\w*)$", tag)
    letters = INSTRUMENT_LETTERS.get(m.kind(asset))
    if mm and mm.group(2):
        return mm.group(1).upper()[:4], mm.group(2)
    return letters or "X", re.sub(r"\D", "", tag) or tag


def _draw_items(c, m, blocks, items, a, b, layer, label_below=True):
    """Inline items evenly along the horizontal run a->b, line broken at
    each symbol so the symbol is not crossed by the line."""
    (x0, y), (x1, _) = a, b
    sign = 1 if x1 >= x0 else -1
    total = _items_len(m, blocks, items) - INLINE_GAP
    span = abs(x1 - x0)
    x = x0 + sign * max(INLINE_GAP, (span - total) / 2)
    c.line((x0, y), (x, y), layer)
    for it in items:
        block = _inline_block(m, it)
        if block is None:                       # an inline instrument
            w = 10.0
            cx = x + sign * w / 2
            c.circle((cx, y), 1.2, layer)
            fn, loop = _letters(m, it)
            c.insert("P-INST", (cx, y + 13), "P-INST",
                     attribs={"FUNC": fn, "LOOP": loop})
            c.line((cx, y + 1.2), (cx, y + 8), "P-SIGNAL")
        else:
            w = blocks[block].size[0]
            cx = x + sign * w / 2
            c.insert(block, (cx, y), "P-VALVE", rotation=0 if sign > 0 else 180)
            if label_below:
                c.text((cx, y - 4.5), m.tag(it), TXT, "P-TAG",
                       align="TOP_CENTER")
        nx = x + sign * (w + INLINE_GAP)
        if it != items[-1]:
            c.line((x + sign * w, y), (nx, y), layer)
        x = nx
    c.line((x - sign * INLINE_GAP, y), (x1, y), layer)


def _arrow(c, a, b, layer):
    (x0, y0), (x1, y1) = a, b
    mx, my = x0 + (x1 - x0) * 0.5, y0 + (y1 - y0) * 0.5
    rot = 0 if x1 > x0 else 180 if x1 < x0 else (90 if y1 > y0 else 270)
    c.insert("P-ARROW", (mx, my), layer, rotation=rot)


def layout(m: Model, blocks):
    lines, equipment = collect(m)
    plan = Plan(lines=lines)
    if not lines:
        plan.warnings.append("the model has no pipes between assets")
        return Canvas(), plan
    rank = _rank(m, lines, equipment)
    cols = _order(m, lines, rank)
    c = Canvas()

    def size(n):
        if m.kind(n) == "header":
            k = max(len([l for l in lines if l.dst == n]),
                    len([l for l in lines if l.src == n]), 2)
            return (4.0, k * 12.0 + 8)
        return blocks[_equip_block(m, n)].size

    # columns and channels
    ranks = sorted(cols)
    col_w = {r: max(size(n)[0] for n in cols[r]) for r in ranks}
    out_by_rank = defaultdict(list)
    for ln in lines:
        out_by_rank[rank[ln.src]].append(ln)
    in_back = defaultdict(list)
    for ln in lines:
        if ln.kind == "return":
            in_back[rank[ln.dst]].append(ln)
    chan = {}
    for r in ranks + [min(ranks) - 1]:
        fw = [ln for ln in out_by_rank.get(r, []) if ln.kind != "return"]
        need_items = max((_items_len(m, blocks, ln.items) for ln in fw
                          if ln.kind == "forward"), default=0)
        label = max((text_width(pipe_line_number(ln.pipes[0]), TXT)
                     for ln in fw), default=0)
        back = in_back.get(r + 1, [])
        chan[r] = max(24.0, need_items + 16 + len(fw) * 4,
                      label + 14) + len(back) * 4 + (8 if back else 0)
    x_c = {}
    x = chan[min(ranks) - 1]
    for r in ranks:
        x_c[r] = x + col_w[r] / 2
        x += col_w[r] + chan[r]
    row_h = max(size(n)[1] for n in equipment) + ROW_GAP
    rows = max(len(v) for v in cols.values())
    pos = {}
    for r in ranks:
        off = (rows - len(cols[r])) / 2
        for i, n in enumerate(cols[r]):
            pos[n] = (x_c[r], -(i + off) * row_h)

    # ports: inputs down the left side, outputs down the right, ordered by
    # where the other end is so lines do not cross needlessly
    port = {}
    for n in equipment:
        w, h = size(n)
        cx, cy = pos[n]
        block = _equip_block(m, n)
        fixed = blocks[block].ports
        ins_ = sorted([l for l in lines if l.dst == n],
                      key=lambda l: -pos[l.src][1])
        outs_ = sorted([l for l in lines if l.src == n],
                       key=lambda l: -pos[l.dst][1])
        for side, group, sx in (("in", ins_, -w / 2), ("out", outs_, w / 2)):
            for k, ln in enumerate(group):
                if side in fixed and len(group) == 1:
                    px, py = fixed[side]
                    p = (cx + px, cy + py)
                else:
                    span = h - 8
                    py = (span / 2 - k * span / max(len(group) - 1, 1)
                          if len(group) > 1 else 0.0)
                    p = (cx + sx, cy + py)
                port[(id(ln), side)] = p

    # equipment
    for n in equipment:
        cx, cy = pos[n]
        w, h = size(n)
        if m.kind(n) == "header":
            c.polyline([(cx, cy - h / 2), (cx, cy + h / 2)], "P-EQUIP",
                       width=1.4)
        else:
            block = _equip_block(m, n)
            att = {}
            if block.startswith("P-INST"):
                fn, loop = _letters(m, n)
                att = {"FUNC": fn, "LOOP": loop}
            c.insert(block, (cx, cy), "P-INST" if att else "P-EQUIP",
                     attribs=att)
        if not m.kind(n) in INSTRUMENT_LETTERS:
            c.text((cx, cy - h / 2 - 3), m.tag(n), TAG, "P-TAG",
                   align="TOP_CENTER")
            sub = [m.name(n)] if m.name(n) != m.tag(n) else []
            r = rating(m.attrs(n))
            if r:
                sub.append(r)
            for i, s in enumerate(sub):
                c.text((cx, cy - h / 2 - 3 - TAG - 1.5 - i * TXT * 1.4), s,
                       TXT, "P-TEXT", align="TOP_CENTER")
        plan.nodes[n] = {"rank": rank[n], "x": cx, "y": cy,
                         "block": _equip_block(m, n)}

    # lines
    ymin = min(p[1] for p in pos.values()) - row_h / 2 - 10
    ymax = max(p[1] for p in pos.values()) + row_h / 2 + 4
    track = defaultdict(int)
    lane_lo, lane_hi = 0, 0
    pending = []
    for ln in lines:
        a, b = port[(id(ln), "out")], port[(id(ln), "in")]
        layer = layer_for_service((ln.pipes[0].get("attributes") or {})
                                  .get("service"))
        rs, rd = rank[ln.src], rank[ln.dst]
        number = pipe_line_number(ln.pipes[0])
        chan_x0 = x_c[rs] + col_w[rs] / 2
        if ln.kind == "forward":
            k = track[rs]
            track[rs] += 1
            items = _items_len(m, blocks, ln.items)
            xt = chan_x0 + 8 + items + k * 4
            if abs(a[1] - b[1]) < 0.01:
                xt = b[0] - 4
            first = ((a[0], a[1]), (xt, a[1]))
            _draw_items(c, m, blocks, ln.items, *first, layer)
            pts = [(xt, a[1]), (xt, b[1]), b]
            c.polyline(pts, layer)
            if abs(a[1] - b[1]) < 0.01:
                runs = [(a, b)]
            else:
                runs = [first, ((xt, b[1]), b)]
        else:
            k = track[rs]
            track[rs] += 1
            xt = chan_x0 + 8 + k * 4
            if ln.kind == "return":
                ly = ymin - lane_lo * LANE
                lane_lo += 1
            else:
                ly = ymax + lane_hi * LANE
                lane_hi += 1
            kin = track[("in", rd)]
            track[("in", rd)] += 1
            xe = x_c[rd] - col_w[rd] / 2 - 8 - kin * 4
            c.line(a, (xt, a[1]), layer)
            c.polyline([(xt, a[1]), (xt, ly)], layer)
            lane = ((xt, ly), (xe, ly))
            _draw_items(c, m, blocks, ln.items, *lane, layer)
            c.polyline([(xe, ly), (xe, b[1]), b], layer)
            runs = [lane, (a, (xt, a[1])), ((xe, b[1]), b)]
        runs.sort(key=lambda r: -abs(r[1][0] - r[0][0]))
        pending.append((number, runs))
        seg = runs[0]
        if not ln.items:
            _arrow(c, *seg, layer)
        else:
            _arrow(c, (b[0] - 6, b[1]), b, layer)
    _place_labels(c, blocks, pending)
    return c, plan


def _overlaps(a, b, pad=0.6):
    return not (a[2] + pad < b[0] or b[2] + pad < a[0] or
                a[3] + pad < b[1] or b[3] + pad < a[1])


def _box(prim, blocks):
    from .canvas import text_box
    if prim.kind == "text":
        pts = text_box(prim.data)
    elif prim.kind == "insert":
        b = blocks.get(prim.data["block"])
        if not b or prim.data["block"] == "P-ARROW":
            return None
        (x, y), k = prim.data["at"], prim.data.get("scale", 1.0)
        w, h = b.size
        pts = [(x - w * k / 2, y - h * k / 2), (x + w * k / 2, y + h * k / 2)]
    elif prim.kind == "polyline" and prim.data.get("width"):
        w = prim.data["width"] / 2 + 0.5          # headers: a thick bar
        q = prim.data["pts"]
        pts = [(min(p[0] for p in q) - w, min(p[1] for p in q)),
               (max(p[0] for p in q) + w, max(p[1] for p in q))]
    else:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _place_labels(c, blocks, pending):
    """Each line number above or below one of its horizontal runs, the
    longest that is clear of every symbol and label already placed."""
    from .canvas import text_box
    taken = [b for b in (_box(p, blocks) for p in c.prims) if b]
    for number, runs in pending:
        choice = None
        # first a run the label fits along, then any run it can overhang,
        # always clear of what is already drawn
        for need_fit in (True, False):
            for (x0, y), (x1, _) in runs:
                if abs(x1 - x0) < 4:
                    continue
                lo, hi = min(x0, x1), max(x0, x1)
                spots = [((lo + hi) / 2, "CENTER"), (lo + 1, "LEFT"),
                         (hi - 1, "RIGHT")]
                cands = [(x, dy, f"{v}_{h}") for dy, v in
                         ((1.5, "BOTTOM"), (-1.8, "TOP"), (4.2, "BOTTOM"),
                          (-7.5, "TOP")) for x, h in spots]
                for x, dy, align in cands:
                    d = {"at": (x, y + dy), "text": number,
                         "height": TXT, "align": align}
                    pts = text_box(d)
                    bx = (min(p[0] for p in pts), min(p[1] for p in pts),
                          max(p[0] for p in pts), max(p[1] for p in pts))
                    fits = bx[2] - bx[0] <= abs(x1 - x0) + 2
                    if (fits or not need_fit) and \
                            not any(_overlaps(bx, t) for t in taken):
                        choice = (d, bx)
                        break
                if choice:
                    break
            if choice:
                break
        if not choice:
            (x0, y), (x1, _) = runs[0]
            d = {"at": ((x0 + x1) / 2, y + 1.5), "text": number,
                 "height": TXT, "align": "BOTTOM_CENTER"}
            pts = text_box(d)
            choice = (d, (min(p[0] for p in pts), min(p[1] for p in pts),
                          max(p[0] for p in pts), max(p[1] for p in pts)))
        d, bx = choice
        c.text(d["at"], number, TXT, "P-LINE-TEXT", align=d["align"])
        taken.append(bx)


def legend_items(canvas: Canvas, blocks):
    used = []
    for p in canvas.prims:
        if p.kind == "insert" and p.data["block"] not in used:
            used.append(p.data["block"])
    order = list(blocks)
    items = [(blocks[b].description, b, {"layer": "P-EQUIP"})
             for b in sorted(used, key=order.index)]
    services = sorted({p.layer for p in canvas.prims
                       if p.layer.startswith("P-LINE-")
                       and p.layer != "P-LINE-TEXT"})
    for s in services:
        items.append((f"Process line, {s[7:]}", None, {"layer": s}))
    if any(p.layer == "P-LINE" for p in canvas.prims):
        items.append(("Process line", None, {"layer": "P-LINE"}))
    if any(p.layer == "P-SIGNAL" for p in canvas.prims):
        items.append(("Instrument signal", None,
                      {"layer": "P-SIGNAL", "linetype": "DASHED"}))
    return items
