#!/usr/bin/env python3
"""AIWave video generation example: submit a job, poll until done, print the URL.

Video routes are experimental and require a paid account group (from $5).
Battle-tested notes (from real productions, 2026-10):
  - A single shot takes 5-11 minutes. Poll every 15s; give up after 15 min.
  - Some upstream channels stall without a reference image. If a task stays
    NOT_START with 0% progress for >3 minutes, keep its task ID and check
    status or usage before submitting another billable job.

Usage:
    export AIWAVE_API_KEY="sk-..."   # https://aiwave.live/register
    python3 examples/video_python.py "A red sports car drifting through a neon city"
"""
import json
import os
import sys
import time
import urllib.request

BASE_URL = os.environ.get("AIWAVE_BASE_URL", "https://aiwave.live/v1")
MODEL = os.environ.get("AIWAVE_VIDEO_MODEL", "kling-v2-6")
API_KEY = os.environ.get("AIWAVE_API_KEY", "")


def req(url: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else \
        "A red sports car drifting through a neon-lit city at night, cinematic tracking shot, rain reflections"

    if not API_KEY:
        sys.exit("Set AIWAVE_API_KEY first (https://aiwave.live/register)")

    print(f"==> Submitting video job ({MODEL})...")
    resp = req(f"{BASE_URL}/video/generations", {"model": MODEL, "prompt": prompt})
    task_id = resp.get("task_id") or resp.get("id")
    if not task_id:
        sys.exit(f"No task_id in response: {json.dumps(resp)[:300]}")
    print(f"    task_id: {task_id}")

    not_start_since = None
    for i in range(60):  # 15 min max
        time.sleep(15)
        status = req(f"{BASE_URL}/video/generations/{task_id}")
        data = status.get("data", status)
        st = data.get("status", "?")
        prog = data.get("progress", "")
        print(f"  [{(i + 1) * 15}s] {st} {prog}")

        if st == "SUCCESS":
            # The result URL may live at different depths depending on channel;
            # scan the JSON for the first mp4 link.
            raw = json.dumps(status)
            import re
            m = re.search(r'https?://[^"\\]+\.mp4[^"\\]*', raw)
            print(f"\nDone: {m.group(0) if m else '(scan response for URL)'}")
            return
        if st == "FAILURE":
            sys.exit(f"Failed upstream: {data.get('fail_reason', 'unknown')}")

        # Silent-failure heuristic: stuck at NOT_START/0% for >3 minutes
        if st in ("NOT_START", "QUEUING") and prog in ("", "0%", 0):
            not_start_since = not_start_since or time.time()
            if time.time() - not_start_since > 180:
                sys.exit("Stuck >3 min with 0% progress. Keep the task ID and "
                         "check status or usage before submitting another job.")
        else:
            not_start_since = None

    sys.exit("Timed out after 15 minutes")


if __name__ == "__main__":
    main()
