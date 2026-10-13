"""Drawings from a model: what the SLD and P&ID layouts decide, the sheet,
and the DXF that comes out.

Layout tests need nothing beyond PyYAML. DXF tests need ezdxf and skip
without it.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from drawings import pid, sld  # noqa: E402
from drawings.canvas import Canvas  # noqa: E402
from drawings.model import Model, cable_spec, load, pipe_line_number  # noqa: E402
from drawings.sheet import compose  # noqa: E402
from drawings.symbols import library  # noqa: E402

MODELS = os.path.join(ROOT, "examples", "models")
DC = os.path.join(MODELS, "dc_hall_demo.yaml")
RAVEN = os.path.join(MODELS, "ravenbrook_site.yaml")

try:
    import ezdxf  # noqa: F401
    HAVE_EZDXF = True
except ImportError:
    HAVE_EZDXF = False


@pytest.fixture(scope="module")
def blocks():
    return library()


@pytest.fixture(scope="module")
def dc():
    return Model(load(DC))


@pytest.fixture(scope="module")
def raven():
    return Model(load(RAVEN))


# ---------------------------------------------------------------- symbols

def test_every_symbol_has_a_description_and_size(blocks):
    for name, b in blocks.items():
        assert b.description, name
        assert b.size[0] > 0 and b.size[1] > 0, name
        assert b.prims, name


def test_electrical_inline_symbols_have_top_and_bottom_ports(blocks):
    for name in ("E-CB", "E-ACB", "E-ISO", "E-FUSE", "E-CT", "E-TX"):
        assert {"top", "bottom"} <= set(blocks[name].ports), name


# -------------------------------------------------------------------- SLD

def test_inline_breaker_is_drawn_on_the_feeder_not_as_a_node(raven):
    feeds = sld.collect(raven)
    f = next(f for f in feeds if f.dst == "VFD-P1")
    assert f.src == "MCC1"
    assert f.devices == ["BRK-VFD1"]
    assert [c["id"] for c in f.cables] == ["C-MCC1-BRK", "C-BRK-VFD"]


def test_every_cable_is_drawn_once(dc, blocks):
    feeds = sld.collect(dc)
    drawn = [c["id"] for f in feeds for c in f.cables]
    cables = [c["id"] for c in dc.connections if c["type"] == "cable"]
    assert sorted(drawn) == sorted(cables)


def test_bus_tie_secondary_feeds_and_side_sources(dc, blocks):
    canvas, plan = sld.layout(dc, blocks)
    kinds = {f.cables[0]["id"]: f.kind for f in plan.feeds}
    assert kinds["C-TIE"] == "tie"
    # the STS is fed from A and B: one feed is drawn under A, one across
    assert sorted([kinds["C-STS-A"], kinds["C-STS-B"]]) == \
        ["primary", "secondary"]
    # generators sit level with their transformers, above the ATS
    n = plan.nodes
    assert n["GEN-A"]["rank"] == n["TX-A"]["rank"] == n["ATS-A"]["rank"] - 1
    assert n["GEN-A"]["x"] > n["TX-A"]["x"]
    assert not plan.warnings


def test_board_ports_put_protective_devices_at_the_busbar(dc, blocks):
    canvas, plan = sld.layout(dc, blocks)
    devs = [p.data for p in canvas.prims if p.kind == "insert"
            and p.data["attribs"].get("TAG") == "F-UPS"]
    assert devs and devs[0]["block"] == "E-ACB"
    assert devs[0]["attribs"]["RATING"] == "1000A 65kA"


def test_cable_text_carries_construction_and_length(dc):
    c = next(c for c in dc.connections if c["id"] == "C-TX-A")
    assert cable_spec(c) == ["C-TX-A",
                             "4 x (1C 630mm² Cu XLPE) + E 300mm²",
                             "L = 30 m, ladder"]


def test_hv_cables_go_on_the_hv_layer(dc, blocks):
    canvas, _ = sld.layout(dc, blocks)
    layers = {p.layer for p in canvas.prims}
    assert {"E-HV", "E-LV", "E-BUSBAR", "E-ENCL"} <= layers


def test_supply_is_above_load(dc, blocks):
    _, plan = sld.layout(dc, blocks)
    n = plan.nodes
    assert n["UTIL"]["y"] > n["TX-A"]["y"] > n["MSB-A"]["y"] > \
        n["UPS-A"]["y"] > n["PDU-A1"]["y"]


# -------------------------------------------------------------------- P&ID

def test_every_pipe_is_drawn_once(dc):
    lines, _ = pid.collect(dc)
    drawn = [p["id"] for ln in lines for p in ln.pipes]
    pipes = [c["id"] for c in dc.connections if c["type"] == "pipe"]
    assert sorted(drawn) == sorted(pipes)


def test_valves_are_inline_in_model_order(dc):
    lines, equipment = pid.collect(dc)
    ln = next(l for l in lines if l.src == "PMP-1")
    assert ln.dst == "CH-1"
    assert ln.items == ["NRV-1", "BFV-103"]
    assert "NRV-1" not in equipment


def test_closed_loop_starts_at_the_chillers(dc, blocks):
    _, plan = pid.layout(dc, blocks)
    n = plan.nodes
    assert n["CH-1"]["rank"] == n["CH-2"]["rank"] == 0
    returns = {(l.src, l.dst) for l in plan.lines if l.kind == "return"}
    assert returns == {("PMP-1", "CH-1"), ("PMP-2", "CH-2")}
    assert n["HDR-S"]["rank"] < n["CDU-1"]["rank"] < n["HDR-R"]["rank"]


def test_line_numbers(dc):
    c = next(c for c in dc.connections if c["id"] == "L-C1S-1")
    assert pipe_line_number(c) == "DN150-CHWS-L-C1S-1"
    c = dict(c, attributes={**c["attributes"], "line_number": "150-CHWS-001"})
    assert pipe_line_number(c) == "150-CHWS-001"


def test_instrument_bubbles_take_letters_from_the_tag(dc, blocks):
    canvas, _ = pid.layout(dc, blocks)
    bubbles = {p.data["attribs"].get("FUNC") + p.data["attribs"].get("LOOP")
               for p in canvas.prims if p.kind == "insert"
               and p.data["block"] == "P-INST"}
    assert bubbles == {"TT101", "PT102"}


def test_line_numbers_do_not_overlap(dc, blocks):
    from drawings.pid import _box, _overlaps
    canvas, _ = pid.layout(dc, blocks)
    boxes = [_box(p, blocks) for p in canvas.prims
             if p.kind == "text" and p.layer == "P-LINE-TEXT"]
    clashes = [(a, b) for i, a in enumerate(boxes) for b in boxes[i + 1:]
               if _overlaps(a, b, pad=-0.2)]
    assert not clashes


# ------------------------------------------------------------------- sheet

def test_small_diagram_goes_on_a3_full_size(blocks):
    c = Canvas()
    c.rect((0, 0), (100, 80))
    _, meta = compose(c, blocks, {"title": "T"}, [], ["n"])
    assert meta["size"] == "A3" and meta["scale"] == 1.0


def test_huge_diagram_is_scaled_onto_a0(blocks):
    c = Canvas()
    c.rect((0, 0), (5000, 3000))
    sheet, meta = compose(c, blocks, {"title": "T"}, [], ["n"])
    assert meta["size"] == "A0" and meta["scale"] < 1
    x0, y0, x1, y1 = sheet.bounds(blocks)
    assert x1 <= 1189 + 0.01 and y1 <= 841 + 0.01


# --------------------------------------------------------------------- DXF

@pytest.mark.skipif(not HAVE_EZDXF, reason="ezdxf not installed")
def test_dxf_is_clean_and_carries_attributes(tmp_path):
    from drawings.build import draw
    r = draw(DC, str(tmp_path), plot=False)
    import ezdxf
    for d in r["drawings"]:
        doc = ezdxf.readfile(os.path.join(tmp_path, d["dxf"]))
        assert doc.dxfversion == "AC1027"
        assert doc.header["$INSUNITS"] == 4
        assert not doc.audit().errors
        msp = doc.modelspace()
        assert msp.query("INSERT")
    sld_doc = ezdxf.readfile(os.path.join(tmp_path, r["drawings"][0]["dxf"]))
    tags = {a.dxf.text for i in sld_doc.modelspace().query("INSERT")
            for a in i.attribs if a.dxf.tag == "TAG"}
    assert {"TX-A", "GEN-B", "F-UPS"} <= tags
    assert sld_doc.ezdxf_metadata()["industroml_drawing"] == "sld"


@pytest.mark.skipif(not HAVE_EZDXF, reason="ezdxf not installed")
def test_flat_dxf_has_no_blocks(tmp_path):
    from drawings.build import draw
    r = draw(RAVEN, str(tmp_path), kinds=("sld",), plot=False, flat=True)
    import ezdxf
    doc = ezdxf.readfile(os.path.join(tmp_path, r["drawings"][0]["dxf"]))
    assert not doc.modelspace().query("INSERT")
    texts = {t.dxf.text for t in doc.modelspace().query("TEXT")}
    assert "TX1" in texts


@pytest.mark.skipif(not HAVE_EZDXF, reason="ezdxf not installed")
@pytest.mark.parametrize("name", sorted(os.listdir(MODELS)))
def test_every_example_draws(tmp_path, name):
    if not name.endswith((".yaml", ".yml")):
        pytest.skip("not a YAML model")
    from drawings.build import draw
    r = draw(os.path.join(MODELS, name), str(tmp_path), plot=False)
    assert all(os.path.exists(os.path.join(tmp_path, d["dxf"]))
               for d in r["drawings"]
               if "dxf" in d)


def test_schema_kinds_are_unique_and_include_the_plant_kinds():
    import json
    with open(os.path.join(ROOT, "industroml.schema.json")) as fh:
        kinds = json.load(fh)["$defs"]["assetKind"]["enum"]
    assert len(kinds) == len(set(kinds))
    assert {"chiller", "cdu", "crah", "header", "ring_main_unit",
            "static_transfer_switch", "pdu"} <= set(kinds)


def test_fixed_sheet_size_scales_to_fit(blocks):
    c = Canvas()
    c.rect((0, 0), (700, 450))
    _, meta = compose(c, blocks, {"title": "T"}, [], ["n"], size="A3")
    assert meta["size"] == "A3" and meta["scale"] < 1


def test_sld_splits_into_overall_and_board_sheets(blocks):
    """A board whose feeders all end at loads gets its own sheet."""
    data = load(DC)
    m = Model(data)
    parts = sld.split(m, blocks, min_feeders=2)
    titles = [t for t, _, _ in parts]
    assert titles[0] == "OVERALL"
    assert "MECHANICAL SWITCHBOARD A" in titles
    overall = parts[0][1]
    notes = [p.data["text"] for p in overall.prims if p.kind == "text"
             and p.data["text"].startswith("OUTGOING CIRCUITS")]
    assert notes
    mssb = parts[titles.index("MECHANICAL SWITCHBOARD A")][1]
    incoming = [p for p in mssb.prims if p.kind == "insert"
                and p.data["block"] == "E-OPC"]
    assert len(incoming) == 1


def _placed_model():
    """Tank -> valve -> pump, each with a schematic position."""
    def a(i, kind, x, y, **kw):
        return {"id": i, "name": i, "kind": kind, "domain": "mechanical",
                "container": "S", "attributes": {"schematic": [x, y], **kw}}

    def iface(i):
        return {"id": i, "asset": i.split(".")[0], "name": i.split(".")[1],
                "domain": "mechanical", "medium": "pipe_flanged"}

    return Model({
        "meta": {"format": "IndustroML", "version": "0.1"},
        "containers": [{"id": "S", "name": "S", "type": "site"}],
        "assets": [a("T1", "tank", 0, 0, schematic_size=[1, 2]),
                   a("V1", "valve", 2, 0, valve_type="gate"),
                   a("P1", "pump", 4, 0, schematic_size=[0.8, 0.8])],
        "interfaces": [iface(x) for x in ("T1.OUT", "V1.A", "V1.B", "P1.IN")],
        "connections": [
            {"id": "L1", "type": "pipe", "from": "T1.OUT", "to": "V1.A",
             "attributes": {"schematic_path": [[0.5, 0], [2, 0]]}},
            {"id": "L2", "type": "pipe", "from": "V1.B", "to": "P1.IN",
             "attributes": {"schematic_path": [[2, 0], [3.6, 0]]}}],
    })


def test_schematic_positions_are_drawn_where_the_model_says(blocks):
    m = _placed_model()
    assert pid.placed(m)
    canvas, plan = pid.layout(m, blocks)
    k = pid.PLACED_MM
    assert plan.nodes["V1"]["x"] == pytest.approx(2 * k)
    valve = [p for p in canvas.prims if p.kind == "insert"
             and p.data["block"] == "P-GATE"]
    assert valve and valve[0].data["at"] == pytest.approx((2 * k, 0))
    # the pipe stops at the valve body instead of running through it
    lines = [p.data["pts"] for p in canvas.prims if p.kind == "polyline"
             and p.layer.startswith("P-LINE")]
    ends = [pt for pts in lines for pt in (pts[0], pts[-1])]
    assert all(abs(x - 2 * k) > 1 for x, _ in ends)


def test_models_without_positions_are_laid_out(dc):
    assert not pid.placed(dc)
