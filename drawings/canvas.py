"""A drawing as a list of primitives, in millimetres on the sheet.

Layout code draws here, not into a DXF, so a layout can be tested without
ezdxf and moved or scaled as a whole before it is written. dxf.py turns a
Canvas into a DXF; nothing else knows about the DXF format.

Symbols are blocks: a Block is a little Canvas with attribute definitions,
drawn once and inserted wherever the symbol is used, as a CAD user would
expect. Attribute values travel on the insert, so a breaker's rating can be
edited in CAD without exploding anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Point = Tuple[float, float]

#: Character width as a fraction of text height, for a plain sans font.
#: Used only to keep labels apart; the CAD font decides the real width.
CHAR_W = 0.7


def text_width(text: str, height: float) -> float:
    longest = max((len(s) for s in str(text).split("\n")), default=0)
    return longest * height * CHAR_W


def text_lines(text: str) -> int:
    return len(str(text).split("\n"))


@dataclass
class Prim:
    kind: str                      # line, polyline, circle, arc, text, insert, solid
    layer: str
    data: dict


@dataclass
class AttDef:
    tag: str
    at: Point
    height: float
    rotation: float = 0.0
    align: str = "LEFT"            # LEFT, CENTER, RIGHT, MIDDLE_CENTER, ...
    prompt: str = ""


@dataclass
class Block:
    name: str
    description: str               # what the legend calls it
    standard: str = ""             # where the symbol comes from
    prims: List[Prim] = field(default_factory=list)
    attdefs: List[AttDef] = field(default_factory=list)
    ports: Dict[str, Point] = field(default_factory=dict)
    size: Tuple[float, float] = (10.0, 10.0)   # w, h, centred on the origin

    @property
    def canvas(self) -> "Canvas":
        c = Canvas()
        c.prims = self.prims
        return c


class Canvas:
    def __init__(self):
        self.prims: List[Prim] = []

    # geometry
    def line(self, a: Point, b: Point, layer="0", **kw):
        self.prims.append(Prim("line", layer, {"a": tuple(a), "b": tuple(b), **kw}))

    def polyline(self, pts, layer="0", closed=False, width=0.0, **kw):
        self.prims.append(Prim("polyline", layer, {
            "pts": [tuple(p) for p in pts], "closed": closed,
            "width": width, **kw}))

    def rect(self, lo: Point, hi: Point, layer="0", **kw):
        (x0, y0), (x1, y1) = lo, hi
        self.polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer,
                      closed=True, **kw)

    def circle(self, c: Point, r: float, layer="0", **kw):
        self.prims.append(Prim("circle", layer, {"c": tuple(c), "r": r, **kw}))

    def arc(self, c: Point, r: float, start: float, end: float, layer="0", **kw):
        """Counter-clockwise from start to end, degrees."""
        self.prims.append(Prim("arc", layer, {"c": tuple(c), "r": r,
                                              "start": start, "end": end, **kw}))

    def solid(self, pts, layer="0", **kw):
        """A filled triangle or quadrilateral."""
        self.prims.append(Prim("solid", layer, {"pts": [tuple(p) for p in pts],
                                                **kw}))

    def text(self, at: Point, text: str, height: float, layer="0",
             align="LEFT", rotation=0.0, **kw):
        if text is None or text == "":
            return
        self.prims.append(Prim("text", layer, {
            "at": tuple(at), "text": str(text), "height": height,
            "align": align, "rotation": rotation, **kw}))

    def insert(self, block: str, at: Point, layer="0", attribs=None,
               rotation=0.0, scale=1.0):
        self.prims.append(Prim("insert", layer, {
            "block": block, "at": tuple(at), "rotation": rotation,
            "scale": scale, "attribs": dict(attribs or {})}))

    # whole-canvas operations
    def extend(self, other: "Canvas"):
        self.prims.extend(other.prims)

    def bounds(self, blocks: Optional[Dict[str, Block]] = None):
        """(xmin, ymin, xmax, ymax) of everything drawn, text included."""
        xs, ys = [], []

        def add(p):
            xs.append(p[0])
            ys.append(p[1])

        for p in self.prims:
            d = p.data
            if p.kind == "line":
                add(d["a"]), add(d["b"])
            elif p.kind in ("polyline", "solid"):
                for q in d["pts"]:
                    add(q)
            elif p.kind in ("circle", "arc"):
                (x, y), r = d["c"], d["r"]
                add((x - r, y - r)), add((x + r, y + r))
            elif p.kind == "text":
                for q in text_box(d):
                    add(q)
            elif p.kind == "insert":
                b = (blocks or {}).get(d["block"])
                w, h = b.size if b else (0, 0)
                x, y = d["at"]
                s = d.get("scale", 1.0)
                if d.get("rotation") in (90, 270, -90):
                    w, h = h, w
                add((x - w * s / 2, y - h * s / 2)), add((x + w * s / 2, y + h * s / 2))
        if not xs:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(xs), min(ys), max(xs), max(ys))

    def transformed(self, dx=0.0, dy=0.0, k=1.0) -> "Canvas":
        """A copy scaled by k about the origin, then moved by (dx, dy)."""
        def tp(p):
            return (p[0] * k + dx, p[1] * k + dy)

        out = Canvas()
        for p in self.prims:
            d = dict(p.data)
            if p.kind == "line":
                d["a"], d["b"] = tp(d["a"]), tp(d["b"])
            elif p.kind in ("polyline", "solid"):
                d["pts"] = [tp(q) for q in d["pts"]]
                if "width" in d:
                    d["width"] = d["width"] * k
            elif p.kind in ("circle", "arc"):
                d["c"], d["r"] = tp(d["c"]), d["r"] * k
            elif p.kind == "text":
                d["at"], d["height"] = tp(d["at"]), d["height"] * k
            elif p.kind == "insert":
                d["at"], d["scale"] = tp(d["at"]), d.get("scale", 1.0) * k
            out.prims.append(Prim(p.kind, p.layer, d))
        return out


def text_box(d) -> List[Point]:
    """Corners of a text's rough extent, honouring alignment and 0/90 rotation."""
    x, y = d["at"]
    h = d["height"]
    w = text_width(d["text"], h)
    n = text_lines(d["text"])
    th = h * (1 + 0.6 * (n - 1)) if n > 1 else h
    a = d.get("align", "LEFT")
    if "CENTER" in a or a == "MIDDLE":
        x0 = -w / 2
    elif "RIGHT" in a:
        x0 = -w
    else:
        x0 = 0.0
    if a.startswith("MIDDLE"):
        y0 = -th / 2
    elif a.startswith("TOP"):
        y0 = -th
    else:
        y0 = 0.0 if n == 1 else -(th - h)
    corners = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + th), (x0, y0 + th)]
    rot = d.get("rotation", 0) % 360
    if rot == 90:
        corners = [(-v, u) for u, v in corners]
    elif rot == 270:
        corners = [(v, -u) for u, v in corners]
    elif rot == 180:
        corners = [(-u, -v) for u, v in corners]
    return [(x + u, y + v) for u, v in corners]
