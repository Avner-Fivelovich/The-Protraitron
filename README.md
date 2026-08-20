# The Portraitron 3000 🎨🤖
> An end-to-end automated robotic system that captures a subject's portrait, translates it into optimized vector paths using generative AI, and physically draws it with a UR5e robotic arm.

---

## 📌 Project Overview
**The Portraitron** is a complete, automated robotic artist. The system runs the following pipeline:
1. **Subject Capture**: High-definition image capture of the subject.
2. **Stroke Generation**: Converts the raster portrait into vector strokes using the **SwiftSketch** diffusion model.
3. **Path Optimization**: Solves the Double-Ended Traveling Salesperson Problem (TSP) using a Nearest Neighbor search and 2-opt heuristic to minimize transition travel distance by over 80%.
4. **Robotic Execution**: Executes precision coordinates control on a **UR5e** robotic arm via compliance force control to physically draw the portrait.
5. **Branding & Delivery**: Presses a custom 3D-printed stamp onto an inkpad, applies a commemorative stamp mark, and retracts safely.

---

## 💻 Tech Stack & Environment
The project leverages two decoupled environments to keep robotic real-time control isolated from heavy deep-learning dependencies:

### 1. Robot Control Environment (`./venv`)
Runs the main control orchestration, calibration, and trajectory planning.
* **Core**: Python 3.9+
* **Dependencies**: `ur-rtde` (Universal Robots RTDE interface), `numpy`, `matplotlib`, `pyyaml`, `pillow`, `opencv-python`, `fastapi`, `uvicorn`, `python-multipart`
* **Setup**:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  python3 -m pip install -r requirements.txt
  ```

### 2. AI Sketching Environment (`swiftsketch_env` Conda)
Runs the SwiftSketch neural networks.
* **Core**: Python 3.9.19 (Conda)
* **Dependencies**: `PyTorch`, `torchvision`, `pydiffvg` (differentiable vector graphics), `CLIP`
* **Apple Silicon GPU (MPS) Support**: Fully optimized to run on macOS Metal Performance Shaders (MPS), executing the 50 diffusion steps in **1 second** (accelerated from ~2 minutes on CPU).

---

## ⚙️ SwiftSketch Setup & Checkpoints

### 1. Clone Side-by-Side
For relative paths to resolve automatically, clone the `swiftsketch` repository in the same parent directory:
```bash
# Parent Folder
git clone https://github.com/swiftsketch/swiftsketch.git
git clone https://github.com/YourUsername/The-Portraitron-AI-agent.git
```

### 2. Create the Conda Environment
```bash
cd ../swiftsketch
conda create -n swiftsketch_env python=3.9.19 -y
conda activate swiftsketch_env
pip install torch==2.3.1 torchvision==0.18.1 torchaudio==2.3.1
pip install -r requirements.txt
pip install git+https://github.com/openai/CLIP.git
```

### 3. Pre-trained Checkpoints
Download the pre-trained checkpoints from Google Drive, unzip them, and place them inside the `swiftsketch/SwiftSketch/save/` directory:
* [sketch-diffusion](https://drive.google.com/uc?export=download&id=19FryO99dCmz-Dw1jzeZITUI0uuksiOA-)
* [refinement-network](https://drive.google.com/uc?export=download&id=1OrLzwaJXZ4SlDw3hqn71Yg1L01ytLv2x)

Expected structure:
```
swiftsketch/SwiftSketch/save/
├── sketch-diffusion/
│   ├── args.json
│   └── model000450000.pt
└── refinement-network/
    ├── args.json
    └── model000430000.pt
