# RD110 one-line importer

Reads the electrical one-line of Schneider Electric's Reference Design 110
(a public 10 MW GB300 data centre design) into an IndustroML model, keeping
the drawing's arrangement so `drawings` can redraw it as a formal SLD.

The drawing is Schneider Electric's and is not in this repository. Download
the RD110 package from se.com and point the importer at
`RD110_2.2_Elec_Oneline_EN_R0.dxf`:

```bash
python3 -m importers.rd110.sld RD110_2.2_Elec_Oneline_EN_R0.dxf \
    --variant paris --out examples/models/rd110_elec_paris.yaml
python3 -m drawings examples/models/rd110_elec_paris.yaml --sld --out out/
```

The DXF holds the IT room once and the mechanical plant twice, sized for
Paris and for Singapore. A model is the IT room plus one mechanical
variant. The two variants share every connection; they differ only in the
mechanical plant's ratings (transformers and generators 2500 kVA in Paris,
2000 kVA in Singapore; boards 66 kA and 50 kA).

## What comes out

| | Each variant |
|---|---|
| Breakers | 168, on their boards, with designation, frame and trip |
| Boards | 12 switchboards, with current, voltage, earthing and fault level |
| Sources | 6 transformers, 6 generators, 6 HV supplies, with nameplates |
| UPS | 12 Galaxy VXL (IT), 2 Galaxy VL (mechanical) |
| Busways | 24, four to each rack group of 16 racks |
| Loads | chillers, CDUs, fan walls, pumps, condenser fans, DX units, rack groups |
| Cables | 362, each with its path on the sheet |

The examples are `examples/models/rd110_elec_paris.yaml` and
`rd110_elec_singapore.yaml`, and the Paris SLD redrawn on two sheets in
`examples/outputs/drawings/rd110_elec_paris_sld_*`.

## Found in the source

- **A repeated designation.** IT CRITICAL SWBD C has two breakers labelled
  `AIIT-3.2C` and none labelled `AIIT-3.1C`. Both are kept; the second is
  `CB-AIIT-3_2C-DUP2`, with a `check` attribute saying so. Its feed (rack
  group 65-80, the one `AIIT-3.1D` feeds on board D) suggests it is 3.1C.
- **Four spares** on the mechanical critical boards feed nothing, as drawn.

## How it reads the drawing

The module docstring in `sld.py` has the detail. In short: breakers are the
only real block; boards and busways are thick polylines; transformers,
generators, UPS and loads are recognised from their geometry and labels;
cables are traced from each breaker's terminals. RD110 draws a cable
crossing another with a short break, and a busway in two halves either side
of its notes. The importer joins each break only where the two ends face
each other along one line, and treats an end landing on the crossed cable
as a crossing, not a tee.

Tests are in `tests/test_rd110_importer.py`. The full-read tests run when
`RD110_SLD_DXF` names the DXF, and skip otherwise.
