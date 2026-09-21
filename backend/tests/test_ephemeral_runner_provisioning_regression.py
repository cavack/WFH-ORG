from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROVISIONER = ROOT / "deploy" / "self-hosted" / "provision-ephemeral-runner.sh"


def test_runner_config_runs_from_runner_directory() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")
    assert '(\n  cd "$RUNNER_DIR"\n  runuser -u "$RUNNER_USER" -- ./config.sh \\' in text


def test_runner_online_gate_accepts_active_ephemeral_runner() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")
    polling = text.split("online=0", maxsplit=1)[1].split("systemd-run", maxsplit=1)[0]
    assert 'runner_status="${state%%$\'\\t\'*}"' in polling
    assert 'if [[ "$runner_status" == "online" ]]; then' in polling
    assert "online\\tfalse" not in polling
