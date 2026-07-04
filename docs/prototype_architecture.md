# First-Round Prototype Architecture

This repository keeps the original PyTorch compatibility model code for the
next round, but the first-round demo uses deterministic algorithm scoring.

## Board Responsibilities

- SS928 runs Linux and acts as the edge decision node.
- SS928 fetches weather data, keeps wardrobe state, runs the scoring algorithm,
  handles camera-side inventory events, and exposes results to apps or demos.
- WS63 controls low-level external modules such as GY-AS7341, door sensors,
  buttons, LEDs, or other cabinet-side devices.
- WS63 sends sensor packets to SS928 through UART, Wi-Fi, BLE, MQTT, or HTTP.
- IMX179 image capture should be handled by SS928 or a camera pipeline attached
  to SS928 because 8 MP image data is too heavy for WS63-style control work.

## First-Round Demo Flow

1. Load wardrobe data from `examples/wardrobe.example.json`.
2. Fetch real weather on SS928 through Open-Meteo by latitude and longitude.
3. Generate complete outfit candidates from in-stock clothes.
4. Score each item by temperature, humidity, weather condition, style, material,
   wash status, and inventory state.
5. Return Top-K outfits with scores and explanation reasons.

Run:

```bash
python scripts/recommend.py examples/wardrobe.example.json \
  --weather-source live \
  --latitude 31.2304 \
  --longitude 121.4737 \
  --city Shanghai \
  --occasion business
```

For offline debugging only:

```bash
python scripts/recommend.py examples/wardrobe.example.json \
  --weather-source context \
  --context examples/context.example.json
```

## Reserved Model Path

The training and model files remain in the repository:

- `src/outfit_recommender/model.py`
- `scripts/train.py`
- `scripts/evaluate.py`
- `scripts/recommend_model.py`

They are intentionally not used by the first-round recommendation command.
Before the final round, the model path can be reconnected behind a mode switch
or combined with the rule score as a hybrid recommender.
