"""Drawing symbols, as DXF blocks.

Electrical symbols follow IEC 60617 (adopted in Australia as AS/NZS 1102),
drawn for a single-line diagram that reads top to bottom: a symbol's "top"
port faces the supply. Process symbols follow ISO 10628-2 for equipment,
valves and lines and ISA-5.1 for instrument bubbles, drawn for flow left to
right.

Every symbol is drawn on layer 0 inside its block, so it takes the colour and
linetype of the layer it is inserted on, which is how CAD users expect blocks
to behave. Sizes are millimetres on the printed sheet. The origin is the
symbol's centre; ports are where lines attach.
"""
from __future__ import annotations

from typing import Dict

from .canvas import AttDef, Block, Canvas

IEC = "IEC 60617 / AS/NZS 1102"
ISO = "ISO 10628-2"
ISA = "ISA-5.1"

TAG_H = 2.5        # attribute text on symbols
SMALL_H = 2.0


def _block(name, description, standard, size, ports, draw, attdefs=()):
    c = Canvas()
    draw(c)
    return Block(name=name, description=description, standard=standard,
                 prims=c.prims, attdefs=list(attdefs), ports=dict(ports),
                 size=size)


def _side_attrs(x, y0, tags, h=SMALL_H, step=None):
    """Attribute definitions stacked downwards from (x, y0), left aligned."""
    step = step or h * 1.5
    return [AttDef(t, (x, y0 - i * step), h) for i, t in enumerate(tags)]


# --------------------------------------------------------------- electrical

def _cb(c, half=7.0, cross=True, bar=False):
    c.line((0, half), (0, 3))
    c.line((0, -half), (0, -3))
    c.line((0, -3), (-3.2, 3.4))                 # the moving contact
    if cross:
        c.line((-1.2, 1.8), (1.2, 4.2))
        c.line((-1.2, 4.2), (1.2, 1.8))
    if bar:
        c.line((-1.6, 3), (1.6, 3))


def _chevrons(c, y, up):
    s = 1 if up else -1
    c.line((-1.6, y - s * 1.2), (0, y), )
    c.line((0, y), (1.6, y - s * 1.2))


def _acb(c):
    _cb(c, half=9.0)
    _chevrons(c, 7.6, True)
    _chevrons(c, -6.4, True)


def _fuse(c):
    c.line((0, 7), (0, -7))
    c.rect((-1.5, -4), (1.5, 4))


def _ct(c):
    c.line((0, 5), (0, -5))
    c.circle((0, 0), 2.5)


def _tx(c):
    c.line((0, 11), (0, 10))
    c.circle((0, 4.2), 6)
    c.circle((0, -4.2), 6)
    c.line((0, -10.2), (0, -11))


def _gen(c):
    c.circle((0, 0), 7)
    c.text((0, 0.8), "G", 5, align="MIDDLE_CENTER")
    c.text((0, -3.6), "3~", 2.2, align="MIDDLE_CENTER")


def _motor(c):
    c.circle((0, 0), 6)
    c.text((0, 0.8), "M", 4.5, align="MIDDLE_CENTER")
    c.text((0, -3.2), "3~", 2.0, align="MIDDLE_CENTER")


def _load(c):
    c.line((0, 5), (0, 0))
    c.solid([(-2.5, 0), (2.5, 0), (0, -4)])


def _converter(left, right):
    def draw(c):
        c.line((0, 8), (0, 6))
        c.rect((-8, -6), (8, 6))
        c.line((-8, -6), (8, 6))
        c.text((-4.5, 2.6), left, 3, align="MIDDLE_CENTER")
        c.text((4.5, -2.6), right, 3, align="MIDDLE_CENTER")
        c.line((0, -6), (0, -8))
    return draw


def _ups(c):
    _converter("~", "~")(c)
    # the battery, on the DC link
    c.line((8, 0), (11, 0))
    c.line((11, 2.5), (11, -2.5))
    c.line((12.4, 1.3), (12.4, -1.3))


def _labelled_box(label, w=18, h=10, dashed=False, top=(0,), bottom=(0,)):
    def draw(c):
        kw = {"linetype": "DASHED"} if dashed else {}
        c.rect((-w / 2, -h / 2), (w / 2, h / 2), **kw)
        c.text((0, 0), label, 3, align="MIDDLE_CENTER")
        for x in top:
            c.line((x, h / 2), (x, h / 2 + 2))
        for x in bottom:
            c.line((x, -h / 2), (x, -h / 2 - 2))
    return draw


