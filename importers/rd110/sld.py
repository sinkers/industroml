#!/usr/bin/env python3
"""Read Schneider Electric's Reference Design 110 one-line (DXF) into IndustroML.

  python3 -m importers.rd110.sld RD110_2.2_Elec_Oneline_EN_R0.dxf \\
      [--variant paris|singapore] [--out examples/models/rd110_elec_paris.yaml]

RD110 is Schneider Electric's public EcoStruxure reference design for a
10 MW GB300 data centre (se.com). Its one-line drawing RD110_2.2 has three
sheets in one DXF: the IT room (four powertrains A-D), and the mechanical
plant twice, sized for Paris and for Singapore. A model is the IT room plus
one mechanical variant.

How the drawing is read:

- **Breakers** are the only real block (`uni006`, 240 of them). Each has its
  designation printed at (+2.1, +0.9) from the insert and its frame and trip
  ratings, as ATTDEF *tags*, at (+1.75, -5.95) and (+1.79, -9.57). The
  insert point is the top terminal; the bottom is 9.63 lower.
- **Boards** are the 1.0-wide polylines; their name (`... SWBD ...`) and
  rating (`5000A, 400V, TN-S, 66kA AT 1 SEC`) sit at the right-hand end.
  Shorter ones in the IT room are busway sections.
- **Transformers** are two overlapping circles, **generators** one larger
  circle, each with a pill label (`TX A`, `GEN A`) and its ratings beside.
- **UPSs** are the dashed enclosures labelled `GALAXY VXL UPS` / `GALAXY VL`.
- **Cables** are lines on `E-AC CABLE` and `E-CABLING-AC-SYS A`. Each
  breaker's terminals are traced along them to whatever they reach:
  another breaker, a board bus, a source, a UPS, or a labelled load.
- **Cross-sheet feeds** (`FED FROM MECH SWBD A CB FW-4A [RD110_2.2.2]`) join
  a mechanical board's breaker to its load on the IT-room sheet.

Everything keeps its position on the sheet (schematic placement and cable
paths), so the generator can redraw it in the same arrangement.
"""
from __future__ import annotations

import argparse
import collections
import math
import os
import re
import sys

import ezdxf

SHEETS = {  # model-space window of each sheet, from its layout viewport
    "IT": (313.0, 55.0, 3052.0, 1904.0),
    "paris": (3653.0, 603.0, 4727.0, 1328.0),
    "singapore": (5227.0, 595.0, 6292.0, 1314.0),
}
CABLE_LAYERS = {"E-AC CABLE", "E-CABLING-AC-SYS A"}
BRK_DROP = 14.25 * 0.6759           # top to bottom terminal of uni006
TOL = 0.2                           # this drawing is coarse: ends miss by 0.1
P_DESIG = re.compile(r"^[A-Z][A-Z0-9 ]*-[A-Z0-9.]+$")
P_FRAME = re.compile(r"^(\d{2,5})\s*AF$")
P_TRIP = re.compile(r"^(\d{1,5})\s*AT$")
P_BOARD = re.compile(r"(\d{2,5})\s*A\s*,\s*(\d{3,4})\s*V\s*,\s*(TN-[SC])\s*,"
                     r"\s*(\d{1,3})\s*kA", re.I)


def plain(e):
    """Text of TEXT, MTEXT or ATTDEF (whose tag is the value here)."""
    t = e.dxftype()
    if t == "TEXT":
        return e.dxf.text
    if t == "MTEXT":
        return e.plain_text()
    if t == "ATTDEF":
        return e.dxf.tag
    return None


def where(e):
    """Where a text sits: its alignment point when it is aligned (the
    insert point of aligned TEXT and ATTDEF is not where it is drawn)."""
    if e.dxftype() in ("TEXT", "ATTDEF") and (e.dxf.get("halign", 0) or
                                              e.dxf.get("valign", 0)) \
            and e.dxf.hasattr("align_point"):
        return (float(e.dxf.align_point.x), float(e.dxf.align_point.y))
    if e.dxf.hasattr("insert"):
        return (float(e.dxf.insert.x), float(e.dxf.insert.y))
    return None


def sheet_of(p):
    for name, (x0, y0, x1, y1) in SHEETS.items():
        if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            return name
    return None


class Drawing:
    def __init__(self, path):
        self.doc = ezdxf.readfile(path)
        msp = self.doc.modelspace()
        self.texts = []                                 # (text, pos, entity)
        for e in msp:
            t = plain(e)
            p = where(e)
            if t and p:
                t = " ".join(str(t).split())
                if t:
                    self.texts.append((t, p, e))
        self.inserts = list(msp.query('INSERT[name=="uni006"]'))
        self.msp = msp

    def text_near(self, p, dx, dy, pattern=None):
        """Text whose insert lies within p + dx-range, dy-range."""
        best = None
        for t, q, _ in self.texts:
            ox, oy = q[0] - p[0], q[1] - p[1]
            if dx[0] <= ox <= dx[1] and dy[0] <= oy <= dy[1]:
                if pattern and not pattern.match(t):
                    continue
                d = abs(ox) + abs(oy)
                if best is None or d < best[0]:
                    best = (d, t, q)
        return best[1:] if best else None


