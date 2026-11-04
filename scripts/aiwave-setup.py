#!/usr/bin/env python3
"""Add AIWave as a provider for Claude Code and Codex CLI.

Backed by verified config formats (see README section "Agent tool setup"):
  - Claude Code: ~/.claude/settings.json -> {"env": {"ANTHROPIC_BASE_URL": ...,
    "ANTHROPIC_AUTH_TOKEN": ..., "ANTHROPIC_MODEL": ...}}
    AIWave exposes an Anthropic-compatible endpoint at /anthropic.
  - Codex CLI: ~/.codex/config.toml -> [model_providers.aiwave] with
    base_url, wire_api="chat", env_key; plus top-level model_provider.

Safety:
  - Keeps a private, immutable backup of the pre-AIWave configuration
  - --dry-run lists changed fields without printing existing config values
  - --restore refuses to overwrite edits made after setup
  - Never prints configuration secrets

Usage:
    export AIWAVE_API_KEY="sk-..."
    python3 scripts/aiwave-setup.py --dry-run
    python3 scripts/aiwave-setup.py
    python3 scripts/aiwave-setup.py --restore
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import uuid
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


def digest(data):
    return hashlib.sha256(data).hexdigest()


def state_path(path):
    return Path(str(path) + ".aiwave.state.json")


def ensure_safe_target(path):
    """Refuse dotfile symlinks and untracked changes before any setup write."""
    state = state_path(path)
    if path.is_symlink() or state.is_symlink():
        sys.exit(f"{path} uses a symlink; manage it directly instead. No file changed.")
    if state.exists():
        try:
            record = json.loads(state.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            sys.exit(f"Cannot verify prior AIWave state for {path}; no file changed.")
        if not path.exists() or digest(path.read_bytes()) != record.get("applied_sha256"):
            sys.exit(f"{path} changed since AIWave setup; no file changed. Review it before rerunning.")


def atomic_write(path, data):
    """Replace one config atomically, using private permissions for the new file."""
    fd, temp_name = tempfile.mkstemp(prefix=".aiwave-", dir=str(path.parent))
    try:
        try:
            os.chmod(temp_name, 0o600)
        except OSError:
            pass  # Windows applies the user's ACL to the new file.
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp_name, str(path))
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def backup(path):
    if not path.exists():
        return None
    bak = Path(str(path) + ".aiwave.bak." + uuid.uuid4().hex)
    atomic_write(bak, path.read_bytes())
    return bak


def write_config(path, after):
    """Write atomically while retaining the original pre-AIWave backup."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_safe_target(path)
    current = path.read_bytes() if path.exists() else None
    state = state_path(path)
    if state.exists():
        old_state = json.loads(state.read_text(encoding="utf-8"))
        original_exists = old_state.get("original_exists")
        bak = Path(old_state["backup"]) if old_state.get("backup") else None
        backup_hash = old_state.get("backup_sha256")
        if original_exists and (bak is None or not str(bak).startswith(str(path) + ".aiwave.bak.")
                                or not bak.is_file() or digest(bak.read_bytes()) != backup_hash):
            sys.exit(f"Original AIWave backup for {path} cannot be verified; no file changed.")
    new_data = after.encode("utf-8")
    if current == new_data:
        print("  unchanged")
        return
    if not state.exists():
        original_exists = current is not None
        bak = backup(path)
        backup_hash = digest(bak.read_bytes()) if bak else None
    record = {
        "version": 1,
        "applied_sha256": digest(new_data),
        "original_exists": original_exists,
        "backup": str(bak) if bak else None,
        "backup_sha256": backup_hash,
    }
    try:
        atomic_write(path, new_data)
        atomic_write(state, (json.dumps(record, sort_keys=True) + "\n").encode("utf-8"))
    except OSError:
        # Keep the previous config if writing either file fails.
        if current is None:
            path.unlink(missing_ok=True)
        else:
            atomic_write(path, current)
        raise
    print(f"  written (backup: {bak})" if bak else "  written (new file)")