def _supply(c):
    c.line((0, 7), (0, -7))
    c.solid([(-2.2, 1), (2.2, 1), (0, -3)])


def _meter(c):
    c.line((0, 6), (0, 3))
    c.circle((0, 0), 3)
    c.text((0, 0), "Wh", 1.8, align="MIDDLE_CENTER")
    c.line((0, -3), (0, -6))


def _earth(c):
    c.line((0, 4), (0, 0))
    for i, w in enumerate((3, 2, 1)):
        c.line((-w, -i * 1.2), (w, -i * 1.2))


ELECTRICAL = {
    "E-CB": ("Circuit breaker", (8, 14), {"top": (0, 7), "bottom": (0, -7)},
             _cb, _side_attrs(3.5, 2.5, ["TAG", "RATING"])),
    "E-ACB": ("Air circuit breaker, withdrawable", (8, 18),
              {"top": (0, 9), "bottom": (0, -9)}, _acb,
              _side_attrs(3.5, 3, ["TAG", "RATING"])),
    "E-ISO": ("Switch-disconnector", (8, 14), {"top": (0, 7), "bottom": (0, -7)},
              lambda c: _cb(c, cross=False, bar=True),
              _side_attrs(3.5, 2.5, ["TAG", "RATING"])),
    "E-FUSE": ("Fuse", (6, 14), {"top": (0, 7), "bottom": (0, -7)}, _fuse,
               _side_attrs(3, 2.5, ["TAG", "RATING"])),
    "E-CT": ("Current transformer", (6, 10), {"top": (0, 5), "bottom": (0, -5)},
             _ct, _side_attrs(3.5, 1, ["RATIO"])),
    "E-METER": ("Energy meter", (6, 12), {"top": (0, 6), "bottom": (0, -6)},
                _meter, _side_attrs(4, 1, ["TAG"])),
    "E-TX": ("Transformer, two winding", (12, 22),
             {"top": (0, 11), "bottom": (0, -11)}, _tx,
             _side_attrs(8, 6, ["TAG", "RATING", "VOLTS", "VECTOR"], h=TAG_H)),
    "E-GEN": ("Generator", (14, 14), {"bottom": (0, -7)}, _gen,
              _side_attrs(9, 3, ["TAG", "RATING", "VOLTS"], h=TAG_H)),
    "E-MOTOR": ("Motor", (12, 12), {"top": (0, 6)}, _motor, []),
    "E-LOAD": ("Load", (6, 9), {"top": (0, 5)}, _load, []),
    "E-UPS": ("UPS (rectifier, battery, inverter)", (26, 16),
              {"top": (0, 8), "bottom": (0, -8)}, _ups, []),
    "E-VSD": ("Variable speed drive", (16, 16),
              {"top": (0, 8), "bottom": (0, -8)}, _converter("~", "~"), []),
    "E-ATS": ("Automatic transfer switch", (20, 14),
              {"top": (-5, 7), "top2": (5, 7), "bottom": (0, -7)},
              _labelled_box("ATS", 20, 10, top=(-5, 5)), []),
    "E-STS": ("Static transfer switch", (20, 14),
              {"top": (-5, 7), "top2": (5, 7), "bottom": (0, -7)},
              _labelled_box("STS", 20, 10, top=(-5, 5)), []),
    "E-RMU": ("HV ring main unit", (22, 16), {"top": (0, 8), "bottom": (0, -8)},
              _labelled_box("RMU", 22, 12, dashed=True), []),
    "E-PDU": ("Power distribution unit", (16, 12), {"top": (0, 6)},
              _labelled_box("PDU", 16, 8, bottom=()), []),
    "E-EQUIP": ("Equipment", (18, 12), {"top": (0, 6)},
                _labelled_box("", 18, 8, bottom=()),
                [AttDef("LABEL", (0, 0), 2.2, align="MIDDLE_CENTER")]),
    "E-SUPPLY": ("Incoming supply", (6, 14), {"bottom": (0, -7)}, _supply, []),
    "E-EARTH": ("Earth", (6, 8), {"top": (0, 4)}, _earth, []),
}


