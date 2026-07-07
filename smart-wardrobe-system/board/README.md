# SS928 Smart Wardrobe Backend

This backend runs on HiEulerPI/SS928 and provides:

- clothing database based on SQLite
- camera-based clothing capture through `/dev/video0` and `fswebcam`
- rule-based image analysis for color, category and rough material hints
- rule-based GY-AS7341 spectral material hints from WS63 JSON packets
- explainable outfit recommendation
- internet weather lookup through Open-Meteo
- WS63 sensor packet ingestion through `/api/ws63/sensor`
- static mobile web app hosting

## Run on the board

```bash
cd /root/workspace/smart-wardrobe
bash scripts/install_board.sh
bash scripts/run_server.sh
```

Open:

```text
http://192.168.137.2:8000
```

## Useful API

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/clothes
curl 'http://127.0.0.1:8000/api/recommendations?city=Hangzhou&occasion=school'
```

Capture a clothing image and store it:

```bash
curl -X POST http://127.0.0.1:8000/api/clothes/capture \
  -H 'Content-Type: application/json' \
  -d '{"name":"","category":"auto","season":"spring_autumn","occasion":"school,casual","auto_analyze":true}'
```

WS63 + GY-AS7341 spectral material check:

```bash
curl -X POST http://127.0.0.1:8000/api/ws63/sensor \
  -H 'Content-Type: application/json' \
  -d '{"device":"WS63","sensor":"GY-AS7341","f1":90,"f2":110,"f3":120,"f4":95,"f5":70,"f6":52,"f7":35,"f8":28,"clear":670,"nir":135}'
```

The response and `data/ws63_latest.json` include `material_prediction`, for
example `denim`, `cotton`, `linen`, `wool`, `leather`, `silk_satin` or
`polyester`. If the AS7341 signal is too weak, the result is
`unknown_low_light`; re-scan with a fixed white light source and keep the sensor
close to the fabric.

You can also classify a saved serial JSONL file directly:

```bash
python tools/classify_as7341_material.py ./as7341_samples.jsonl
```
