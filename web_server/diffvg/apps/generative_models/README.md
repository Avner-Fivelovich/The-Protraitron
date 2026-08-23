# Generative Models for Differentiable Vector Graphics (DiffVG)

This directory contains implementations of generative models that output vector graphics primitives (e.g., Bézier curves, path strokes) trained end-to-end with the differentiable rasterizer **DiffVG** (`pydiffvg`).

---

## Table of Contents

- [Overview](#overview)
- [Directory Structure](#directory-structure)
- [Requirements & Setup](#requirements--setup)
- [Vector GANs](#vector-gans)
  - [Training](#training-a-vector-gan)
  - [Evaluation & Sampling](#evaluating--generating-samples)
- [Variational Autoencoders (VAE / AE)](#variational-autoencoders-vae--ae)
  - [MNIST Vector VAE / AE](#mnist-vector-vae--ae)
  - [Sketch-VAE](#sketch-vae)
- [Sketch-RNN](#sketch-rnn)
- [Monitoring & Visualization](#monitoring--visualization)

---

## Overview

Traditional generative models synthesize raster images (pixel grids). Using DiffVG, the neural networks in this module parameterize vector primitives (control points, stroke widths, opacities, and colors) and render them directly into raster images during training. Backpropagation flows through the differentiable rasterizer into the vector parameter generators, allowing models to learn vector representations directly from raster image supervision or vector datasets (such as QuickDraw and MNIST).

---

## Directory Structure

| File | Description |
|---|---|
| `train_gan.py` | Training script for Vector GAN architectures on MNIST or QuickDraw. |
| `eval_gan.py` | Evaluation and inference script to generate SVG files, PNG grids, and interpolation videos. |
| `mnist_vae.py` | Conditional and unconditional Vector VAE / Autoencoder for MNIST digits. |
| `sketch_vae.py` | Sketch-VAE model trained with raster perceptual loss and differentiable rendering on QuickDraw. |
| `sketch_rnn.py` | Differentiable Sketch-RNN recurrent generator. |
| `models.py` | PyTorch model definitions (`BezierVectorGenerator`, `VectorGenerator`, `RNNVectorGenerator`, `ChainRNNVectorGenerator`, discriminators). |
| `rendering.py` | PyDiffVG helper functions for scene assembly and batch rendering. |
| `losses.py` | Loss functions including Wasserstein GAN gradient penalty and perceptual losses. |
| `data.py` | Dataset loaders for QuickDraw (bitmap `.npy` and stroke `.npz`) and MNIST. |
| `modules.py` | Utility neural network layers and modules. |

---

## Requirements & Setup

Ensure you have installed:
- `torch` and `torchvision`
- `pydiffvg` (built and installed from the repository root)
- `ttools` (PyTorch training tools)
- `visdom` (optional, for live loss and sample tracking)
- `ffmpeg` (optional, for generating MP4 latent walk videos)
- `wget` and `imageio`

---

## Vector GANs

### Training a Vector GAN

The script `train_gan.py` trains a generative adversarial network whose generator outputs vector control parameters.

#### Basic Usage

- **Train on MNIST:**
  ```bash
  python train_gan.py --task mnist --generator bezier_fc
  ```

- **Train on QuickDraw:**
  ```bash
  python train_gan.py --task quickdraw --generator bezier_fc
  ```

#### Common Training Options

| Flag | Default | Description |
|---|---|---|
| `--task` | `mnist` | Dataset task (`mnist` or `quickdraw`). |
| `--generator` | `bezier_fc` | Generator architecture (`bezier_fc`, `fc`, `rnn`, `chain_rnn`). |
| `--standard_gan` | `False` (uses WGAN-GP) | Use standard GAN loss instead of WGAN-GP. |
| `--raster_only` | `False` | Train only a raster baseline generator. |
| `--num_strokes` | `16` | Number of vector stroke paths to output. |
| `--stroke_width` | `0.5 1.5` | Min and max stroke widths. |
| `--raster_resolution` | `32` | Canvas size for rasterization. |
| `--zdim` | `32` | Latent space dimension. |
| `--bs` | `4` | Batch size. |
| `--lr` | `1e-4` | Learning rate. |
| `--num_epochs` | `200` | Number of training epochs. |
| `--port` | `8097` | Visdom server port for live progress. |

---

### Evaluating & Generating Samples

Use `eval_gan.py` to evaluate a trained model checkpoint, generate sample grids, output vector SVG files, and render latent space interpolations:

```bash
python eval_gan.py path/to/model/checkpoint_folder --output_dir results/eval_gan
```

#### Evaluation Options

| Flag | Default | Description |
|---|---|---|
| `model` | *(Positional)* | Path to the directory containing model checkpoints and metadata. |
| `--output_dir` | `<model>/eval` | Directory where images, SVGs, and videos will be saved. |
| `--nsamples` | `16` | Number of samples or interpolation pairs to generate. |
| `--imsize` | `None` | Override output raster resolution. |
| `--nsteps` | `9` | Number of discrete steps for static latent space interpolations. |
| `--nframes` | `120` | Number of animation frames for video latent walks. |
| `--invert` | `False` | Invert output colors (render black on white). |

Outputs generated:
- `latent_interp/*.png`: Latent space interpolation strips.
- `latent_interp_svg/<sample_idx>/*.svg`: Rendered SVG files for each step.
- `latent_interp_video/*.mp4`: Smooth latent walk animation videos (requires `ffmpeg`).
- `samples_*.png`: Random sample grids.

---

## Variational Autoencoders (VAE / AE)

### MNIST Vector VAE / AE

`mnist_vae.py` trains and evaluates a Vector Variational Autoencoder or Autoencoder on the MNIST digit dataset.

#### 1. Train
```bash
python mnist_vae.py train --generator vae --paths 1 --segments 3 --num_epochs 50
```

#### 2. Generate Random Samples
```bash
python mnist_vae.py sample --digit 7
```
*(Omit `--digit` to sample across random digit classes).*

#### 3. Latent Space Interpolation
```bash
python mnist_vae.py interpolate
```

#### Key Arguments for `mnist_vae.py`
- `--generator`: `vae` (Variational Autoencoder) or `ae` (standard Autoencoder).
- `--paths`: Number of Bézier curves / paths per digit (default: `1`).
- `--segments`: Number of Bézier segments per path (default: `3`).
- `--samples`: Number of Monte Carlo samples used by the rasterizer (default: `4`).
- `--kld_weight`: KL divergence loss scalar weight (default: `1.0`).
- `--cpu`: Force execution on CPU.

---

### Sketch-VAE

`sketch_vae.py` trains an encoder-decoder architecture that translates QuickDraw sketches into differentiable vector representations using raster perceptual losses.

```bash
python sketch_vae.py --dataset cat.npz --bs 1 --num_epochs 10000 --raster_resolution 64
```

- `--dataset`: QuickDraw `.npz` file name (automatically downloaded if not found).
- `--absolute_coordinates`: Use absolute coordinates rather than stroke-3 relative offsets.
- `--sequence_length`: Maximum number of stroke points to process (default: `50`).
- `--kl_weight`: Initial KL divergence loss weight.

---

## Sketch-RNN

`sketch_rnn.py` implements a recurrent sequence-to-sequence model for sketch generation:

```bash
python sketch_rnn.py --dataset cat.npz --bs 100 --zdim 128 --sampling_temperature 0.4
```

- `--dataset`: QuickDraw `.npz` dataset (default: `cat.npz`).
- `--sampling_temperature`: Softmax temperature for controlling generation randomness (default: `0.4`).
- `--num_gaussians`: Number of mixture Gaussians for the stroke displacement prediction (default: `20`).

---

## Monitoring & Visualization

Many scripts in this directory integrate with **Visdom** via `ttools` for real-time visualization of loss curves, intermediate vector renderings, and reconstructions.

To launch a local Visdom server before training:
```bash
visdom -port 8097
```
Then navigate to `http://localhost:8097` in your browser.