# ------------------------------------------------------------------ process

def _bowtie(c, fill_left=False):
    left = [(-4, -2.5), (-4, 2.5), (0, 0)]
    right = [(4, -2.5), (4, 2.5), (0, 0)]
    if fill_left:
        c.solid(left)
    else:
        c.polyline(left, closed=True)
    c.polyline(right, closed=True)


def _gate(c):
    _bowtie(c)


def _globe(c):
    _bowtie(c)
    c.solid([(-0.9, -0.9), (0.9, -0.9), (0.9, 0.9), (-0.9, 0.9)])


def _ball(c):
    _bowtie(c)
    c.circle((0, 0), 1.6)


def _butterfly(c):
    c.line((-3, 2.8), (-3, -2.8))
    c.line((3, 2.8), (3, -2.8))
    c.line((-4, 0), (-3, 0))
    c.line((3, 0), (4, 0))
    c.line((-2.2, -2.6), (2.2, 2.6))
    c.circle((0, 0), 0.8)


def _check(c):
    _bowtie(c, fill_left=True)
    c.line((0, 2.8), (0, -2.8))


def _control(c):
    _globe(c)
    c.line((0, 0), (0, 5))
    c.arc((0, 5), 3, 0, 180)
    c.line((-3, 5), (3, 5))


def _prv(c):
    _bowtie(c)
    c.line((0, 0), (0, 3))
    pts = [(0, 3)] + [((-1.5 if i % 2 else 1.5), 3 + 0.8 * (i + 1))
                      for i in range(5)] + [(0, 8)]
    c.polyline(pts)


def _strainer(c):
    c.line((-4, 0), (4, 0))
    c.polyline([(-2, 0), (1, -4), (3, -2.6), (0, 1.4)])
    c.line((1, -4), (2.2, -5.2))


def _filter(c):
    c.line((-5, 0), (-3.5, 0))
    c.line((3.5, 0), (5, 0))
    c.rect((-3.5, -3), (3.5, 3))
    c.line((-3.5, -3), (3.5, 3), linetype="DASHED")


def _orifice(c):
    c.line((-0.8, 3), (-0.8, -3))
    c.line((0.8, 3), (0.8, -3))


def _pump(c):
    c.circle((0, 0), 6)
    c.line((0, 6), (8, 6))
    c.polyline([(-3.5, -4.9), (-5.5, -8.5), (5.5, -8.5), (3.5, -4.9)])
    c.line((-6, 0), (-8, 0))


def _vessel(w, h):
    r = w / 2
    s = h / 2 - r

    def draw(c):
        c.line((-r, -s), (-r, s))
        c.line((r, -s), (r, s))
        c.arc((0, s), r, 0, 180)
        c.arc((0, -s), r, 180, 360)
    return draw


def _exp_tank(c):
    _vessel(12, 20)(c)
    c.line((-6, 0), (6, 0), linetype="DASHED")      # the diaphragm


def _instrument(c):
    c.circle((0, 0), 5)


def _instrument_panel(c):
    c.circle((0, 0), 5)
    c.line((-5, 0), (5, 0))


def _arrow(c):
    c.solid([(-1.6, -1.1), (-1.6, 1.1), (1.6, 0)])


def _off_page(c):
    c.polyline([(-6, -2.5), (3, -2.5), (6, 0), (3, 2.5), (-6, 2.5)], closed=True)


def _box_with(art):
    """Equipment drawn as a box of the standard size with a mark inside."""
    def draw(c):
        c.rect((-15, -10), (15, 10))
        art(c)
    return draw


def _chiller_art(c):
    c.line((-15, 0), (15, 0))
    c.text((0, 4.5), "CONDENSER", 1.8, align="MIDDLE_CENTER")
    c.text((0, -4.5), "EVAPORATOR", 1.8, align="MIDDLE_CENTER")


def _plate_art(c, x=0.0, y=0.0, w=6.0, h=12.0):
    c.rect((x - w / 2, y - h / 2), (x + w / 2, y + h / 2))
    pts = [(x - w / 2, y + h / 2 - 1)]
    for i in range(6):
        pts.append((x + (w / 2 if i % 2 == 0 else -w / 2),
                    y + h / 2 - 1 - (i + 1) * (h - 2) / 6))
    c.polyline(pts)


