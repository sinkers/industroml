#!/usr/bin/env python3
"""Write examples/models/dc_hall_demo.yaml, an invented data hall.

  python3 examples/tools/make_dc_demo.py

Big enough to exercise the drawings: an HV supply and ring main unit, two
transformers and two generators through transfer switches, A and B main
switchboards with a bus tie, UPS, critical boards, PDUs and a static transfer
switch; and a chilled-water loop with two chillers, supply and return
headers, three CDUs, an air separator, pumps, valves and instruments.
Every name and number is made up.
"""
import os

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "models", "dc_hall_demo.yaml")

containers = [
    {"id": "SITE", "name": "Example Data Centre", "type": "site"},
    {"id": "HV-YARD", "name": "HV Yard", "type": "area", "parent": "SITE"},
    {"id": "GEN-YARD", "name": "Generator Yard", "type": "area", "parent": "SITE"},
    {"id": "SWR-A", "name": "Switchroom A", "type": "room", "parent": "SITE"},
    {"id": "SWR-B", "name": "Switchroom B", "type": "room", "parent": "SITE"},
    {"id": "PLANT", "name": "Chiller Plant", "type": "room", "parent": "SITE"},
    {"id": "HALL-1", "name": "Data Hall 1", "type": "room", "parent": "SITE"},
]
assets, interfaces, connections = [], [], []


def asset(id, name, kind, domain, container, **attrs):
    assets.append({"id": id, "name": name, "kind": kind, "domain": domain,
                   "container": container, "attributes": attrs})


def port(asset_id, name, domain, medium, **attrs):
    pid = f"{asset_id}.{name}"
    if not any(i["id"] == pid for i in interfaces):
        i = {"id": pid, "asset": asset_id, "name": name, "domain": domain,
             "medium": medium}
        if attrs:
            i["attributes"] = attrs
        interfaces.append(i)
    return pid


def cable(cid, a, b, hv=False, **attrs):
    med = "ac_hv_3ph" if hv else "ac_lv_3ph"
    fa = port(*a[:2], "electrical", med, **(a[2] if len(a) > 2 else {}))
    tb = port(*b[:2], "electrical", med, **(b[2] if len(b) > 2 else {}))
    connections.append({"id": cid, "type": "cable", "from": fa, "to": tb,
                        "attributes": {"conductor": "Cu", "insulation": "XLPE",
                                       **attrs}})


def pipe(pid, a, b, dn, service, length):
    fa = port(a[0], a[1], "mechanical", "pipe_flanged")
    tb = port(b[0], b[1], "mechanical", "pipe_flanged")
    connections.append({"id": pid, "type": "pipe", "from": fa, "to": tb,
                        "attributes": {"dn_mm": dn, "service": service,
                                       "spec": "CS-PN16", "length_m": length}})


ACB = lambda a, ka=65: {"device": "acb", "rating_a": a, "breaking_capacity_ka": ka}
MCCB = lambda a, ka=50: {"device": "mccb", "rating_a": a, "breaking_capacity_ka": ka}

# ---- electrical
asset("UTIL", "Utility supply 11 kV", "utility_supply", "electrical", "HV-YARD",
      voltage_v=11000, fault_ka=16)
asset("RMU-1", "Ring main unit", "ring_main_unit", "electrical", "HV-YARD",
      voltage_v=11000, current_a=630)
cable("C-HV-01", ("UTIL", "OUT"), ("RMU-1", "IN"), hv=True, csa_mm2=240,
      cores=3, length_m=120, method="buried")
