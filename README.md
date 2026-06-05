# Intelligent Outfit Recommendation Platform

An intelligent outfit recommendation project based on PyTorch and the Polyvore
Outfits dataset.

## Features

- Official Polyvore disjoint train, validation, and test splits
- Positive and negative outfit compatibility samples
- MobileNetV3 image encoder with semantic category embeddings
- Transformer-based variable-length outfit encoder
- CUDA, Apple MPS, and CPU device selection
- Training, validation, checkpointing, evaluation, and Top-K recommendation

## Project Structure

```text
.
├── examples/
│   └── wardrobe.example.json
├── main.py
├── requirements.txt
├── scripts/
│   ├── evaluate.py
│   ├── inspect_dataset.py
│   ├── prepare_images.py
│   ├── recommend.py
│   └── train.py
├── src/
│   └── outfit_recommender/
└── tests/
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

## Prepare Images

Polyvore images are stored inside Parquet files. Extract the images required by
the official compatibility samples before training:

```bash
python scripts/prepare_images.py --splits train validation test
```

For a quick local smoke test:

```bash
python scripts/prepare_images.py \
  --splits train validation \
  --max-samples 32
```

## Train

Run full training on the GPU server:

```bash
python scripts/train.py \
  --epochs 10 \
  --batch-size 32 \
  --num-workers 4 \
  --freeze-backbone
```

The best validation checkpoint is saved to `checkpoints/best.pt`. Remove
`--freeze-backbone` for full fine-tuning after the initial frozen-backbone run.

Run a small pipeline check without downloading pretrained weights:

```bash
python scripts/train.py \
  --epochs 1 \
  --batch-size 2 \
  --image-size 64 \
  --max-train-samples 32 \
  --max-validation-samples 32 \
  --no-pretrained
```

## Evaluate

Prepare test images, then evaluate:

```bash
python scripts/evaluate.py \
  --checkpoint checkpoints/best.pt \
  --split test
```

## Recommend Outfits

Create a wardrobe manifest using
`examples/wardrobe.example.json` as the template. Supported categories include
`tops`, `bottoms`, `all-body`, `outerwear`, and `shoes`.

```bash
python scripts/recommend.py wardrobe.json \
  --checkpoint checkpoints/best.pt \
  --top-k 5
```

The recommender generates valid top-bottom-shoes or dress-shoes combinations,
optionally adds outerwear, scores them with the trained model, and returns the
highest-ranked outfits.

## Tests

```bash
PYTHONPATH=src pytest -q
```

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
