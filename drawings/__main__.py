"""python3 -m drawings MODEL --out DIR [--sld] [--pid] [--no-plot] [--mono]"""
import argparse
import os
import json
import sys

from .build import draw


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="python3 -m drawings",
        description="Draw an IndustroML model as DXF single line diagrams "
                    "and P&IDs, with PDF and PNG prints.")
    ap.add_argument("model")
    ap.add_argument("--out", default="drawings_out")
    ap.add_argument("--sld", action="store_true", help="only the SLD")
    ap.add_argument("--pid", action="store_true", help="only the P&ID")
    ap.add_argument("--no-plot", action="store_true",
                    help="DXF only, no PDF or PNG")
    ap.add_argument("--mono", action="store_true",
                    help="print in black only")
    ap.add_argument("--flat", action="store_true",
                    help="explode symbols to plain lines and text (for "
                         "FreeCAD, which drops block attributes)")
    a = ap.parse_args(argv)
    kinds = [k for k, on in (("sld", a.sld), ("pid", a.pid)) if on] or \
        ["sld", "pid"]
    r = draw(a.model, a.out, kinds, plot=not a.no_plot, mono=a.mono,
             flat=a.flat)
    for d in r["drawings"]:
        print(d["kind"], d.get("size", ""),
              os.path.join(a.out, d["dxf"]) if "dxf" in d else d["skipped"])
        for w in d.get("warnings", []):
            print("  warning:", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
