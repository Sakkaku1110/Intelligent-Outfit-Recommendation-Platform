# Intelligent Outfit Recommendation Platform

Smart wardrobe prototype for inventory sensing and outfit recommendation.

The repository currently supports two tracks:

- First-round demo: deterministic algorithm scoring, no large model required.
- Later optimization: the original PyTorch compatibility model is preserved for
  future training, deployment, or hybrid recommendation.

## Current Prototype Scope

- SS928: Linux edge node for weather fetching, wardrobe state, recommendation
  scoring, camera-side events, and future model inference.
- WS63: external module controller for sensors such as GY-AS7341 and other
  cabinet-side signals.
- GY-AS7341: spectral sensor adapter that produces material and thickness hints.
- IMX179: camera scan event interface for inventory in/out records.
- Apps/tablet UI: not developed in this repository; they can consume outputs
  from the SS928-side service or scripts.

## Project Structure

```text
.
├── docs/
│   └── prototype_architecture.md
├── examples/
│   ├── context.example.json
│   ├── wardrobe.example.json
│   └── ws63_packet.example.json
├── scripts/
│   ├── demo_hardware_pipeline.py
│   ├── evaluate.py
│   ├── inspect_dataset.py
│   ├── prepare_images.py
│   ├── recommend.py
│   ├── recommend_model.py
│   └── train.py
├── src/
│   └── outfit_recommender/
│       ├── algorithm.py
│       ├── hardware/
│       ├── model.py
│       └── weather.py
└── tests/
```

## Environment

Python 3.10 or 3.11 is recommended on the board. Create or activate an
environment, then install dependencies:

```bash
pip install -r requirements.txt
```

The first-round algorithm command only uses the Python standard library. PyTorch
dependencies remain for the preserved model training/evaluation path.

## Run First-Round Recommendation With Real Weather

```bash
python scripts/recommend.py examples/wardrobe.example.json \
  --weather-source live \
  --latitude 31.2304 \
  --longitude 121.4737 \
  --city Shanghai \
  --occasion business
```

JSON output for integration demos:

```bash
python scripts/recommend.py examples/wardrobe.example.json \
  --weather-source live \
  --latitude 31.2304 \
  --longitude 121.4737 \
  --city Shanghai \
  --occasion business \
  --json
```

This uses Open-Meteo current weather data, so SS928 needs network access.

If the board is offline during debugging, use the fixed fallback context:

```bash
python scripts/recommend.py examples/wardrobe.example.json \
  --weather-source context \
  --context examples/context.example.json
```

The recommender generates complete outfits from in-stock clothes, scores them by
weather, humidity, temperature, occasion, style, material, thickness, wash
status, and inventory state, then prints Top-K results with reasons.

## Demo WS63 Sensor Packet

```bash
python scripts/demo_hardware_pipeline.py examples/ws63_packet.example.json
```

This shows the intended WS63-to-SS928 flow. In the first-round version the
packet is read from a JSON file; later it can come from UART, Wi-Fi, BLE, MQTT,
or HTTP.

## Preserved Model Path

The previous Polyvore/PyTorch code remains available:

- `src/outfit_recommender/model.py`
- `scripts/train.py`
- `scripts/evaluate.py`
- `scripts/prepare_images.py`
- `scripts/recommend_model.py`

It is not used by `scripts/recommend.py` now, so the first-round demo does not
depend on a checkpoint or model output. Before the next round, this path can be
optimized and reconnected as a large-model or hybrid recommendation mode.

## Tests

```bash
PYTHONPATH=src pytest -q
```
