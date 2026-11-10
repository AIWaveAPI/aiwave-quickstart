#!/usr/bin/env python3
"""Estimate what your AIWave usage will cost, using live public prices.

Usage:
    python3 scripts/cost.py --model deepseek-v4-flash --messages 500
    python3 scripts/cost.py --compare glm-5,kimi-k3,deepseek-v4-pro
    python3 scripts/cost.py --preset agent --model deepseek-v4-pro
    python3 scripts/cost.py --preset video --model kling-v2-6 --group "Visual Team" --clips 30

Prices come from the same public endpoint as the website's pricing page:
https://aiwave.live/api/pricing — no API key needed. Every run prints the
fetch time and the pricing version so results are reproducible.

Billing model (from the live endpoint's fields, for the selected eligible group):
  quota_type = 0 (per token)  input  = model_ratio * group_ratio * 2
                              output = model_ratio * completion_ratio * group_ratio * 2
                              cache  = model_ratio * cache_ratio * group_ratio * 2
  quota_type = 1 (per call)   cost   = model_price * group_ratio USD per call

If the catalog omits the selected group's multiplier or the model's price,
the estimator refuses to quote. Catalog eligibility is not a health check.
"""
import argparse
import difflib
import json
import math
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


def catalog_index(data):
    """Index a complete, unambiguous catalog before making any price quote."""
    if not isinstance(data, dict):
        raise ValueError("invalid catalog response")
    models = data.get("models") if "models" in data else data.get("data")
    if not isinstance(models, list) or not models:
        raise ValueError("endpoint returned no model list")
    by_name = {}
    for row in models:
        if not isinstance(row, dict):
            raise ValueError("invalid model row")
        name = row.get("model_name") or row.get("id")
        if not isinstance(name, str) or not name.strip() or name != name.strip():
            raise ValueError("invalid model ID")
        if name in by_name:
            raise ValueError(f"duplicate model ID: {name}")
        by_name[name] = row
    return by_name


def _number(value, label, *, allow_zero=False):
    if isinstance(value, bool):
        raise ValueError(f"missing or invalid {label}")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"missing or invalid {label}") from None
    if not math.isfinite(result) or result < 0 or (result == 0 and not allow_zero):
        raise ValueError(f"missing or invalid {label}")
    return result


def price_of(m, group, group_ratios):
    """Return an estimate only when the named group and rate are observable."""
    if not isinstance(group_ratios, dict):
        raise ValueError("missing group ratio map")
    ratio = _number(group_ratios.get(group), f"{group!r} group ratio")
    eligible_groups = m.get("enable_groups")
    if not isinstance(eligible_groups, list) or group not in eligible_groups:
        raise ValueError(f"{m.get('model_name', 'model')} is not enabled for {group!r}")
    if m.get("quota_type") == 1:
        per_call = _number(m.get("model_price"), "per-call model price")
        return "per_call", {"per_call": per_call * ratio}
    if m.get("quota_type") != 0:
        raise ValueError("unknown quota_type; cannot infer billing unit")
    model_ratio = _number(m.get("model_ratio"), "model_ratio")
    cr = _number(m.get("completion_ratio"), "completion_ratio")
    cache_ratio = (_number(m["cache_ratio"], "cache_ratio", allow_zero=True)
                   if m.get("cache_ratio") is not None else None)
    return "per_token", {
        "input": model_ratio * ratio * 2,
        "output": model_ratio * cr * ratio * 2,
        "cache": model_ratio * cache_ratio * ratio * 2 if cache_ratio is not None else None,
    }


def cost_token(rates, messages, avg_in, avg_out, cache_hit=0.0):
    if cache_hit and rates["cache"] is None:
        raise ValueError("cache hit rate requested but the live card has no cache price")
    in_tok = messages * avg_in
    out_tok = messages * avg_out
    billed_in = in_tok * (1 - cache_hit)
    cached_in = in_tok * cache_hit
    return (
        billed_in / 1e6 * rates["input"]
        + (cached_in / 1e6 * rates["cache"] if cache_hit else 0)
        + out_tok / 1e6 * rates["output"]
    )


def fmt(v):
    if 0 < v < 0.00005:
        return f"${v:.8g}"
    return f"${v:,.4f}" if v < 1 else f"${v:,.2f}"


def main():
    ap = argparse.ArgumentParser(description="Estimate AIWave usage cost from live prices")
    ap.add_argument("--model", help="exact model ID (see https://aiwave.live/models)")
    ap.add_argument("--compare", help="comma-separated model IDs for side-by-side comparison")
    ap.add_argument("--group", default="default", help="eligible account group with a published ratio (default: default)")
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
    if args.days <= 0:
        sys.exit("--days must be positive")
    if args.messages <= 0 or args.avg_input < 0 or args.avg_output < 0:
        sys.exit("--messages must be positive; --avg-input and --avg-output cannot be negative")
    if args.avg_input == 0 and args.avg_output == 0:
        sys.exit("--avg-input and --avg-output cannot both be zero")
    if args.clips is not None and args.clips <= 0:
        sys.exit("--clips must be positive")
    if args.clips is not None and args.preset != "video":
        sys.exit("--clips is only used with --preset video")

    try:
        data = fetch()
    except Exception as e:
        sys.exit(f"Could not reach {ENDPOINT}: {e}")
    try:
        by_name = catalog_index(data)
    except ValueError as exc:
        sys.exit(f"Cannot use live catalog: {exc}; refusing to guess prices.")
    version = str(data.get("pricing_version", "unknown"))[:16]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Workload
    if args.preset in PRESETS:
        avg_in, avg_out, msgs, label = PRESETS[args.preset]
        args.messages, args.avg_input, args.avg_output = msgs, avg_in, avg_out
        workload = f"{label} ({msgs} req/day, {avg_in} in + {avg_out} out)"
    elif args.preset == "video":
        workload = f"Video — {args.clips if args.clips is not None else VIDEO_PRESET_CLIPS} clips/day"
    else:
        workload = (f"{args.messages} req/day, {args.avg_input} in + "
                    f"{args.avg_output} out, cache hit {args.cache_hit:.0%}")

    print(f"AIWave cost estimate — {now}")
    print(f"Source: {ENDPOINT} (live, no key) | pricing_version {version}…")
    print(f"Account group: {args.group} (catalog-listed eligibility and ratio only)")
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
        try:
            kind, rates = price_of(by_name[name], args.group, data.get("group_ratio") or {})
        except ValueError as exc:
            sys.exit(f"Cannot quote {name}: {exc}. Check group access and https://aiwave.live/pricing")
        if kind == "per_call":
            if args.preset != "video":
                sys.exit(f"{name} is per-call; use --preset video and --clips instead of a text workload")
            clips = args.clips if args.clips is not None else VIDEO_PRESET_CLIPS
            daily = clips * rates["per_call"]
            detail = f"{fmt(rates['per_call'])}/call × {clips} calls"
        else:
            if args.preset == "video":
                sys.exit(f"{name} is token-priced; --preset video cannot estimate it as clips")
            try:
                daily = cost_token(rates, args.messages, args.avg_input,
                                   args.avg_output, args.cache_hit)
            except ValueError as exc:
                sys.exit(f"Cannot quote {name}: {exc}")
            detail = (f"in {fmt(rates['input'])}/1M  out {fmt(rates['output'])}/1M  "
                      f"cache {fmt(rates['cache']) + '/1M' if rates['cache'] is not None else 'not published'}")
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
    print("per-call estimates use the base rate and omit request-specific modifiers.")
    print("Confirm group access and final usage against https://aiwave.live/pricing and Console.")


if __name__ == "__main__":
    main()
