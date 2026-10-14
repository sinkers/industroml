"""Model in, drawing set out: DXF for CAD, PDF to issue, PNG to review.

  python3 -m drawings MODEL.yaml --out DIR [--sld] [--pid] [--no-plot]

The title block is filled from the model's ``meta.drawing`` (client,
project, numbers, people, status) and ``meta.revisions``; anything missing
is left blank rather than invented. Each drawing carries a note giving the
model file and its hash, so a sheet can be traced back to the model that
made it.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from typing import Dict, List, Optional

from . import pid, sld
from .canvas import Canvas
from .model import Model, digest
from .sheet import compose
from .symbols import library

VERSION = "0.1.0"

KINDS = {
    "sld": {"title": "ELECTRICAL SINGLE LINE DIAGRAM", "suffix": "E-SLD",
            "module": sld,
            "notes": [
                "Symbols to IEC 60617 (AS/NZS 1102). Single line "
                "representation: one line is a three phase circuit.",
                "Protective devices at boards are drawn from each port's "
                "device and rating attributes in the model.",
                "Cable text: connection id, construction and route length.",
            ]},
    "pid": {"title": "PIPING AND INSTRUMENTATION DIAGRAM", "suffix": "M-PID",
            "module": pid,
            "notes": [
                "Symbols to ISO 10628-2; instrument bubbles to ISA-5.1.",
                "Line numbers: DN-service-line, or the line_number the model gives.",
                "Valves and strainers on a line are drawn in the order "
                "the model connects them.",
            ]},
}


def _info(m: Model, kind: str, sheet_no: str, model_path: str) -> Dict:
    d = dict(m.meta.get("drawing") or {})
    num = (d.get("numbers") or {}).get(kind) or d.get("number")
    if num and kind not in (d.get("numbers") or {}):
        num = f"{num}-{KINDS[kind]['suffix']}"
    revs = m.meta.get("revisions") or []
    rev = revs[-1].get("rev") if revs else d.get("revision", "")
    return {
        "client": d.get("client", ""),
        "project": d.get("project", ""),
        "site": m.meta.get("site_name", ""),
        "title": d.get("title") or m.meta.get("site_name", ""),
        "subtitle": KINDS[kind]["title"],
        "number": num or "",
        "revision": rev,
        "revisions": revs,
        "sheet": sheet_no,
        "date": d.get("date") or (revs[-1].get("date") if revs else ""),
        "drawn": d.get("drawn", "IndustroML"),
        "checked": d.get("checked", ""),
        "approved": d.get("approved", ""),
        "status": d.get("status", "Preliminary - not for construction"),
    }


def draw(model_path: str, out_dir: str, kinds=("sld", "pid"),
         plot: bool = True, mono: bool = False, flat: bool = False,
         split: str = "auto", size: Optional[str] = None) -> Dict:
    """Write each drawing in kinds for the model. Returns a report.

    split: "auto" breaks an SLD that would need an A0 sheet into an overall
    sheet and a sheet per final board; "always" and "never" force it.
    """
    from .dxf import plot as plot_dxf
    from .dxf import write

    data = Model_load(model_path)
    m = Model(data)
    blocks = library()
    sha = digest(data)
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(model_path))[0]
    report = {"model": os.path.basename(model_path), "sha256": sha,
              "generator": f"industroml drawings {VERSION}", "drawings": []}

    jobs = []                         # (kind, subtitle, diagram, plan)
    for kind in kinds:
        spec = KINDS[kind]
        diagram, plan = spec["module"].layout(m, blocks)
        if not diagram.prims:
            report["drawings"].append({"kind": kind, "skipped":
                                       "nothing to draw",
                                       "warnings": plan.warnings})
            continue
        if kind == "sld" and sld.placed(m):
            parts = sld.placed_parts(m, blocks)
            if len(parts) > 1:
                jobs += [(kind, sub, c, p) for sub, c, p in parts]
                continue
            diagram, plan = parts[0][1], parts[0][2]
        elif kind == "sld" and split != "never":
            _, fit = compose(diagram, blocks, {},
                             sld.legend_items(diagram, blocks), [])
            if (split == "always" or fit["size"] == "A0"
                    or (size and fit["size"] != size)):
                parts = sld.split(m, blocks, first_sheet=len(jobs) + 1,
                                  size=size)
                if len(parts) > 1:
                    jobs += [(kind, sub, c, p) for sub, c, p in parts]
                    continue
        if kind == "pid" and size:
            _, fit = compose(diagram, blocks, {},
                             pid.legend_items(diagram, blocks), [], size=size)
            if fit["scale"] < 0.6:
                ps = pid.parts(m, blocks)
                if len(ps) > 1:
                    jobs += [(kind, sub, c, p) for sub, c, p in ps]
                    continue
        jobs.append((kind, "", diagram, plan))

    total = len(jobs)
    per_kind = {k: sum(1 for j in jobs if j[0] == k) for k in kinds}
    seen = dict.fromkeys(kinds, 0)
    for i, (kind, sub, diagram, plan) in enumerate(jobs, 1):
        spec = KINDS[kind]
        seen[kind] += 1
        many = per_kind[kind] > 1
        notes = spec["notes"] + [
            f"Generated from {os.path.basename(model_path)} "
            f"(sha256 {sha[:12]}) by industroml drawings {VERSION}. Edit "
            "the model and regenerate rather than editing this drawing.",
        ]
        info = _info(m, kind, f"{i} OF {total}", model_path)
        if sub:
            info["subtitle"] += f" - {sub}"
        if many and info["number"]:
            info["number"] += f"-{seen[kind]:02d}"
        sheet, meta = compose(diagram, blocks, info,
                              spec["module"].legend_items(diagram, blocks),
                              notes, size=size)
        base = os.path.join(out_dir, f"{stem}_{kind}"
                            + (f"_{seen[kind]:02d}" if many else ""))
        write(sheet, blocks, base + ".dxf", paper=meta["paper_mm"], props={
            "industroml_model": os.path.basename(model_path),
            "industroml_sha256": sha, "industroml_drawing": kind},
            flat=flat)
        entry = {"kind": kind, "sheet": i, "title": info["subtitle"],
                 "warnings": plan.warnings, "nodes": len(plan.nodes),
                 **meta, "dxf": os.path.basename(base) + ".dxf"}
        if plot:
            plot_dxf(base + ".dxf", meta["paper_mm"], pdf=base + ".pdf",
                     png=base + ".png", mono=mono)
            entry.update(pdf=os.path.basename(base) + ".pdf",
                         png=os.path.basename(base) + ".png")
        report["drawings"].append(entry)
    with open(os.path.join(out_dir, f"{stem}_drawings.json"), "w") as fh:
        json.dump(report, fh, indent=1)
    return report


def Model_load(path):
    from .model import load
    return load(path)