for s in "AB":
    asset(f"TX-{s}", f"Transformer {s} 1500 kVA", "transformer", "electrical",
          "HV-YARD", power_kva=1500, primary_voltage_v=11000,
          secondary_voltage_v=415, vector_group="Dyn11")
    asset(f"GEN-{s}", f"Generator {s} 1250 kVA", "generator", "electrical",
          "GEN-YARD", power_kva=1250, voltage_v=415)
    asset(f"ATS-{s}", f"Transfer switch {s} 2500 A", "automatic_transfer_switch",
          "electrical", f"SWR-{s}", current_a=2500)
    asset(f"MSB-{s}", f"Main switchboard {s}", "switchboard", "electrical",
          f"SWR-{s}", voltage_v=415, current_a=2500, fault_ka=65)
    asset(f"UPS-{s}", f"UPS {s} 500 kVA", "ups", "electrical", f"SWR-{s}",
          power_kva=500)
    asset(f"CSB-{s}", f"Critical switchboard {s}", "switchboard", "electrical",
          f"SWR-{s}", voltage_v=415, current_a=800)
    asset(f"MSSB-{s}", f"Mechanical switchboard {s}", "switchboard",
          "electrical", "PLANT", voltage_v=415, current_a=1000)
    asset(f"DB-{s}", f"House services board {s}", "distribution_board",
          "electrical", f"SWR-{s}", voltage_v=415, current_a=160)
    cable(f"C-HV-{s}", ("RMU-1", f"OUT-{s}"), (f"TX-{s}", "HV"), hv=True,
          csa_mm2=95, cores=3, length_m=25, method="buried")
    cable(f"C-TX-{s}", (f"TX-{s}", "LV"), (f"ATS-{s}", "N")
          , csa_mm2=630, cores=1, runs=4, earth_mm2=300, length_m=30,
          method="ladder")
    cable(f"C-GEN-{s}", (f"GEN-{s}", "OUT"), (f"ATS-{s}", "E"),
          csa_mm2=630, cores=1, runs=3, earth_mm2=240, length_m=45,
          method="ladder")
    cable(f"C-MSB-{s}", (f"ATS-{s}", "OUT"), (f"MSB-{s}", "IN", ACB(2500)),
          csa_mm2=630, cores=1, runs=4, earth_mm2=300, length_m=8,
          method="ladder")
    cable(f"C-UPS-{s}", (f"MSB-{s}", "F-UPS", ACB(1000)), (f"UPS-{s}", "IN"),
          csa_mm2=240, cores=1, runs=2, earth_mm2=120, length_m=15,
          method="ladder")
    cable(f"C-CSB-{s}", (f"UPS-{s}", "OUT"), (f"CSB-{s}", "IN", MCCB(800)),
          csa_mm2=240, cores=1, runs=2, earth_mm2=120, length_m=12,
          method="ladder")
    cable(f"C-MSSB-{s}", (f"MSB-{s}", "F-MECH", ACB(1000)),
          (f"MSSB-{s}", "IN", MCCB(1000)), csa_mm2=300, cores=1, runs=2,
          earth_mm2=150, length_m=60, method="ladder")
    cable(f"C-DB-{s}", (f"MSB-{s}", "F-DB", MCCB(160)), (f"DB-{s}", "IN"),
          csa_mm2=70, cores=4, earth_mm2=25, length_m=20, method="tray")
    for k in (1, 2, 3):
        pdu = f"PDU-{s}{k}"
        asset(pdu, f"PDU {s}{k} 150 kVA", "pdu", "electrical", "HALL-1",
              power_kva=150)
        cable(f"C-{pdu}", (f"CSB-{s}", f"F-PDU{k}", MCCB(250)), (pdu, "IN"),
              csa_mm2=120, cores=4, earth_mm2=35, length_m=40 + 8 * k,
              method="tray")
cable("C-TIE", ("MSB-A", "TIE", ACB(2500)), ("MSB-B", "TIE"), tie=True,
      csa_mm2=630, cores=1, runs=4, length_m=6, method="busduct")
asset("STS-1", "Static transfer switch 250 A", "static_transfer_switch",
      "electrical", "HALL-1", current_a=250)
asset("PDU-S1", "PDU S1 single corded 150 kVA", "pdu", "electrical", "HALL-1",
      power_kva=150)
cable("C-STS-A", ("CSB-A", "F-STS", MCCB(250)), ("STS-1", "A"), csa_mm2=120,
      cores=4, earth_mm2=35, length_m=35, method="tray")
cable("C-STS-B", ("CSB-B", "F-STS", MCCB(250)), ("STS-1", "B"), csa_mm2=120,
      cores=4, earth_mm2=35, length_m=38, method="tray")
cable("C-PDU-S1", ("STS-1", "OUT"), ("PDU-S1", "IN"), csa_mm2=120, cores=4,
      earth_mm2=35, length_m=6, method="tray")

# ---- mechanical, and the plant's power
for k, s in ((1, "A"), (2, "B")):
    asset(f"CH-{k}", f"Chiller {k} 1200 kW", "chiller", "mechanical", "PLANT",
          capacity_kw=1200, power_kw=260)
    asset(f"PMP-{k}", f"CHW pump {k}", "pump", "mechanical", "PLANT",
          flow_ls=55, head_m=28, power_kw=30)
    cable(f"C-CH-{k}", (f"MSSB-{s}", f"F-CH{k}", MCCB(630)), (f"CH-{k}", "PWR"),
          csa_mm2=240, cores=4, earth_mm2=95, length_m=25, method="ladder")
    cable(f"C-PMP-{k}", (f"MSSB-{s}", f"F-PMP{k}", MCCB(80)),
          (f"PMP-{k}", "PWR"), csa_mm2=25, cores=4, earth_mm2=6,
          length_m=18, method="tray")

asset("HDR-S", "CHW supply header", "header", "mechanical", "PLANT")
asset("HDR-R", "CHW return header", "header", "mechanical", "PLANT")
asset("HDR-P", "Pump suction header", "header", "mechanical", "PLANT")
asset("AS-1", "Air and dirt separator", "air_separator", "mechanical", "PLANT")
asset("EXP-1", "Expansion vessel 500 L", "expansion_tank", "mechanical",
      "PLANT", volume_m3=0.5)
