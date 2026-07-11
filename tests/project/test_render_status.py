import json
from pathlib import Path

import pytest

from tools.project.render_status import render_status, render_to_path


def sample_state():
    return {
        "state_revision": 249,
        "project_name": "强化学习",
        "active_research_line": "PyBullet 圆周跟踪 / PID-based Residual TD3",
        "current_task": "Task6_v2_1_Gate3_NO_GO",
        "scientific_gate": {"stage": "Gate 3 v2.1", "decision": "NO-GO"},
        "blocked_reason": "Direct TD3 collapsed after updates.",
        "next_action": {
            "action_type": "await_user_authorization_after_gate_3_no_go",
            "command": "Do not launch Stage A.",
        },
        "status_evidence": ["evidence/gate_3_summary.json"],
        "updated_at": "2026-07-11T20:13:41+08:00",
    }


def test_render_status_uses_execution_state():
    text = render_status(sample_state())
    assert text.startswith("<!-- AUTO-GENERATED")
    assert "强化学习" in text
    assert "Gate 3 v2.1" in text
    assert "NO-GO" in text
    assert "Do not launch Stage A." in text
    assert "evidence/gate_3_summary.json" in text


def test_render_status_rejects_missing_required_fields():
    state = sample_state()
    del state["next_action"]
    with pytest.raises(ValueError, match="next_action"):
        render_status(state)


def test_render_to_path_check_mode(tmp_path: Path):
    state_path = tmp_path / "state.json"
    output_path = tmp_path / "STATUS.md"
    state_path.write_text(json.dumps(sample_state(), ensure_ascii=False), encoding="utf-8")
    render_to_path(state_path, output_path, check=False)
    render_to_path(state_path, output_path, check=True)
    output_path.write_text("stale", encoding="utf-8")
    with pytest.raises(RuntimeError, match="out of date"):
        render_to_path(state_path, output_path, check=True)
