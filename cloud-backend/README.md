# Smart Wardrobe Cloud Backend

This is the minimal cloud API for syncing the real wardrobe to the mobile App.

## What It Does

- SS928 uploads recognized wardrobe items.
- The mobile App reads the real wardrobe through HTTP.
- Item photos are stored under `/uploads`.
- Wardrobe metadata is stored in PostgreSQL.

## Run On A Lightweight Cloud Server

1. Buy an Ubuntu 22.04/24.04 lightweight server.
2. Open ports `22`, `3000` for early testing. Later use `80`/`443` with Nginx.
3. Install Docker:

```bash
apt update
apt install -y curl
curl -fsSL https://get.docker.com | sh
```

4. Upload this `cloud-backend` directory to the server.
5. Create the environment file:

```bash
cp .env.example .env
nano .env
```

Change at least:

```bash
PUBLIC_PORT=80
PUBLIC_BASE_URL=http://YOUR_SERVER_IP
CLOUD_API_KEY=your-long-random-write-key
POSTGRES_PASSWORD=your-long-random-db-password
```

6. Start the backend:

```bash
docker compose up -d --build
docker compose logs -f api
```

7. Check health:

```bash
curl http://YOUR_SERVER_IP/health
```

## API Examples

Create or update an item from SS928:

```bash
curl -X POST http://YOUR_SERVER_IP/api/wardrobe/items \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-long-random-write-key" \
  -d '{
    "id": "cloth_001",
    "name": "白色短袖T恤",
    "type": "衬衫/T恤",
    "color": "白色",
    "season": "夏季",
    "material": "棉",
    "location": "衣柜A区-第2层",
    "confidence": 0.92,
    "spectralSignature": {
      "ch415": 123,
      "ch445": 98,
      "ch480": 76,
      "ch515": 64,
      "ch555": 70,
      "ch590": 88,
      "ch630": 91,
      "ch680": 79
    }
  }'
```

Upload a photo:

```bash
curl -X POST http://YOUR_SERVER_IP/api/wardrobe/items/cloth_001/photo \
  -H "x-api-key: your-long-random-write-key" \
  -F "photo=@/path/to/cloth.jpg"
```

Read items from the App:

```bash
curl http://YOUR_SERVER_IP/api/wardrobe/items
```

Check LLM recommendation status:

```bash
curl http://YOUR_SERVER_IP/api/llm/status
```

Ask the cloud LLM interface for a recommendation:

```bash
curl -X POST http://YOUR_SERVER_IP/api/llm/recommend \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-long-random-write-key" \
  -d '{
    "occasion": "school",
    "weather": {"city": "Hangzhou", "temperature_c": 22, "weather_text": "多云"},
    "wardrobe": [
      {"id": "top_1", "name": "白色Polo", "category": "top", "color": "white", "season": "spring_autumn,summer_light", "occasion": "school,casual", "warmth": 2, "favorite_score": 4},
      {"id": "bottom_1", "name": "黑色长裤", "category": "bottom", "color": "black", "season": "all", "occasion": "school,casual", "warmth": 3, "favorite_score": 4},
      {"id": "shoes_1", "name": "白色运动鞋", "category": "shoes", "color": "white", "season": "all", "occasion": "school,sport,casual", "warmth": 2, "favorite_score": 4}
    ]
  }'
```

By default this endpoint returns a deployable mock/fallback result with the same shape as the SS928 recommendation response. After the LoRA model is trained and served, set these variables in `.env`:

```bash
LLM_INFERENCE_URL=http://YOUR_MODEL_SERVER/v1/outfit/recommend
LLM_API_KEY=optional-model-server-key
LLM_MODEL=Qwen2.5-7B-Instruct-ClothesAI-LoRA
LLM_FALLBACK=true
```

The model server should accept the same JSON payload and return a JSON object containing `recommendations`, `explain`, and optional `model`/`source` fields.

## Connect SS928 To The Cloud LLM Interface

On the SS928 service environment, set:

```bash
SMART_WARDROBE_LLM_ENABLED=true
SMART_WARDROBE_LLM_URL=http://YOUR_SERVER_IP/api/llm/recommend
SMART_WARDROBE_LLM_API_KEY=your-long-random-write-key
SMART_WARDROBE_LLM_TIMEOUT=6
```

Then restart the board service. Existing `/api/recommendations` calls will try the cloud LLM first and automatically fall back to the local rule recommender if the cloud endpoint is unavailable.

## Connect The Mobile App

Create a frontend `.env.production` in the project root:

```bash
VITE_WARDROBE_API_BASE=http://YOUR_SERVER_IP
```

Then rebuild the APK. The App will try the cloud API first. If it fails, it falls back to local demo clothes.

## Later Upgrade Path

- Put Nginx in front of this API.
- Add HTTPS with Let's Encrypt.
- Move photos to OSS/COS.
- Add MQTT/EMQX for realtime refresh.
- Add per-device keys for every SS928.
