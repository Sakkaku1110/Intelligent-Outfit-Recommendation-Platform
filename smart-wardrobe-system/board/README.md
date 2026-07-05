# SS928 Smart Wardrobe Backend

This backend runs on HiEulerPI/SS928 and provides:

- clothing database based on SQLite
- camera-based clothing capture through `/dev/video0` and `fswebcam`
- rule-based image analysis for color, category and rough material hints
- explainable outfit recommendation
- internet weather lookup through Open-Meteo
- placeholder API for future WS63 sensor packets
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

WS63 placeholder:

```bash
curl -X POST http://127.0.0.1:8000/api/ws63/sensor \
  -H 'Content-Type: application/json' \
  -d '{"device":"WS63","temperature":26.5,"material_feature":[0.12,0.34,0.56]}'
```
