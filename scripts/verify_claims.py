#!/usr/bin/env python3
"""Verify the public claims in AIWaveAPI repos against live public endpoints.

Usage:
    python3 scripts/verify_claims.py

Exit code 0 = all claims verified. Non-zero = a claim mismatched (details
printed). No API key required — this reads only public endpoints.

Claims checked (as written in our READMEs, dated 2026-11-01):
  1. Public rate card exposes 97 routes
  2. 10 Chinese model families on the public card
  3. 10 public video-generation routes
"""
import json
import sys
import urllib.request
from datetime import date

BASE = "https://aiwave.live"
CHINESE_PREFIXES = ["deepseek", "glm", "kimi", "qwen", "doubao", "step",
                    "xiaomi", "minimax", "kling", "wan3"]
VIDEO_MARKERS = ["kling", "seedance", "hailuo", "wan3.0-video", "vidu"]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "aiwave-verify/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    failures = []

    print(f"AIWave public-claims verification — run date {date.today().isoformat()}")
    print(f"Endpoint: {BASE}/api/pricing (public, no key)\n")

    data = fetch(f"{BASE}/api/pricing")
    models = data.get("models") or data.get("data") or []
    version = (models[0].get("pricing_version", "unknown")[:16] + "…") if models else "unknown"
    print(f"pricing_version: {version}")

    # Claim 1: total routes
    total = len(models)
    claim1 = (total == 97)
    print(f"\n[1] Public rate card routes")
    print(f"    claim: 97   actual: {total}   {'PASS' if claim1 else 'FAIL'}")
    if not claim1:
        failures.append(f"routes: claimed 97, actual {total}")

    # Claim 2: Chinese families
    families = set()
    for m in models:
        name = (m.get("model_name") or m.get("id") or "").lower()
        for p in CHINESE_PREFIXES:
            if name.startswith(p):
                families.add("qwen" if p == "qwen" else p)
                break
    claim2 = (len(families) == 10)
    print(f"\n[2] Chinese model families")
    print(f"    claim: 13   actual: {len(families)}   {'PASS' if claim2 else 'FAIL'}")
    print(f"    families: {', '.join(sorted(families))}")
    if not claim2:
        failures.append(f"families: claimed 13, actual {len(families)} ({sorted(families)})")

    # Claim 3: public video routes
    video = sorted({(m.get("model_name") or m.get("id")) for m in models
                    if any(k in (m.get("model_name") or m.get("id") or "").lower()
                           for k in VIDEO_MARKERS)})
    claim3 = (len(video) == 13)
    print(f"\n[3] Public video-generation routes")
    print(f"    claim: 13   actual: {len(video)}   {'PASS' if claim3 else 'FAIL'}")
    for v in video:
        print(f"      - {v}")
    if not claim3:
        failures.append(f"video routes: claimed 13, actual {len(video)}")

    # Secondary endpoint sanity: v1 pricing shape
    try:
        v1 = fetch(f"{BASE}/api/v1/pricing")
        v1n = len(v1.get("models", []))
        print(f"\n[.] Secondary endpoint /api/v1/pricing: {v1n} dated rows, "
              f"checked={v1.get('checked', '?')}")
    except Exception as e:
        print(f"\n[.] Secondary endpoint /api/v1/pricing: unreachable ({e})")

    print("\n" + "=" * 60)
    if failures:
        print("RESULT: MISMATCH — the READMEs are out of date. Please open an issue:")
        print("        https://github.com/AIWaveAPI/aiwave-quickstart/issues")
        for f in failures:
            print(f"        - {f}")
        sys.exit(1)
    print("RESULT: ALL CLAIMS VERIFIED")
    print("If your run shows different numbers, open an issue with this output:")
    print("https://github.com/AIWaveAPI/aiwave-quickstart/issues")
    sys.exit(0)


if __name__ == "__main__":
    main()
