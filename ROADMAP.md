# debim-ingetrazo Roadmap

This document outlines the milestones and roadmap for `debim-ingetrazo` (Building-as-Code Loader for IngeTrazo).

---

## 🗺️ Milestone Overview

### Phase 1: Core Extension MVP (Completed ✅)
- [x] **Repository Scaffolding & Packaging:** Standalone GitHub repo `PRIDA-TAKON/debim-ingetrazo` with CI workflows, metadata, and automated packaging tools (`tools/package_extension.py`).
- [x] **IngeTrazo Menu & UI Integration:** Registered under `Extensions > debim` with commands:
  - `Import .debim Manifest...` (with file dialog filter)
  - `Toggle Live Sync`
  - `Open Agentic AI Console`
- [x] **Native 3D Geometry Rendering:** Convert manifest elements into native IngeTrazo closed quad faces (`scene.mesh.add_face()`, `scene.bump_view()`, `viewport.update()`).
- [x] **Agent Bridge (Port 8482):** Local JSON-RPC / HTTP server enabling live streaming from external AI agents and Python scripts.
- [x] **In-App AI Console (`console.py`):** Interactive PySide6 editor dialog for live typing and injecting `.debim` manifests.
- [x] **Structural Core Classes:**
  - `Storey / Group` (`A-STOREY`, `A-GROUP`)
  - `Slab` (`S-SLAB` and `S-FOOTING`)
  - `Wall` (`A-WALL` with `Opening` support)
  - `Column` (`S-COLS` - Rectangular and Circular)
  - `Beam` (`S-BEAM` - Concrete beams with rebar metadata: `4DB12`, `RB9@0.15`)
- [x] **Catalog Registry:** Conforming `catalog_entry.json` for IngeTrazo Extensions Hub.

---

### Phase 2: debim CLI / IFC4-Minimal Standard Compatibility (Current & Upcoming 🚀)
Align `debim-ingetrazo` with the official debim CLI specification (`schema: IFC4-Minimal`).

- [ ] **Dual-Mode Parser:**
  - **Standard debim CLI mode:** `elements: [{ class: Ifc..., placement: { grid: ... } }]`
  - **Simplified mode:** `columns: [...]`, `beams: [...]`, `walls: [...]`, `slabs: [...]`
- [ ] **Structural Grid System (`grids` / `IfcGrid`):**
  - Parse `grids.axes_x` and `grids.axes_y`.
  - Grid mathematical expression evaluation (e.g. `["GX_1 + 0.10", "GY_1 - 0.10"]`).
  - Render 2D/3D grid axes and elevation levels directly in IngeTrazo viewport.
- [ ] **Complete BIM Entity Suite:**
  - **`IfcFooting` / `Footing`:** Dedicated isolated spread & pile footing class with automatic column base placement.
  - **`IfcRoof` / `Roof`:** Gable (จั่ว), Hip (ปั้นหยา), Shed (เพิงหมาแหงน), and Flat (ดาดฟ้า) parametric roofs.
  - **`IfcStair` / `Stair`:** Architectural stairs with automated tread, riser, and landing geometry.
  - **`IfcSpace` / `Space`:** Functional room boundaries, net area calculation ($m^2$), and translucent 3D zone rendering.
  - **`IfcDoor` / `IfcWindow`:** Parametric 3D window frames and door panels.
  - **`IfcFurniture` / `IfcEquipment`:** 3D sanitary and furniture blocks.

---

### Phase 3: Bi-Directional Engineering & Production (Future 🔮)
- [ ] **Bi-directional Sync:** Edit element in IngeTrazo viewport and synchronize back to `.debim.yaml`.
- [ ] **Instant QTO / BOQ Dialog:** Calculate concrete volume, formwork, and rebar tonnage directly inside IngeTrazo via debim zero-dependency engine.
- [ ] **PDF Layout & Sheet Plotting:** Automated 2D plan, elevation, section generation, and drawing border/titleblock layout for multi-sheet PDF plotting.
