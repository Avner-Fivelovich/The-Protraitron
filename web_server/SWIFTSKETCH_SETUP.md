# SwiftSketch Model Integration & Setup Guide

This guide provides step-by-step instructions for installing, configuring, and running the **SwiftSketch** diffusion model within The Portraitron web server ecosystem.

---

## 📌 Overview

**SwiftSketch** is a deep learning diffusion model that converts raster portrait images into high-quality vector sketches in SVG format by denoising stroke coordinates in vector space.

### Pipeline Architecture
```
[User Upload (Raster Image)]
           │
           ▼
┌───────────────────────────────────────────────┐
│              server.py                        │
│    (run_swiftsketch_pipeline Hook)            │
└──────┬─────────────────────────────────┬──────┘
       │ [GPU / SwiftSketch Available]   │ [Fallback / Error]
       ▼                                 ▼
┌───────────────────────────────┐ ┌──────────────────────────────┐
│  SwiftSketch / generate.py    │ │  Custom Vector Line Tracer   │
│  (Deep Learning Diffusion)    │ │  (Local Edge & Path Tracer)  │
└──────────────┬────────────────┘ └──────────────┬───────────────┘
               │                                 │
               └───────────────┬─────────────────┘
                               ▼
                    [Output Vector (.SVG)]
                               │
                               ▼
                   [G-Code Plotter Pipeline]
```

> [!NOTE]
> Because SwiftSketch relies on PyTorch, CUDA, and differentiable vector rendering (`diffvg`), it is strongly recommended to run this pipeline on a **GPU-enabled workstation** (e.g., laboratory PCs with NVIDIA GPUs). If running without a GPU or if dependencies are missing, `server.py` automatically falls back to the built-in custom vector tracer.

---

## 💻 System & Hardware Prerequisites

- **Operating System:** Windows 10/11, Linux (Ubuntu 20.04+ recommended), or macOS (CPU-only / experimental)
- **GPU:** NVIDIA GPU with at least 6GB–8GB VRAM and CUDA 11.8 or CUDA 12.1+
- **Python Version:** Python `3.9.x` (recommended for full compatibility with `diffvg` and PyTorch wheels)
- **C++ Compiler:**
  - **Windows:** Visual Studio 2019/2022 with **"Desktop development with C++"** and Windows SDK installed.
  - **Linux:** `build-essential`, `cmake`, and `gcc`/`g++` (>= 9.0).
  - **macOS:** Xcode Command Line Tools (`xcode-select --install`).

---

## 🚀 Part 1: Environment Setup

### 1. Create a Dedicated Conda or Python Environment
It is best practice to isolate dependencies using Conda:
```bash
conda create -n swiftsketch_env python=3.9.19 -y
conda activate swiftsketch_env
```

Alternatively, using standard `venv`:
```bash
python -m venv swiftsketch_env
# Windows:
swiftsketch_env\Scripts\activate
# Linux / macOS:
source swiftsketch_env/bin/activate
```

---

### 2. Install PyTorch with CUDA Support
Install PyTorch matching your CUDA version (CUDA 12.1 example):
```bash
pip install torch==2.3.1 torchvision==0.18.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cu121
```

To verify CUDA accessibility:
```bash
python -c "import torch; print('CUDA Available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
```

---

### 3. Compile and Install `diffvg` (Differentiable Vector Graphics)
`diffvg` compiles C++/CUDA rasterization primitives required by vector diffusion pipelines.

The repository includes `diffvg` as a submodule under `web_server/diffvg`. You can also clone it independently:

```bash
# Navigate to web_server/diffvg (or clone fresh)
cd web_server/diffvg
git submodule update --init --recursive

# Build and install into current environment
python setup.py install
```

> [!IMPORTANT]
> **Windows compilation note:** Ensure that your environment has `cl.exe` (MSVC) and `nvcc` in the system path. Launch your terminal via **"x64 Native Tools Command Prompt for VS"** if encountering compiler recognition issues.

---

### 4. Install Additional Dependencies
Install the remaining packages for CLIP, transformers, diffusion utilities, and the web server:

```bash
# Install CLIP directly from OpenAI's repository
pip install git+https://github.com/openai/CLIP.git

# Install diffusion and transformer tools
pip install diffusers transformers accelerate

# Install web server requirements
cd ../
pip install -r requirements.txt
```

---

## 📦 Part 2: Downloading Pretrained Model Checkpoints

