#!/usr/bin/env python3
"""Verify matching backticked model IDs in Markdown against the live card.

A made-up ID in a README is worse than a missing one: a developer copies it,
gets a 404, and leaves. This checker prevents that, and runs in CI daily
alongside verify_claims.py.

Rules:
  - Only IDs that LOOK like model IDs are checked (backslash-free lowercase
    strings inside backticks, matching known vendor prefixes).
  - Search-query cells (e.g. `deepseek v4 flash` with spaces) are ignored.
  - Any ID preceded by "no " / "not " / "There is no" is a deliberate
    negative statement and is ignored.
  - Family shorthand (`kling`, `qwen3.8`) is ignored via a whitelist.

Usage:
    python3 scripts/verify_model_ids.py --repo-root <root> [--catalog-json PATH]
Exit code 0 = all IDs real. 1 = at least one made-up ID. 2 = no catalog data.
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

ENDPOINT = "https://aiwave.live/api/pricing"
PREFIXES = ("deepseek", "qwen", "kimi", "glm-", "kling-", "wan3", "doubao",
            "minimax", "claude-", "gpt-", "cohere/", "nvidia/", "step-",
            "xiaomi/", "happyhorse", "inclusionai/", "vidu")
# Family names / version shorthands used in prose, not exact model IDs.
WHITELIST = {"kling", "seedance", "hailuo", "wan", "qwen3.8", "qwen3.7",
             "glm", "deepseek", "kimi", "claude", "qwen", "minimax"}
# A row/line that explicitly says an ID does not exist is a deliberate
# negative statement ("There is no `qwen3-coder` ID on our card"), not a
# made-up ID. Check the whole line, not just the text before the token,
# because the phrase can sit in a later table column.
NEGATIVE = re.compile(r"\b(?:there\s+is\s+)?no\s+`?[a-z0-9._-]+`?\s+(?:id|model|route)\b|\bnot\s+on\s+(?:our|the)\s+(?:card|rate\s+card)\b", re.I)
IN_CODE = re.compile(r"`([^`\n]+)`")

SKIP_DIRS = {".git", "node_modules", "build", "dist", "__pycache__", "pkg", "secrets"}
SKIP_FILES = {"MODEL_REFERENCE.md", "verify_model_ids.py", "test_claims_tools.py",
              "catalog-claims.json", "CHANGELOG.md", "test_error_handlers.py",
              "test_aiwave_setup.py"}


def load_catalog(path):
    if path:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(ENDPOINT, headers={"User-Agent": "aiwave-idcheck/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def looks_like_id(token):
    t = token.strip()
    if not t or " " in t or "/" in t and not t.startswith(("cohere/", "nvidia/", "xiaomi/", "inclusionai/")):
        return False
    if t in WHITELIST:
        return False
    return any(t.lower().startswith(p) for p in PREFIXES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--catalog-json", default=None)
    args = ap.parse_args()

    try:
        data = load_catalog(args.catalog_json)
    except Exception as e:
        print(f"ERROR: cannot load catalog: {e}", file=sys.stderr)
        return 2
    models = data.get("models") or data.get("data") or []
    if not models:
        print("ERROR: empty catalog — refusing to check against nothing.", file=sys.stderr)
        return 2
    real = {(m.get("model_name") or m.get("id") or "") for m in models}

    print(f"Model-ID verification — {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}")
    print(f"Source: {args.catalog_json or ENDPOINT} ({len(real)} live IDs)\n")

    bad, seen = [], 0
    for dirpath, dirnames, filenames in os.walk(args.repo_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".md") or fn in SKIP_FILES:
                continue
            path = os.path.join(dirpath, fn)
            text = open(path, encoding="utf-8", errors="ignore").read()
            rel = os.path.relpath(path, args.repo_root)
            for lineno, line in enumerate(text.splitlines(), 1):
                for m in IN_CODE.finditer(line):
                    token = m.group(1)
                    if not looks_like_id(token):
                        continue
                    seen += 1
                    if token in real:
                        continue
                    prefix = line[:m.start()]
                    if NEGATIVE.search(line):
                        continue  # deliberate "there is no `x` ID" statement
                    bad.append((rel, lineno, token, line.strip()[:96]))

    print(f"Checked {seen} model-ID mentions")
    print("-" * 76)
    if bad:
        print(f"RESULT: MISMATCH — {len(bad)} ID(s) not on the live card\n")
        for rel, lineno, token, snippet in bad:
            print(f"  {rel}:{lineno}  `{token}`")
            print(f"      > {snippet}")
        print("\nFix the ID (copy it from /api/pricing), or mark it clearly as")
        print("a negative statement (\"there is no `x` ID\"). Never invent one.")
        return 1
    print("RESULT: CHECKED MODEL ID MENTIONS VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

