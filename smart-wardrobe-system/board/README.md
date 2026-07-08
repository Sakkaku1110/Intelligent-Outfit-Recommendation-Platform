# SS928 Smart Wardrobe Backend

This backend runs on HiEulerPI/SS928 and provides:

- clothing database based on SQLite
- camera-based clothing capture through `/dev/video0` and `fswebcam`
- rule-based image analysis for color, category and rough material hints
- explainable outfit recommendation
- internet weather lookup through Open-Meteo
- cloud sync for metadata and captured photos
- WS63 serial bridge for GY-AS7341 spectral material packets
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
curl http://127.0.0.1:8000/api/cloud/sync/status
curl http://127.0.0.1:8000/api/ws63/latest
```

Capture a clothing image and store it:

```bash
curl -X POST http://127.0.0.1:8000/api/clothes/capture \
  -H 'Content-Type: application/json' \
  -d '{"name":"","category":"auto","season":"spring_autumn","occasion":"school,casual","auto_analyze":true}'
```

Sync existing local clothing items to cloud:

```bash
curl -X POST http://127.0.0.1:8000/api/cloud/sync \
  -H 'Content-Type: application/json' \
  -d '{}'
```

## Cloud sync environment

Keep these values in the local board environment or service environment file, not in Git:

```bash
SMART_WARDROBE_CLOUD_SYNC=1
SMART_WARDROBE_CLOUD_API_BASE=http://your-cloud-server
SMART_WARDROBE_DEVICE_ID=ss928_001
SMART_WARDROBE_CLOUD_SYNC_TIMEOUT=12
```

`SMART_WARDROBE_CLOUD_API_KEY` is required, but set it only in the board's
local `.env` or systemd environment file.

## WS63 serial bridge

Install and run both services on the board:

```bash
cp scripts/smart-wardrobe.service /etc/systemd/system/
cp scripts/smart-wardrobe-ws63.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now smart-wardrobe.service smart-wardrobe-ws63.service
```

The bridge reads JSON lines or binary `SWSP` frames from WS63 and posts them to SS928. Optional environment variables:

```bash
SMART_WARDROBE_WS63_SERIAL=auto
SMART_WARDROBE_WS63_BAUD=115200
SMART_WARDROBE_WS63_POST_URL=http://127.0.0.1:8000/api/ws63/sensor
SMART_WARDROBE_WS63_IDLE_RESCAN=15
```

Example WS63 JSON packet:

```bash
curl -X POST http://127.0.0.1:8000/api/ws63/sensor \
  -H 'Content-Type: application/json' \
  -d '{"device":"WS63","sensor":"GY-AS7341","f1":620,"f2":710,"f3":860,"f4":910,"f5":1120,"f6":1210,"f7":980,"f8":760,"clear":7200,"nir":430}'
```

The backend stores the latest packet and adds `material_prediction` with material, label, confidence, feature summary, and quality hints.
