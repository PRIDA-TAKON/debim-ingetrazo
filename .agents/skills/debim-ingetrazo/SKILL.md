---
name: debim-ingetrazo
description: 3D architectural modeling, live canvas visualization, and real-time viewport streaming for .debim (Building-as-Code) models in IngeTrazo. Use when asked to visualize debim models in 3D, stream models live to IngeTrazo via Agent Bridge (port 8482), develop or debug debim-ingetrazo extension, validate IFC4-Minimal geometry anchors, or roundtrip between IngeTrazo and debim CLI.
---

# debim-ingetrazo Skill — 3D Visualizer & Live Agent Bridge

**Version:** 0.1.0  
**Target Platform:** IngeTrazo 3D Modeler (>= 0.5.8)  
**Specification:** debim OpenBIM Building-as-Code & IFC4-Minimal Standard

This skill guides AI agents in modeling, visualizing, and live-streaming `.debim` declarative manifests into the **IngeTrazo 3D Modeler** in real time.

---

## 🏛️ Ecosystem Overview & Separation of Concerns

The debim ecosystem is composed of two decoupled, complementary tools communicating via the open `.debim` specification:

1. **`debim CLI` (Core Engine):**
   - Headless deterministic engine for BOQ calculation, QTO take-offs, 2D drafting (`debim draw`), and IFC4 compilation (`debim ifc`).
   - Heavy dependencies (e.g. `ifcopenshell`, `ezdxf`, `reportlab`) are kept optional or standalone.
2. **`debim-ingetrazo` (3D Interactive Canvas & Visualizer):**
   - Lightweight plugin running inside IngeTrazo.
   - Parses `.debim` manifests and constructs native 3D geometry (`scene.mesh.add_face()`, layers, colors).
   - Hosts the **Agent Bridge** on `http://127.0.0.1:8482` so AI agents can live-stream models into the active 3D viewport instantly without touching the GUI.
   - **Keep it lean:** No BOQ or PDF plotting bloat inside the extension. It outputs valid `.debim.yaml` files and delegates heavy engineering calculations to `debim CLI`.

---

## ⚡ Live Streaming via Agent Bridge (Port 8482)

When IngeTrazo is running with `debim-ingetrazo` loaded, an internal HTTP & JSON-RPC listener runs on `http://127.0.0.1:8482`.

### 1. Probe Listener Status
Check if IngeTrazo is running and listening:
```bash
python scripts/send_to_ingetrazo.py --probe
```
Or via standard HTTP GET:
```bash
curl -s http://127.0.0.1:8482
```
Expected Response:
```json
{
  "status": "online",
  "service": "debim-ingetrazo Agent Bridge",
  "host": "127.0.0.1",
  "port": 8482,
  "received_count": 0
}
```

### 2. Stream a Manifest (Zero External Dependencies)
Push any `.debim` or `.debim.yaml` model to the IngeTrazo viewport using standard Python:

```bash
python scripts/send_to_ingetrazo.py -f path/to/model.debim.yaml
```

Or execute directly via Python one-liner in any agent workflow:
```python
import urllib.request

manifest_text = """
project:
  name: "Living Pavilion"
  units: "m"
storeys:
  - id: "ST_01"
    name: "Ground"
    elevation: 0.0
    height: 3.5
    columns:
      - id: "C1"
        position: [0, 0]
        section: [0.4, 0.4]
        height: 3.5
"""

req = urllib.request.Request(
    "http://127.0.0.1:8482",
    data=manifest_text.encode("utf-8"),
    headers={"Content-Type": "text/plain; charset=utf-8"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=5) as resp:
    print("IngeTrazo updated:", resp.status)
```

---

## 📐 Dual-Mode Manifest Formats

`debim-ingetrazo` supports two authoring formats seamlessly:

### Mode A: Standard `schema: IFC4-Minimal` (Official debim CLI Specification)
Strict open standard format used for interoperability between debim CLI and IngeTrazo:
```yaml
schema: "IFC4-Minimal"
project:
  name: "Modern Residence"
  units: "m"
grids:
  axes_x: [{ id: "GX_1", position: 0.0 }, { id: "GX_2", position: 5.0 }]
  axes_y: [{ id: "GY_1", position: 0.0 }, { id: "GY_2", position: 6.0 }]
storeys:
  - id: "ST_01"
    name: "Level 1"
    elevation: 0.0
    height: 3.5
elements:
  - id: "F1"
    class: "IfcFooting"
    storey: "ST_01"
    footing_type: "SPREAD"
    dimensions: { length: 1.2, width: 1.2, thickness: 0.35 }
    placement: { grid: ["GX_1", "GY_1"], offset_z: -0.85 }

  - id: "C1"
    class: "IfcColumn"
    storey: "ST_01"
    profile: "RECTANGULAR"
    dimensions: { width: 0.3, depth: 0.3 }
    height: 3.5
    placement: { grid: ["GX_1", "GY_1"] }

  - id: "B1"
    class: "IfcBeam"
    storey: "ST_01"
    dimensions: { width: 0.2, depth: 0.45 }
    placement: { from_grid: ["GX_1", "GY_1"], to_grid: ["GX_2", "GY_1"] }
    rebar:
      main_top: "2DB16"
      main_bottom: "3DB16"
      stirrups: "RB9@0.15"

  - id: "SLAB_01"
    class: "IfcSlab"
    storey: "ST_01"
    thickness: 0.15
    boundary:
      - ["GX_1", "GY_1"]
      - ["GX_2", "GY_1"]
      - ["GX_2", "GY_2"]
      - ["GX_1", "GY_2"]

  - id: "W1"
    class: "IfcWall"
    storey: "ST_01"
    thickness: 0.10
    height: 3.0
    start_point: [0.0, 0.0]
    end_point: [5.0, 0.0]
    openings:
      - id: "OP_D1"
        opening_type: "DOOR"
        width: 1.0
        height: 2.2
        offset_x: 1.5

  - id: "SP_LIVING"
    class: "IfcSpace"
    storey: "ST_01"
    name: "Living Room"
    height: 3.0
    boundary:
      - [0.0, 0.0]
      - [5.0, 0.0]
      - [5.0, 6.0]
      - [0.0, 6.0]
```

