#!/usr/bin/env python3
"""Validate that GEMINI_API_KEY can call the Gemini API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))
    parser.add_argument("--timeout", type=float, default=20)
    args = parser.parse_args()

    api_key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("SMART_WARDROBE_GEMINI_API_KEY")
        or ""
    ).strip()
    if not api_key:
        print("GEMINI_API_KEY is not set")
        return 2

    body = {
        "contents": [{"parts": [{"text": "Return only JSON: {\"ok\":true}"}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + urllib.parse.quote(args.model, safe="-_.")
        + ":generateContent?key="
        + urllib.parse.quote(api_key)
    )
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        print("Gemini API rejected the key: HTTP %s" % exc.code)
        print(detail)
        return 1
    except Exception as exc:
        print("Gemini API request failed: %s" % exc)
        return 1

    text = ""
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        pass
    print("Gemini API key works.")
    print(text.strip() or json.dumps(payload, ensure_ascii=False)[:300])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
