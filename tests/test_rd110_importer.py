"""The RD110 one-line importer: the cable network it reads, the models it
wrote into examples/, and (when the drawing is on disk) a full read.

The DXF is Schneider Electric's, downloadable from se.com and not kept in
this repository. Set RD110_SLD_DXF to its path to run the full-read tests.
"""
import collections
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

pytest.importorskip("ezdxf")

from drawings import sld  # noqa: E402
from drawings.model import Model, load  # noqa: E402
from drawings.symbols import library  # noqa: E402
from importers.rd110 import sld as rd110  # noqa: E402

MODELS = os.path.join(ROOT, "examples", "models")
DXF = os.environ.get("RD110_SLD_DXF", "")
need_dxf = pytest.mark.skipif(not os.path.isfile(DXF),
                              reason="RD110_2.2 DXF not on disk")


def reach(net, p):
    """Every point joined to p."""
    start = [k for k, q in net.pts.items() if q == p]
    seen, todo = set(start), list(start)
    while todo:
        for n in net.adj[todo.pop()]:
            if n not in seen:
                seen.add(n)
                todo.append(n)
    return {net.pts[k] for k in seen}


def test_a_break_where_cables_cross_is_a_crossing_not_a_tee():
    # a feeder runs right, breaks either side of a vertical cable, carries
    # on; its near end lands exactly on the vertical
    segs = [((0.0, 10.0), (20.0, 10.0)), ((25.0, 10.0), (40.0, 10.0)),
            ((20.0, 0.0), (20.0, 30.0))]
    net = rd110.Net(segs)
    net.split_crossings()
    net.bridge_gaps()
    assert (40.0, 10.0) in reach(net, (0.0, 10.0))
    assert (20.0, 0.0) not in reach(net, (0.0, 10.0))
    assert (20.0, 30.0) in reach(net, (20.0, 0.0))


def test_a_real_tee_stays_a_tee():
    segs = [((0.0, 10.0), (20.0, 10.0)), ((20.0, 0.0), (20.0, 30.0))]
    net = rd110.Net(segs)
    net.split_crossings()
    net.bridge_gaps()
    assert (20.0, 30.0) in reach(net, (0.0, 10.0))


def test_gap_bridging_joins_ends_that_face_each_other_only():
    # two parallel feeders end side by side, closer to each other than to
    # their continuations across a break
    segs = [((0.0, 10.0), (20.0, 10.0)), ((25.2, 10.0), (40.0, 10.0)),
            ((0.0, 15.0), (20.0, 15.0)), ((25.2, 15.0), (40.0, 15.0))]
    net = rd110.Net(segs)
    net.bridge_gaps()
    assert (40.0, 10.0) in reach(net, (0.0, 10.0))
    assert (0.0, 15.0) not in reach(net, (0.0, 10.0))


@pytest.fixture(scope="module", params=["paris", "singapore"])
def example(request):
    return load(os.path.join(MODELS, f"rd110_elec_{request.param}.yaml"))


def test_example_models_are_complete(example):
    assets = {a["id"]: a for a in example["assets"]}
    owner = {i["id"]: i["asset"] for i in example["interfaces"]}
    kinds = collections.Counter(a["kind"] for a in assets.values())
    assert kinds["acb_breaker"] + kinds["mccb_breaker"] == 168
    assert kinds["busbar_section"] == 24
    assert kinds["transformer"] == kinds["generator"] == 6
    assert kinds["ups"] == 14
    # every breaker sits on a board and feeds something, bar the spares
    feeds = {owner[c["from"]] for c in example["connections"]}
    for aid, a in assets.items():
        if a["kind"].endswith("_breaker"):
            assert a["container"] != "SITE", aid
            assert aid in feeds or aid.startswith("CB-SPARE"), aid
    # each busway is fed once, each rack group by its four busways
    fed = collections.Counter(owner[c["to"]] for c in example["connections"])
    assert all(fed[a] == 1 for a in assets if a.startswith("BUSWAY-"))
    groups = [a for a in assets if a.startswith("RACK-GROUP-")]
    assert len(groups) == 6 and all(fed[g] == 4 for g in groups)


def test_a_repeated_designation_is_kept_and_flagged(example):
    repeats = [a for a in example["assets"]
               if "check" in a.get("attributes", {})]
    assert [a["attributes"]["designation"] for a in repeats] == ["AIIT-3.2C"]


def test_example_redraws_as_two_sheets():
    m = Model(load(os.path.join(MODELS, "rd110_elec_paris.yaml")))
    assert sld.placed(m)
    parts = sld.placed_parts(m, library())
    assert len(parts) == 2


@need_dxf
def test_full_read_matches_the_example(tmp_path):
    for variant in ("paris", "singapore"):
        model, report = rd110.to_model(DXF, variant)
        assert report["unconnected_breakers"] == []
        ref = load(os.path.join(MODELS, f"rd110_elec_{variant}.yaml"))
        assert sorted(a["id"] for a in model["assets"]) == \
            sorted(a["id"] for a in ref["assets"])
        assert len(model["connections"]) == len(ref["connections"])


@need_dxf
def test_variants_share_the_it_room():
    links = {}
    for variant in ("paris", "singapore"):
        model, _ = rd110.to_model(DXF, variant)
        owner = {i["id"]: i["asset"] for i in model["interfaces"]}
        links[variant] = {(owner[c["from"]], owner[c["to"]])
                          for c in model["connections"]}
    assert links["paris"] == links["singapore"]
