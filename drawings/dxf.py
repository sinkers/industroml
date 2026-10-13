"""Write a Canvas to DXF, and print a DXF to PDF and PNG.

Everything ezdxf-specific is here. The DXF is AutoCAD 2013 (AC1027), in
millimetres, drawn full size on the sheet in model space, so it opens in
AutoCAD, BricsCAD, DraftSight, LibreCAD and FreeCAD, and plots at 1:1 on the
named sheet. Symbols are blocks with attributes; layers carry colour,
linetype and lineweight, so the drawing can be restyled by layer in CAD.
"""
from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

from .canvas import Block, Canvas

#: name -> (ACI colour, linetype, lineweight in 1/100 mm)
LAYERS: Dict[str, Tuple[int, str, int]] = {
    "0": (7, "Continuous", -3),
    "SHEET-BORDER": (7, "Continuous", 25),
    "SHEET-TEXT": (7, "Continuous", 18),
    "SHEET-TITLE": (7, "Continuous", 35),
    # electrical
    "E-HV": (1, "Continuous", 35),
    "E-LV": (7, "Continuous", 35),
    "E-BUSBAR": (7, "Continuous", 100),
    "E-DEVICE": (7, "Continuous", 25),
    "E-EQUIP": (7, "Continuous", 25),
    "E-ENCL": (8, "IND-DASHED", 18),
    "E-TEXT": (7, "Continuous", 18),
    "E-CABLE-TEXT": (5, "Continuous", 18),
    "E-TAG": (7, "Continuous", 25),
    # process
    "P-EQUIP": (7, "Continuous", 50),
    "P-VALVE": (7, "Continuous", 25),
    "P-INST": (7, "Continuous", 25),
    "P-SIGNAL": (7, "IND-DASHED", 18),
    "P-LINE": (7, "Continuous", 50),
    "P-LINE-TEXT": (7, "Continuous", 18),
    "P-TEXT": (7, "Continuous", 18),
    "P-TAG": (7, "Continuous", 25),
}

#: Process line layers by service, P-LINE-<SERVICE>, coloured so a reviewer
#: can follow supply against return. Plots fine in monochrome too.
SERVICE_COLOURS = {"CHWS": 5, "CHWR": 1, "CWS": 4, "CWR": 6, "TCSS": 140,
                   "TCSR": 210, "HTWS": 30, "HTWR": 22, "HHWS": 30, "HHWR": 6,
                   "RW": 3, "PW": 4}

LINETYPES = {
    # name: (description, pattern) -- pattern is total length then dashes,
    # negative for gaps, in mm on the sheet
    "IND-DASHED": ("Dashed __ __ __", [5.0, 3.5, -1.5]),
    "IND-PHANTOM": ("Phantom ___ _ _ ___", [12.0, 6.0, -1.5, 1.5, -1.5, 1.5,
                                            -1.5]),
}

LINETYPE_ALIASES = {"DASHED": "IND-DASHED", "PHANTOM": "IND-PHANTOM"}

FONT = "arial.ttf"
STYLE = "IND"


def layer_for_service(service: Optional[str]) -> str:
    return f"P-LINE-{service.upper()}" if service else "P-LINE"


def _ensure_layer(doc, name):
    if name in doc.layers:
        return
    colour, lt, lw = LAYERS.get(name, (7, "Continuous", -3))
    if name.startswith("P-LINE-") and name != "P-LINE-TEXT":
        colour, lt, lw = SERVICE_COLOURS.get(name[7:], 7), "Continuous", 50
    doc.layers.add(name, color=colour, linetype=lt, lineweight=lw)


def _align(name):
    from ezdxf.enums import TextEntityAlignment
    return getattr(TextEntityAlignment, name)


MTEXT_ATTACH = {
    "TOP_LEFT": 1, "TOP_CENTER": 2, "TOP_RIGHT": 3, "MIDDLE_LEFT": 4,
    "MIDDLE_CENTER": 5, "MIDDLE_RIGHT": 6, "BOTTOM_LEFT": 7,
    "BOTTOM_CENTER": 8, "BOTTOM_RIGHT": 9, "LEFT": 7, "CENTER": 8,
    "RIGHT": 9, "MIDDLE": 5,
}


def _attribs(d, layer):
    a = {"layer": layer}
    lt = d.get("linetype")
    if lt:
        a["linetype"] = LINETYPE_ALIASES.get(lt, lt)
    return a


