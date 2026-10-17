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

### Phase 2: debim CLI / IFC4-Minimal Standard Compatibility (Completed ✅)
Align `debim-ingetrazo` with the official debim CLI specification (`schema: IFC4-Minimal`).

- [x] **Dual-Mode Parser:**
  - **Standard debim CLI mode:** `elements: [{ class: Ifc..., placement: { grid: ... } }]`
  - **Simplified mode:** `columns: [...]`, `beams: [...]`, `walls: [...]`, `slabs: [...]`
- [x] **Structural Grid System (`grids` / `IfcGrid`):**
  - Parse `grids.axes_x` and `grids.axes_y`.
  - Grid mathematical expression evaluation (e.g. `["GX_1 + 0.10", "GY_1 - 0.10"]`).
  - Render 2D/3D grid axes and elevation levels directly in IngeTrazo viewport.
- [x] **Complete BIM Entity Suite:**
  - **`IfcFooting` / `Footing`:** Dedicated isolated spread & pile footing class with automatic column base placement.
  - **`IfcRoof` / `Roof`:** Gable (จั่ว), Hip (ปั้นหยา), Shed (เพิงหมาแหงน), and Flat (ดาดฟ้า) parametric roofs.
  - **`IfcStair` / `Stair`:** Architectural stairs with automated tread, riser, and landing geometry.
  - **`IfcSpace` / `Space`:** Functional room boundaries, net area calculation ($m^2$), and translucent 3D zone rendering.
  - **`IfcDoor` / `IfcWindow`:** Parametric 3D window frames and door panels.
- [x] **E2E Benchmark & QTO Take-Off Validation:**
  - End-to-end benchmark validation against debim CLI playground models (`playground.debim.yaml` and `villa_db1.debim.yaml`).
  - Verification of element counts, dimensions, positions, and QTO take-off metrics (area, gross/net volume).

---

### Phase 3: Manifest Export & Seamless debim CLI Handoff (Final Polish 🎯)
Focus on producing a 100% valid, compliant `.debim` manifest from IngeTrazo to pass directly to `debim CLI`:
- [ ] **Export / Save .debim Manifest:** Menu action `Extensions > debim > Export .debim Manifest...` to serialize the active 3D model into a clean `schema: IFC4-Minimal` YAML file.
- [ ] **Model Validator:** Built-in lightweight schema validator to ensure zero syntax or continuity errors before handing off to `debim CLI`.
- [ ] **debim CLI Integration Trigger (Optional Shortcut):** Quick action to trigger `debim qto` or `debim boq` via CLI command without leaving the workflow.
- [ ] **Packaging & Extensions Hub Submission:** Final verification against IngeTrazo Extensions Hub catalog.