asset("TT-101", "CHW supply temperature", "temperature_transmitter",
      "control", "PLANT")
asset("PT-102", "Pump suction pressure", "pressure_transmitter", "control",
      "PLANT")


def valve(id, name, vt, container="PLANT"):
    asset(id, name, "valve", "mechanical", container, valve_type=vt)


def chain(prefix, start, items, end, dn, service):
    """A pipe run through inline items: start -> item... -> end."""
    pts = [start] + [(i, "A", "B") for i in items] + [end]
    for n in range(len(pts) - 1):
        a = pts[n]
        b = pts[n + 1]
        src = (a[0], a[2]) if len(a) == 3 else a
        dst = (b[0], b[1]) if len(b) == 3 else b
        pipe(f"{prefix}-{n + 1}", src, dst, dn, service, 4)


for k in (1, 2):
    valve(f"BFV-{k}01", f"Chiller {k} outlet isolation", "butterfly")
    chain(f"L-CH{k}S", (f"CH-{k}", "CHWS"), [f"BFV-{k}01"], ("HDR-S", f"IN{k}"),
          200, "CHWS")
    valve(f"BFV-{k}02", f"Pump {k} suction isolation", "butterfly")
    asset(f"STR-{k}", f"Pump {k} strainer", "strainer_y", "mechanical", "PLANT")
    valve(f"NRV-{k}", f"Pump {k} check valve", "check")
    valve(f"BFV-{k}03", f"Pump {k} discharge isolation", "butterfly")
    chain(f"L-P{k}S", ("HDR-P", f"OUT{k}"), [f"BFV-{k}02", f"STR-{k}"],
          (f"PMP-{k}", "SUC"), 200, "CHWR")
    chain(f"L-P{k}D", (f"PMP-{k}", "DIS"), [f"NRV-{k}", f"BFV-{k}03"],
          (f"CH-{k}", "CHWR"), 200, "CHWR")
for k in (1, 2, 3):
    asset(f"CDU-{k}", f"CDU {k} 600 kW", "cdu", "mechanical", "HALL-1",
          capacity_kw=600)
    valve(f"BV-{k}1", f"CDU {k} supply isolation", "ball")
    valve(f"FCV-{k}", f"CDU {k} flow control", "control")
    valve(f"BV-{k}2", f"CDU {k} return isolation", "ball")
    chain(f"L-C{k}S", ("HDR-S", f"OUT{k}"), [f"BV-{k}1"], (f"CDU-{k}", "PRI-S"),
          150, "CHWS")
    chain(f"L-C{k}R", (f"CDU-{k}", "PRI-R"), [f"FCV-{k}", f"BV-{k}2"],
          ("HDR-R", f"IN{k}"), 150, "CHWR")
pipe("L-AS-1", ("HDR-R", "OUT"), ("AS-1", "IN"), 250, "CHWR", 3)
pipe("L-AS-2", ("AS-1", "OUT"), ("HDR-P", "IN"), 250, "CHWR", 3)
pipe("L-EXP", ("AS-1", "EXP"), ("EXP-1", "IN"), 50, "CHWR", 2)
pipe("L-TT", ("HDR-S", "TT"), ("TT-101", "PROC"), 25, "CHWS", 1)
pipe("L-PT", ("HDR-P", "PT"), ("PT-102", "PROC"), 25, "CHWR", 1)
connections.append({"id": "IO-TT-101", "type": "io_link",
                    "from": port("TT-101", "AO", "control", "ao_4_20mA"),
                    "to": port("CSB-A", "BMS", "control", "ai_4_20mA")})

model = {
    "meta": {
        "format": "IndustroML", "version": "0.1",
        "site_name": "Example Data Centre, Hall 1",
        "units": {"length": "m", "diameter": "mm", "voltage": "V",
                  "current": "A", "power": "kW"},
        "drawing": {"client": "Example Data Centres", "project": "DC1 Hall 1",
                    "number": "EX-DC1-0001", "drawn": "IndustroML",
                    "checked": "", "approved": "",
                    "status": "Preliminary - not for construction"},
        "revisions": [{"rev": "A", "date": "2026-10-13",
                       "description": "Generated for review", "by": "IML",
                       "chk": ""}],
    },
    "containers": containers, "assets": assets, "interfaces": interfaces,
    "connections": connections,
}
with open(OUT, "w") as fh:
    fh.write("# Invented data hall for the drawing generator. Regenerate with\n"
             "# python3 examples/tools/make_dc_demo.py\n")
    yaml.safe_dump(model, fh, sort_keys=False, width=100)
print(OUT, len(assets), "assets", len(connections), "connections")
