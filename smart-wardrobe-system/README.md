# Smart Wardrobe System

This folder contains the current MVP for the embedded competition project.

- `board/`: SS928 backend, SQLite database, camera capture, weather, recommendation algorithm, and AS7341 spectral material hints from WS63 packets.
- `mobile-app/`: mobile-style web app. It can be opened from a phone browser after the board server starts.

The WS63 sensor path can now post GY-AS7341 JSON readings to `/api/ws63/sensor`.
The backend saves the latest packet and adds an explainable material prediction
for demo-stage clothing intake.

