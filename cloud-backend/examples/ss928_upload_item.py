#!/usr/bin/env python3
import json
import sys
import urllib.request


def post_json(url, api_key, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: ss928_upload_item.py http://SERVER:3000 YOUR_API_KEY")
        raise SystemExit(2)

    base_url = sys.argv[1].rstrip("/")
    api_key = sys.argv[2]
    payload = {
        "id": "cloth_demo_001",
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
            "ch680": 79,
        },
    }
    print(json.dumps(post_json(f"{base_url}/api/wardrobe/items", api_key, payload), ensure_ascii=False, indent=2))
