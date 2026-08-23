# CLIP (Contrastive Language-Image Pre-Training)

[![Paper](https://img.shields.io/badge/arXiv-2103.00020-b31b1b.svg)](https://arxiv.org/abs/2103.00020)
[![Blog](https://img.shields.io/badge/OpenAI-Blog-412991.svg)](https://openai.com/blog/clip/)
[![Model Card](https://img.shields.io/badge/Model%20Card-model--card.md-blue.svg)](model-card.md)
[![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/openai/clip/blob/master/notebooks/Interacting_with_CLIP.ipynb)

**CLIP** (*Contrastive Language-Image Pre-Training*) is a neural network trained on a vast variety of `(image, text)` pairs. It can be instructed in natural language to predict the most relevant text snippet for a given image without directly optimizing for the downstream task—mirroring the zero-shot capabilities of GPT-2 and GPT-3. CLIP achieves competitive zero-shot performance across many computer vision benchmarks (such as matching ResNet-50 accuracy on ImageNet without using any labeled ImageNet training data).

> **Note**: This repository branch includes modified Vision Transformer attention hooks (`attn_probs`, `attn_grad`) for attention explainability and cross-modal relevance visualization, used within ControlSketch.

---

## Table of Contents

- [Approach](#approach)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Interpretability & Attention Visualization](#interpretability--attention-visualization)
- [API Reference](#api-reference)
- [More Examples](#more-examples)
  - [Zero-Shot Prediction](#zero-shot-prediction)
  - [Linear-Probe Evaluation](#linear-probe-evaluation)
- [Citation](#citation)
- [License](#license)

---

## Approach

CLIP jointly trains an image encoder and a text encoder to predict the correct pairings of a batch of `(image, text)` training examples using a contrastive objective:

![CLIP Architecture](https://raw.githubusercontent.com/openai/CLIP/main/CLIP.png)

---

## Installation

### 1. Prerequisites

Ensure you have Python 3.8+ and PyTorch installed. For GPU acceleration, install the appropriate CUDA build:

```bash
# Using Conda
conda install --yes -c pytorch pytorch torchvision cudatoolkit=11.8

# Or using Pip
pip install torch torchvision
```

### 2. Install Dependencies & Package

Install required dependencies:

```bash
pip install ftfy regex tqdm scikit-learn opencv-python matplotlib
```

To install this local version of CLIP with interpretability support:

```bash
# From this directory (ControlSketch/CLIP_)
pip install -e .
```

Alternatively, to install the upstream OpenAI repository:

```bash
pip install git+https://github.com/openai/CLIP.git
```

---

## Quick Start

```python
import torch
import clip
from PIL import Image

# Select device
device = "cuda" if torch.cuda.is_available() else "cpu"

# Load CLIP model and preprocessing pipeline
model, preprocess = clip.load("ViT-B/32", device=device)

# Prepare input image and candidate text prompts
image = preprocess(Image.open("astronaut.png")).unsqueeze(0).to(device)
text = clip.tokenize(["an astronaut", "a dog", "a rocket"]).to(device)

with torch.no_grad():
    image_features = model.encode_image(image)
    text_features = model.encode_text(text)
    
    # Compute similarity logits
    logits_per_image, logits_per_text = model(image, text)
    probs = logits_per_image.softmax(dim=-1).cpu().numpy()

print("Label probabilities:", probs)
```

---

## Interpretability & Attention Visualization

This module incorporates attention gradient extraction hooks into the Vision Transformer blocks (`model.visual.transformer.resblocks`), enabling token-level and image-region relevance mapping.

To run the sample interpretability script:

```bash
python example.py
```

### Basic Attention Extraction Example

```python
import torch
import clip
import numpy as np
import cv2
from PIL import Image

device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device, jit=False)

image = preprocess(Image.open("astronaut.png")).unsqueeze(0).to(device)
text = clip.tokenize(["an astronaut", "a spacecraft"]).to(device)

logits_per_image, _ = model(image, text)
one_hot = torch.zeros_like(logits_per_image)
one_hot[0, 0] = 1.0

model.zero_grad()
(logits_per_image * one_hot).sum().backward(retain_graph=True)

# Access attention maps from transformer blocks
image_attn_blocks = list(dict(model.visual.transformer.resblocks.named_children()).values())
print(f"Number of transformer blocks: {len(image_attn_blocks)}")
```

---

## API Reference

### Module Functions (`clip`)

#### `clip.available_models() -> List[str]`
Returns a list of available model architecture names, including:
- `RN50`, `RN101`, `RN50x4`, `RN50x16`, `RN50x64` (ResNet variants)
- `ViT-B/32`, `ViT-B/16`, `ViT-L/14`, `ViT-L/14@336px` (Vision Transformer variants)

#### `clip.load(name: str, device: Union[str, torch.device] = "cuda", jit: bool = True) -> Tuple[torch.nn.Module, Callable]`
Loads the specified model architecture and returns a tuple `(model, preprocess)`.
- `name`: Name from `clip.available_models()` or path to a model checkpoint `.pt` file.
- `device`: Device to run on (`"cuda"`, `"cpu"`, etc.).
- `jit`: When `True` (default), loads the optimized TorchScript JIT archive. Set `jit=False` to access internals, gradients, and custom attention hooks.

#### `clip.tokenize(text: Union[str, List[str]], context_length: int = 77, truncate: bool = False) -> torch.LongTensor`
Tokenizes string or list of strings into a `LongTensor` of shape `(batch_size, context_length)`.

---

### Model Methods (`torch.nn.Module`)

#### `model.encode_image(image: torch.Tensor) -> torch.Tensor`
Given a batch of normalized images `[N, 3, H, W]`, returns normalized vision feature vectors `[N, D]`.

#### `model.encode_text(text: torch.LongTensor) -> torch.Tensor`
Given a batch of token sequences `[N, context_length]`, returns normalized language feature vectors `[N, D]`.

#### `model(image: torch.Tensor, text: torch.LongTensor) -> Tuple[torch.Tensor, torch.Tensor]`
Performs a forward pass computing cross-modal cosine similarity logits scaled by 100:
- `logits_per_image`: Tensor of shape `[N_image, N_text]`
- `logits_per_text`: Tensor of shape `[N_text, N_image]`

---

## More Examples

### Zero-Shot Prediction

Predict the top classes from CIFAR-100 without fine-tuning:

```python
import os
import torch
import clip
from torchvision.datasets import CIFAR100

device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)

# Download CIFAR-100 test set
cifar100 = CIFAR100(root=os.path.expanduser("~/.cache"), download=True, train=False)

# Prepare single sample input
image, class_id = cifar100[3637]
image_input = preprocess(image).unsqueeze(0).to(device)
text_inputs = torch.cat([clip.tokenize(f"a photo of a {c}") for c in cifar100.classes]).to(device)

# Compute embeddings
with torch.no_grad():
    image_features = model.encode_image(image_input)
    text_features = model.encode_text(text_inputs)

# Normalize and compute cosine similarity
image_features /= image_features.norm(dim=-1, keepdim=True)
text_features /= text_features.norm(dim=-1, keepdim=True)
similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
values, indices = similarity[0].topk(5)

print("\nTop predictions:\n")
for value, index in zip(values, indices):
    print(f"{cifar100.classes[index]:>16s}: {100 * value.item():.2f}%")
```

Sample output:
```text
Top predictions:

           snake: 65.31%
          turtle: 12.29%
    sweet_pepper:  3.83%
          lizard:  1.88%
       crocodile:  1.75%
```

---

### Linear-Probe Evaluation

Extract frozen CLIP features and train a logistic regression classifier on top:

```python
import os
import torch
import clip
import numpy as np
from sklearn.linear_model import LogisticRegression
from torch.utils.data import DataLoader
from torchvision.datasets import CIFAR100
from tqdm import tqdm

device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)

# Load dataset
root = os.path.expanduser("~/.cache")
train_set = CIFAR100(root, download=True, train=True, transform=preprocess)
test_set = CIFAR100(root, download=True, train=False, transform=preprocess)

def get_features(dataset):
    all_features, all_labels = [], []
    with torch.no_grad():
        for images, labels in tqdm(DataLoader(dataset, batch_size=100)):
            features = model.encode_image(images.to(device))
            all_features.append(features)
            all_labels.append(labels)
    return torch.cat(all_features).cpu().numpy(), torch.cat(all_labels).cpu().numpy()

# Extract features
train_features, train_labels = get_features(train_set)
test_features, test_labels = get_features(test_set)

# Fit Logistic Regression
classifier = LogisticRegression(random_state=0, C=0.316, max_iter=1000, verbose=1)
classifier.fit(train_features, train_labels)

# Evaluate
predictions = classifier.predict(test_features)
accuracy = np.mean((test_labels == predictions).astype(float)) * 100.0
print(f"Linear probe accuracy = {accuracy:.3f}%")
```

---

## Citation

```bibtex
@inproceedings{Radford2021LearningTV,
  title={Learning Transferable Visual Models From Natural Language Supervision},
  author={Alec Radford and Jong Wook Kim and Chris Hallacy and Aditya Ramesh and Gabriel Goh and Sandhini Agarwal and Girish Sastry and Amanda Askell and Pamela Mishkin and Jack Clark and Gretchen Krueger and Ilya Sutskever},
  booktitle={ICML},
  year={2021}
}
```

For Transformer interpretability and relevance propagation:

```bibtex
@article{chefer2021generic,
  title={Generic Attention-model Explainability for Interpreting Bi-modal and Multi-modal Transformers},
  author={Chefer, Hila and Gur, Shir and Wolf, Lior},
  journal={arXiv preprint arXiv:2103.15679},
  year={2021}
}
```

---

## License

This project is licensed under the [MIT License](LICENSE). For safety and usage constraints, refer to the [Model Card](model-card.md).