```

---

## 🚀 Execution & Command-Line Options

The main script [main.py](main.py) coordinates the entire system.

### Interactive Menu
To launch the interactive control panel:
```bash
./venv/bin/python main.py
```
This prints the following options banner:
```
1. POC (Semicircle & Diameter)
2. Write Custom Text
3. Draw SVG file
4. Sketch & Draw Portrait (SwiftSketch)
5. Capture Photo from Webcam & Sketch
```

### One-Shot CLI Modes
You can bypass the interactive menu by calling direct flags:

* **POC Semicircle Drawing**:
  ```bash
  ./venv/bin/python main.py --POC left --radius 5.0 --angle 180.0
  ```
* **Custom Text Writing**:
  ```bash
  ./venv/bin/python main.py --text "Hello World"
  ```
* **SVG Drawing**:
  ```bash
  ./venv/bin/python main.py --svg plots/trajectory_preview.svg
  ```
* **Sketch & Draw Portrait (SwiftSketch AI)**:
  Runs SwiftSketch on the target image, generates the SVG vectors, runs TSP path optimization, and draws it:
  ```bash
  ./venv/bin/python main.py --sketch pictures/portrait.jpg
  ```
* **Webcam Capture & Sketch**:
  Opens a video stream preview, crops the face, extracts the foreground with a vignetted background mask, runs SwiftSketch, and draws it:
  ```bash
  ./venv/bin/python main.py --capture
  ```

### Advanced Configuration & Safety Flags
* **Dry Run Mode (`--dryrun` / `-d`)**: Plots the expected drawing output via Matplotlib without connecting to the physical robot. Prepend `MPLBACKEND=Agg` for headless execution (e.g. in background terminal sessions).
  ```bash
  MPLBACKEND=Agg ./venv/bin/python main.py --dryrun --sketch pictures/portrait.jpg
  ```
* **Path Optimization Control**:
  * `--optimize`: Enable pre-TSP ordering, stroke merging, and post-TSP path optimization (default: True).
  * `--no-optimize`: Disable TSP optimization.
* **Background Noise Masking**:
  * `--mask <path_to_mask.png>`: Filters out strokes that are background noise outside the subject.
  * `--mask-keep-ratio <ratio>`: Ratio of stroke coordinate points that must lie within the white/foreground region of the mask to keep the stroke (default: `0.7`). Automatically generates comparison logs and preview plots for `80%`, `85%`, `90%`, and `95%` keep ratios under `plots/` to help evaluate thresholds.
* **Stroke Merging (Continuous Chains)**:
  * `--merge-threshold <meters>`: Connects consecutive stroke endpoints that are within a physical distance threshold (default: `0.002` m / 2.0 mm). Minimizes the count of pen lifts. Setting this to `0.0` disables merging.
* **Safety Approval Prompt**:
  * `--approve`: Safety control flag for physical drawings. Displays the expected drawing preview blocking plot; closing the plot prompts you in the terminal for verification before starting the physical robot movements.
  * **Interactive TTY Safeguard**: The script detects non-interactive terminals automatically (e.g., background servers or cron jobs) and auto-cancels physical drawing to prevent safety lockups.

---

## 🎛️ Interactive Web Command Dashboard Server

We have added a custom, standard-library-based multi-threaded web controller dashboard to easily configure drawing parameters visually, generate CLI commands, and execute/abort them with real-time logging.

### Start the Control Server
```bash
./venv/bin/python command_generator_server.py
```
Then, open **http://localhost:8080** in your browser.

### Features
* **Live Command Builder**: Drag sliders for **Mask Keep Ratio** and **Merge Threshold**, toggle TSP or Dry Run options, and view the generated command update in real-time.
* **Stream Terminal Console**: Runs drawing executions asynchronously and streams standard stdout/stderr logs in real-time inside a dark dashboard console window.
* **Abort Execution**: Kill running physical/dryrun drawing processes instantly with a click of a button.

---

## 🌐 FastAPI Web Server & Client Dashboard

For a production environment or remote capture kiosk, run the local FastAPI service:

### Start the Server
```bash
./venv/bin/python src/server/main.py
```
This boots a web server listening on `http://0.0.0.0:8000`.

### Features
1. **Subject Capture Tab**: Stream live camera streams over local networks, frame subjects inside alignment guides, and capture photos.
2. **File Upload Tab**: Standard drag-and-drop interface for local images.
3. **Queue Telemetry**: A background worker thread queue that draws sequential jobs and posts real-time coordinate drawing progress values.
4. **Passcode Handshake**: Protects the physical robot from unauthorized trigger requests (default passcode: `portraitron` configurable in `config/marker.yaml`).

## 🛠️ Scripts & Tools Documentation

All peripheral scripts for hardware calibration, diagnostics, and notifications have dedicated markdown documentation files. Explore them here:

* [Paper Calibration GUI](docs/scripts/calibrate_paper_gui.md) - Adjust physical gripper boundaries, paper swaps, and jog the robot intuitively.
* [Workspace Calibration](docs/scripts/calibrate_workspace.md) - Force-probing the drawing surface and locking in the canvas box coordinates.
* [Go-to YAML Location](docs/scripts/go_to_ymal_location.md) - Diagnostic script to move the UR5e to any pre-saved YAML coordinate.
* [Record Location to YAML](docs/scripts/record_location_to_ymal.md) - Save the current robot end-effector position to config files dynamically.
* [Send Notification](docs/scripts/send_notification.md) - Integration tool to push job completion/status updates to smartphones.
* [Test UR5e Connection](docs/scripts/test_ur5e_connection.md) - Simple diagnostic to verify RTDE network links and host reachability.
