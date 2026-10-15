"""Tests for validate_industroML.py: the examples pass, and each check fires.

  python3 -m pytest -q tests
"""
from __future__ import annotations

import copy
import glob
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

import validate_industroML as v  # noqa: E402

EXAMPLES = sorted(glob.glob(os.path.join(ROOT, "examples", "models", "*.y*ml"))
                  + glob.glob(os.path.join(ROOT, "examples", "models", "*.json")))
KIND_DOMAINS = v.load_kind_domains()

BASE = {
    "meta": {"format": "IndustroML", "version": "1.0"},
    "containers": [{"id": "SITE", "name": "Site", "type": "site"},
                   {"id": "TRAY-1", "name": "Rack", "type": "pipe_rack",
                    "parent": "SITE"}],
    "assets": [
        {"id": "PUMP-1", "name": "Pump", "domain": "mechanical",
         "kind": "pump", "container": "SITE"},
        {"id": "TANK-1", "name": "Tank", "domain": "mechanical",
         "kind": "tank", "container": "SITE"},
    ],
    "interfaces": [
        {"id": "PUMP-1.out", "asset": "PUMP-1", "domain": "mechanical",
         "medium": "pipe_flanged"},
        {"id": "TANK-1.in", "asset": "TANK-1", "domain": "mechanical",
         "medium": "pipe_flanged"},
    ],
    "connections": [{"id": "L-1", "type": "pipe", "from": "PUMP-1.out",
                     "to": "TANK-1.in", "route": ["TRAY-1"]}],
}


def errors(model):
    return v.ref_validate(model, KIND_DOMAINS)


def test_examples_exist():
    assert len(EXAMPLES) >= 4


@pytest.mark.parametrize("path", EXAMPLES, ids=os.path.basename)
def test_examples_pass_reference_checks(path):
    assert errors(v.load_model(path)) == []


@pytest.mark.parametrize("path", EXAMPLES, ids=os.path.basename)
def test_examples_pass_schema(path):
    pytest.importorskip("jsonschema")
    schema = v.load_json(os.path.join(ROOT, "industroml.schema.json"))
    assert v.try_schema_validate(v.load_model(path), schema) == []


def test_base_model_is_valid():
    assert errors(BASE) == []


def test_base_model_passes_schema():
    pytest.importorskip("jsonschema")
    schema = v.load_json(os.path.join(ROOT, "industroml.schema.json"))
    assert v.try_schema_validate(BASE, schema) == []


@pytest.mark.parametrize("key", ["containers", "assets", "interfaces",
                                 "connections"])
def test_duplicate_ids_are_caught(key):
    m = copy.deepcopy(BASE)
    m[key].append(copy.deepcopy(m[key][-1]))
    assert any(e.startswith("Duplicate") for e in errors(m)), errors(m)


def test_container_and_asset_cannot_share_an_id():
    m = copy.deepcopy(BASE)
    m["containers"].append({"id": "PUMP-1", "name": "x", "type": "area",
                            "parent": "SITE"})
    assert any("both a container and an asset" in e for e in errors(m))


def test_route_must_resolve():
    m = copy.deepcopy(BASE)
    m["connections"][0]["route"] = ["TRAY-9"]
    assert errors(m) == ["Connection L-1 route via TRAY-9 not found"]


def test_kind_in_wrong_domain():
    if not KIND_DOMAINS:
        pytest.skip("catalogue unreadable")
    m = copy.deepcopy(BASE)
    m["assets"][0]["domain"] = "electrical"
    assert any("kind 'pump' in domain 'electrical'" in e for e in errors(m))


@pytest.mark.parametrize("mutate,expect", [
    (lambda m: m["containers"][1].update(parent="NOWHERE"),
     "references missing parent"),
    (lambda m: m["assets"][0].update(container="NOWHERE"), "not found"),
    (lambda m: m["interfaces"][0].update(asset="NOWHERE"),
     "references missing asset"),
    (lambda m: m["connections"][0].update(to="NOWHERE.in"),
     "'to' interface NOWHERE.in not found"),
    (lambda m: m["connections"][0].update(type="hose"), "unknown type 'hose'"),
    (lambda m: m["interfaces"][0].update(domain="data"),
     "type pipe connects data -> mechanical"),
])
def test_each_reference_check_fires(mutate, expect):
    m = copy.deepcopy(BASE)
    mutate(m)
    assert any(expect in e for e in errors(m)), errors(m)


def test_cli_exit_codes(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(BASE))
    bad = tmp_path / "bad.json"
    m = copy.deepcopy(BASE)
    m["assets"].append(copy.deepcopy(m["assets"][0]))
    bad.write_text(json.dumps(m))
    run = lambda p: subprocess.run(  # noqa: E731
        [sys.executable, os.path.join(ROOT, "validate_industroML.py"), str(p),
         "--schema", os.path.join(ROOT, "industroml.schema.json")],
        capture_output=True, text=True)
    assert run(good).returncode == 0
    r = run(bad)
    assert r.returncode in (1, 2) and "Duplicate asset id: PUMP-1" in r.stderr


def test_catalogue_connectors_map_to_schema_types():
    yaml = pytest.importorskip("yaml")
    with open(os.path.join(ROOT, "catalog", "master_catalog.yaml")) as fh:
        cat = yaml.safe_load(fh)
    schema = v.load_json(os.path.join(ROOT, "industroml.schema.json"))
    types = set(schema["$defs"]["connectionType"]["enum"])
    mapped = {c["type"]: c.get("connection_type") for c in cat["connectors"]}
    assert all(t in types for t in mapped.values()), mapped
    assert set(mapped.values()) == types
    assert cat["meta"]["format"] == "IndustroML-Catalog"
