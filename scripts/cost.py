#!/usr/bin/env python3
"""Estimate what your AIWave usage will cost, using live public prices.

Usage:
    python3 scripts/cost.py --model deepseek-v4-flash --messages 500
    python3 scripts/cost.py --compare glm-5,kimi-k3,deepseek-v4-pro
    python3 scripts/cost.py --preset agent --model deepseek-v4-pro
    python3 scripts/cost.py --preset video --model kling-v2-6 --clips 30

Prices come from the same public endpoint as the website's pricing page:
https://aiwave.live/api/pricing — no API key needed. Every run prints the
fetch time and the pricing version so results are reproducible.

Billing model (from the live endpoint's fields):
  quota_type = 0 (per token)  input  = model_ratio * 2
                              output = model_ratio * completion_ratio * 2
                              cache  = model_ratio * cache_ratio * 2
  quota_type = 1 (per call)   cost   = model_price USD per call
"""
import argparse
import difflib
import json
import sys
import urllib.request
from datetime import datetime, timezone

ENDPOINT = "https://aiwave.live/api/pricing"

PRESETS = {
    # name: (avg_input_tokens, avg_output_tokens, messages_per_day, label)
    "chat":  (800, 300, 100, "Chat / Q&A — short turns"),
    "agent": (12000, 2000, 50, "Agent — long context, tool-heavy"),
}
VIDEO_PRESET_CLIPS = 10


def fetch():
    req = urllib.request.Request(ENDPOINT, headers={"User-Agent": "aiwave-cost/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def price_of(m):
    """Return (kind, rates dict) from one model record."""
    if m.get("quota_type") == 1 or (m.get("model_price") or 0) > 0:
        return "per_call", {"per_call": float(m.get("model_price") or 0)}
    ratio = float(m.get("model_ratio") or 0)
    cr = float(m.get("completion_ratio") or 1)
    cache_ratio = float(m.get("cache_ratio") or 0)
    return "per_token", {
        "input": ratio * 2,
        "output": ratio * cr * 2,
        "cache": ratio * cache_ratio * 2,
    }


def cost_token(rates, messages, avg_in, avg_out, cache_hit=0.0):
    in_tok = messages * avg_in
    out_tok = messages * avg_out
    billed_in = in_tok * (1 - cache_hit)
    cached_in = in_tok * cache_hit
    return (
        billed_in / 1e6 * rates["input"]
        + cached_in / 1e6 * rates["cache"]
        + out_tok / 1e6 * rates["output"]
    )


def fmt(v):
    return f"${v:,.4f}" if v < 1 else f"${v:,.2f}"


def main():
    ap = argparse.ArgumentParser(description="Estimate AIWave usage cost from live prices")
    ap.add_argument("--model", help="exact model ID (see https://aiwave.live/models)")
    ap.add_argument("--compare", help="comma-separated model IDs for side-by-side comparison")
    ap.add_argument("--messages", type=int, default=100, help="requests per day (default 100)")
    ap.add_argument("--avg-input", type=int, default=800, help="avg input tokens per request")
    ap.add_argument("--avg-output", type=int, default=300, help="avg output tokens per request")
    ap.add_argument("--cache-hit", type=float, default=0.0,
                    help="fraction of input tokens served from cache (0.0-1.0)")
    ap.add_argument("--preset", choices=["chat", "agent", "video"],
                    help="use a workload preset instead of raw numbers")
    ap.add_argument("--clips", type=int, help="video clips per day (video preset only)")
    ap.add_argument("--days", type=int, default=30, help="days for the monthly figure (default 30)")
    args = ap.parse_args()

    if not 0 <= args.cache_hit <= 1:
        sys.exit("--cache-hit must be between 0 and 1")

    try:
        data = fetch()
    except Exception as e:
        sys.exit(f"Could not reach {ENDPOINT}: {e}")
    models = data.get("models") or data.get("data") or []
    if not models:
        sys.exit("Endpoint returned no models — refusing to guess prices.")

    by_name = {m.get("model_name") or m.get("id"): m for m in models}
    version = str(models[0].get("pricing_version", "unknown"))[:16]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Workload
    if args.preset in PRESETS:
        avg_in, avg_out, msgs, label = PRESETS[args.preset]
        args.messages, args.avg_input, args.avg_output = msgs, avg_in, avg_out
        workload = f"{label} ({msgs} req/day, {avg_in} in + {avg_out} out)"
    elif args.preset == "video":
        workload = f"Video — {args.clips or VIDEO_PRESET_CLIPS} clips/day"
    else:
        workload = (f"{args.messages} req/day, {args.avg_input} in + "
                    f"{args.avg_output} out, cache hit {args.cache_hit:.0%}")

    print(f"AIWave cost estimate — {now}")
    print(f"Source: {ENDPOINT} (live, no key) | pricing_version {version}…")
    print(f"Workload: {workload}")
    print()

    targets = ([x.strip() for x in args.compare.split(",")] if args.compare
               else [args.model] if args.model else [])
    if not targets:
        ap.error("provide --model or --compare")

    # Validate names first — with useful suggestions
    bad = [t for t in targets if t not in by_name]
    if bad:
        print("Unknown model ID(s):", ", ".join(bad))
        for t in bad:
            near = difflib.get_close_matches(t, by_name.keys(), n=3, cutoff=0.5)
            print(f"  {t} — closest available: {', '.join(near) if near else '(none; see /models)'}")
        sys.exit(1)

    rows = []
    for name in targets:
        kind, rates = price_of(by_name[name])
        if kind == "per_call":
            clips = args.clips or (args.messages if args.preset == "video" else VIDEO_PRESET_CLIPS)
            daily = clips * rates["per_call"]
            detail = f"{fmt(rates['per_call'])}/call × {clips} calls"
        else:
            if args.preset == "video":
                print(f"  ! {name} is token-priced, not per-call — treating as text workload")
            daily = cost_token(rates, args.messages, args.avg_input,
                               args.avg_output, args.cache_hit)
            detail = (f"in {fmt(rates['input'])}/1M  out {fmt(rates['output'])}/1M  "
                      f"cache {fmt(rates['cache'])}/1M")
        rows.append((name, daily, daily * args.days, detail))

    rows.sort(key=lambda r: r[1])
    print(f"{'Model':<34} {'Per day':>12} {'Per '+str(args.days)+' days':>16}  Rates")
    print("-" * 100)
    for name, daily, monthly, detail in rows:
        print(f"{name:<34} {fmt(daily):>12} {fmt(monthly):>16}  {detail}")

    if len(rows) > 1:
        cheapest, priciest = rows[0], rows[-1]
        diff = priciest[2] - cheapest[2]
        print()
        print(f"Cheapest: {cheapest[0]} — saves {fmt(diff)} over {args.days} days "
              f"vs {priciest[0]} on this workload.")

    print()
    print("Rates change as vendors update pricing. Re-run before budgeting;")
    print("confirm against https://aiwave.live/pricing for production decisions.")


if __name__ == "__main__":
    main()
