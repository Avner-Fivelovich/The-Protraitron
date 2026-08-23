# 🎨 The Portraitron 3000 — Roadmap & Task Tracker

> Master tracking document for the Portraitron 3000 robotic portrait sketcher. Tracks algorithmic development, robot control integration, web infrastructure, and physical hardware deployment.

---

## 📊 Progress Summary

| Track / Category | Focus Area | Status |
| :--- | :--- | :--- |
| **Setup & Core** | Environment setup, patching & preprocessing pipeline | ✅ **Completed** (3/3) |
| **Track A** | Robot motion control, trajectory planning & SwiftSketch | ✅ **Completed** (3/3) |
| **Track B** | Stamp branding, 3D printing & physical inking end-effector | 🟡 **In Progress / Blocked** (1/3) |
| **Track C** | Vision capture pipeline, FastAPI server, UI & hardware fixture | 🟡 **In Progress / Blocked** (2/4) |

---

## 🛠️ Setup & Core Maintenance

- [x] **Core-1: Update Requirements & Documentation**
  - Audit and consolidate Python virtual environment (`venv`) and Conda (`swiftsketch_env`) requirements.
  - Maintain comprehensive setup documentation in `README.md`.

- [x] **Core-2: Fix SwiftSketch Non-Square Image Masking Bug**
  - Fix dimension mismatch crash in `create_masked_image` inside the `swiftsketch` repository (in both ControlSketch and SwiftSketch utils) by dynamically resizing the generated `1024×1024` mask back to the original image dimensions before masking.

- [x] **Core-3: Preprocess Input Images for SwiftSketch to Prevent Shape Mismatches**
  - Implement square aspect ratio padding with white pixels (e.g., `1024×1024` or matching the maximum dimension) to preserve original aspect ratio without distortion/smearing.
  - Automatically save padded preprocessed images to temporary paths and pass them to the SwiftSketch generator.

---

## 🤖 Track A: Robot Control & Vector Drawing

- [x] **A1: SVG Vector Drawing Engine**
  - Implement XML parser to extract `<path>` elements and path commands (`M`, `L`, `C`, `Q`, `Z`, etc.).
  - Convert Bézier vector curves into an interpolated sequence of physical `(x, y)` coordinates.
  - Implement normalization functions to center and fit paths within physical canvas boundaries (`19 × 27 cm`).
  - Implement coordinate transformation from normalized canvas space `[0, 1]` to UR5e Base frame coordinate system using calibration reference `P1` and canvas width/height.

- [x] **A2: TSP Stroke Order Optimization**
  - Write a trajectory order optimization module using Nearest Neighbor search and 2-opt heuristics.
  - Implement **Double-Ended TSP** (allowing stroke reversal) to minimize air transit distances between endpoints.
  - Benchmark and plot travel distance metrics (drawing vs. air transit) before and after optimization.
  - Verify trajectory timing and execution efficiency in dry-run mode on complex portrait layouts.

- [x] **A3: SwiftSketch Core Integration**
  - Interface with the dedicated `swiftsketch_env` Conda environment containing PyTorch and `pydiffvg`.
  - Create Python bridge in `src/sketching/swiftsketch_integration.py` running SwiftSketch inference via subprocess.
  - Expose CLI arguments (e.g., `--sketch`) and YAML configuration options in `config/marker.yaml`.
  - Validate output curve generation, parsing, normalization, and optimization pipeline.

---

## 🏷️ Track B: Stamp Branding & Physical Hardware

- [x] **B1: Stamp Branding Graphic Design**
  - Design vector graphic / logo for the commemorative Portraitron signature stamp.
  - Export clean vector SVG assets for 3D extrusion modeling.

- [ ] **[BLOCKED / MANUAL] B2: 3D Modeling & Stamp Printing** *(In Progress)*
  - Design CAD mounting bracket for the robot end-effector.
  - Convert signature logo SVG into a raised 3D surface model.
  - Test print stamp pads using flexible filament (TPU) to evaluate surface flatness, ink retention, and compliance.
  - Define tool center point (TCP) offset parameters (`X`, `Y`, `Z` translations relative to UR5e tool flange).

- [ ] **[BLOCKED / MANUAL] B3: Procure Stamp Ink & Physical Inking Pad**
  - Select and procure fast-drying, high-contrast archival stamp ink and inkpads.
  - Calibrate the physical 3D base coordinates and surface normal of the inkpad fixture.
  - Implement robotic re-inking motion routine utilizing UR5e force-torque compliance control.

---

## 🌐 Track C: Vision, Server & User Experience

- [x] **C1: Direct Camera & Phone Capture Pipeline**
  - Implement video capture interface (webcam and direct stream).
  - Add automated face detection and bounding box cropping logic.
  - Implement background removal / subject segmentation filter.
  - Provide real-time live preview feedback loop.

- [x] **C2: FastAPI Server & Web Portal Dashboard**
  - Initialize FastAPI backend server with REST endpoints and WebSocket channels.
  - Build responsive web dashboard for portrait submission and status monitoring.
  - Integrate request queue management system with state machine transitions.
  - Implement security handshakes and command dispatching.

- [ ] **[BLOCKED / MANUAL] C3: Souvenir Delivery Fixture & Paper Handling**
  - Design and test paper clamping / mounting board fixture on the drawing table.
  - Establish safe workspace boundaries and robot arm homing/retraction safety zones.
  - Select optimal paper stock (texture, weight, ink absorption).

- [ ] **[BLOCKED / MANUAL] C4: Phone / DSLR External Camera Integration**
  - Implement network camera stream capture (MJPEG / RTSP) for smartphone clients on local Wi-Fi.
  - Integrate `gphoto2` or USB tethered camera control protocols for high-res DSLR capture.
  - Add auto-focus trigger and image transfer synchronization.

---

## 📌 Legend & Status Definitions

- ✅ **Completed**: Implemented, tested, and integrated into master workflow.
- 🟡 **In Progress**: Active development or pending physical validation.
- 🔴 **Blocked / Manual**: Requires physical hardware access, procurement, or manual mechanical assembly.
