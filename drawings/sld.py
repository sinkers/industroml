"""Electrical single line diagram from an IndustroML model.

Every cable in the model is a line on the diagram. Boards (switchboards,
MCCs, distribution boards) are drawn as busbars inside a dashed enclosure,
with each feeder dropping from the busbar through its protective device to
the next board or the load. Supply is at the top and load at the bottom.

How the model maps onto the drawing:

- A board's outgoing interface with a ``device`` attribute (acb, cb, mccb,
  mcb, fuse, switch_fuse, isolator) or a current rating gets that protective
  device drawn at the busbar, labelled with the rating. A board's incoming
  interface does the same at the top of its enclosure.
- Assets of a switching kind (breaker, fuse, isolator, CT, meter) with one
  cable in and one out are drawn inline on the feeder, not as nodes.
- A node fed from more than one place (a UPS with A and B inputs, an ATS)
  is drawn under its nearest supply; the other feeds are routed across to it.
- A cable between two boards that already have their own supplies is a bus
  tie, drawn between the busbars when they sit side by side.
- Cable text is the connection id, construction (runs, cores, size,
  conductor, insulation, earth) and length, beside the line.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .canvas import Canvas, text_width
from .model import Model, cable_spec, rating, volts
from .symbols import SLD_BOARDS, SLD_DEVICE, SLD_INLINE, SLD_NODES

PITCH = 26.0            # width of one feeder column, mm
TXT = 2.0               # cable and description text height
TAG = 3.0               # tag text height
LINE_GAP = TXT * 1.35


@dataclass
class Feed:
    src: str
    dst: str
    src_port: str
    dst_port: str
    devices: List[str]
    cables: List[dict]
    kind: str = "primary"          # primary, secondary, tie
    lane: int = 0


@dataclass
class Plan:
    """Everything the layout decided, kept for tests and the agent."""
    nodes: Dict[str, dict] = field(default_factory=dict)
    feeds: List[Feed] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _is_hv(m: Model, feed: Feed) -> bool:
    for c in feed.cables:
        for end in (c.get("from"), c.get("to")):
            i = m.interfaces.get(end) or {}
            if i.get("medium") == "ac_hv_3ph":
                return True
            v = (i.get("attributes") or {}).get("voltage_v")
            if isinstance(v, (int, float)) and v > 1000:
                return True
        v = (c.get("attributes") or {}).get("voltage_v")
        if isinstance(v, (int, float)) and v > 1000:
            return True
    return False


def collect(m: Model) -> List[Feed]:
    """Cables, joined through inline devices into feeds between nodes."""
    cables = [c for c in m.connections if c.get("type") == "cable"]
    outs, ins = defaultdict(list), defaultdict(list)
    for c in cables:
        a, b = m.asset_of(c.get("from", "")), m.asset_of(c.get("to", ""))
        if not a or not b or a == b:
            continue
        outs[a].append(c)
        ins[b].append(c)
    nodes = set(outs) | set(ins)
    inline = {n for n in nodes if m.kind(n) in SLD_INLINE
              and len(ins[n]) == 1 and len(outs[n]) == 1}
    feeds = []
    for c in cables:
        a = m.asset_of(c.get("from", ""))
        b = m.asset_of(c.get("to", ""))
        if not a or not b or a == b or a in inline:
            continue
        devs, chain, cur, seen = [], [c], b, set()
        while cur in inline and cur not in seen:
            seen.add(cur)
            devs.append(cur)
            nxt = outs[cur][0]
            chain.append(nxt)
            cur = m.asset_of(nxt["to"])
        feeds.append(Feed(a, cur, c["from"], chain[-1]["to"], devs, chain))
    return feeds


def _classify(m: Model, feeds: List[Feed]):
    """Mark ties and secondary feeds; return ranks and primary children."""
    boards = {n for f in feeds for n in (f.src, f.dst)
              if m.kind(n) in SLD_BOARDS}
    incoming = defaultdict(list)
    for f in feeds:
        incoming[f.dst].append(f)
    for f in feeds:
        if f.src in boards and f.dst in boards:
            named = any("TIE" in p.upper() for p in (f.src_port, f.dst_port))
            flagged = any((c.get("attributes") or {}).get("tie")
                          for c in f.cables)
            other = [g for g in incoming[f.dst] if g is not f
                     and g.src not in boards]
            if named or flagged or other:
                f.kind = "tie"
    dag = [f for f in feeds if f.kind != "tie"]
    nodes = sorted({n for f in feeds for n in (f.src, f.dst)},
                   key=lambda n: m.order.get(n, 1e9))
    outs = defaultdict(list)
    indeg = defaultdict(int)
    for f in dag:
        outs[f.src].append(f)
        indeg[f.dst] += 1
    # break cycles: a feed back to something still being walked is secondary
    state = {}

    def walk(n):
        state[n] = 1
        for f in outs[n]:
            s = state.get(f.dst)
            if s == 1:
                f.kind = "secondary"
            elif s is None:
                walk(f.dst)
        state[n] = 2

    for n in nodes:
        if indeg[n] == 0 and n not in state:
            walk(n)
    for n in nodes:
        if n not in state:
            walk(n)
    dag = [f for f in dag if f.kind == "primary"]
    rank = {n: 0 for n in nodes}
    changed = True
    guard = 0
    while changed and guard < len(nodes) + 2:
        changed, guard = False, guard + 1
        for f in dag:
            if rank[f.dst] < rank[f.src] + 1:
                rank[f.dst] = rank[f.src] + 1
                changed = True
    # one primary supply per node: the nearest one above it
    by_dst = defaultdict(list)
    for f in dag:
        by_dst[f.dst].append(f)
    for dst, fs in by_dst.items():
        fs.sort(key=lambda f: (-rank[f.src], m.order.get(f.src, 1e9)))
        for f in fs[1:]:
            f.kind = "secondary"
    return nodes, rank


class _Layout:
    def __init__(self, m: Model, feeds: List[Feed]):
        self.m = m
        self.feeds = feeds
        self.nodes, self.rank = _classify(m, feeds)
        self.slots = defaultdict(list)     # src -> feeds needing a column
        self.parent = {}
        for f in feeds:
            if f.kind == "primary":
                self.slots[f.src].append(f)
                self.parent[f.dst] = f
            elif f.kind == "secondary":
                self.slots[f.src].append(f)
        self.x: Dict[str, float] = {}
        self.slot_x: Dict[int, float] = {}
        self.w_cache: Dict[str, float] = {}
        # a source that nothing feeds and that only feeds the alternate
        # input of something (a generator into an ATS) is drawn beside
        # that thing's main supply, a level above it
        fed = {f.dst for f in feeds if f.kind != "tie"}
        n_out = defaultdict(int)
        for f in feeds:
            if f.kind != "tie":
                n_out[f.src] += 1
        self.side = defaultdict(list)
        self.side_src = set()
        for f in feeds:
            if (f.kind == "secondary" and f.src not in fed
                    and n_out[f.src] == 1 and not self.is_board(f.src)):
                self.side[f.dst].append(f)
                self.side_src.add(f.src)
                self.rank[f.src] = max(0, self.rank[f.dst] - 1)

    # ---- sizes
    def is_board(self, n):
        return self.m.kind(n) in SLD_BOARDS

    def block(self, n):
        return SLD_NODES.get(self.m.kind(n), "E-EQUIP")

    def label_lines(self, n) -> List[str]:
        a = self.m.attrs(n)
        lines = [self.m.name(n)]
        r = ", ".join(x for x in (volts(a), rating(a)) if x)
        if r:
            lines.append(r)
        return lines

    def own_width(self, n, blocks) -> float:
        if self.is_board(n):
            w = max(text_width(self.m.tag(n), TAG),
                    *(text_width(s, TXT) for s in self.label_lines(n)))
            return max(2 * w + 16, PITCH)
        bw = blocks[self.block(n)].size[0]
        if not self.slots[n]:
            n_lines = 1 + len(self.label_lines(n))
            return max(PITCH, bw + 6, n_lines * LINE_GAP + 8)
        w = max(text_width(s, TXT) for s in [self.m.tag(n)]
                + self.label_lines(n))
        return bw + 2 * (w + 4)

    def side_width(self, g, blocks) -> float:
        bw = blocks[self.block(g)].size[0]
        w = max(text_width(s, TXT) for s in [self.m.tag(g)]
                + self.label_lines(g))
        return bw + w + 14

    def main_width(self, n, blocks) -> float:
        total = 0.0
        for f in self.slots[n]:
            total += (self.width(f.dst, blocks) if f.kind == "primary"
                      else PITCH)
        return max(total, self.own_width(n, blocks))

    def width(self, n, blocks) -> float:
        if n in self.w_cache:
            return self.w_cache[n]
        self.w_cache[n] = PITCH          # guards a cycle the walk missed
        w = self.main_width(n, blocks) + sum(
            self.side_width(f.src, blocks) for f in self.side[n])
        self.w_cache[n] = w
        return w

    def place(self, n, left, blocks):
        w = self.main_width(n, blocks)
        gx = left + w
        for f in self.side[n]:
            sw = self.side_width(f.src, blocks)
            self.x[f.src] = gx + 8
            self.slot_x[id(f)] = gx + 8
            gx += sw
        slots = self.slots[n]
        total = sum(self.width(f.dst, blocks) if f.kind == "primary" else PITCH
                    for f in slots)
        start = left + (w - total) / 2
        xs = []
        for f in slots:
            if f.kind == "primary":
                self.place(f.dst, start, blocks)
                sx = self.x[f.dst]
                start += self.width(f.dst, blocks)
            else:
                sx = start + PITCH / 2
                start += PITCH
            self.slot_x[id(f)] = sx
            xs.append(sx)
        if not xs:
            self.x[n] = left + w / 2
        elif len(xs) == 1 and not self.is_board(n):
            self.x[n] = xs[0]
        else:
            self.x[n] = (min(xs) + max(xs)) / 2


def _device_for_port(m: Model, port: str) -> Optional[tuple]:
    """(block, tag, rating) for the protective device on a board port."""
    i = m.interfaces.get(port) or {}
    a = i.get("attributes") or {}
    dev = a.get("device")
    amps = a.get("rating_a", a.get("trip_a", a.get("current_a")))
    if dev in (None, "") and amps is None:
        return None
    if dev in ("none", False):
        return None
    block = SLD_DEVICE.get(str(dev or "cb").lower(), "E-CB")
    parts = []
    if amps is not None:
        parts.append(f"{amps:g}A" if isinstance(amps, float) else f"{amps}A")
    if a.get("poles"):
        parts.append(f"{a['poles']}P")
    if a.get("breaking_capacity_ka"):
        parts.append(f"{a['breaking_capacity_ka']}kA")
    tag = a.get("tag") or port.split(".", 1)[-1]
    return block, tag, " ".join(parts)


def _inline_device(m: Model, asset: str) -> tuple:
    a = m.attrs(asset)
    block = SLD_INLINE.get(m.kind(asset), "E-CB")
    amps = a.get("rating_a", a.get("current_a"))
    parts = []
    if amps is not None:
        parts.append(f"{amps}A")
    if a.get("curve"):
        parts.append(f"C{a['curve']}" if len(str(a["curve"])) == 1
                     else str(a["curve"]))
    if a.get("breaking_capacity_ka"):
        parts.append(f"{a['breaking_capacity_ka']}kA")
    if a.get("ratio"):
        parts.append(str(a["ratio"]))
    return block, m.tag(asset), " ".join(parts)


def _dev_attribs(block, tag, rate, blocks):
    tags = {d.tag for d in blocks[block].attdefs}
    out = {}
    if "TAG" in tags:
        out["TAG"] = tag
    if "RATING" in tags:
        out["RATING"] = rate
    if "RATIO" in tags:
        out["RATIO"] = rate or tag
    return out


def _rotated_lines(c: Canvas, x, y_start, lines, layer, h=TXT, downward=False):
    """Text lines turned 90 degrees, stacked to the right of x.

    Reads upwards from y_start, or ends at y_start reading upwards when
    downward is set (so the text hangs below a point).
    """
    for i, s in enumerate(lines):
        hh = TAG if (i == 0 and downward) else h
        xi = x + hh + i * (h * 1.35) + (TAG - h if (downward and i) else 0)
        c.text((xi, y_start), s, hh, layer, rotation=90,
               align="BOTTOM_RIGHT" if downward else "BOTTOM_LEFT")


def layout(m: Model, blocks) -> (Canvas, Plan):
    feeds = collect(m)
    plan = Plan(feeds=feeds)
    if not feeds:
        plan.warnings.append("the model has no cables between assets")
        return Canvas(), plan
    L = _Layout(m, feeds)
    rank, nodes = L.rank, L.nodes

    # x: each root tree in model order, side by side
    roots = [n for n in nodes if n not in L.parent and n not in L.side_src]
    left = 0.0
    for r in roots:
        if r in L.x:
            continue
        L.place(r, left, blocks)
        left += L.width(r, blocks) + 10

    # what each feed needs vertically
    def devs(f):
        out = []
        d = _device_for_port(m, f.src_port) if L.is_board(f.src) else None
        if d:
            out.append(d)
        out.extend(_inline_device(m, a) for a in f.devices)
        return out

    def incomer(n, port):
        return _device_for_port(m, port) if L.is_board(n) else None

    def dev_h(ds):
        return sum(blocks[b].size[1] + 3 for b, _, _ in ds)

    def label_len(f):
        return max(text_width(s, TXT) for s in cable_spec(f.cables[-1]))

    max_rank = max(rank.values())
    band = defaultdict(float)          # space above a rank's top
    lanes = defaultdict(int)           # secondary feeds routed into a rank
    for f in feeds:
        if f.kind == "tie":
            continue
        r = rank[f.dst]
        # a board's outgoing devices sit inside its enclosure, counted there
        own = 0 if L.is_board(f.src) else dev_h(devs(f))
        need = own + label_len(f) + 8
        if f.kind == "secondary":
            f.lane = lanes[r]
            lanes[r] += 1
        band[r] = max(band[r], need)
    for r in range(max_rank + 1):
        band[r] += lanes[r] * 4 + (4 if lanes[r] else 0)

    def below(n) -> float:
        """Height a node takes below its top line."""
        if L.is_board(n):
            outs = [devs(f) for f in L.slots[n]]
            inc = max((dev_h([incomer(n, f.dst_port)]) for f in feeds
                       if f.dst == n and incomer(n, f.dst_port)), default=0)
            label_h = TAG + 3 + len(L.label_lines(n)) * LINE_GAP
            return (max(inc + 4, label_h + 2)
                    + max((dev_h(d) for d in outs), default=0) + 6)
        h = blocks[L.block(n)].size[1]
        if not L.slots[n]:
            lines = [m.tag(n)] + L.label_lines(n)
            return h + 3 + max(text_width(s, TAG if i == 0 else TXT)
                               for i, s in enumerate(lines))
        return h + (6 if len(L.slots[n]) > 1 else 0)

    node_h = defaultdict(float)
    for n in nodes:
        node_h[rank[n]] = max(node_h[rank[n]], below(n))
    supply_roots = [r for r in roots if m.kind(r) in ("transformer",
                                                      "ring_main_unit")]
    y_top, cursor = {}, -(22.0 if supply_roots else 0.0)
    for r in range(max_rank + 1):
        cursor -= band[r] if r else 0
        y_top[r] = cursor
        cursor -= node_h[r]

    c = Canvas()
    port_xy = {}          # node -> {'top': (x,y), 'top2': ..., 'bus': (x0,x1,y)}
    enclosure_w = {}

    # ---- nodes
    for n in nodes:
        x, yt = L.x[n], y_top[rank[n]]
        info = {"rank": rank[n], "x": x, "y": yt}
        if L.is_board(n):
            xs = [L.slot_x[id(f)] for f in L.slots[n]] or [x]
            half = L.own_width(n, blocks) / 2 - 4
            x0 = min(min(xs) - 8, x - half)
            x1 = max(max(xs) + 8, x + half)
            incs = [incomer(n, f.dst_port) for f in feeds
                    if f.dst == n and f.kind != "tie"]
            inc_h = max((dev_h([d]) for d in incs if d), default=0)
            label_h = TAG + 3 + len(L.label_lines(n)) * LINE_GAP
            yb = yt - max(inc_h + 4, label_h + 2)
            out_h = max((dev_h(devs(f)) for f in L.slots[n]), default=0)
            c.polyline([(x0, yb), (x1, yb)], "E-BUSBAR", width=1.0)
            c.rect((x0 - 4, yb - out_h - 4), (x1 + 4, yt), "E-ENCL")
            a = m.attrs(n)
            c.text((x0 - 2, yt - 2), m.tag(n), TAG, "E-TAG",
                   align="TOP_LEFT")
            for i, s in enumerate(L.label_lines(n)):
                c.text((x0 - 2, yt - 2 - TAG - 1.5 - i * LINE_GAP), s, TXT,
                       "E-TEXT", align="TOP_LEFT")
            if a.get("fault_ka") or a.get("breaking_capacity_ka"):
                pass
            port_xy[n] = {"top": (x, yt), "bus": (x0, x1, yb),
                          "inc_h": inc_h}
            enclosure_w[n] = (x0 - 4, x1 + 4)
            info.update(kind="board", busbar=[x0, x1, yb])
        else:
            b = blocks[L.block(n)]
            h = b.size[1]
            cy = yt - h / 2
            a = m.attrs(n)
            names = {d.tag for d in b.attdefs}
            att = {}
            if "TAG" in names:
                att["TAG"] = m.tag(n)
            if "RATING" in names:
                att["RATING"] = rating(a)
            if "VOLTS" in names:
                att["VOLTS"] = volts(a)
            if "VECTOR" in names:
                att["VECTOR"] = a.get("vector_group", "")
            if "LABEL" in names:
                att["LABEL"] = m.kind(n).replace("_", " ").upper()[:12]
            c.insert(L.block(n), (x, cy), "E-EQUIP", attribs=att)
            ports = {k: (x + px, cy + py) for k, (px, py) in b.ports.items()}
            ports.setdefault("top", (x, cy + h / 2))
            ports.setdefault("bottom", (x, cy - h / 2))
            if "top2" not in ports:
                ports["top2"] = (ports["top"][0] + 4, ports["top"][1])
            if not L.slots[n]:
                lines = [] if "TAG" in names else [m.tag(n)]
                lines += [] if "RATING" in names else L.label_lines(n)
                if lines and "TAG" not in names:
                    _rotated_lines(c, x - (len(lines) * TXT * 1.35) / 2 - 0.5,
                                   cy - h / 2 - 2, lines, "E-TEXT",
                                   downward=True)
            elif "TAG" not in names:
                tx = x + b.size[0] / 2 + 3
                c.text((tx, cy + 2), m.tag(n), TAG, "E-TAG",
                       align="BOTTOM_LEFT")
                for i, s in enumerate(L.label_lines(n)):
                    c.text((tx, cy - i * LINE_GAP), s, TXT, "E-TEXT",
                           align="TOP_LEFT")
            if len(L.slots[n]) > 1:
                xs = [L.slot_x[id(f)] for f in L.slots[n]]
                yb = ports["bottom"][1] - 5
                c.line(ports["bottom"], (x, yb), "E-LV")
                c.line((min(xs), yb), (max(xs), yb), "E-LV", width=0.35)
                ports["branch"] = yb
            port_xy[n] = ports
            info.update(kind=m.kind(n), block=L.block(n))
        plan.nodes[n] = info

    # supply arrows above transformers and RMUs that nothing feeds
    for r in supply_roots:
        x, y = port_xy[r]["top"]
        c.insert("E-SUPPLY", (x, y + 7), "E-HV")
        pv = m.attrs(r).get("primary_voltage_v")
        label = "INCOMING SUPPLY" + (f" {pv / 1000:g} kV" if pv else "")
        c.text((x + 3, y + 12), label, TXT, "E-TEXT", align="MIDDLE_LEFT")

    # ---- feeds
    sec_count = defaultdict(int)
    for f in feeds:
        if f.kind == "tie":
            continue
        layer = "E-HV" if _is_hv(m, f) else "E-LV"
        sx = L.slot_x[id(f)]
        if L.is_board(f.src):
            y = port_xy[f.src]["bus"][2]
        elif "branch" in port_xy[f.src]:
            y = port_xy[f.src]["branch"]
        else:
            y = port_xy[f.src]["bottom"][1]
        for block, tag, rate in devs(f):
            h = blocks[block].size[1]
            top = y - 3
            c.line((sx, y), (sx, top), layer)
            c.insert(block, (sx, top - h / 2), "E-DEVICE",
                     attribs=_dev_attribs(block, tag, rate, blocks))
            y = top - h
        # where it lands
        dst = f.dst
        if L.is_board(dst):
            inc = incomer(dst, f.dst_port)
            ex, ey = port_xy[dst]["top"]
            if f.kind == "secondary":
                k = sec_count[dst]
                sec_count[dst] += 1
                x0, x1, _ = port_xy[dst]["bus"]
                ex = x0 + 6 + 10 * k if ex - x0 > 20 else x1 - 6 - 10 * k
        else:
            key = "top2" if f.kind == "secondary" else "top"
            ex, ey = port_xy[dst][key]
            inc = None
        spec = cable_spec(f.cables[-1])
        if f.kind == "primary" and abs(ex - sx) < 0.01:
            c.line((sx, y), (sx, ey), layer)
            _rotated_lines(c, sx + 1.4, ey + 3, spec, "E-CABLE-TEXT")
        else:
            lane_y = ey + 6 + 4 * f.lane
            c.polyline([(sx, y), (sx, lane_y), (ex, lane_y), (ex, ey)], layer)
            _rotated_lines(c, sx + 1.4, lane_y + 3, spec, "E-CABLE-TEXT")
        if L.is_board(dst):
            yb = port_xy[dst]["bus"][2]
            yy = ey
            if inc:
                block, tag, rate = inc
                h = blocks[block].size[1]
                c.line((ex, yy), (ex, yy - 3), layer)
                c.insert(block, (ex, yy - 3 - h / 2), "E-DEVICE",
                         attribs=_dev_attribs(block, tag, rate, blocks))
                yy = yy - 3 - h
            c.line((ex, yy), (ex, yb), layer)

    # ---- ties: between busbars side by side, else routed like a feed
    for f in feeds:
        if f.kind != "tie":
            continue
        a, b = f.src, f.dst
        (ax0, ax1, ay), (bx0, bx1, by) = port_xy[a]["bus"], port_xy[b]["bus"]
        if abs(ay - by) > 0.01:
            plan.warnings.append(f"bus tie {f.cables[0]['id']} joins boards at "
                                 "different levels; drawn as a link")
        if ax1 < bx0:
            p, q = (ax1, ay), (bx0, by)
        else:
            p, q = (ax0, ay), (bx1, by)
        ds = [_device_for_port(m, f.src_port)] + \
             [_inline_device(m, d) for d in f.devices]
        ds = [d for d in ds if d]
        y = max(ay, by) + 0.0
        mid = (p[0] + q[0]) / 2
        if abs(ay - by) < 0.01 and ds:
            total = sum(blocks[d[0]].size[1] + 2 for d in ds)
            x = mid - total / 2
            c.line(p, (x, y), "E-LV", width=1.0)
            for block, tag, rate in ds:
                h = blocks[block].size[1]
                c.insert(block, (x + h / 2 + 1, y), "E-DEVICE", rotation=90,
                         attribs=_dev_attribs(block, tag, rate, blocks))
                x += h + 2
            c.line((x, y), q, "E-LV", width=1.0)
        else:
            top = max(ay, by) + 10
            c.polyline([p, (p[0], top), (q[0], top), q], "E-LV")
        c.text((mid, y - 9), "BUS TIE " + f.cables[0]["id"], TXT, "E-TEXT",
               align="TOP_CENTER")

    return c, plan


def legend_items(canvas: Canvas, blocks):
    used = []
    for p in canvas.prims:
        if p.kind == "insert" and p.data["block"] not in used:
            used.append(p.data["block"])
    order = list(blocks)
    items = [(blocks[b].description, b, {"layer": "E-DEVICE"})
             for b in sorted(used, key=order.index)]
    layers = {p.layer for p in canvas.prims}
    if "E-BUSBAR" in layers:
        items.append(("Busbar", None, {"layer": "E-BUSBAR", "width": 1.0}))
    if "E-LV" in layers:
        items.append(("LV cable", None, {"layer": "E-LV"}))
    if "E-HV" in layers:
        items.append(("HV cable", None, {"layer": "E-HV"}))
    if "E-ENCL" in layers:
        items.append(("Switchboard enclosure", None,
                      {"layer": "E-ENCL", "linetype": "DASHED"}))
    return items