def _cdu_art(c):
    _plate_art(c, -6, 0, 6, 14)
    c.circle((7, -3), 3.5)
    c.line((7, 0.5), (11, 0.5))
    c.text((7, 6.5), "CDU", 2.2, align="MIDDLE_CENTER")


def _dry_cooler(c):
    c.rect((-15, -10), (15, 6))
    for x in (-7.5, 7.5):
        c.circle((x, 10), 4)
        c.line((x - 2.8, 7.2), (x + 2.8, 12.8))
        c.line((x - 2.8, 12.8), (x + 2.8, 7.2))
        c.line((x, 6), (x, 6))
    c.polyline([(-13, -6), (-9, -2), (-5, -6), (-1, -2), (3, -6), (7, -2),
                (11, -6), (13, -4)])


def _crah_art(c):
    pts = [(-11, 7)]
    for i in range(6):
        pts.append((-11 + (i + 1) * 2, -7 if i % 2 == 0 else 7))
    c.polyline(pts)                                   # the coil
    for y in (4.5, -4.5):
        c.circle((7, y), 4)
        c.line((4.2, y - 2.8), (9.8, y + 2.8))
        c.line((4.2, y + 2.8), (9.8, y - 2.8))


def _hx_plate(c):
    _plate_art(c, 0, 0, 10, 20)


def _air_sep(c):
    _vessel(10, 18)(c)
    c.line((0, 9), (0, 12))
    c.line((-1.5, 12), (1.5, 12))


PROCESS = {
    "P-GATE": ("Gate valve", (8, 6), {"in": (-4, 0), "out": (4, 0)}, _gate),
    "P-GLOBE": ("Globe valve", (8, 6), {"in": (-4, 0), "out": (4, 0)}, _globe),
    "P-BALL": ("Ball valve", (8, 6), {"in": (-4, 0), "out": (4, 0)}, _ball),
    "P-BFLY": ("Butterfly valve", (8, 6), {"in": (-4, 0), "out": (4, 0)},
               _butterfly),
    "P-CHECK": ("Check valve (flow left to right)", (8, 6),
                {"in": (-4, 0), "out": (4, 0)}, _check),
    "P-CV": ("Control valve", (8, 16), {"in": (-4, 0), "out": (4, 0)}, _control),
    "P-PRV": ("Pressure relief valve", (8, 18), {"in": (-4, 0), "out": (4, 0)},
              _prv),
    "P-STRAINER": ("Y-strainer", (8, 12), {"in": (-4, 0), "out": (4, 0)},
                   _strainer),
    "P-FILTER": ("Filter", (10, 6), {"in": (-5, 0), "out": (5, 0)}, _filter),
    "P-ORIFICE": ("Orifice plate", (4, 6), {"in": (-0.8, 0), "out": (0.8, 0)},
                  _orifice),
    "P-PUMP": ("Centrifugal pump", (16, 18), {"in": (-8, 0), "out": (8, 6)},
               _pump),
    "P-TANK": ("Vessel / tank", (16, 30), {}, _vessel(16, 30)),
    "P-EXPTANK": ("Expansion vessel, diaphragm", (12, 20), {}, _exp_tank),
    "P-AIRSEP": ("Air and dirt separator", (10, 22), {}, _air_sep),
    "P-CHILLER": ("Chiller", (30, 20), {}, _box_with(_chiller_art)),
    "P-CDU": ("Coolant distribution unit", (30, 20), {}, _box_with(_cdu_art)),
    "P-HX": ("Plate heat exchanger", (10, 20), {}, _hx_plate),
    "P-CRAH": ("Air handler / fan wall, CHW coil", (30, 20), {},
               _box_with(_crah_art)),
    "P-DRYCOOLER": ("Dry cooler", (30, 28), {}, _dry_cooler),
    "P-EQUIP": ("Equipment", (30, 20), {}, _box_with(lambda c: None)),
    "P-INST": ("Instrument, field mounted", (10, 10), {}, _instrument),
    "P-INST-PANEL": ("Instrument, panel or control system", (10, 10), {},
                     _instrument_panel),
    "P-ARROW": ("Flow direction", (3, 3), {}, _arrow),
    "P-OPC": ("Off-sheet connector", (12, 5), {}, _off_page),
}