def merge_buses(d):
    """Thick polylines (const width >= 0.9), joined where they overlap."""
    raw = collections.defaultdict(list)
    for e in d.msp.query("LWPOLYLINE"):
        if e.dxf.get("const_width", 0) < 0.9:
            continue
        pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
        xs = [p[0] for p in pts]
        y = round(sum(p[1] for p in pts) / len(pts), 1)
        raw[y].append((min(xs), max(xs)))
    out = []
    for y, spans in raw.items():
        spans.sort()
        cur = list(spans[0])
        for a, b in spans[1:]:
            if a <= cur[1] + 0.5:
                cur[1] = max(cur[1], b)
            else:
                out.append((cur[0], cur[1], y))
                cur = [a, b]
        out.append((cur[0], cur[1], y))
    return out


def cable_segments(d):
    segs = []
    for e in d.msp:
        if e.dxf.layer not in CABLE_LAYERS:
            continue
        if e.dxftype() == "LINE":
            segs.append(((float(e.dxf.start.x), float(e.dxf.start.y)),
                         (float(e.dxf.end.x), float(e.dxf.end.y))))
        elif e.dxftype() == "LWPOLYLINE" and e.dxf.get("const_width", 0) < 0.9:
            pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
            if e.closed:
                pts.append(pts[0])
            segs.extend(zip(pts, pts[1:]))
    return [(a, b) for a, b in segs if math.dist(a, b) > 1e-6]


class Net:
    """Cable network: points joined by segments, split where an end lands
    on another segment."""

    def __init__(self, segs):
        self.adj = collections.defaultdict(set)
        self.pts = {}
        ends = [p for s in segs for p in s]
        for a, b in segs:
            cuts = [p for p in ends if on_segment(p, a, b)]
            pts = sorted([a, b] + cuts, key=lambda q: (q[0] - a[0]) ** 2
                         + (q[1] - a[1]) ** 2)
            for p, q in zip(pts, pts[1:]):
                self.link(self.key(p), self.key(q))

    def split_crossings(self, max_gap=8.0):
        """A cable crossing another is drawn with a short break in it. Where
        the near side of the break lands on the other cable, the two are
        joined into one node, making a false tee. Find a cable that arrives
        square on at a node, with nothing carrying on from it there but a
        loose end just across the break, and move it off the node onto its
        own continuation."""
        moved = 0
        for k in list(self.pts):
            p = self.pts[k]
            for n in list(self.adj[k]):
                q = self.pts[n]
                d = (p[0] - q[0], p[1] - q[1])
                ld = math.hypot(*d)
                if not ld or min(abs(d[0]), abs(d[1])) > 0.05 * ld:
                    continue                    # only square runs
                u = (d[0] / ld, d[1] / ld)
                others = [self.pts[m] for m in self.adj[k] if m != n]
                if not others or any(
                        (o[0] - p[0]) * u[0] + (o[1] - p[1]) * u[1] > 0.3
                        for o in others):
                    continue                    # a through run or a corner
                if not any(abs((o[0] - p[0]) * u[0] + (o[1] - p[1]) * u[1])
                           < 0.3 for o in others):
                    continue                    # nothing square across it
                for m, r in list(self.pts.items()):
                    if m == k or len(self.adj[m]) != 1:
                        continue
                    v = (r[0] - p[0], r[1] - p[1])
                    gap = math.hypot(*v)
                    if not (0.3 < gap <= max_gap) or \
                            v[0] * u[0] + v[1] * u[1] < 0.98 * gap:
                        continue
                    nk = ("x", k, n)
                    self.pts[nk] = p
                    self.adj[k].discard(n)
                    self.adj[n].discard(k)
                    self.link(nk, n)
                    self.link(nk, m)
                    moved += 1
                    break
        return moved

    def bridge_gaps(self, max_gap=8.0, keep=()):
        """A cable crossing another is drawn with a short break in it:
        join two ends that face each other along one line. Points in keep
        (breaker terminals) are never joined this way."""
        ends = [k for k in self.pts if len(self.adj[k]) == 1
                and not any(math.dist(self.pts[k], q) < 0.6 for q in keep)]
        pairs = []
        for i, a in enumerate(ends):
            pa = self.pts[a]
            na = self.pts[next(iter(self.adj[a]))]
            da = (pa[0] - na[0], pa[1] - na[1])
            for b in ends[i + 1:]:
                pb = self.pts[b]
                gap = math.dist(pa, pb)
                if gap > max_gap or (abs(pa[0] - pb[0]) > 0.3
                                     and abs(pa[1] - pb[1]) > 0.3):
                    continue
                nb = self.pts[next(iter(self.adj[b]))]
                db = (pb[0] - nb[0], pb[1] - nb[1])
                v = (pb[0] - pa[0], pb[1] - pa[1])
                # each end must point at the other, not merely not away
                if da[0] * v[0] + da[1] * v[1] > 0.95 * math.hypot(*da) * gap and \
                        db[0] * -v[0] + db[1] * -v[1] > 0.95 * math.hypot(*db) * gap:
                    pairs.append((gap, a, b))
        used = set()
        for gap, a, b in sorted(pairs):
            if a in used or b in used:
                continue
            used |= {a, b}
            self.link(a, b)
        return len(used) // 2

    def key(self, p):
        k = (round(p[0] / TOL), round(p[1] / TOL))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                kk = (k[0] + dx, k[1] + dy)
                if kk in self.pts:
                    return kk
        self.pts[k] = p
        return k

    def link(self, a, b):
        if a != b:
            self.adj[a].add(b)
            self.adj[b].add(a)

    def near(self, p, r=0.6):
        return [k for k, q in self.pts.items() if math.dist(p, q) <= r]


