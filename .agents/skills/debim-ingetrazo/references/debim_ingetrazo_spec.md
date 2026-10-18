# debim-ingetrazo Technical Specification & Entity Reference

This document details the geometry construction, layer conventions, anchor points, and rebar formatting rules implemented in `debim-ingetrazo`.

---

## 1. Supported Entity Catalog

### 1.1 Structural Foundations (`IfcFooting` / `Footing`)
- **Layer:** `S-FOOTING`
- **Color:** `#505050` (Dark Charcoal)
- **Anchor Point:** `TOP-CENTER`
- **Z-Behavior:** Thickness extends downwards into the ground ($-Z$).
- **Properties:**
  - `footing_type`: `SPREAD` (ฐานแผ่) or `PILE_CAP` (ฐานรากเสาเข็ม)
  - `dimensions`: `{ length: float, width: float, thickness: float }`
  - `placement`: `{ grid: ["GX", "GY"], offset_z: float }`

### 1.2 Structural Columns (`IfcColumn` / `Column`)
- **Layer:** `S-COLS`
- **Color:** `#4682B4` (Steel Blue)
- **Anchor Point:** `BOTTOM-CENTER`
- **Z-Behavior:** Base sits on the storey elevation ($Z_{\text{base}} = 0$); extrudes upward $+Z$ to height.
- **Profiles:**
  - `RECTANGULAR`: `dimensions: { width: float, depth: float }`
  - `CIRCULAR`: `dimensions: { diameter: float }`

### 1.3 Structural Beams (`IfcBeam` / `Beam`)
- **Layer:** `S-BEAM`
- **Color:** `#4169E1` (Royal/Steel Blue)
- **Anchor Point:** `TOP-CENTERLINE`
- **Z-Behavior:** Top of the beam aligns with the target datum/ceiling level; `depth` hangs downwards ($-Z$).
- **Rebar Annotations:**
  - Formats: `4DB12`, `2DB16 + 2DB12`, `RB9@0.15`
  - Main bars: `main_top`, `main_bottom`
  - Stirrup ties: `stirrups` (e.g. `RB9@0.15` or `RB6@0.20`)

### 1.4 Floor Slabs (`IfcSlab` / `Slab`)
- **Layer:** `S-SLAB`
- **Color:** `#A9A9A9` (Medium Concrete Gray)
- **Anchor Point:** `TOP-FINISH`
- **Z-Behavior:** Top surface sits at storey elevation ($Z = 0$); `thickness` drops downwards ($-Z$).
- **Boundary:** Listed in Counter-Clockwise (CCW) 2D polygon vertices `[[x1, y1], [x2, y2], ...]`.

### 1.5 Walls (`IfcWall` / `Wall`)
- **Layer:** `A-WALL`
- **Color:** `#D2B48C` (Tan / Brick-finish)
- **Anchor Point:** `BOTTOM-START-CENTERLINE`
- **Z-Behavior:** Sits on floor level, extends upwards $+Z$.
- **Openings:** Sub-elements of type `DOOR` or `WINDOW` with `{ width, height, offset_x, sill_height }` cut out automatic voids in the 3D wall mesh.

### 1.6 Roofs (`IfcRoof` / `Roof`)
- **Layer:** `A-ROOF`
- **Color:** `#A0522D` (Terracotta Clay)
- **Anchor Point:** `EAVES-LINE`
- **Types:**
  - `GABLE` (หลังคาจั่ว)
  - `HIP` (หลังคาปั้นหยา)
  - `SHED` (หลังคาเพิงหมาแหงน)
  - `FLAT` (หลังคาดาดฟ้าคอนกรีต)
- **Parameters:** `pitch_deg` (ความชันหลังคา), `eaves_overhang` (ระยะยื่นชายคา).

### 1.7 Stairs (`IfcStair` / `Stair`)
- **Layer:** `A-STAIR`
- **Color:** `#8B4513` (Saddle Brown / Hardwood)
- **Anchor Point:** `BOTTOM-START`
- **Geometry:** Parametrically generated treads (ลูกนอน), risers (ลูกตั้ง), and landing platforms (ชานพัก).

### 1.8 Architectural Spaces (`IfcSpace` / `Space`)
- **Layer:** `A-SPACE`
- **Color:** `#7FFFD4` with 25% Alpha (Translucent Aquamarine)
- **Anchor Point:** `BOTTOM-PERIMETER`
- **Geometry:** Semi-transparent 3D volume representing functional rooms (Living, Bedroom, Kitchen, Restroom) with automated net floor area calculation ($m^2$).

### 1.9 Doors & Windows (`IfcDoor` / `IfcWindow`)
- **Layer:** `A-DOOR` / `A-GLAZ`
- **Colors:** `#8B5A2B` (Door wood) / `#87CEEB` (Window glass)
- **Geometry:** Outer frames, glass pane infill, and opening clearance swing indications.

---

## 2. Structural Grids & Math Evaluation

`debim-ingetrazo` parses the `grids` object with standard mathematical offset expressions:

```yaml
grids:
  axes_x:
    - id: "GX_1"
      position: 0.0
    - id: "GX_2"
      position: 4.5
    - id: "GX_3"
      position: 8.5
  axes_y:
    - id: "GY_A"
      position: 0.0
    - id: "GY_B"
      position: 5.0
```

Placement expressions support relative offsets:
- `grid: ["GX_1", "GY_A"]` $\rightarrow (0.0, 0.0)$
- `grid: ["GX_2 + 0.20", "GY_B - 0.15"]` $\rightarrow (4.5 + 0.20, 5.0 - 0.15) = (4.70, 4.85)$
