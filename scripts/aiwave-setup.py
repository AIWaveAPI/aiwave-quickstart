#!/usr/bin/env python3
"""Add AIWave as a provider for Claude Code and Codex CLI.

Backed by verified config formats (see README section "Agent tool setup"):
  - Claude Code: ~/.claude/settings.json -> {"env": {"ANTHROPIC_BASE_URL": ...,
    "ANTHROPIC_AUTH_TOKEN": ..., "ANTHROPIC_MODEL": ...}}
    AIWave exposes an Anthropic-compatible endpoint at /anthropic.
  - Codex CLI: ~/.codex/config.toml -> [model_providers.aiwave] with
    base_url, wire_api="chat", env_key; plus top-level model_provider.

Safety:
  - Backs up every file it changes to <file>.aiwave.bak (never overwrites an
    existing backup)
  - --dry-run prints the exact diff and writes nothing
  - --restore puts the backups back
  - Never prints the API key

Usage:
    export AIWAVE_API_KEY="sk-..."
    python3 scripts/aiwave-setup.py --dry-run
    python3 scripts/aiwave-setup.py
    python3 scripts/aiwave-setup.py --restore
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

HOME = Path.home()
CLAUDE_SETTINGS = HOME / ".claude" / "settings.json"
CODEX_CONFIG = HOME / ".codex" / "config.toml"

# Verified against the live catalog on 2026-11-04 (/api/pricing).
# These are exact model IDs currently on the public rate card.
CLAUDE_MODEL = "claude-sonnet-5-coding-team"
CODEX_MODEL = "deepseek-v4-pro"
ANTHROPIC_BASE = "https://aiwave.live/anthropic"
OPENAI_BASE = "https://aiwave.live/v1"


def backup(path):
    bak = Path(str(path) + ".aiwave.bak")
    if path.exists() and not bak.exists():
        shutil.copy2(path, bak)
        return bak
    return bak if bak.exists() else None


def restore_one(path):
    bak = Path(str(path) + ".aiwave.bak")
    if bak.exists():
        shutil.copy2(bak, path)
        return True
    return False


def preview(label, before, after):
    print(f"\n--- {label} ---")
    if before == after:
        print("  (no change)")
        return
    for line in after.splitlines():
        if "<REDACTED>" in line or "ANTHROPIC_AUTH_TOKEN" in line or "env_key" in line:
            print("  + [contains key reference — not shown]")
        else:
            print("  + " + line[:110])


def setup_claude(key, dry):
    before = CLAUDE_SETTINGS.read_text(encoding="utf-8") if CLAUDE_SETTINGS.exists() else ""
    try:
        cfg = json.loads(before) if before.strip() else {}
    except json.JSONDecodeError:
        sys.exit(f"Cannot parse {CLAUDE_SETTINGS} — fix the JSON first, or use --dry-run.")

    env = cfg.setdefault("env", {})
    env["ANTHROPIC_BASE_URL"] = ANTHROPIC_BASE
    env["ANTHROPIC_AUTH_TOKEN"] = key
    env["ANTHROPIC_MODEL"] = CLAUDE_MODEL
    env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = CLAUDE_MODEL
    env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = "claude-opus-5-coding-team"
    env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = CLAUDE_MODEL
    after = json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"

    shown = after.replace(key, "<REDACTED>") if key else after
    preview(str(CLAUDE_SETTINGS), before, shown)
    if not dry:
        CLAUDE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        bak = backup(CLAUDE_SETTINGS)
        CLAUDE_SETTINGS.write_text(after, encoding="utf-8")
        print(f"  written (backup: {bak})" if bak else "  written")


TOML_BLOCK_TEMPLATE = '''
[model_providers.aiwave]
name = "AIWave"
base_url = "{base}"
wire_api = "chat"
env_key = "AIWAVE_API_KEY"
'''


def setup_codex(key, dry):
    before = CODEX_CONFIG.read_text(encoding="utf-8") if CODEX_CONFIG.exists() else ""
    if "[model_providers.aiwave]" in before:
        print(f"\n--- {CODEX_CONFIG} ---\n  (AIWave provider already configured; left as-is)")
        return

    block = TOML_BLOCK_TEMPLATE.format(base=OPENAI_BASE)
    # Top-level keys must come before any [section]; insert the selection
    # right after the leading scalar block.
    lines = before.splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("["):
            insert_at = i
            break
        insert_at = i + 1

    if "model_provider =" not in before:
        lines.insert(insert_at, 'model_provider = "aiwave"')
        insert_at += 1
    # Switching provider must also switch the model: an old model ID
    # (e.g. gpt-5.6-sol) would 404 against the AIWave catalog.
    replaced = False
    for i in range(insert_at):
        if lines[i].strip().startswith("model ="):
            lines[i] = f'model = "{CODEX_MODEL}"'
            replaced = True
            break
    if not replaced:
        lines.insert(insert_at, f'model = "{CODEX_MODEL}"')

    after = "\n".join(lines).rstrip() + "\n" + block
    preview(str(CODEX_CONFIG), before, after)
    if not dry:
        CODEX_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        bak = backup(CODEX_CONFIG)
        CODEX_CONFIG.write_text(after, encoding="utf-8")
        print(f"  written (backup: {bak})" if bak else "  written")


def main():
    ap = argparse.ArgumentParser(description="Configure Claude Code / Codex to use AIWave")
    ap.add_argument("--tool", choices=["claude", "codex", "both"], default="both")
    ap.add_argument("--dry-run", action="store_true", help="show changes, write nothing")
    ap.add_argument("--restore", action="store_true", help="restore from .aiwave.bak files")
    args = ap.parse_args()

    targets = ([CLAUDE_SETTINGS, CODEX_CONFIG] if args.tool == "both"
               else [CLAUDE_SETTINGS] if args.tool == "claude" else [CODEX_CONFIG])

    if args.restore:
        for p in targets:
            print(f"  restored {p}" if restore_one(p) else f"  no backup for {p}")
        return

    key = os.environ.get("AIWAVE_API_KEY", "")
    if not key:
        sys.exit("Set AIWAVE_API_KEY first (https://aiwave.live/register). "
                 "Use --dry-run with a placeholder if you only want to preview.")

    print(f"AIWave provider setup — tool={args.tool} "
          f"{'(DRY RUN, nothing written)' if args.dry_run else ''}")
    print(f"  Claude endpoint: {ANTHROPIC_BASE}  model: {CLAUDE_MODEL}")
    print(f"  Codex  endpoint: {OPENAI_BASE}  model: {CODEX_MODEL}")
    if args.tool in ("claude", "both"):
        setup_claude(key, args.dry_run)
    if args.tool in ("codex", "both"):
        setup_codex(key, args.dry_run)
    if not args.dry_run:
        print("\nBackups saved as *.aiwave.bak. To undo: --restore")
        print("Verify with: claude --version / codex --version, then one real request.")


if __name__ == "__main__":
    main()
