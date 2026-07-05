# Smart Wardrobe System

This folder contains the current MVP for the embedded competition project.

- `board/`: SS928 backend, SQLite database, camera capture, weather, recommendation algorithm.
- `mobile-app/`: mobile-style web app. It can be opened from a phone browser after the board server starts.

The current version intentionally skips the WS63 firmware because that board is not available now. A `/api/ws63/sensor` endpoint is kept for later integration.