### Mode B: Simplified Declarative Manifest
Hierarchical, compact format ideal for rapid AI generation:
```yaml
project:
  name: "Compact Villa"
  units: "m"
storeys:
  - id: "ST_01"
    name: "Ground Floor"
    elevation: 0.0
    height: 3.2
    slabs:
      - id: "S1"
        thickness: 0.15
        boundary: [[0, 0], [6, 0], [6, 4], [0, 4]]
    columns:
      - id: "C1"
        position: [0, 0]
        section: [0.3, 0.3]
        height: 3.2
    beams:
      - id: "B1"
        start_point: [0, 0]
        end_point: [6, 0]
        section: [0.2, 0.4]
        elevation: 3.2
        rebar:
          main: "4DB12"
          stirrups: "RB9@0.15"
    walls:
      - id: "W1"
        start_point: [0, 0]
        end_point: [6, 0]
        thickness: 0.1
        height: 3.2
```

---

## 🎯 Coordinate & Anchor Standards (Immutable Rules)

To eliminate rendering artifacts and Z-fighting in IngeTrazo, adhere to the deterministic anchor standards:

| Entity Class | Anchor Point | Z-Direction & Behavior | CAD Layer | Default Color |
| :--- | :--- | :--- | :--- | :--- |
| **`IfcFooting`** | `TOP-CENTER` | Thickness drops down ($-Z$) into soil | `S-FOOTING` | Dark Gray (`#505050`) |
| **`IfcColumn`** | `BOTTOM-CENTER` | Extrudes upwards ($+Z$) to ceiling | `S-COLS` | Blue-Gray (`#4682B4`) |
| **`IfcBeam`** | `TOP-CENTERLINE` | Depth hangs down ($-Z$) below slab/datum | `S-BEAM` | Steel Blue (`#4169E1`) |
| **`IfcSlab`** | `TOP-FINISH` | Thickness drops down ($-Z$) to preserve clear room height | `S-SLAB` | Light Gray (`#A9A9A9`) |
| **`IfcWall`** | `BOTTOM-START-CENTERLINE`| Starts on floor, extends upwards ($+Z$) | `A-WALL` | Cream/Tan (`#D2B48C`) |
| **`IfcRoof`** | `EAVES-LINE` | Slopes upwards at pitch angle $\theta$ | `A-ROOF` | Terracotta (`#A0522D`) |
| **`IfcStair`** | `BOTTOM-START` | Steps up ($+Z$) with risers and treads | `A-STAIR` | Wood/Gray (`#8B4513`) |
| **`IfcSpace`** | `BOTTOM-PERIMETER` | Translucent zone ($+Z$), alpha 0.25 | `A-SPACE` | Soft Green/Cyan (`#7FFFD4`) |
| **`IfcDoor`** | `BOTTOM-CENTER` | Door frame + panel cutout | `A-DOOR` | Brown (`#8B5A2B`) |
| **`IfcWindow`**| `SILL-CENTER` | Frame + glazed panel | `A-GLAZ` | Translucent Blue (`#87CEEB`) |
| **`IfcGrid`** | `DATUM` | 2D/3D axes lines with balloons | `S-GRID` | Light Slate (`#708090`) |

### Critical Rules:
1. **Right-Handed Coordinates:** $+X = \text{East}$, $+Y = \text{North}$, $+Z = \text{Elevation (Up)}$.
2. **Counter-Clockwise (CCW) Vertices:** Polygon boundaries for slabs, spaces, and roofs **MUST** be listed in CCW order when viewed from above ($+Z$).
3. **Elevations:**
   - Elements inherit their storey's base elevation.
   - Beams placed at ceiling level have `elevation = storey.height`. Because their anchor is `TOP-CENTERLINE`, their bottom sits at `storey.height - depth`, preserving floor-to-ceiling clear height.

---

## 🛠️ CLI Utilities & Extension Tools

### Packaging the Extension for IngeTrazo Hub
Run the packaging tool inside `debim-ingetrazo`:
```bash
python tools/package_extension.py
```
Outputs `dist/debim-ingetrazo.zip` along with its SHA-256 hash.

### Installing in IngeTrazo
Copy the package folder `debim_ingetrazo` to:
- **Windows:** `%APPDATA%\ingetrazo\plugins\debim_ingetrazo`
- **Linux:** `~/.local/share/ingetrazo/plugins/debim_ingetrazo`
- **macOS:** `~/Library/Application Support/ingetrazo/plugins/debim_ingetrazo`

### Running Test Suite
```bash
python -m pytest
```
Verifies all 45+ unit and benchmark tests across parser, builder, agent bridge, watcher, and QTO metrics.

---

## 🔄 Roundtrip Handoff to `debim CLI`

Once a 3D model is reviewed in IngeTrazo:
1. Save or export to `.debim.yaml`.
2. Hand off to `debim CLI` for engineering documentation:
   ```bash
   debim qto project.debim.yaml        # Calculate exact concrete/steel/formwork volumes
   debim boq project.debim.yaml        # Generate CGD-compliant construction cost estimate
   debim draw --layout A3 --batch-pdf blueprints.pdf   # Plot full architectural & structural sheet set
   ```
