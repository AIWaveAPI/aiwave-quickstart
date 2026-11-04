#!/usr/bin/env python3
"""Offline checks that verify_claims.py and sync_claims.py stay in sync.

Both tools must use identical patterns and identical catalog math, otherwise
"sync then verify" could loop forever. This proves they agree using a fixture
catalog — no network, no keys, no production data.
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


v = load("verify_claims")
s = load("sync_claims")


def check(cond, label):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)
    print(f"PASS: {label}")


def mismatches(text, live):
    found = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for pat, gi, key in v.PATTERNS:
            for m in pat.finditer(line):
                if int(m.group(gi)) != live[key]:
                    found.append((lineno, key, int(m.group(gi)), live[key]))
    return found


def main():
    # 1. Both tools define byte-identical patterns, otherwise a fix could
    #    never make verification pass.
    check(len(v.PATTERNS) == len(s.PATTERNS), "same number of claim patterns")
    check([(p.pattern, g, k) for p, g, k in v.PATTERNS] ==
          [(p.pattern, g, k) for p, g, k in s.PATTERNS],
          "patterns are byte-identical across both tools")

    # 2. Fixture: 4 models, 3 Chinese families (deepseek/glm/kling), 1 video.
    fixture = {"models": [
        {"model_name": "deepseek-x", "pricing_version": "abc123"},
        {"model_name": "glm-y", "pricing_version": "abc123"},
        {"model_name": "kling-v9", "pricing_version": "abc123"},
        {"model_name": "gpt-z", "pricing_version": "abc123"},
    ]}
    vn, sn = v.live_numbers(fixture), s.live_numbers(fixture)
    check(vn == sn, "both tools compute identical live numbers")
    check(vn["routes"] == 4 and vn["families"] == 3 and vn["video"] == 1,
          f"fixture math correct: {vn}")

    live = {"routes": 4, "families": 3, "video": 1}
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "README.md"
        stale = ("We offer **9 public routes** and **3 public video routes**.\n"
                 "Badge: routes-3-purple\n")
        path.write_text(stale, encoding="utf-8")

        # 3. verify detects all three stale numbers.
        found = mismatches(stale, live)
        check(len(found) == 3, f"verify detects all 3 stale numbers (got {len(found)})")

        # 4. sync rewrites each of them, and nothing else.
        fixed_lines = [s.replace_line(line, live)[0] for line in stale.splitlines()]
        fixed = "\n".join(fixed_lines)
        check("4 public routes" in fixed, "sync rewrites routes 9 -> 4")
        check("1 public video routes" in fixed, "sync rewrites video 3 -> 1")
        check("routes-1-purple" in fixed, "sync rewrites badge 3 -> 1")
        check("**" in fixed and "We offer" in fixed, "sync preserves surrounding text")

        # 5. After sync, verify is clean (the anti-loop guarantee).
        check(not mismatches(fixed, live), "post-sync verification is clean")

    print("\nAll claims-tool checks passed.")


if __name__ == "__main__":
    main()
