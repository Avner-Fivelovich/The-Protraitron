# Portraitron 3000 - Task List

## Setup & Core Maintenance
- [x] **Core-1: Update Requirements and README**
- [x] **Core-2: Fix SwiftSketch Non-Square Image Masking Bug**
  - Fix dimension mismatch crash in `create_masked_image` inside the `swiftsketch` repository (in both ControlSketch and SwiftSketch utils) by dynamically resizing the generated `1024x1024` mask back to the original image dimensions before masking.
- [x] **Core-3: Preprocess Input Image for SwiftSketch to Prevent Shape Mismatches**
  - If the input image causes dimension mismatch errors, preprocess it by padding with white pixels to make it square (e.g., `1024x1024` or matching its maximum dimension) to preserve its original aspect ratio without smearing/stretching. Save it to a temporary path and pass that to the SwiftSketch generator.


## Track A: Robot & Vector Drawing
- [x] **A1: SVG Vector Drawing Engine**
  - Implement XML parser to extract `<path>` elements and path commands (M, L, C, Q, Z, etc.).
  - Convert Bézier vectors to interpolated list of physical (x, y) coordinates.
  - Test normalization function to center and fit paths inside physical canvas limits (19x27 cm).
  - Implement coordinate transform from normalized canvas [0,1] to UR5e Base frame coordinate system via calibration references P1 and width/height.
- [x] **A2: TSP Stroke Order Optimization**
  - Write a path order optimizer module (e.g., Nearest Neighbor search or 2-opt heuristic).
  - Implement "Double-Ended TSP" where each path can be reversed to make its start point closer to the previous endpoint.
  - Plot/compare overall travel distance (air vs. drawing) before and after optimization.
  - Compare execution times in dryrun mode on complex portrait layouts.
- [x] **A3: SwiftSketch Core Integration**
  - Use the pre-existing conda environment `swiftsketch_env` with PyTorch and pydiffvg.
  - Create python interface in `swiftsketch_integration.py` that runs SwiftSketch inference via conda run subprocess.
  - Expose key parameters as CLI flags (e.g. `--sketch`) and config options in `marker.yaml`.
  - Verify output curves are properly generated, loaded, and optimized.


## Track C: Server, Camera & UX
- [x] **C1: Direct Camera/Phone Capture**
  - Implement video capture interface.
  - Write automatic face cropping logic.
  - Add background removal/masking filter.
  - Build preview loop.
- [x] **C2: FastAPI Server & Web Portal** (Completed)
  - Initialize a FastAPI server.
  - Build responsive web dashboard.
  - Integrate queue management system.
  - Implement security handshakes.
- [x] **B1: Stamp Branding Graphic Design** (Completed)

## Physical & Hardware Tasks (Blocked / Manual)
- [ ] **[BLOCKED/MANUAL] B2: 3D Modeling & Printing Stamp** (In Progress)
  - Design CAD model for the stamp bracket.
  - Translate logo SVG into a raised 3D surface model.
  - Perform test prints using flexible material (TPU) to evaluate surface flatness/rigidity.
  - Define the tool offset parameters (X, Y, Z translation from robotic tool center point).
- [ ] **[BLOCKED/MANUAL] B3: Procure Stamp Ink & Pads**
  - Identify and order stamp ink.
  - Calibrate the physical 3D coordinate of the inkpad base.
  - Create robot routines to "refill ink" by pressing the stamp onto the pad using controlled force.
- [ ] **[BLOCKED/MANUAL] C3: Souvenir Delivery Model**
  - Design and test clamping/board plate fixture.
  - Determine safety zones for robot arm retract/homing.
  - Select high-quality paper stock.
- [ ] **[BLOCKED/MANUAL] C4: Phone/DSLR External Camera Connection Integration**
  - Implement integration for external DSLRs or smartphones as camera feeds.
  - Support IP camera feed fetch (MJPEG/RTSP) for smartphones on the same network.
  - Test gphoto2 or USB camera control protocols for DSLR capture.


