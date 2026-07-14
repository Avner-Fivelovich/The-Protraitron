# SwiftSketch Model Integration Guide

This guide explains how to install the actual **SwiftSketch** diffusion model and connect it to your web server. 

Because SwiftSketch is a deep learning model, it is recommended to run this setup on a **GPU-enabled workstation** (like the PCs in your university robotics lab) rather than a standard home laptop.

---

## Part 1: Installing the Dependencies

To compile and run SwiftSketch, you need a C++ Compiler (like MSVC on Windows or GCC on Linux) and a GPU with CUDA installed.

1. **Install PyTorch & Torchvision** with CUDA support:
   ```bash
   pip install torch==2.3.1 torchvision==0.18.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cu121
   ```

2. **Install the `diffvg` library** (Differentiable Vector Graphics):
   `diffvg` is required for rendering and optimizing vector paths.
   ```bash
   git clone https://github.com/BachiLi/diffvg.git
   cd diffvg
   git submodule update --init --recursive
   python setup.py install
   ```
   *(Note: This step compiles C++ files, so it requires Visual Studio C++ Build Tools to be installed on Windows).*

3. **Install other required packages**:
   ```bash
   pip install git+https://github.com/openai/CLIP.git
   pip install diffusers transformers accelerate
   ```

4. **Clone the SwiftSketch repository**:
   Clone it into a folder (e.g. `C:\tau_university\2026B\Robotics\web_server\swiftsketch_model`):
   ```bash
   git clone https://github.com/swiftsketch/swiftsketch.git
   ```

---

## Part 2: Updating the Server Hook

Once SwiftSketch is installed, open [server.py](file:///C:/tau_university/2026B/Robotics/web_server/server.py) and modify the `run_swiftsketch_pipeline` function.

Replace the current tracer code with a call to the SwiftSketch model. Here is an example of how you can invoke it:

```python
def run_swiftsketch_pipeline(input_path, output_svg_path, sketch_img_obj):
    """
    PIPELINE HOOK FOR SWIFTSKETCH INTEGRATION
    """
    try:
        # 1. Import your SwiftSketch inference script
        # (Assuming you place it in a subdirectory or in your python path)
        # from swiftsketch_model.inference import generate_vector_sketch
        
        # 2. Call the model to generate the SVG
        # generate_vector_sketch(input_path, output_svg_path)
        
        # 3. Alternatively, call it as a subprocess if running from command-line:
        # import subprocess
        # cmd = ["python", "swiftsketch_model/inference.py", "--input", input_path, "--output", output_svg_path]
        # subprocess.run(cmd, check=True)
        
        # For testing, we keep the custom tracer as a fallback if the run fails:
        # return True
        
        pass
    except Exception as e:
        print(f"Error running SwiftSketch model: {e}")
        # Fallback to local tracer
        return run_custom_vector_tracer(sketch_img_obj, output_svg_path)
```

The web server and phone UI will automatically handle the outputs and download requests without any other code changes!
