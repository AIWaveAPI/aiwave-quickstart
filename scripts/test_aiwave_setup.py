"""Full write-path verification in a temp HOME — never touches real configs."""
import importlib.util, os, tempfile, json, sys
from pathlib import Path

import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("setup", _os.path.join(HERE, "aiwave-setup.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / ".claude").mkdir(); (root / ".codex").mkdir()
    cs = root / ".claude" / "settings.json"
    cc = root / ".codex" / "config.toml"
    cs.write_text('{"skipWorkflowUsageWarning": true}\n')
    cc.write_text('model = "gpt-5.6-sol"\nmodel_reasoning_effort = "high"\n\n[features]\nfoo = true\n')
    m.CLAUDE_SETTINGS, m.CODEX_CONFIG = cs, cc

    # --- dry-run must not change anything ---
    b1, b2 = cs.read_text(), cc.read_text()
    os.environ["AIWAVE_API_KEY"] = "sk-test-fake"
    sys.argv = ["x", "--dry-run"]
    print("=== --dry-run (nothing written) ===")
    # capture main's work without argparse exit
    m.setup_claude("sk-test-fake", True); m.setup_codex("sk-test-fake", True)
    assert cs.read_text() == b1 and cc.read_text() == b2, "dry-run WROTE files!"
    print("  PASS: dry-run left both files byte-identical")

    # --- real write ---
    print("=== real write into temp HOME ===")
    m.setup_claude("sk-test-fake", False); m.setup_codex("sk-test-fake", False)
    cfg = json.loads(cs.read_text())
    assert cfg["env"]["ANTHROPIC_BASE_URL"] == "https://aiwave.live/anthropic"
    assert cfg["env"]["ANTHROPIC_MODEL"] == "claude-sonnet-5-coding-team"
    assert cfg["skipWorkflowUsageWarning"] is True, "existing settings lost!"
    print("  PASS: Claude JSON valid, env injected, existing keys preserved")

    toml = cc.read_text()
    try:
        import tomllib
        parsed = tomllib.loads(toml)
        print("  PASS: Codex TOML parses;", "provider =", parsed.get("model_provider"),
              "| base_url =", parsed["model_providers"]["aiwave"]["base_url"])
        assert parsed.get("model") == "deepseek-v4-pro", "old model ID was not replaced!"
        print("  PASS: pre-existing model ID replaced with an in-catalog one")
    except Exception as e:
        print("  FAIL TOML:", e); raise
    assert (root / ".claude" / "settings.json.aiwave.bak").exists()
    assert (root / ".codex" / "config.toml.aiwave.bak").exists()
    print("  PASS: backups created for both")

    # --- restore ---
    print("=== --restore ===")
    assert m.restore_one(cs) and m.restore_one(cc)
    assert cs.read_text() == b1 and cc.read_text() == b2
    print("  PASS: restored byte-identical to original")
