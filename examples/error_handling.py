#!/usr/bin/env python3
"""Copy-paste error handling for AIWave / OpenAI-compatible clients.

Covers 401 / 402 / 404 / 429 / 5xx with real, runnable handlers. Requires
only `openai` (or use the plain-urllib variant at the bottom if you prefer).

Usage:
    export AIWAVE_API_KEY="sk-..."
    python3 examples/error_handling.py
"""
import difflib
import json
import os
import random
import time
import urllib.error
import urllib.request

BASE_URL = "https://aiwave.live/v1"
PRICING = "https://aiwave.live/api/pricing"


def live_model_ids():
    """Exact model IDs from the live catalog (no key needed)."""
    try:
        with urllib.request.urlopen(PRICING, timeout=15) as r:
            d = json.loads(r.read().decode())
        ms = d.get("models") or d.get("data") or []
        return [m.get("model_name") or m.get("id") for m in ms]
    except Exception:
        return []


def handle(status, body, *, request_id=None, attempted_model=None):
    """Print a concrete next action for each error code. Returns True if retryable."""
    try:
        msg = json.loads(body).get("error", {}).get("message", body) if body else ""
    except Exception:
        msg = body or ""

    if status == 401:
        print("401 — authentication failed.")
        print("  Check: AIWAVE_API_KEY is set, starts with 'sk-', and the header is")
        print("  'Authorization: Bearer <key>' (the word Bearer is required).")
        print("  If it worked before, the key may have been rotated — issue a new one.")
        return False

    if status == 402:
        print("402 — insufficient balance or no enabled group with quota.")
        print("  Add balance at https://aiwave.live/pricing, or use a group")
        print("  with available quota. This is not a retryable error.")
        return False

    if status == 404:
        print("404 — model ID not found or retired.")
        ids = live_model_ids()
        if attempted_model and ids:
            near = difflib.get_close_matches(attempted_model, ids, n=3, cutoff=0.5)
            print(f"  Copy the exact ID from https://aiwave.live/models")
            if near:
                print(f"  Closest currently on the rate card: {', '.join(near)}")
        else:
            print("  Copy the exact ID from https://aiwave.live/models")
        return False

    if status == 429:
        print("429 — rate limited. Retry with bounded exponential backoff + jitter.")
        print("  Prefer the server's Retry-After header over local backoff.")
        return True

    if 500 <= status < 600:
        print(f"{status} — upstream/server error. Request id: {request_id or '(none)'}")
        print("  Retry ONLY when the operation is safe to repeat (chat is; a paid")
        print("  generation job may not be). Keep the request id for support.")
        return True

    print(f"{status} — unhandled status. Body: {str(msg)[:200]}")
    return False


def retry_after_seconds(headers, attempt):
    """Use Retry-After when present; otherwise exponential backoff + jitter."""
    raw = headers.get("Retry-After") if headers else None
    if raw:
        try:
            return min(float(raw), 60)
        except (TypeError, ValueError):
            pass
    return min(2 ** attempt + random.uniform(0, 0.5), 30)


def chat_with_retries(model, messages, *, api_key=None, max_retries=3):
    """A complete request with 429/5xx retries. Copy this whole function."""
    key = api_key or os.environ.get("AIWAVE_API_KEY")
    if not key:
        raise ValueError("Set AIWAVE_API_KEY first (https://aiwave.live/register)")

    payload = json.dumps({"model": model, "messages": messages}).encode()
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            f"{BASE_URL}/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            rid = e.headers.get("x-request-id") or e.headers.get("X-Request-Id")
            retryable = handle(e.code, body, request_id=rid, attempted_model=model)
            if not retryable or attempt == max_retries:
                raise
            wait = retry_after_seconds(e.headers, attempt)
            print(f"  retrying in {wait:.1f}s (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait)


if __name__ == "__main__":
    # Smoke test with an obviously invalid key -> a real 401, handled above.
    print("=== Real 401 smoke test (bad key) ===")
    try:
        chat_with_retries("deepseek-v4-flash",
                          [{"role": "user", "content": "hi"}],
                          api_key="sk-invalid-for-smoke-test", max_retries=0)
    except urllib.error.HTTPError as e:
        print(f"  got HTTP {e.code} as expected; handler printed the checklist above.")
    except Exception as e:
        print(f"  network unavailable here ({type(e).__name__}) — run this on your machine.")
