#!/usr/bin/env python3
"""Safely add a customer's own AIWave models to local WorkBuddy on Windows.

No dependencies, no remote code execution, no API key in arguments or output.
The public catalog is an eligibility filter, not proof of runtime capability.
"""

import argparse
import csv
import getpass
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urlparse
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


CATALOG_URL = "https://aiwave.live/api/pricing"
CHAT_URL = "https://aiwave.live/v1/chat/completions"
DEFAULT_MODELS = ("deepseek-v4.1-flash", "deepseek-v4-pro")
NON_CHAT_MARKERS = ("embedding", "image", "audio", "video", "content-safety", "rerank")
KNOWN_NO_ROUTE = {"glm-5-turbo"}  # 2026-11-06 abilities audit; revisit when a route is verified.
MAX_CONFIG_BYTES = 2 * 1024 * 1024
MAX_CATALOG_BYTES = 4 * 1024 * 1024
STATE_FILE = ".aiwave-connect-state.json"


class ConnectError(Exception):
    """An expected, safe-to-display refusal."""


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def entry_digest(entry):
    return digest(json.dumps(entry, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8"))


def fetch_catalog():
    req = urllib.request.Request(CATALOG_URL, headers={"User-Agent": "aiwave-workbuddy-connect/1"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.geturl() != CATALOG_URL:
                raise ConnectError("Catalog redirected; refusing to use it.")
            raw = response.read(MAX_CATALOG_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise ConnectError("Cannot fetch live pricing catalog; no changes made.") from exc
    if len(raw) > MAX_CATALOG_BYTES:
        raise ConnectError("Catalog is unexpectedly large; no changes made.")
    try:
        data = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise ConnectError("Catalog is not valid JSON; no changes made.") from exc
    if not isinstance(data, dict) or data.get("success") is not True or not isinstance(data.get("data"), list):
        raise ConnectError("Unexpected live catalog format; no changes made.")
    return data


def eligible_rows(catalog):
    rows = catalog.get("data")
    if not isinstance(rows, list):
        raise ConnectError("Missing catalog rows.")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("model_name")
        if (isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,159}", name)
                and isinstance(row.get("enable_groups"), list)
                and isinstance(row.get("supported_endpoint_types"), list)
                and "default" in row["enable_groups"]
                and "openai" in row["supported_endpoint_types"]
                and not any(marker in name.lower() for marker in NON_CHAT_MARKERS)
                and name not in KNOWN_NO_ROUTE):
            if name in result:
                raise ConnectError("Duplicate model ID in live catalog; no changes made.")
            result[name] = row
    return result


def eligible_model_ids(catalog):
    return sorted(eligible_rows(catalog))


def select_model_ids(catalog, requested=None, all_eligible=False):
    eligible = eligible_rows(catalog)
    if all_eligible:
        raise ConnectError("Bulk importing an unverified catalog is unsafe; choose exact model IDs.")
    if requested:
        selected = list(dict.fromkeys(requested))
    else:
        selected = list(DEFAULT_MODELS)
    missing = [name for name in selected if name not in eligible]
    if not selected or missing:
        raise ConnectError("Model selection is empty or not eligible for default + OpenAI Chat Completions: "
                           + ", ".join(missing))
    return selected


def default_group_ratio(catalog):
    ratios = catalog.get("group_ratio")
    return ratios.get("default") if isinstance(ratios, dict) else None


def rate_text(row, group_ratio):
    """A dated estimate from live multiplier fields; never a billing guarantee."""
    try:
        if row.get("quota_type") != 0:
            return "see live pricing (non-token billing)"
        ratio = Decimal(str(row["model_ratio"]))
        completion = Decimal(str(row["completion_ratio"]))
        group = Decimal(str(group_ratio))
        if not all(x.is_finite() and x >= 0 for x in (ratio, completion, group)):
            raise InvalidOperation
        return "input $%s / output $%s per 1M (estimated)" % (
            format(ratio * group * 2, "f"), format(ratio * completion * group * 2, "f"))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return "see live pricing (unverified unit)"


def model_entry(model_id, key):
    return {"id": model_id, "name": "AIWave · " + model_id,
            "vendor": "Custom", "url": CHAT_URL, "apiKey": key,
            "supportsToolCall": False, "supportsImages": False,
            "supportsReasoning": False, "useCustomProtocol": False}


def is_existing_aiwave(entry):
    """Recognize a manual AIWave entry without adopting or changing its key."""
    url = entry.get("url")
    if not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        return (parsed.scheme == "https" and parsed.hostname == "aiwave.live"
                and parsed.port is None and parsed.path in ("/v1", "/v1/chat/completions")
                and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment)
    except ValueError:
        return False


def _private(path):
    if os.name != "nt":
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        return
    user = subprocess.run(["whoami"], capture_output=True, text=True, check=True).stdout.strip()
    if not user:
        raise ConnectError("Cannot determine Windows account for private file permissions.")
    # Remove inherited grants, then grant the interactive account. Windows
    # may retain built-in privileged principals such as SYSTEM/Administrators.
    result = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", user + ":(F)"],
                            capture_output=True, text=True)
    if result.returncode:
        raise ConnectError("Cannot secure local file permissions; no config replacement made.")


def _write_private(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".aiwave-connect-", dir=str(path.parent))
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            _private(temp)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _read_regular(path, max_size=MAX_CONFIG_BYTES):
    if path.is_symlink():
        raise ConnectError("Configuration is a symlink; refusing automatic changes.")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > max_size:
        raise ConnectError("Configuration is not a regular small file.")
    return path.read_bytes()


def _parse_config(raw):
    if raw is None:
        return []
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise ConnectError("Existing WorkBuddy JSON cannot be parsed; no changes made.") from exc
    if not isinstance(data, list) or any(not isinstance(x, dict) or not isinstance(x.get("id"), str)
                                         for x in data):
        raise ConnectError("Unknown WorkBuddy configuration schema; no changes made.")
    ids = [x["id"] for x in data]
    if len(ids) != len(set(ids)):
        raise ConnectError("Duplicate IDs in existing WorkBuddy configuration; no changes made.")
    return data


def _json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


class ConfigStore:
    def __init__(self, path):
        self.path = Path(path)
        self.state_path = self.path.parent / STATE_FILE

    def read(self):
        raw = _read_regular(self.path)
        return raw, _parse_config(raw)

    def _state(self):
        raw = _read_regular(self.state_path)
        if raw is None:
            return None
        try:
            state = json.loads(raw)
        except (UnicodeError, ValueError) as exc:
            raise ConnectError("Installer state is damaged; refusing automatic changes.") from exc
        if (not isinstance(state, dict) or state.get("version") != 1
                or state.get("config") != str(self.path.resolve())
                or not isinstance(state.get("owned"), dict)):
            raise ConnectError("Installer state is unknown; refusing automatic changes.")
        return state

    def plan(self, model_ids):
        _, entries = self.read()
        state = self._state()
        by_id = {x["id"]: x for x in entries}
        owned = state["owned"] if state else {}
        conflicts = [name for name in model_ids if name in by_id and name not in owned
                     and not is_existing_aiwave(by_id[name])]
        if conflicts:
            raise ConnectError("Model ID already exists in WorkBuddy; no overwrite: " + ", ".join(conflicts))
        return {"existing": len(entries), "add": [x for x in model_ids if x not in by_id],
                "keep_manual": [x for x in model_ids if x in by_id and x not in owned]}

    def install(self, model_ids, key):
        if not key or key != key.strip() or any(c in key for c in "\r\n\0"):
            raise ConnectError("Invalid key input; no changes made.")
        if len(key) > 4096:
            raise ConnectError("Key is unexpectedly long; no changes made.")
        before, entries = self.read()
        state = self._state()
        original = {x["id"]: x for x in entries}
        owned = dict(state["owned"]) if state else {}
        for name, fingerprint in owned.items():
            if name not in original or entry_digest(original[name]) != fingerprint:
                raise ConnectError("A previously installed AIWave entry changed; review it manually first.")
        collisions = [name for name in model_ids if name in original and name not in owned
                      and not is_existing_aiwave(original[name])]
        if collisions:
            raise ConnectError("Model ID already exists in WorkBuddy; no overwrite: " + ", ".join(collisions))
        for name in model_ids:
            if name in owned and original[name].get("apiKey") != key:
                raise ConnectError("Existing AIWave entry uses another key; rotate it in WorkBuddy UI.")
        additions = [model_entry(name, key) for name in model_ids if name not in original]
        if not additions:
            return {"added": 0, "backup": None}
        if _read_regular(self.path) != before:
            raise ConnectError("WorkBuddy configuration changed during install; no changes made.")
        # Keep a private, immutable copy of the exact pre-write bytes.
        backup = None
        if before is not None:
            backup = self.path.with_name("models.json.aiwave-backup-" + uuid.uuid4().hex)
            _write_private(backup, before)
        for entry in additions:
            owned[entry["id"]] = entry_digest(entry)
        new_state = {"version": 1, "config": str(self.path.resolve()),
                     "owned": owned, "last_backup": str(backup) if backup else None,
                     "updated_utc": utc_now()}
        # State first: a crash between writes is detectable and never silently adopts entries.
        previous_state = _read_regular(self.state_path)
        written_state = _json_bytes(new_state)
        _write_private(self.state_path, written_state)
        try:
            if _read_regular(self.path) != before:
                raise ConnectError("WorkBuddy configuration changed during install; review backup before retrying.")
            _write_private(self.path, _json_bytes(entries + additions))
        except (ConnectError, OSError):
            # On a normal write failure, restore the old state only if neither
            # config nor state has changed since our write. A crash still leaves
            # the new state in place so a later run fails closed.
            if _read_regular(self.path) == before and _read_regular(self.state_path) == written_state:
                if previous_state is None:
                    self.state_path.unlink()
                else:
                    _write_private(self.state_path, previous_state)
            raise
        return {"added": len(additions), "backup": str(backup) if backup else None}

    def verify(self):
        _, entries = self.read()
        state = self._state()
        if not state:
            raise ConnectError("No AIWave Connect installation state found.")
        by_id = {x["id"]: x for x in entries}
        changed = [name for name, fingerprint in state["owned"].items()
                   if name not in by_id or entry_digest(by_id[name]) != fingerprint]
        if changed:
            raise ConnectError("Installed entries were changed or removed: " + ", ".join(changed))
        return len(state["owned"])

    def undo(self):
        before, entries = self.read()
        state = self._state()
        if not state:
            raise ConnectError("No AIWave Connect installation state found.")
        self.verify()
        owned = set(state["owned"])
        remaining = [entry for entry in entries if entry["id"] not in owned]
        if _read_regular(self.path) != before:
            raise ConnectError("WorkBuddy configuration changed during undo; no changes made.")
        # Keep the most recent pre-undo version as a separate private recovery copy.
        recovery = self.path.with_name("models.json.aiwave-backup-" + uuid.uuid4().hex)
        if before is not None:
            _write_private(recovery, before)
        _write_private(self.path, _json_bytes(remaining))
        self.state_path.unlink()
        return {"removed": len(owned), "backup": str(recovery)}


def workbuddy_running():
    if os.name != "nt":
        return False
    try:
        proc = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                              text=True, timeout=10, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConnectError("Cannot check whether WorkBuddy is running; close it and retry.") from exc
    return any("workbuddy" in row[0].lower() for row in csv.reader(io.StringIO(proc.stdout)) if row)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Add your own AIWave Key to WorkBuddy safely")
    parser.add_argument("action", choices=("doctor", "list", "plan", "install", "verify", "undo"))
    parser.add_argument("--models", help="comma-separated exact model IDs; default is a small starter set")
    parser.add_argument("--yes", action="store_true", help="accept config change after preview (key is still prompted)")
    parser.add_argument("--config", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.config is None and os.name != "nt":
        parser.error("Automatic installation currently supports Windows WorkBuddy only.")
    path = args.config or Path.home() / ".workbuddy-ai" / "models.json"
    store = ConfigStore(path)
    try:
        if args.action == "doctor":
            _, entries = store.read()
            state = store._state()
            print("WorkBuddy config:", path)
            print("Existing entries:", len(entries), "| AIWave Connect state:", "yes" if state else "no")
            print("WorkBuddy running:", "yes" if workbuddy_running() else "no")
            return 0
        if args.action == "verify":
            print("Local entries verified:", store.verify())
            print("Next: open WorkBuddy > Settings > Models; test connection and then your own task.")
            print("The connection check and real tasks may incur model usage charges.")
            return 0
        if args.action == "undo":
            if workbuddy_running():
                raise ConnectError("Close WorkBuddy before changing its configuration.")
            result = store.undo()
            print("Removed AIWave Connect entries:", result["removed"])
            print("Private recovery backup:", result["backup"])
            return 0
        catalog = fetch_catalog()
        if args.action == "list":
            rows = eligible_rows(catalog)
            print("Fetched:", utc_now(), "| pricing version:", catalog.get("pricing_version", "unknown"))
            print("Eligible for default + OpenAI endpoint (not runtime-tested):", len(rows))
            for name in sorted(rows):
                print(name, "|", rate_text(rows[name], default_group_ratio(catalog)))
            return 0
        requested = [x.strip() for x in args.models.split(",")] if args.models else None
        ids = select_model_ids(catalog, requested)
        plan = store.plan(ids)
        print("Source:", CATALOG_URL, "| fetched:", utc_now())
        print("Pricing version:", catalog.get("pricing_version", "unknown"))
        print("Existing entries:", plan["existing"], "| to add:", len(plan["add"]))
        print("Existing manual AIWave entries kept unchanged:", len(plan["keep_manual"]))
        for name in ids:
            print(" +", name, "|", rate_text(eligible_rows(catalog)[name],
                                            default_group_ratio(catalog)))
        print("Capabilities are NOT inferred; tool, image and reasoning flags remain off.")
        print("Context limit and reasoning level: unverified; not configured.")
        print("Key is stored locally by WorkBuddy. No key is uploaded to this script or printed.")
        if args.action == "plan":
            return 0
        if not plan["add"]:
            print("Nothing to add; existing configuration remains unchanged.")
            return 0
        if workbuddy_running():
            raise ConnectError("Close WorkBuddy before changing its configuration.")
        if not args.yes and input("Type INSTALL to continue: ").strip() != "INSTALL":
            print("Cancelled; no changes made.")
            return 1
        key = getpass.getpass("Your own AIWave API Key (hidden): ")
        if workbuddy_running():
            raise ConnectError("WorkBuddy started during install; no changes made.")
        result = store.install(ids, key)
        print("Added:", result["added"], "| private backup:", result["backup"] or "none")
        print("Open WorkBuddy > Settings > Models; select and test an AIWave model.")
        print("A connection test or task may incur usage charges. See https://aiwave.live/pricing")
        return 0
    except ConnectError as exc:
        print("Refused:", exc, file=sys.stderr)
        return 2
    except OSError:
        print("Refused: local file operation failed; no further changes attempted."
              " Check the private backup and installer state before retrying.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