def on_segment(p, a, b):
    if math.dist(p, a) < TOL or math.dist(p, b) < TOL:
        return False
    if abs(a[0] - b[0]) < 1e-6 and abs(p[0] - a[0]) < TOL:
        return min(a[1], b[1]) < p[1] < max(a[1], b[1])
    if abs(a[1] - b[1]) < 1e-6 and abs(p[1] - a[1]) < TOL:
        return min(a[0], b[0]) < p[0] < max(a[0], b[0])
    return False


def read(path):
    d = Drawing(path)
    breakers = []
    for i in d.inserts:
        x, y = float(i.dxf.insert.x), float(i.dxf.insert.y)
        sh = sheet_of((x, y))
        if not sh:
            continue
        # designation above, frame then trip below it; the offsets vary a
        # little from board to board, so the nearest of each kind wins
        name = d.text_near((x, y), (0.5, 4.5), (-1.0, 4.0), P_DESIG)
        frame = d.text_near((x, y), (0.0, 4.5), (-9.0, 0.0), P_FRAME)
        trip = d.text_near((x, y), (0.0, 4.5), (-12.0, -3.0), P_TRIP)
        breakers.append({
            "name": name[0] if name else None, "top": (x, y),
            "bottom": (x, y - BRK_DROP), "sheet": sh,
            "frame_a": int(P_FRAME.match(frame[0]).group(1)) if frame else None,
            "trip_a": int(P_TRIP.match(trip[0]).group(1)) if trip else None})
    buses = []
    for x0, x1, y in merge_buses(d):
        sh = sheet_of((x0, y))
        if not sh:
            continue
        label = d.text_near((x1, y), (-200, 12), (0, 22),
                            re.compile(r".*SWBD.*")) or \
            d.text_near((x0, y), (-12, 200), (0, 22), re.compile(r".*SWBD.*"))
        rate = d.text_near((x1, y), (-200, 12), (-6, 22), P_BOARD) or \
            d.text_near((x0, y), (-12, 200), (-6, 22), P_BOARD)
        buses.append({"x0": x0, "x1": x1, "y": y, "sheet": sh,
                      "name": label[0] if label else None,
                      "rating": rate[0] if rate else None})
    return d, breakers, buses


class Symbols:
    """Everything a cable can end at, other than a breaker or a bus."""

    def __init__(self, d, sheets):
        self.d = d
        msp = d.msp
        circles = [(float(c.dxf.center.x), float(c.dxf.center.y),
                    float(c.dxf.radius), c.dxf.layer) for c in msp.query("CIRCLE")]
        circles = [c for c in circles if sheet_of(c[:2]) in sheets]
        texts = [(t, q) for t, q, _ in d.texts if sheet_of(q) in sheets]
        self.sources = []        # {id, kind, centre, r, ratings}
        for t, q in texts:
            m = re.match(r"^(MECH )?(TX|GEN) ([A-D])$", t)
            if not m:
                continue
            want = 9.0 if m.group(2) == "TX" else 13.4
            cs = [c for c in circles if abs(c[2] - want) < 0.3
                  and -60 < c[0] - q[0] < 60 and -30 < c[1] - q[1] < 15]
            if not cs:
                continue
            if m.group(2) == "TX":
                cs = sorted(cs, key=lambda c: math.dist(c[:2], q))[:2]
                cx = sum(c[0] for c in cs) / len(cs)
                cy = sum(c[1] for c in cs) / len(cs)
                r = want + abs(cs[0][1] - cs[-1][1]) / 2
            else:
                c = min(cs, key=lambda c: math.dist(c[:2], q))
                cx, cy, r = c[0], c[1], c[2]
            near = [t2 for t2, q2 in texts if -5 < q2[0] - q[0] < 120
                    and -40 < q2[1] - q[1] < 2 and t2 != t]
            prefix = "MECH-" if m.group(1) else ""
            self.sources.append({
                "id": f"{prefix}{m.group(2)}-{m.group(3)}",
                "kind": "transformer" if m.group(2) == "TX" else "generator",
                "centre": (cx, cy), "r": r, "notes": near,
                "label": t})
        self.loads = []          # circles with a label inside
        for cx, cy, r, lay in circles:
            if r < 10 or lay != "M-OBJECT-DETAILS":
                continue
            inside = [t for t, q in texts if math.dist(q, (cx, cy)) < r]
            if inside and not any(math.dist(l["centre"], (cx, cy)) < 1.0
                                  for l in self.loads):
                self.loads.append({"centre": (cx, cy), "r": r,
                                   "label": " ".join(inside)})
        self.boxes = []          # closed rectangles with a label inside
        for e in msp.query("LWPOLYLINE"):
            if not e.closed and len(e) != 5:
                continue
            pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            b = (min(xs), min(ys), max(xs), max(ys))
            if sheet_of(b[:2]) not in sheets or b[2] - b[0] < 15:
                continue
            inside = [(t, q) for t, q in texts
                      if b[0] <= q[0] <= b[2] and b[1] <= q[1] <= b[3]]
            label = " ".join(t for t, _ in inside)
            if "DESIGN NOT" in label or "SWBD" in label or re.search(
                    r"(ELECTRICAL|MECH) ROOM [A-D]\b", label):
                continue                  # a room or board frame, not a load
            if re.search(r"GALAXY", label) and "SWBD" not in label:
                kind = "ups"
            elif re.search(r"FEEDS|EXTERNAL|CHILLED WATER", label):
                kind = "load"
            else:
                continue
            area = (b[2] - b[0]) * (b[3] - b[1])
            self.boxes.append({"box": b, "label": label, "kind": kind,
                               "area": area})
        # nested boxes: keep the smallest box round each label
        self.boxes.sort(key=lambda x: x["area"])
        kept = []
        for bx in self.boxes:
            # a bigger box round one already kept is its frame: drop it
            if not any(inside_box(((k["box"][0] + k["box"][2]) / 2,
                                   (k["box"][1] + k["box"][3]) / 2), bx["box"])
                       and k["kind"] == bx["kind"] for k in kept):
                kept.append(bx)
        self.boxes = kept
        self.labels = [(t, q) for t, q in texts]