def _draw(space, doc, prims, flat=False):
    for p in prims:
        d = p.data
        layer = p.layer
        if layer != "0":
            _ensure_layer(doc, layer)
        att = _attribs(d, layer)
        if p.kind == "line":
            if d.get("width"):
                space.add_lwpolyline([d["a"], d["b"]], dxfattribs={
                    **att, "const_width": d["width"]})
            else:
                space.add_line(d["a"], d["b"], dxfattribs=att)
        elif p.kind == "polyline":
            e = space.add_lwpolyline(d["pts"], close=d.get("closed", False),
                                     dxfattribs=att)
            if d.get("width"):
                e.dxf.const_width = d["width"]
        elif p.kind == "circle":
            space.add_circle(d["c"], d["r"], dxfattribs=att)
        elif p.kind == "arc":
            space.add_arc(d["c"], d["r"], d["start"], d["end"], dxfattribs=att)
        elif p.kind == "solid":
            pts = d["pts"]
            hatch = space.add_hatch(dxfattribs={"layer": layer})
            hatch.paths.add_polyline_path(pts, is_closed=True)
            hatch.set_solid_fill(color=256)
        elif p.kind == "text":
            att["style"] = STYLE
            att["rotation"] = d.get("rotation", 0.0)
            if "\n" in d["text"]:
                e = space.add_mtext(d["text"], dxfattribs={
                    **att, "char_height": d["height"],
                    "attachment_point": MTEXT_ATTACH.get(d.get("align", "LEFT"), 7),
                    "insert": d["at"]})
                e.dxf.line_spacing_factor = 1.0
            else:
                e = space.add_text(d["text"], height=d["height"], dxfattribs=att)
                e.set_placement(d["at"], align=_align(_dxf_align(d.get("align"))))
        elif p.kind == "insert":
            ref = space.add_blockref(d["block"], d["at"], dxfattribs={
                "layer": layer, "rotation": d.get("rotation", 0.0),
                "xscale": d.get("scale", 1.0), "yscale": d.get("scale", 1.0)})
            vals = {k: str(v) for k, v in (d.get("attribs") or {}).items()
                    if v not in (None, "")}
            if vals:
                ref.add_auto_attribs(vals)
            if flat:
                # plain lines and text, for readers without blocks or
                # attributes (FreeCAD, some viewers); ATTRIBs become TEXT
                ref.explode()


def _dxf_align(a):
    a = a or "LEFT"
    return {"MIDDLE": "MIDDLE_CENTER", "CENTER": "CENTER"}.get(a, a)


def _define_block(doc, b: Block):
    blk = doc.blocks.new(b.name)
    _draw(blk, doc, b.prims)
    for ad in b.attdefs:
        e = blk.add_attdef(ad.tag, ad.at, dxfattribs={
            "height": ad.height, "rotation": ad.rotation, "style": STYLE,
            "prompt": ad.prompt or ad.tag})
        e.set_placement(ad.at, align=_align(_dxf_align(ad.align)))


def write(canvas: Canvas, blocks: Dict[str, Block], path: str,
          paper=(420.0, 297.0), props: Optional[Dict[str, str]] = None,
          flat: bool = False):
    """Write the canvas to path as DXF. Returns the ezdxf document.

    flat explodes every block after placing it, so symbols arrive as plain
    geometry and their attribute values as text. Use it for FreeCAD, whose
    DXF importer drops attributes and text inside blocks.
    """
    import ezdxf
    from ezdxf import units

    doc = ezdxf.new("R2013", setup=True)
    doc.units = units.MM
    doc.header["$MEASUREMENT"] = 1
    doc.header["$LTSCALE"] = 1.0
    doc.header["$PSLTSCALE"] = 1
    doc.header["$LIMMIN"] = (0, 0)
    doc.header["$LIMMAX"] = tuple(paper)
    doc.header["$EXTMIN"] = (0, 0, 0)
    doc.header["$EXTMAX"] = (paper[0], paper[1], 0)
    for name, (desc, pattern) in LINETYPES.items():
        if name not in doc.linetypes:
            doc.linetypes.add(name, pattern=pattern, description=desc)
    if STYLE not in doc.styles:
        doc.styles.add(STYLE, font=FONT)
    for name in LAYERS:
        _ensure_layer(doc, name)
    used = {p.data["block"] for p in canvas.prims if p.kind == "insert"}
    for name in sorted(used):
        _define_block(doc, blocks[name])
    _draw(doc.modelspace(), doc, canvas.prims, flat=flat)
    if flat:
        for name in used:
            doc.blocks.delete_block(name, safe=False)
    if props:
        for k, v in props.items():
            doc.ezdxf_metadata()[k] = str(v)
    doc.set_modelspace_vport(height=paper[1] * 1.05,
                             center=(paper[0] / 2, paper[1] / 2))
    doc.saveas(path)
    return doc


def plot(dxf_path: str, paper=(420.0, 297.0), pdf: Optional[str] = None,
         png: Optional[str] = None, dpi: int = 150, mono: bool = False):
    """Print a DXF written by write() to PDF and/or PNG at paper size."""
    import ezdxf
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import (BackgroundPolicy, ColorPolicy,
                                             Configuration, LineweightPolicy)
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    doc = ezdxf.readfile(dxf_path)
    w, h = paper
    fig = plt.figure(figsize=(w / 25.4, h / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE,
                        color_policy=(ColorPolicy.BLACK if mono
                                      else ColorPolicy.COLOR),
                        lineweight_policy=LineweightPolicy.ABSOLUTE,
                        min_lineweight=0.12)
    Frontend(RenderContext(doc), MatplotlibBackend(ax),
             config=cfg).draw_layout(doc.modelspace(), finalize=True)
    fig.set_size_inches(w / 25.4, h / 25.4)
    ax.set_position([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.set_aspect("equal")
    ax.axis("off")
    out = []
    if pdf:
        fig.savefig(pdf, format="pdf")
        out.append(pdf)
    if png:
        fig.savefig(png, dpi=dpi, facecolor="white")
        out.append(png)
    plt.close(fig)
    return out


def layers_used(prims: Iterable) -> set:
    return {p.layer for p in prims}