def restore_one(path):
    state = state_path(path)
    if path.is_symlink() or state.is_symlink():
        print(f"  symlinked config/state for {path}; refusing automatic restore")
        return False
    if not state.exists():
        print(f"  no verified AIWave restore state for {path}; any older backup needs manual review")
        return False
    try:
        record = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(f"  invalid restore state for {path}; no file changed")
        return False
    if not path.exists() or digest(path.read_bytes()) != record.get("applied_sha256"):
        print(f"  {path} changed after setup; refusing to overwrite later edits")
        return False
    if record.get("original_exists"):
        bak = Path(record.get("backup") or "")
        if not str(bak).startswith(str(path) + ".aiwave.bak.") or not bak.is_file():
            print(f"  verified backup missing for {path}; no file changed")
            return False
        saved = bak.read_bytes()
        if digest(saved) != record.get("backup_sha256"):
            print(f"  backup content changed for {path}; no file changed")
            return False
        atomic_write(path, saved)
    else:
        path.unlink()
    state.unlink()
    return True


def preview(label, before, after, fields):
    print(f"\n--- {label} ---")
    if before == after:
        print("  (no change)")
        return
    print("  fields to update: " + ", ".join(fields))
    print("  configuration values hidden; inspect the file locally after applying")


def setup_claude(key, dry):
    ensure_safe_target(CLAUDE_SETTINGS)
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

    preview(str(CLAUDE_SETTINGS), before, after,
            ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL",
             "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL",
             "ANTHROPIC_DEFAULT_HAIKU_MODEL"))
    if not dry:
        write_config(CLAUDE_SETTINGS, after)


TOML_BLOCK_TEMPLATE = '''
[model_providers.aiwave]
name = "AIWave"
base_url = "{base}"
wire_api = "chat"
env_key = "AIWAVE_API_KEY"
'''


def setup_codex(key, dry):
    ensure_safe_target(CODEX_CONFIG)
    before = CODEX_CONFIG.read_text(encoding="utf-8") if CODEX_CONFIG.exists() else ""
    existing = re.search(r"(?ms)^\[model_providers\.aiwave\]\s*\n(.*?)(?=^\[|\Z)", before)
    if existing:
        def field(name):
            return re.findall(r'(?m)^[ \t]*' + re.escape(name)
                              + r'[ \t]*=[ \t]*"([^"]*)"[ \t]*(?:#.*)?$',
                              existing.group(1))

        if (field("base_url") != [OPENAI_BASE]
                or field("wire_api") != ["chat"]
                or field("env_key") != ["AIWAVE_API_KEY"]):
            sys.exit(f"Existing AIWave provider differs in {CODEX_CONFIG}; no file changed.")
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

    provider_lines = [i for i in range(insert_at)
                      if re.match(r"\s*model_provider\s*=", lines[i])]
    model_lines = [i for i in range(insert_at)
                   if re.match(r"\s*model\s*=", lines[i])]
    if len(provider_lines) > 1 or len(model_lines) > 1:
        sys.exit(f"Duplicate top-level model settings in {CODEX_CONFIG}; no file changed.")
    if provider_lines:
        lines[provider_lines[0]] = 'model_provider = "aiwave"'
    else:
        lines.insert(insert_at, 'model_provider = "aiwave"')
        insert_at += 1
    # Switching provider must also switch the model: an old model ID
    # (e.g. gpt-5.6-sol) would 404 against the AIWave catalog.
    model_lines = [i for i in range(insert_at)
                   if re.match(r"\s*model\s*=", lines[i])]
    if model_lines:
        lines[model_lines[0]] = f'model = "{CODEX_MODEL}"'
    else:
        lines.insert(insert_at, f'model = "{CODEX_MODEL}"')

    after = "\n".join(lines).rstrip() + ("\n" if existing else "\n" + block)
    preview(str(CODEX_CONFIG), before, after,
            ("model_provider", "model", "model_providers.aiwave"))
    if not dry:
        write_config(CODEX_CONFIG, after)


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
    if args.tool == "both" and not args.dry_run:
        # Validate both formats and restore state before either config is changed.
        setup_claude(key, True)
        setup_codex(key, True)
    if args.tool in ("claude", "both"):
        setup_claude(key, args.dry_run)
    if args.tool in ("codex", "both"):
        setup_codex(key, args.dry_run)
    if not args.dry_run:
        print("\nPrivate backups saved as *.aiwave.bak.*. To undo an unchanged setup: --restore")
        print("Verify with: claude --version / codex --version, then one real request.")


if __name__ == "__main__":
    main()