def library() -> Dict[str, Block]:
    out = {}
    for name, (desc, size, ports, draw, atts) in ELECTRICAL.items():
        out[name] = _block(name, desc, IEC, size, ports, draw, atts)
    for name, (desc, size, ports, draw) in PROCESS.items():
        std = ISA if name.startswith("P-INST") else ISO
        atts = []
        if name.startswith("P-INST"):
            atts = [AttDef("FUNC", (0, 1.6), 2.5, align="MIDDLE_CENTER"),
                    AttDef("LOOP", (0, -2.0), 2.2, align="MIDDLE_CENTER")]
        out[name] = _block(name, desc, std, size, ports, draw, atts)
    return out


# ------------------------------------------------------- kind -> symbol

#: Electrical kinds drawn inline on a feeder, between the board and the load.
SLD_INLINE = {
    "breaker": "E-CB", "mccb_breaker": "E-CB", "mcb_breaker": "E-CB",
    "acb_breaker": "E-ACB", "fuse": "E-FUSE", "isolator": "E-ISO",
    "earthing_switch": "E-ISO", "contactor": "E-ISO",
    "current_transformer": "E-CT", "energy_meter": "E-METER",
    "power_meter": "E-METER", "soft_starter": "E-VSD",
}

#: Kinds drawn as a busbar, with feeders hanging off it.
SLD_BOARDS = {"switchboard", "mcc", "distribution_board", "panelboard",
              "busbar_section"}

SLD_NODES = {
    "transformer": "E-TX", "generator": "E-GEN", "motor": "E-MOTOR",
    "pump": "E-MOTOR", "compressor": "E-MOTOR", "ups": "E-UPS",
    "vfd": "E-VSD", "automatic_transfer_switch": "E-ATS",
    "static_transfer_switch": "E-STS", "ring_main_unit": "E-RMU",
    "pdu": "E-PDU", "utility_supply": "E-SUPPLY",
}

#: Device named by an interface's "device" attribute, for the protective
#: device a board puts on each of its feeders.
SLD_DEVICE = {"acb": "E-ACB", "cb": "E-CB", "mccb": "E-CB", "mcb": "E-CB",
              "fuse": "E-FUSE", "switch_fuse": "E-FUSE", "isolator": "E-ISO",
              "switch": "E-ISO"}

#: Process kinds drawn inline on a pipe line rather than as equipment.
PID_INLINE = {
    "valve": "P-GATE", "valve_gate": "P-GATE", "valve_globe": "P-GLOBE",
    "valve_ball": "P-BALL", "valve_butterfly": "P-BFLY",
    "valve_check": "P-CHECK", "valve_control": "P-CV",
    "pressure_relief_valve": "P-PRV", "strainer_y": "P-STRAINER",
    "strainer_basket": "P-STRAINER", "filter": "P-FILTER",
    "filter_bag": "P-FILTER", "orifice_plate": "P-ORIFICE",
    "venturi_tube": "P-ORIFICE", "flow_nozzle": "P-ORIFICE",
}

#: valve_type attribute on a generic "valve".
VALVE_TYPES = {"gate": "P-GATE", "globe": "P-GLOBE", "ball": "P-BALL",
               "butterfly": "P-BFLY", "check": "P-CHECK", "control": "P-CV"}

PID_EQUIPMENT = {
    "pump": "P-PUMP", "pump_positive_displacement": "P-PUMP",
    "tank": "P-TANK", "pressure_vessel": "P-TANK",
    "vessel_horizontal": "P-TANK", "expansion_tank": "P-EXPTANK",
    "air_separator": "P-AIRSEP", "chiller": "P-CHILLER", "cdu": "P-CDU",
    "heat_exchanger": "P-HX", "heat_exchanger_plate": "P-HX",
    "heat_exchanger_shell_tube": "P-HX", "dry_cooler": "P-DRYCOOLER",
    "cooling_tower": "P-DRYCOOLER", "crah": "P-CRAH",
}

#: Control-domain kinds drawn as ISA bubbles, and their function letters.
INSTRUMENT_LETTERS = {
    "flow_transmitter": "FT", "pressure_transmitter": "PT",
    "temperature_transmitter": "TT", "level_transmitter": "LT",
    "pressure_gauge": "PI", "temperature_indicator": "TI", "sensor": "XE",
    "gas_detector": "AT", "proximity_sensor": "ZS", "limit_switch": "ZS",
}
