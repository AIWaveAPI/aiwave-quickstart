#!/usr/bin/env python3
"""Check the numeric Popular picks table against the live /api/pricing card.

Scope is deliberately narrow: only the README table below "Popular picks"
is checked. This does not establish that every published rate is verified, nor
does the public card prove that an enabled route is presently healthy.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path


ENDPOINT = "https://aiwave.live/api/pricing"
MODEL = re.compile(r"^`([^`]+)`$")
RATE = re.compile(r"^\$(\d+(?:\.\d+)?)\s*/\s*\$(\d+(?:\.\d+)?)\s+per\s+1M$", re.I)


def decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"invalid numeric rate field: {value!r}") from None


def check_prices(readme, catalog):
    """Return (number of priced rows checked, list of actionable failures)."""
    rows = catalog.get("data")
    if not isinstance(rows, list) or not rows:
        return 0, ["live catalog has no data rows"]
    group = catalog.get("group_ratio", {}).get("default")
    if group is None:
        return 0, ["live catalog has no default group ratio"]
    try:
        multiplier = decimal(group)
    except ValueError as exc:
        return 0, [str(exc)]
    models = {row.get("model_name"): row for row in rows if isinstance(row, dict)}
    in_table = False
    found = False
    checked = 0
    seen = set()
    errors = []
    for lineno, line in enumerate(readme.splitlines(), 1):
        if "Popular picks (reasoning & chat):" in line:
            if found:
                errors.append(f"line {lineno}: duplicate Popular picks table")
            found = in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("## "):
            in_table = False
            continue
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3:
            errors.append(f"line {lineno}: Popular picks row must have three columns")
            continue
        model_match = MODEL.fullmatch(cells[0])
        if not model_match:
            if cells[0] not in ("Model", "---") and not cells[0].startswith("---"):
                errors.append(f"line {lineno}: cannot identify model ID")
            continue
        model_id = model_match.group(1)
        if model_id in seen:
            errors.append(f"line {lineno}: duplicate model {model_id}")
        seen.add(model_id)
        rate_text = cells[2]
        if "see [pricing]" in rate_text.lower():
            continue
        rate_match = RATE.fullmatch(rate_text)
        if not rate_match:
            errors.append(f"line {lineno}: {model_id} has unparseable numeric rate {rate_text!r}")
            continue
        checked += 1
        row = models.get(model_id)
        if row is None:
            errors.append(f"line {lineno}: {model_id} is absent from live /api/pricing")
            continue
        if "default" not in row.get("enable_groups", []):
            errors.append(f"line {lineno}: {model_id} is not listed for default group")
            continue
        if row.get("quota_type") != 0:
            errors.append(f"line {lineno}: {model_id} is per-call, not per-token")
            continue
        try:
            ratio = decimal(row["model_ratio"])
            completion = decimal(row["completion_ratio"])
            expected_input = ratio * multiplier * Decimal("2")
            expected_output = expected_input * completion
        except (KeyError, ValueError) as exc:
            errors.append(f"line {lineno}: {model_id} has missing or invalid card field: {exc}")
            continue
        shown_input, shown_output = map(Decimal, rate_match.groups())
        if (shown_input, shown_output) != (expected_input, expected_output):
            errors.append(
                f"line {lineno}: {model_id} shows ${shown_input}/${shown_output} per 1M; "
                f"live default-group math gives ${expected_input}/${expected_output} "
                "from model_ratio, completion_ratio, group_ratio")
    if not found:
        errors.append("README has no Popular picks table")
    if checked == 0:
        errors.append("README has no numeric Popular picks rates to verify")
    return checked, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--readme", type=Path, default=Path(__file__).resolve().parents[1] / "README.md")
    parser.add_argument("--catalog-json", type=Path)
    args = parser.parse_args()
    try:
        readme = args.readme.read_text(encoding="utf-8")
        if args.catalog_json:
            catalog = json.loads(args.catalog_json.read_text(encoding="utf-8"))
            source = str(args.catalog_json)
        else:
            request = urllib.request.Request(ENDPOINT, headers={"User-Agent": "aiwave-readme-price-check/1.0"})
            with urllib.request.urlopen(request, timeout=30) as response:
                catalog = json.load(response)
            source = ENDPOINT
    except (OSError, ValueError, urllib.error.URLError) as exc:
        print(f"ERROR: cannot load README or catalog: {exc}", file=sys.stderr)
        return 2
    checked, errors = check_prices(readme, catalog)
    print(f"Source: {source}; numeric README rows checked: {checked}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