def inside_box(p, b, pad=0.0):
    return b[0] - pad <= p[0] <= b[2] + pad and b[1] - pad <= p[1] <= b[3] + pad


def build(path, variant):
    d, breakers, buses = read(path)
    sheets = {"IT", variant}
    breakers = [b for b in breakers if b["sheet"] in sheets]
    buses = [b for b in buses if b["sheet"] in sheets]
    # one breaker per position; spares named; detail-drawing devices out
    seen, kept = set(), []
    spare = 0
    for b in sorted(breakers, key=lambda b: (b["sheet"], b["top"][0], -b["top"][1])):
        k = (round(b["top"][0], 1), round(b["top"][1], 1))
        if k in seen:
            continue
        seen.add(k)
        if not b["name"]:
            near = d.text_near(b["top"], (0.5, 4.5), (-1.0, 4.0),
                               re.compile(r"^SPARE$"))
            if not near:
                continue                     # tap-off detail, not the SLD
            spare += 1
            b["name"] = f"SPARE-{spare}"
        kept.append(b)
    breakers = kept
    # the source repeats a designation now and then (two "AIIT-3.2C" on
    # IT CRITICAL SWBD C): keep both, number the repeat, flag it
    names = collections.Counter()
    for b in sorted(breakers, key=lambda b: (b["sheet"], b["top"][0], -b["top"][1])):
        names[b["name"]] += 1
        if names[b["name"]] > 1:
            b["designation"] = b["name"]
            b["name"] = f"{b['name']} DUP{names[b['name']]}"
    sym = Symbols(d, sheets)
    ups_boxes = [bx for bx in sym.boxes if bx["kind"] == "ups"]
    # the cable network, without what is drawn inside the UPS enclosures
    segs = [(a, b) for a, b in cable_segments(d)
            if sheet_of(a) in sheets and not any(
                inside_box(a, u["box"], -0.5) and inside_box(b, u["box"], -0.5)
                for u in ups_boxes)]
    net = Net(segs)
    net.split_crossings()
    net.bridge_gaps(keep=[q for b in breakers for q in (b["top"], b["bottom"])])

    # what a point touches
    def on_bus(p, tol=1.2):
        for bu in buses:
            if bu["x0"] - 0.5 <= p[0] <= bu["x1"] + 0.5 and abs(p[1] - bu["y"]) < tol:
                return bu
        return None

    terminals = {}
    for b in breakers:
        terminals[("T", b["name"])] = b["top"]
        terminals[("B", b["name"])] = b["bottom"]

    def thing_at(p):
        for (side, name), q in terminals.items():
            if math.dist(p, q) < 0.6:
                return ("breaker", name, side)
        bu = on_bus(p)
        if bu:
            return ("bus", id(bu), None)
        for s in sym.sources:
            if math.dist(p, s["centre"]) < s["r"] + 2.0:
                return ("source", s["id"], None)
        for u in ups_boxes:
            if inside_box(p, u["box"], 2.5):
                return ("ups", id(u), None)
        for ld in sym.loads:
            if math.dist(p, ld["centre"]) < ld["r"] + 2.5:
                return ("load", id(ld), None)
        return None

    busways = [bu for bu in buses if not bu["name"]]
    breaker_names = {b["name"] for b in breakers}
    rating_text = re.compile(r"^\d+\s*(A|AF|AT|kA|kW|kVA|V)$|^ION|^PM8|^iEM")

    def resolve_end(p):
        """A cable that stops short of its load: arrowheads, gaps."""
        for u in ups_boxes:
            if inside_box(p, u["box"], 4.0):
                return ("ups", id(u), None)
        for ld in sym.loads:
            if math.dist(p, ld["centre"]) < ld["r"] + 6.0:
                return ("load", id(ld), None)
        for bx in sym.boxes:
            b = bx["box"]
            if bx["kind"] == "load" and b[0] - 4 <= p[0] <= b[2] + 4 \
                    and b[1] - 4 <= p[1] <= b[3] + 18:
                return ("box", id(bx), None)
        for bw in busways:
            if bw["x0"] - 8 <= p[0] <= bw["x1"] + 8 and abs(p[1] - bw["y"]) < 6:
                return ("bus", id(bw), None)
        # a busway feeder ends at the "800A" feed box at the busway's end
        for t, q in sym.labels:
            if re.match(r"^\d{3,4}A$", t) and math.dist(p, q) < 9:
                ends = [(min(abs(q[0] - bw["x0"]), abs(q[0] - bw["x1"])), bw)
                        for bw in busways if abs(q[1] - bw["y"]) < 6]
                if ends:
                    dist, bw = min(ends, key=lambda e: e[0])
                    if dist < 25:
                        return ("bus", id(bw), None)
        best = None
        for t, q in sym.labels:
            if rating_text.match(t) or t in breaker_names:
                continue
            dd = math.dist(p, q)
            if dd < 6 and (best is None or dd < best[0]):
                best = (dd, t)
        if best:
            return ("label", best[1], None)
        return ("end", p, None)

    def trace(start):
        """From a point, along cables, to everything first reached.
        Returns [(thing, path of points)]."""
        found = []
        starts = [k for k, q in net.pts.items() if math.dist(q, start) < 0.6]
        if not starts:
            # a cable drawn stopping a little short of the terminal
            starts = [k for k, q in net.pts.items() if math.dist(q, start) < 1.5]
        prev = {k: None for k in starts}
        queue = collections.deque(starts)
        while queue:
            k = queue.popleft()
            p = net.pts[k]
            hit = thing_at(p)
            if hit and math.dist(p, start) > 0.6:
                path, j = [], k
                while j is not None:
                    path.append(net.pts[j])
                    j = prev[j]
                found.append((hit, [start] + path[::-1]))
                continue
            nxt = [n for n in net.adj[k] if n not in prev]
            if not nxt and len(net.adj[k]) <= 1 and math.dist(p, start) > 0.6:
                path, j = [], k
                while j is not None:
                    path.append(net.pts[j])
                    j = prev[j]
                found.append((resolve_end(p), [start] + path[::-1]))
            for n in nxt:
                prev[n] = k
                queue.append(n)
        return found

    return d, breakers, buses, sym, net, thing_at, terminals, trace


