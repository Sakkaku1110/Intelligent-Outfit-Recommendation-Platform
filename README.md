# Intelligent Outfit Recommendation Platform

An intelligent outfit recommendation project based on PyTorch and the Polyvore
Outfits dataset.

## Current Status

- Polyvore Outfits dataset integrity check
- Automatic CUDA, MPS, or CPU device detection
- Training data pipeline and recommendation model are under development

## Project Structure

```text
.
├── main.py
├── requirements.txt
└── scripts/
    └── inspect_dataset.py
```

The dataset, model checkpoints, and IDE configuration are intentionally excluded
from Git.

## Environment

Python 3.10 or 3.11 is recommended. Create or activate a Python environment,
then install the dependencies:

```bash
pip install -r requirements.txt
```

For NVIDIA GPU training, install the PyTorch build matching the CUDA version on
the training server by following the official PyTorch installation instructions.

## Dataset

Request access to the
[Polyvore Outfits dataset](https://huggingface.co/datasets/mvasil/polyvore-outfits)
and download it into:

```text
data/polyvore-outfits/
```

The project uses the official `disjoint` split for evaluation.

Verify the downloaded dataset:

```bash
python scripts/inspect_dataset.py
```

Expected split sizes:

- Train: 16,995 outfits
- Validation: 3,000 outfits
- Test: 15,145 outfits

## Device Check

Run:

```bash
python main.py
```

The program reports the available PyTorch device: CUDA, Apple MPS, or CPU.

## Dataset Citation

```bibtex
@inproceedings{vasileva2018learning,
  title={Learning Type-Aware Embeddings for Fashion Compatibility},
  author={Vasileva, Mariya I. and Plummer, Bryan A. and Dusad, Krishna and
          Rajpal, Shreya and Kumar, Ranjitha and Forsyth, David A.},
  booktitle={European Conference on Computer Vision},
  year={2018}
}
```
