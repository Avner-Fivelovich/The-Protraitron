# The Portraitron: Robotic Portrait Artist

> An end-to-end autonomous robotic portraitist combining generative AI stroke synthesis, path optimization, and precision force-compliant UR5e robotic execution.

---

## 📌 Project Overview

**The Portraitron** is an automated robotic system designed to capture a subject's likeness and translate it into a physical artistic drawing using a Universal Robots UR5e 6-DOF robotic arm. The system bridges state-of-the-art generative diffusion models with real-time industrial robot trajectory planning and physical end-effector interaction.

---

## 👥 Project Team & Core Responsibilities

| Team Member | Primary Domain | Core Focus Areas |
| :--- | :--- | :--- |
| **Avner** | System Architecture & Robot Control | Real-time RTDE trajectory planning, TSP path optimization, system integration |
| **Hila** | Computer Vision & Generative AI | Subject capture, SwiftSketch diffusion integration, stroke synthesis |
| **Shira** | Hardware & Tooling Integration | End-effector design, 3D-printed mounts, paper handling & stamping mechanics |

---

## 🔄 End-to-End Workflow Pipeline

```mermaid
flowchart LR
    A[1. Subject Capture] --> B[2. Stroke Generation]
    B --> C[3. Path Optimization]
    C --> D[4. Robotic Drawing]
    D --> E[5. Commemorative Stamping]
    E --> F[6. Paper Delivery]
```

1. **Subject Capture & Preprocessing:**
   - Captures high-definition portrait photography via workspace vision cameras.
   - Detects facial landmarks, crops/centers the subject, and removes extraneous background.

2. **AI Stroke Generation (SwiftSketch):**
   - Converts raster portraits into vector stroke representations using the SwiftSketch diffusion model.
   - Utilizes Apple Silicon Metal Performance Shaders (MPS) for high-speed local inference (~1 second for 50 diffusion steps).

3. **Trajectory & Path Optimization:**
   - Translates vector paths into Cartesian tool trajectories.
   - Solves the Double-Ended Traveling Salesperson Problem (TSP) using Nearest Neighbor search and 2-opt heuristics to reduce air transition time by over 80%.

4. **Robotic Drawing Execution:**
   - Grips the drawing tool with the Robotiq 2F-85 adaptive gripper and custom 3D-printed tool mount.
   - Executes precise 3D trajectory control on the UR5e arm with compliant Z-axis force control for uniform line weight.

5. **Commemorative Stamping:**
   - Swaps/utilizes the dedicated stamp end-effector.
   - Inks the stamp on the inkpad fixture and applies a uniform commemorative mark on the finished artwork.

6. **Paper Delivery & Presentation:**
   - Releases the finished portrait and presents the artwork to the subject.

---

## 🛠️ Technology Stack & Environment

### Hardware Architecture
* **Robotic Arm:** Universal Robots UR5e (6-DOF collaborative arm with integrated force/torque sensing).
* **Gripper & Tooling:** Robotiq 2F-85 adaptive parallel gripper with custom 3D-printed pen and stamp mounts.
* **Vision System:** Dual 2D cameras (subject capture camera & workspace tracking camera).
* **Fixtures:** Calibrated drawing board, paper roll/bed mechanism, and inkpad station.

### Software Stack
* **Robotic Control:** Python 3.9+, `ur-rtde` (Real-Time Data Exchange protocol interface).
* **AI & Stroke Synthesis:** PyTorch, Torchvision, PyDiffVG (differentiable vector graphics), CLIP, SwiftSketch diffusion pipeline.
* **Computer Vision & Utilities:** OpenCV, Pillow, NumPy, PyYAML.
* **Interface & Orchestration:** FastAPI, Uvicorn, Interactive CLI, and Web Dashboard.

### Dual-Environment Architecture
* **Robot Control Environment (`./venv`):** Dedicated Python environment for deterministic real-time communication and hardware orchestration.
* **AI Generative Environment (`swiftsketch_env` Conda):** Dedicated PyTorch/MPS environment for heavy neural network dependencies and differentiable rendering.

---

## 📅 Project Timeline & Milestones

| Phase | Timeframe | Key Deliverables |
| :--- | :--- | :--- |
| **Phase 1: Foundation & Setup** | Weeks 1–4 | Hardware mounting, UR5e network configuration, RTDE setup, basic Cartesian trajectory control |
| **Phase 2: Vision & Stroke Generation** | Weeks 5–8 | Camera calibration, SwiftSketch pipeline integration, SVG-to-trajectory parsing, TSP path optimization |
| **Phase 3: Proof of Concept (POC)** | Week 9 | **POC Milestone:** Autonomous execution of semicircle and diameter drawing with compliant force control |
| **Phase 4: Full Integration & Polish** | Weeks 10–12 | End-to-end automated pipeline, automated stamping, paper delivery, interactive web UI, and final demo |

---

## 🎯 Proof of Concept (POC) - Week 9

* **Objective:** Execute a precision geometric drawing (semicircle arc and baseline diameter) autonomously.
* **Validation Criteria:**
  - Accurate transformation from 2D coordinate space to the robot's physical workspace plane.
  - Consistent pen pressure and stroke quality maintained via compliance / force control.
  - Smooth pen-up and pen-down transitions without ink blotches or paper tearing.
  - Reliable repeatability across multiple consecutive runs.

---

## 📊 Team Responsibility Matrix

| Task / Domain | Primary Lead | Supporting Members |
| :--- | :--- | :--- |
| **Vision & Image Processing** | Hila | Avner |
| **SwiftSketch Generative AI Pipeline** | Hila | Avner |
| **Robot Kinematics & RTDE Trajectory Control** | Avner | Shira |
| **Path Optimization (TSP & 2-Opt)** | Avner | Hila |
| **Mechanical Design & 3D-Printed Mounts** | Shira | Avner |
| **Stamping Station & Paper Handling** | Shira | Hila |
| **System Orchestration & Web UI** | Avner | Hila, Shira |
| **System Testing & Calibration** | All | All |