def slug(text):
    """An IndustroML id. Dots are kept out: an interface id is ASSET.PORT,
    so a dot in the asset part (CDU-1.3) would make it ambiguous."""
    s = str(text).strip().replace(".", "_")
    s = re.sub(r"[^A-Za-z0-9_]+", "-", s).strip("-_").upper()
    return re.sub(r"-{2,}", "-", s)


def r2(p):
    return [round(float(p[0]), 2), round(float(p[1]), 2)]


#: UPS ratings are not on the drawing; RD110DSR3 gives them.
UPS_KW = {"IT": 1000.0}         # Galaxy VXL, three per powertrain (3000 kW)
SOURCE_DOC = "RD110_2.2 Electrical one-line R0"


def to_model(path, variant):
    d, breakers, buses, sym, net, thing_at, terminals, trace = build(path, variant)
    assets, interfaces, connections = {}, {}, []
    containers = [{"id": "SITE", "name": "RD110 reference data centre",
                   "type": "site"}]

    def asset(aid, name, kind, domain="electrical", container="SITE",
              attrs=None, at=None, size=None):
        if aid in assets:
            return aid
        a = {"id": aid, "name": name, "kind": kind, "domain": domain,
             "container": container,
             "attributes": {"source": SOURCE_DOC, **(attrs or {})}}
        if at is not None:
            a["schematic"] = {"at": r2(at)}
            if size:
                a["schematic"]["size"] = [round(size[0], 2), round(size[1], 2)]
        assets[aid] = a
        return aid

    def port(aid, name, role=None):
        pid = f"{aid}.{slug(name)}"
        if pid not in interfaces:
            i = {"id": pid, "asset": aid, "domain": "electrical",
                 "medium": "ac_lv_3ph"}
            if role:
                i["role"] = role
            interfaces[pid] = i
        return pid

    # boards and busways
    bus_id = {}
    bw_n = collections.Counter()
    for bu in buses:
        if bu["name"]:
            aid = slug(bu["name"])
            m = P_BOARD.search(bu["rating"] or "")
            attrs = {"bus": [r2((bu["x0"], bu["y"])), r2((bu["x1"], bu["y"]))]}
            if m:
                attrs.update(current_a=int(m.group(1)), voltage_v=int(m.group(2)),
                             earthing=m.group(3).upper(), fault_ka=int(m.group(4)))
            asset(aid, bu["name"].title().replace("Swbd", "SWBD"), "switchboard",
                  attrs=attrs, at=((bu["x0"] + bu["x1"]) / 2, bu["y"]),
                  size=(bu["x1"] - bu["x0"], 2.0))
        else:
            continue                             # busways: below
        bus_id[id(bu)] = aid
    # busways: RD110 draws most busways in two halves either side of the
    # tap-off notes, at one height. Halves less than a note's width apart
    # are one busway. Busways stacked one above another serve one rack
    # group, named by the "RACKS a - b" label printed just below the stack;
    # one group is unlabelled and takes the rack numbers no label claims.
    runs = sorted((bu for bu in buses if not bu["name"] and bu["y"] >= 700),
                  key=lambda b: (round(b["y"]), b["x0"]))
    ways = []                                    # [x0, x1, y, [runs]]
    for bu in runs:
        w = ways[-1] if ways else None
        if w and abs(w[2] - bu["y"]) < 1.0 and bu["x0"] - w[1] <= 80:
            w[1] = max(w[1], bu["x1"])
            w[3].append(bu)
        else:
            ways.append([bu["x0"], bu["x1"], bu["y"], [bu]])
    stacks = []
    for w in sorted(ways, key=lambda w: (-w[2], w[0])):         # top down
        for st in stacks:
            if any(min(w[1], o[1]) - max(w[0], o[0]) > 5
                   and abs(w[2] - o[2]) <= 25 for o in st):
                st.append(w)
                break
        else:
            stacks.append([w])
    labels = [(t, q) for t, q in sym.labels if re.match(r"^RACKS \d+ - \d+$", t)]
    named = []
    for st in stacks:
        x0, x1 = min(w[0] for w in st), max(w[1] for w in st)
        y0 = min(w[2] for w in st)
        cand = [(abs(q[1] - (y0 - 15)), t, q) for t, q in labels
                if x0 - 80 <= q[0] <= x1 + 80 and y0 - 45 <= q[1] <= y0 + 5]
        named.append((st, min(cand)[1:] if cand else None))
    for i, (st, lab) in enumerate(named):
        if lab is None:
            lo = min(n for n in range(1, 97) if not any(
                int(a) <= n <= int(b) for a, b in (re.findall(r"\d+", t)
                                                    for t, _ in labels)))
            x0 = min(w[0] for w in st)
            y0 = min(w[2] for w in st)
            named[i] = (st, (f"RACKS {lo} - {lo + 15}", (x0 + 40, y0 - 20)))
    for st, (text, q) in sorted(named, key=lambda n: int(re.findall(r"\d+", n[1][0])[0])):
        group = slug(text)
        for j, (x0, x1, y, parts) in enumerate(sorted(st, key=lambda w: -w[2]), 1):
            aid = f"BUSWAY-{group.replace('RACKS-', 'R')}-{j}"
            asset(aid, f"Busway {j} for {text.lower()}", "busbar_section",
                  attrs={"current_a": 800, "rack_group": group,
                         "rack_group_at": r2(q),
                         "bus": [r2((x0, y)), r2((x1, y))]},
                  at=((x0 + x1) / 2, y), size=(x1 - x0, 2.0))
            for bu in parts:
                bus_id[id(bu)] = aid
    # rack groups: each pod row's busways feed its racks; the drawing
    # gives the composition in a note, the same for every group
    for aid in [a for a in assets if a.startswith("BUSWAY-")]:
        group = assets[aid]["attributes"]["rack_group"]
        q = assets[aid]["attributes"]["rack_group_at"]
        gid = f"RACK-GROUP-{group.replace('RACKS-', '')}"
        asset(gid, f"Racks {group.replace('RACKS-', '')}: 8 AI racks (142 kW) "
                   f"and 8 networking racks (15 kW)", "load",
              attrs={"ai_racks": 8, "ai_rack_kw": 142, "net_racks": 8,
                     "net_rack_kw": 15, "power_kw": 8 * 142 + 8 * 15,
                     "feeds": "each AI rack 8 x 63 A, two from each of "
                              "busways A-D; each networking rack 2 x 32 A"},
              at=q, size=(30.0, 8.0) if q else None)
        bw = assets[aid]["attributes"]["bus"]
        mid = ((bw[0][0] + bw[1][0]) / 2, bw[0][1])
        connections.append({
            "id": f"C-{aid}-{gid}", "type": "cable",
            "from": port(aid, "TAP-OFFS", "out"), "to": port(gid, f"IN-{aid}", "in"),
            "attributes": {"source": SOURCE_DOC,
                           "description": "tap-off units to the racks"},
            "schematic": {"path": [r2(mid), r2(q)] if q else [r2(mid), r2(mid)]}})

    # sources
    for src in sym.sources:
        notes = " ".join(src["notes"])
        attrs = {}
        if src["kind"] == "transformer":
            m = re.search(r"(\d{3,5})\s*kVA", notes)
            if m:
                attrs["power_kva"] = int(m.group(1))
            m = re.search(r"(\d{1,3})\s*kV\b", notes)
            if m:
                attrs["primary_voltage_v"] = int(m.group(1)) * 1000
            m = re.search(r"(\d{3})/(\d{3})", notes)
            if m:
                attrs["secondary_voltage_v"] = int(m.group(1))
            m = re.search(r"(\d+(?:\.\d+)?)%+\s*IMP", notes)
            if m:
                attrs["impedance_pct"] = float(m.group(1))
            if re.search(r"D\s*-\s*Y", notes):
                attrs["vector_group"] = "Dyn"
        else:
            m = re.search(r"(\d{3,5})\s*kW\s*/\s*(\d{3,5})\s*kVA", notes)
            if m:
                attrs.update(power_kw=int(m.group(1)), power_kva=int(m.group(2)))
            m = re.search(r"(\d{3})/(\d{3})", notes)
            if m:
                attrs["voltage_v"] = int(m.group(1))
            if "DCP" in notes:
                attrs["rating_basis"] = "DCP (data centre power)"
        name = ("Transformer " if src["kind"] == "transformer" else
                "Generator ") + src["label"]
        asset(src["id"], name, src["kind"], attrs=attrs, at=src["centre"],
              size=(2 * src["r"], 2 * src["r"]))
        if src["kind"] == "transformer":
            # the supply arrow above each transformer
            up = (src["centre"][0], src["centre"][1] + src["r"] + 22)
            hv = asset(f"HV-{src['id']}", f"HV supply to {src['label']}",
                       "utility_supply", attrs={
                           "voltage_v": attrs.get("primary_voltage_v")},
                       at=up, size=(8, 14))
            connections.append({
                "id": f"C-HV-{src['id']}", "type": "cable",
                "from": port(hv, "OUT", "out"), "to": port(src["id"], "HV", "in"),
                "attributes": {"source": SOURCE_DOC, "voltage_class": "HV"},
                "schematic": {"path": [r2((up[0], up[1] - 7)),
                                       r2((up[0], src["centre"][1] + src["r"]))]}})
    # UPSs, loads, boxes
    ups_names = {}
    for u in [b for b in sym.boxes if b["kind"] == "ups"]:
        b = u["box"]
        m = re.search(r"(\d{2,4})\s*kW", u["label"])
        sheet = sheet_of(b[:2])
        kw = int(m.group(1)) if m else UPS_KW.get(sheet)
        model = "Galaxy VL" if "GALAXY VL" in u["label"] else "Galaxy VXL"
        ups_names[id(u)] = (b, kw, model)
    load_id = {}
    for ld in sym.loads:
        lab = ld["label"].replace(" P", "")
        m = re.search(r"(FW-\d|CDU \d\.\d|HT CH-\d|CH-\d)$", lab)
        tag = slug(m.group(1)) if m else slug(lab)
        kind = ("crah" if tag.startswith("FW") else "cdu" if tag.startswith("CDU")
                else "chiller")
        model = lab.split(" ")[0]
        aid = asset(tag, lab, kind, domain="mechanical",
                    attrs={"model": model}, at=ld["centre"],
                    size=(2 * ld["r"], 2 * ld["r"]))
        load_id[id(ld)] = aid
    box_id = {}
    box_n = collections.Counter()
    for bx in sorted((b for b in sym.boxes if b["kind"] == "load"),
                     key=lambda b: (b["box"][0], b["box"][1])):
        b = bx["box"]
        label = bx["label"]
        if "[RD110_2.2.1]" in label:
            box_id[id(bx)] = ("xref", label)
            continue
        kind = "pump" if "PUMP" in label else "load"
        # lettered in drawing order, A side first; the mechanical sheet's
        # own boxes take a MECH prefix, as its boards do
        pre = "" if sheet_of(b[:2]) == "IT" else "MECH-"
        box_n[pre + slug(label)] += 1
        aid = asset(f"{pre}{slug(label)[:24].strip('-')}-"
                    f"{'ABCDEFGH'[box_n[pre + slug(label)] - 1]}",
                    label.title(), kind,
                    domain="mechanical" if kind == "pump" else "electrical",
                    attrs={"group": True}, at=((b[0] + b[2]) / 2, (b[1] + b[3]) / 2),
                    size=(b[2] - b[0], b[3] - b[1]))
        box_id[id(bx)] = aid

    # breakers
    brk_id = {}
    for b in breakers:
        aid = "CB-" + slug(b["name"])
        frame = b["frame_a"]
        kind = "acb_breaker" if frame and frame >= 1000 else "mccb_breaker"
        board = None
        bt = thing_at(b["top"])
        for side in ("top", "bottom"):
            for bu in buses:
                q = b[side]
                # a breaker sits a short stub (up to ~8) off its bus
                if bu["x0"] - 0.5 <= q[0] <= bu["x1"] + 0.5 and \
                        abs(q[1] - bu["y"]) < 10.0 and bu["name"]:
                    board = bus_id[id(bu)]
        attrs = {"designation": b.get("designation", b["name"])}
        if "designation" in b:
            attrs["check"] = (f"source drawing repeats designation "
                              f"{b['designation']}; this is the repeat")
        if frame:
            attrs["frame_a"] = frame
        if b["trip_a"]:
            attrs["trip_a"] = b["trip_a"]
            attrs["rating_a"] = b["trip_a"]
        asset(aid, f"Breaker {b['name']}", kind, container=board or "SITE",
              attrs=attrs, at=((b["top"][0] + b["bottom"][0]) / 2,
                               (b["top"][1] + b["bottom"][1]) / 2),
              size=(4.0, BRK_DROP))
        brk_id[b["name"]] = aid

    # cables: what each breaker's line side and load side reach
    seen_pairs = set()
    n = [0]

    def cable(frm, to, path, extra=None):
        key = (frm, to)
        if key in seen_pairs or frm == to:
            return
        seen_pairs.add(key)
        n[0] += 1
        connections.append({"id": f"C{n[0]:04d}", "type": "cable",
                            "from": frm, "to": to,
                            "attributes": {"source": SOURCE_DOC, **(extra or {})},
                            "schematic": {"path": [r2(p) for p in path]}})

    def target(hit, brk, side):
        """Interface on what a trace reached, and the role it plays."""
        kind, ref, extra = hit
        role_far = "out" if side == "T" else "in"
        if kind == "bus":
            aid = bus_id.get(ref)
            return port(aid, f"{'IN' if side == 'B' else 'OUT'}-{brk}",
                        "in" if side == "B" else "out") if aid else None
        if kind == "source":
            return port(ref, "LV", "out")
        if kind == "ups":
            b, kw, model = next(v for k, v in ups_names.items() if k == ref)
            uid = "UPS-" + re.sub(r"^M?UPS(IN|OUT|BYP)-", "", brk)
            if "MUPS" in brk:
                uid = "UPS-M" + re.sub(r"^MUPS(IN|OUT|BYP)-", "", brk)
            asset(uid, f"UPS {uid[4:]} ({model})", "ups",
                  attrs={"power_kw": kw, "model": model},
                  at=((b[0] + b[2]) / 2, (b[1] + b[3]) / 2),
                  size=(b[2] - b[0], b[3] - b[1]))
            return port(uid, "OUT" if side == "T" else "IN",
                        "out" if side == "T" else "in")
        if kind == "load":
            return port(load_id[ref], "SUPPLY-" + brk[-1], "in")
        if kind == "box":
            v = box_id.get(ref)
            if isinstance(v, tuple):
                # a feed to the IT room sheet: the load of the same name
                m = re.match(r"^(FW-\d|CDU-\d\.\d)[AB]$", brk)
                if m and slug(m.group(1)) in assets:
                    return port(slug(m.group(1)), "SUPPLY-" + brk[-1], "in")
                return None
            return port(v, f"IN-{brk}", "in")
        if kind == "label":
            text = ref
            aid = slug(text)
            q = next((q for t, q in sym.labels if t == text), None)
            asset(aid, text.title(), "load", attrs={"label": text},
                  at=q, size=(4.0, 4.0) if q else None)
            return port(aid, "IN", "in")
        return None

    xref_later = []
    for b in breakers:
        bid = brk_id[b["name"]]
        for side, q in (("T", b["top"]), ("B", b["bottom"])):
            mine = port(bid, "LINE" if side == "T" else "LOAD",
                        "in" if side == "T" else "out")
            touch = thing_at(q)
            hits = [] if touch and touch[0] == "bus" else trace(q)
            if touch and touch[0] == "bus":
                hits = [(touch, [q, (q[0], buses_y(buses, touch[1]))])]
            for hit, path in hits:
                if hit[0] == "breaker":
                    other, oside = hit[1], hit[2]
                    if oside == side:
                        assets[bid]["attributes"]["interlocked_with"] = \
                            brk_id[other]
                        continue
                    if side == "B":
                        cable(mine, port(brk_id[other], "LINE", "in"), path)
                    continue
                tgt = target(hit, b["name"], side)
                if tgt is None:
                    if hit[0] == "box":
                        xref_later.append((b["name"], path))
                    continue
                extra = {"busbar": True} if hit[0] == "bus" and \
                    len(path) <= 2 else None
                if side == "T":
                    cable(tgt, mine, path[::-1], extra)
                else:
                    cable(mine, tgt, path, extra)
        # incomers: the line from the source to its breaker is not on a
        # cable layer; the breaker is named after its source
        m = re.match(r"^(MECH )?(TX|GEN)-([A-D])$", b["name"])
        if m:
            sid = f"{'MECH-' if m.group(1) else ''}{m.group(2)}-{m.group(3)}"
            if sid in assets:
                src = assets[sid]["schematic"]["at"]
                cable(port(sid, "LV", "out"), port(bid, "LINE", "in"),
                      [src, b["top"]])
    model = {
        "meta": {"format": "IndustroML", "version": "0.1",
                 "site_name": f"Schneider Electric RD110 ({variant.title()})",
                 "schematic": {"units": "RD110_2.2 drawing units",
                               "source": "RD110_2.2_Elec_Oneline_EN_R0 (se.com)"},
                 "drawing": {"client": "Schneider Electric",
                             "project": "RD110 10 MW GB300",
                             "numbers": {"sld": f"RD110-2.2-IML-{variant[:3].upper()}"},
                             "status": "Read from a public reference design - "
                                       "not for construction"},
                 "revisions": [{"rev": "A", "date": "2026-10-14",
                                "description": "Read from RD110_2.2 R0",
                                "by": "IML", "chk": ""}]},
        "containers": containers,
        "assets": list(assets.values()),
        "interfaces": list(interfaces.values()),
        "connections": connections,
    }
    report = {"breakers": len(breakers), "assets": len(assets),
              "cables": len(connections),
              "unconnected_breakers": [b["name"] for b in breakers
                                       if not any(c["from"].startswith(brk_id[b["name"]] + ".")
                                                  or c["to"].startswith(brk_id[b["name"]] + ".")
                                                  for c in connections)]}
    return model, report


def buses_y(buses, ref):
    for bu in buses:
        if id(bu) == ref:
            return bu["y"]
    return 0.0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dxf")
    ap.add_argument("--variant", choices=["paris", "singapore"], default="paris")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    import yaml
    model, report = to_model(a.dxf, a.variant)
    out = a.out or f"rd110_elec_{a.variant}.yaml"
    with open(out, "w") as fh:
        fh.write("# Read from Schneider Electric's public Reference Design 110 "
                 "one-line\n# (RD110_2.2, se.com) by importers/rd110/sld.py.\n")
        yaml.safe_dump(model, fh, sort_keys=False, width=100)
    print(out, report)


if __name__ == "__main__":
    main()
