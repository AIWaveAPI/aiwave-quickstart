#!/usr/bin/env python3
"""AIWave video generation example: submit a job, poll until done, print the URL.

Video routes are experimental; model and account-group eligibility varies.
This example polls every 15 seconds and stops after 15 minutes. Completion
time varies by route. If the task remains at NOT_START with 0% progress,
keep its task ID and check status or usage before another paid submission.

Usage:
    export AIWAVE_API_KEY="sk-..."   # https://aiwave.live/register
    python3 examples/video_python.py "A red sports car drifting through a neon city"
"""
import json
import os
import sys
import time
import urllib.request
from urllib.parse import quote

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
    try:
        resp = req(f"{BASE_URL}/video/generations", {"model": MODEL, "prompt": prompt})
    except Exception:
        sys.exit("Submission outcome unknown. Check task history and usage before submitting another paid job.")
    data = resp.get("data", resp) if isinstance(resp, dict) else None
    task_id = data.get("task_id") or data.get("id") if isinstance(data, dict) else None
    if not isinstance(task_id, str) or not task_id:
        sys.exit("No task ID in submission response. Check task history and usage before submitting another paid job.")
    print(f"    task_id: {task_id}")

    not_start_since = None
    for i in range(60):  # 15 min max
        time.sleep(15)
        try:
            status = req(f"{BASE_URL}/video/generations/{quote(task_id, safe='')}")
        except Exception:
            sys.exit(f"Cannot check task {task_id}. Keep its ID and review status or usage before another submission.")
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

    sys.exit(f"Task {task_id} was not complete after 15 minutes. Check status and usage before another submission.")


if __name__ == "__main__":
    main()
