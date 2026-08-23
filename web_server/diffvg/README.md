# diffvg: Differentiable Rasterizer for 2D Vector Graphics

[![Project Page](https://img.shields.io/badge/Project-Page-blue)](https://people.csail.mit.edu/tzumao/diffvg)
[![Paper](https://img.shields.io/badge/Paper-ACM%20TOG-green)](https://people.csail.mit.edu/tzumao/diffvg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**diffvg** is a differentiable rasterizer for 2D vector graphics. It computes analytical gradients of rasterized vector graphics (such as Bézier curves, shapes, paths, and color gradients) with respect to shape parameters, stroke widths, colors, and transformations, enabling gradient-based optimization and deep learning applications with vector graphics.

For more details, visit the [project webpage](https://people.csail.mit.edu/tzumao/diffvg).

---

## Gallery & Demonstrations

![teaser](https://user-images.githubusercontent.com/951021/92184822-2a0bc500-ee20-11ea-81a6-f26af2d120f4.jpg)

### Shape Optimization Examples

| Circle | Ellipse | Rectangle |
| :---: | :---: | :---: |
| ![circle](https://user-images.githubusercontent.com/951021/63556018-0b2ddf80-c4f8-11e9-849c-b4ecfcb9a865.gif) | ![ellipse](https://user-images.githubusercontent.com/951021/63556021-0ec16680-c4f8-11e9-8fc6-8b34de45b8be.gif) | ![rect](https://user-images.githubusercontent.com/951021/63556028-12ed8400-c4f8-11e9-8072-81702c9193e1.gif) |
| **Polygon** | **Curve** | **Path** |
| ![polygon](https://user-images.githubusercontent.com/951021/63980999-1e99f700-ca72-11e9-9786-1cba14d2d862.gif) | ![curve](https://user-images.githubusercontent.com/951021/64042667-3d9e9480-cb17-11e9-88d8-2f7b9da8b8ab.gif) | ![path](https://user-images.githubusercontent.com/951021/64070625-7a52b480-cc19-11e9-9380-eac02f56f693.gif) |
| **Radial Gradient** | **Circle Outline** | **Ellipse Transform** |
| ![gradient](https://user-images.githubusercontent.com/951021/64898668-da475300-d63c-11e9-917a-825b94be0710.gif) | ![circle_outline](https://user-images.githubusercontent.com/951021/65125594-84f7a280-d9aa-11e9-8bc4-669fd2eff2f4.gif) | ![ellipse_transform](https://user-images.githubusercontent.com/951021/67149013-06b54700-f25b-11e9-91eb-a61171c6d4a4.gif) |

---

## Installation

### Prerequisites

Make sure git submodules are initialized:
```bash
git submodule update --init --recursive
```

Install FFmpeg for your platform:
- **macOS (Homebrew):** `brew install ffmpeg`
- **Linux (Ubuntu/Debian):** `sudo apt install ffmpeg`
- **Conda:** `conda install -y -c conda-forge ffmpeg`

---

### Option 1: Install with Conda & Pip (Recommended)

1. Create and activate a conda environment:
   ```bash
   conda create -n diffvg python=3.8
   conda activate diffvg
   ```

2. Install core packages:
   ```bash
   conda install -y pytorch torchvision -c pytorch
   conda install -y numpy scikit-image
   conda install -y -c anaconda cmake
   conda install -y -c conda-forge ffmpeg
   ```

3. Install Python dependencies:
   ```bash
   pip install svgwrite svgpathtools cssutils numba torch-tools visdom
   ```

4. Build and install `diffvg` (`pydiffvg`):
   ```bash
   python setup.py install
   ```

---

### Option 2: Install with Poetry

1. Install [Poetry](https://python-poetry.org/docs/#installation):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Install Python dependencies:
   ```bash
   poetry install
   ```

3. Build and install `diffvg`:
   ```bash
   poetry run python setup.py install
   ```

> **Note:** When using Poetry, prefix Python commands with `poetry run`, e.g.:
> ```bash
> poetry run python single_circle.py
> ```

---

### Building in Debug Mode

To build `diffvg` with debug symbols:
```bash
python setup.py build --debug install
```

---

## Applications & Examples

Navigate to the `apps/` directory to run the example scripts:
```bash
cd apps
```

### 1. Basic Shape Optimization
Optimize a single primitive to match a target image:
```bash
python single_circle.py
```
*(Additional single primitive optimization scripts are available in `apps/`: `single_ellipse.py`, `single_rect.py`, `single_polygon.py`, `single_curve.py`, `single_path.py`, `single_gradient.py`, etc.)*

### 2. Finite Difference Comparison
Compare analytical gradients against finite differences:
```bash
python finite_difference_comp.py [-h] [--size_scale SIZE_SCALE] \
                                [--clamping_factor CLAMPING_FACTOR] \
                                [--use_prefiltering USE_PREFILTERING] \
                                svg_file
```
**Example:**
```bash
python finite_difference_comp.py imgs/tiger.svg
```

### 3. Interactive Vector Brush
Launch the interactive vector editor:
```bash
python svg_brush.py
```

### 4. Painterly Rendering
Render a raster image into a set of painterly vector strokes using differentiable rasterization:
```bash
python painterly_rendering.py [-h] [--num_paths NUM_PATHS] \
                             [--max_width MAX_WIDTH] [--use_lpips_loss] \
                             [--num_iter NUM_ITER] [--use_blob] \
                             target
```
**Example:**
```bash
python painterly_rendering.py imgs/fallingwater.jpg --num_paths 2048 --max_width 4.0 --use_lpips_loss
```

### 5. Image Vectorization / SVG Refinement
Refine and fit an existing SVG file to match a target raster image:
```bash
python refine_svg.py [-h] [--use_lpips_loss] [--num_iter NUM_ITER] svg target
```
**Example:**
```bash
python refine_svg.py imgs/flower.svg imgs/flower.jpg
```

### 6. Seam Carving
Perform content-aware resizing on vector artwork:
```bash
python seam_carving.py [-h] [--svg SVG] [--optim_steps OPTIM_STEPS]
```
**Example:**
```bash
python seam_carving.py imgs/hokusai.svg
```

### 7. Generative Models (Vector VAE & GAN)
- **Vector GAN:**
  - Training: `python generative_models/train_gan.py`
  - Evaluation / Sampling: `python generative_models/eval_gan.py`
- **Vector VAE:**
  - MNIST VAE: `python generative_models/mnist_vae.py`

---

## Citation

If you use `diffvg` in your research or academic work, please cite:

```bibtex
@article{Li:2020:DVG,
    title   = {Differentiable Vector Graphics Rasterization for Editing and Learning},
    author  = {Li, Tzu-Mao and Luk\'{a}\v{c}, Michal and Gharbi Micha\"{e}l and Jonathan Ragan-Kelley},
    journal = {ACM Trans. Graph. (Proc. SIGGRAPH Asia)},
    volume  = {39},
    number  = {6},
    pages   = {193:1--193:15},
    year    = {2020}
}
```

---

## License

`diffvg` is open-source software licensed under the MIT License. See [LICENSE](LICENSE) for details.
