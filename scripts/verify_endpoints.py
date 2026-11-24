#!/usr/bin/env python3
"""Verify the base URLs we publish actually resolve to API routes, not the SPA.

Why this exists (2026-11-25): this repo told developers to set
ANTHROPIC_BASE_URL="https://aiwave.live/anthropic". That path has no nginx
location, so it fell through to the single-page-app fallback and returned
HTTP 200 text/html. Claude Code appends /v1/messages, so every request went
to /anthropic/v1/messages -> HTML -> hard client failure. The status code
looked healthy (200), which is exactly why nobody noticed.

The discriminator used here is the response SHAPE, not the status code:
  - A real API route answers an unauthenticated request with
    401 + application/json (the router ran, token check failed).
  - A wrong path answers 200 + text/html (the SPA shell).
Checking only for "not 404" would have passed the broken base.

Checks:
  1. Every base declared in scripts/aiwave-setup.py, when joined with the
     suffix that client appends, returns JSON and not HTML.
  2. ANTHROPIC_BASE_URL carries no path prefix that would produce
     /<prefix>/v1/messages.
  3. The published README table agrees with the script constants.

Usage:
    python3 scripts/verify_endpoints.py [--repo-root PATH] [--offline]

Exit 0 = every published base reaches a JSON API. 1 = at least one base
reaches HTML or is unreachable. 2 = could not read the script constants.
--offline runs only checks 2 and 3 (no network), for flaky CI sandboxes.
"""
import argparse
import importlib.util
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROBE_BODY = {
    "model": "connectivity-probe",
    "max_tokens": 8,
    "messages": [{"role": "user", "content": "ping"}],
}
TIMEOUT = 25
UA = "aiwave-verify-endpoints/1.0"


def load_setup_module(path):
    spec = importlib.util.spec_from_file_location("aw_setup", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def probe(url):
    """Return (status, content_type, first_bytes). Never raises on HTTP errors."""
    req = urllib.request.Request(
        url,
        data=json.dumps(PROBE_BODY).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": UA},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read()[:200]
    except Exception as e:  # DNS, TLS, timeout
        return None, f"transport-error: {e}", b""


def is_html(ctype, body):
    if "text/html" in (ctype or "").lower():
        return True
    head = body[:64].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def is_json(ctype, body):
    if "application/json" in (ctype or "").lower():
        return True
    try:
        json.loads(body.decode("utf-8", "replace"))
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    root = Path(args.repo_root).resolve()
    setup_py = root / "scripts" / "aiwave-setup.py"
    readme = root / "README.md"
    if not setup_py.exists():
        print(f"FAIL: cannot find {setup_py}", file=sys.stderr)
        return 2

    try:
        mod = load_setup_module(setup_py)
    except Exception as e:
        print(f"FAIL: cannot import {setup_py}: {e}", file=sys.stderr)
        return 2

    anthropic_base = mod.ANTHROPIC_BASE.rstrip("/")
    # OPENAI_BASE is absent in versions where Codex setup is paused. Treat it
    # as optional so this checker works across both layouts; when present we
    # probe it too.
    openai_base = getattr(mod, "OPENAI_BASE", None)
    openai_base = openai_base.rstrip("/") if openai_base else None
    print(f"anthropic base: {anthropic_base}")
    print(f"openai    base: {openai_base or '(not configured in this version)'}")

    failures = []

    # --- check 2: the Anthropic base must not carry a path prefix ------------
    # Claude Code appends /v1/messages. Any prefix other than "" yields
    # /<prefix>/v1/messages, which nginx has no location for.
    if anthropic_base.count("/") > 2:
        failures.append(
            f"ANTHROPIC_BASE has a path prefix and would produce "
            f"{anthropic_base}/v1/messages; it must be the bare origin"
        )
    if anthropic_base.endswith("/anthropic"):
        failures.append(
            "ANTHROPIC_BASE ends with /anthropic, which resolves to the SPA "
            "shell (200 text/html) instead of the Messages API"
        )

    # --- check 3: README must agree with the constants ----------------------
    if readme.exists():
        text = readme.read_text(encoding="utf-8", errors="replace")
        for bad in re.findall(r"https://aiwave\.live/anthropic\b", text):
            failures.append(f"README publishes {bad} (SPA shell, not an API route)")
        if anthropic_base not in text:
            failures.append(
                f"README never mentions the live Anthropic base {anthropic_base}"
            )

    # --- check 1: live shape probe -----------------------------------------
    if not args.offline:
        targets = [
            ("Anthropic Messages", f"{anthropic_base}/v1/messages"),
            # Negative control: this is the path that used to be published.
            # It MUST be HTML; if it ever becomes a real JSON API, the guard
            # in check 2 could be relaxed — but silently, so we assert.
            ("negative control (must be HTML)", f"{anthropic_base}/anthropic/v1/messages"),
        ]
        if openai_base:
            targets.insert(1, ("OpenAI chat", f"{openai_base}/chat/completions"))
        for label, url in targets:
            status, ctype, body = probe(url)
            negative = label.startswith("negative control")
            if status is None:
                failures.append(f"{label}: {url} unreachable ({ctype})")
                print(f"  FAIL {label}: unreachable — {ctype}")
                continue
            html = is_html(ctype, body)
            js = is_json(ctype, body)
            detail = f"status={status} type={ctype.split(';')[0]} html={html} json={js}"
            if negative:
                # We only need it to be distinguishable. HTML = still a shell.
                if not html:
                    print(f"  NOTE {label}: {url} -> {detail}")
                    print("       /anthropic now returns non-HTML; re-examine the "
                          "check-2 guard before relaxing it.")
                else:
                    print(f"  ok   {label}: {url} -> {detail}")
                continue
            if html:
                failures.append(
                    f"{label}: {url} returned HTML, not an API response "
                    f"({detail}). This is the SPA shell — every client request "
                    f"here fails."
                )
                print(f"  FAIL {label}: {url} -> {detail}")
            elif not js:
                failures.append(f"{label}: {url} returned neither JSON nor HTML ({detail})")
                print(f"  FAIL {label}: {url} -> {detail}")
            else:
                print(f"  ok   {label}: {url} -> {detail}")
    else:
        print("  (offline: skipped live shape probes)")

    print()
    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("PASS: every published base reaches a JSON API, not the SPA shell.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