SwiftSketch requires two pretrained model weights: the **sketch-diffusion** checkpoint and the **refinement-network** checkpoint.

1. Download the model files from the official Google Drive links:
   - **`sketch-diffusion` Checkpoint:** [Download model000450000.pt](https://drive.google.com/uc?export=download&id=19FryO99dCmz-Dw1jzeZITUI0uuksiOA-)
   - **`refinement-network` Checkpoint:** [Download model000430000.pt](https://drive.google.com/uc?export=download&id=1OrLzwaJXZ4SlDw3hqn71Yg1L01ytLv2x)

2. Organize the downloaded models in the `save/` directory inside `web_server/swiftsketch_model/SwiftSketch/save/`:

```
web_server/
└── swiftsketch_model/
    └── SwiftSketch/
        ├── generate.py
        ├── save/
        │   ├── sketch-diffusion/
        │   │   └── model000450000.pt
        │   └── refinement-network/
        │       └── model000430000.pt
        └── ...
```

---

## 🧪 Part 3: CLI Verification Test

Before launching the web server, test SwiftSketch from the command line to ensure all modules and CUDA kernels execute cleanly.

Run the following from `web_server/swiftsketch_model/SwiftSketch`:
```bash
cd web_server/swiftsketch_model/SwiftSketch

python generate.py \
  --model_path "./save/sketch-diffusion/model000450000.pt" \
  --refine_model_path "./save/refinement-network/model000430000.pt" \
  --input_data "./examples" \
  --output_dir "./output_sketches" \
  --save_svg 1 \
  --use_refine 1
```

If successful, inspect `./output_sketches` to verify that generated `.svg` and `.png` files are created.

---

## ⚙️ Part 4: Web Server Integration & Configuration

The Flask application in `web_server/server.py` contains a built-in handler `run_swiftsketch_pipeline` that executes SwiftSketch via subprocess.

### Path Configuration in `server.py`
Open `web_server/server.py` and ensure the paths point to your local directories or use relative resolution:

```python
# In web_server/server.py:
def run_swiftsketch_pipeline(input_path, output_svg_path, sketch_img_obj):
    try:
        # Base directory resolution
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cwd = os.path.join(base_dir, "swiftsketch_model", "SwiftSketch")
        model_script = os.path.join(cwd, "generate.py")
        model_path = os.path.join(cwd, "save", "sketch-diffusion", "model000450000.pt")
        refine_model_path = os.path.join(cwd, "save", "refinement-network", "model000430000.pt")
        
        # Temp output directory
        temp_out_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_ss_{os.urandom(4).hex()}")
        os.makedirs(temp_out_dir, exist_ok=True)
        
        # Execute SwiftSketch generation subprocess
        cmd = [
            sys.executable,
            model_script,
            "--model_path", model_path,
            "--refine_model_path", refine_model_path,
            "--input_data", os.path.abspath(input_path),
            "--output_dir", os.path.abspath(temp_out_dir),
            "--save_svg", "1",
            "--use_refine", "1"
        ]
        
        result = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        ...
```

---

## 🌐 Part 5: Starting the Web Server

Start the web server:
```bash
python server.py
```

- Access the web interface on: `http://localhost:5000` (or the printed LAN IP address for mobile devices).
- Upload a photo from your phone or desktop.
- The server will execute SwiftSketch, save the resulting `.svg` file, and prepare it for plotting!

---

## 🛠️ Troubleshooting & FAQ

### 1. `ImportError: No module named 'pydiffvg'`
- **Cause:** `diffvg` was not built or installed into the active Python environment.
- **Solution:** Re-run `python setup.py install` inside the `diffvg` folder under the active Conda/venv environment.

### 2. `CUDA out of memory (OOM)`
- **Cause:** Insufficient VRAM when loading diffusion transformers and refinement networks simultaneously.
- **Solution:** Close other GPU-heavy processes, reduce batch processing, or utilize a machine with >= 8GB VRAM.

### 3. `FileNotFoundError: model000450000.pt`
- **Cause:** Model weights were not placed in the designated folder structure.
- **Solution:** Ensure paths match `save/sketch-diffusion/model000450000.pt` and `save/refinement-network/model000430000.pt`.

### 4. Automatic Fallback Triggered
- If SwiftSketch fails (e.g. missing CUDA or timeout), `server.py` logs the error message to standard output and automatically generates an SVG using `run_custom_vector_tracer(...)` so the user workflow is never blocked.
