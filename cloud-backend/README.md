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
