# 《强化学习》仓库布局迁移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将唯一正式 worktree 整理成《强化学习》项目仓库，使 MATLAB/Simulink 与 PyBullet 两条研究线并列、PyBullet 当前阶段与历史协议分离、根目录入口清楚，并完整退役悬停复现和定点控制研究。

**Architecture:** GitHub 根目录直接对应当前正式 worktree，不再镜像本地父工作区。MATLAB/Simulink 使用 `experiments/circular_tracking/matlab_simulink/`，PyBullet 使用 `experiments/circular_tracking/pybullet_td3/`；阶段目录只保存配置、清单、证据和本地 runs，共享实现只保留一份。历史证据按协议逐字归档，运行时 PID 契约通过哈希引用原冻结证据，不改写原证据身份。

**Tech Stack:** Git/GitHub、PowerShell、Python 3.11、pytest、PyBullet、Stable-Baselines3 TD3、MATLAB/Simulink、JSON/CSV、GitHub Actions。

---

## 执行约束

- 不启动任何强化学习训练、PID 网格调优或长时间仿真。
- 不修改奖励、动作语义、扰动协议、训练阈值或历史数值。
- 不删除外部 MATLAB 原始工程、其他 worktree、备份或圆周跟踪大文件。
- 不对归档 JSON、旧命令、旧绝对路径和旧 Git SHA 做全局替换。
- 迁移期间只做一次基线全量测试、各任务的聚焦验证和一次最终全量测试，避免反复审查循环。
- 任何目录移动前检查解析后的绝对路径仍位于当前 worktree 或明确的源目录。
- Replay Buffer 的硬基线是 8 个文件、总计 `16,864,079,016` 字节；任一不符立即停止。
- 原冻结 PID 文件 raw SHA-256 必须始终为 `c7530d2725d4c55b31252f89c1ed126ae140a35789b3c653b86e955165e48ef3`。
- 不把中间不可运行状态推送到 GitHub；本地检查点提交必须在各自边界内可验证，发布前保留检查点备份分支并折叠成一个公开布局迁移提交。

## 文件结构锁定

### 新建

```text
STATUS.md
ROADMAP.md
.gitattributes

docs/project/repository_structure.md
docs/project/public_snapshot_policy.md
docs/project/research_history.md
docs/project/decisions/README.md
docs/project/migration/pre_migration_inventory.md

docs/projects/pybullet_td3/research_plan.md
docs/projects/pybullet_td3/implementation_plan.md
docs/projects/pybullet_td3/parallel_runbook.md
docs/projects/pybullet_td3/protocol_history.md

tools/project/__init__.py
tools/project/render_status.py
tests/project/test_render_status.py
tests/project/test_repository_layout.py

experiments/circular_tracking/matlab_simulink/**
experiments/circular_tracking/pybullet_td3/**
tests/circular_tracking/pybullet_td3/**
```

### 根目录迁出

```text
PROJECT_STRUCTURE.md
PROJECT_LAYOUT.json
RL_PAPER_EXECUTION_PLAN.md
```

The active plan and runbook sources remain at their old paths until Task 10 updates `.research/execution_state.json` in the same commit that deletes those old copies. This prevents an intermediate checkpoint from containing a broken machine-state path.

### 完整退役

```text
experiments/hover_rl_reproduction/
experiments/hover_fixed_point/
gym_pybullet_drones/examples/learn.py
gym_pybullet_drones/examples/play.py
gym_pybullet_drones/examples/mrac.py
reproducibility/docker/Dockerfile.repro
tools/visualization/live_progress_viewer.py
tools/visualization/render_policy_scene.py
docs/guides/PPO悬停复现说明_零基础.md
docs/report_generators/create_visit_docx.py
docs/report_generators/create_training_workflow_materials.py
docs/report_generators/create_compact_training_ppt.py
docs/reports/visit_overview/强化学习控制项目参观说明.md
gym_pybullet_drones/assets/rl.gif
gym_pybullet_drones/assets/marl.gif
```

## Task 1: 建立迁移安全锚点和只读资产清单

**Files:**
- Create: `docs/project/migration/pre_migration_inventory.md`
- Inspect: `.research/execution_state.json`
- Inspect: `experiments/circular_tracking/config/hidden_pid_frozen.json`
- Inspect: `experiments/circular_tracking/results/hidden_disturbance_td3_paper/`

- [ ] **Step 1: 确认工作区干净且没有活跃训练**

Run:

```powershell
git status --short --branch
$state = Get-Content -Raw .research/execution_state.json | ConvertFrom-Json
if (@($state.active_runs).Count -ne 0) { throw '存在 active_runs，禁止布局迁移' }
$running = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match 'train_hidden_td3|evaluate_hidden_td3|tune_hidden_pid'
}
if ($running) { $running | Select-Object ProcessId, CommandLine; throw '存在相关训练或评估进程' }
git rev-parse HEAD
git ls-remote td3 refs/heads/main
```

Expected:

- `git status` 无改动；
- `active_runs` 为空；
- 无相关进程；
- 本地 HEAD 是设计提交或其后继；
- 记录远端 `main` SHA，当前已知值为 `678afb90353171a360ee47d296adf29581aaa5e4`。

- [ ] **Step 2: 创建不可变迁移标签**

```powershell
git tag -a layout-pre-migration-20260712 -m "Pre-layout migration anchor"
git show-ref --verify refs/tags/layout-pre-migration-20260712
```

Expected: 标签指向迁移开始前 HEAD。

- [ ] **Step 3: 在旧布局锚点验证冻结 PID 证据一次**

Use `superpowers:using-git-worktrees` before creating the temporary detached worktree.

```powershell
$anchor = '519f74c8d02f9ab6bddaff87b47ae5dfed32a950'
$temp = 'E:\1-AI辅助工作\科研项目\强化学习\wt-gpd\pid-evidence-anchor'
$resolvedParent = [IO.Path]::GetFullPath((Split-Path -Parent $temp))
$expectedParent = [IO.Path]::GetFullPath('E:\1-AI辅助工作\科研项目\强化学习\wt-gpd')
if ($resolvedParent -ne $expectedParent) { throw '临时 worktree 目标越界' }
git worktree add --detach $temp $anchor
py -3.11 -c "import sys; sys.path.insert(0, r'$temp'); from experiments.circular_tracking.scripts.td3.tune_hidden_pid import load_frozen_pid_config; p=load_frozen_pid_config(r'$temp\experiments\circular_tracking\config\hidden_pid_frozen.json'); print(p['pid_payload_hash'])"
```

Expected: 输出 `624e86cf7452410e15608774d5630512bd8a7f48f5d4e8d30fd5a8dcca37b99a`。

After verification:

```powershell
$resolved = [IO.Path]::GetFullPath($temp)
if (-not $resolved.StartsWith($expectedParent + [IO.Path]::DirectorySeparatorChar)) { throw '拒绝移除越界 worktree' }
git worktree remove $temp
```

- [ ] **Step 4: 核对 Replay 和 MATLAB 基线**

```powershell
$replays = @(Get-ChildItem experiments/circular_tracking/results/hidden_disturbance_td3_paper -Recurse -File -Filter replay_buffer.pkl)
$replayBytes = ($replays | Measure-Object Length -Sum).Sum
if ($replays.Count -ne 8) { throw "Replay 数量异常：$($replays.Count)" }
if ($replayBytes -ne 16864079016) { throw "Replay 总字节异常：$replayBytes" }

$matlabSource = 'E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl'
$matlabFiles = @(Get-ChildItem -LiteralPath $matlabSource -Recurse -File -Force)
$models = @(Get-ChildItem -LiteralPath (Join-Path $matlabSource 'models') -Filter *.slx -File)
if ($matlabFiles.Count -ne 108) { throw "MATLAB 完整副本文件数异常：$($matlabFiles.Count)" }
if ($models.Count -ne 9) { throw "Simulink 模型数异常：$($models.Count)" }
```

- [ ] **Step 5: 运行唯一一次迁移前基线测试**

```powershell
py -3.11 -m pytest tests -q
```

Expected: 当前基线全部通过；记录通过数和警告数，不在后续文档任务中重复全量运行。

- [ ] **Step 6: 写入迁移清单**

Use `apply_patch` to create `docs/project/migration/pre_migration_inventory.md` with the observed HEADs, test result, Replay count/bytes, MATLAB source counts, nine model names, frozen PID raw hash and remote `main` SHA. Do not include credentials or machine-local GitHub tokens.

- [ ] **Step 7: 提交安全锚点清单**

```powershell
git add docs/project/migration/pre_migration_inventory.md
git diff --cached --check
git commit -m "docs: record repository migration baseline"
```

## Task 2: 建立状态渲染器和稳定路线图

**Files:**
- Create: `ROADMAP.md`
- Create: `tools/project/__init__.py`
- Create: `tools/project/render_status.py`
- Create: `tests/project/test_render_status.py`
- Inspect only: `.research/execution_state.json`

- [ ] **Step 1: 写状态渲染器的失败测试**

Create `tests/project/test_render_status.py`:

```python
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
```

- [ ] **Step 2: 运行测试并确认失败**

```powershell
py -3.11 -m pytest tests/project/test_render_status.py -v
```

Expected: FAIL because `tools.project.render_status` does not exist.

- [ ] **Step 3: 实现确定性状态渲染器**

Create `tools/project/__init__.py` as an empty package marker and create `tools/project/render_status.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


REQUIRED_FIELDS = (
    "state_revision",
    "project_name",
    "active_research_line",
    "current_task",
    "scientific_gate",
    "next_action",
    "updated_at",
)


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def render_status(state: Mapping[str, Any]) -> str:
    for field in REQUIRED_FIELDS:
        if field not in state:
            raise ValueError(f"missing required field: {field}")
    gate = _mapping(state["scientific_gate"], "scientific_gate")
    next_action = _mapping(state["next_action"], "next_action")
    evidence = state.get("status_evidence", [])
    if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
        raise ValueError("status_evidence must be a list of paths")
    evidence_lines = "\n".join(f"- `{item}`" for item in evidence) or "- 尚未登记"
    blocker = state.get("blocked_reason") or "无"
    return (
        "<!-- AUTO-GENERATED by tools/project/render_status.py; DO NOT EDIT. -->\n"
        "# 项目状态\n\n"
        f"- 项目：{state['project_name']}\n"
        f"- 当前研究线：{state['active_research_line']}\n"
        f"- 当前任务：`{state['current_task']}`\n"
        f"- 科学门槛：{gate.get('stage', 'N/A')} — **{gate.get('decision', 'N/A')}**\n"
        f"- 阻塞原因：{blocker}\n"
        f"- 唯一下一步：{next_action.get('command', next_action.get('action_type', 'N/A'))}\n"
        f"- 状态修订：{state['state_revision']}\n"
        f"- 更新时间：{state['updated_at']}\n\n"
        "## 证据\n\n"
        f"{evidence_lines}\n"
    )


def render_to_path(state_path: Path, output_path: Path, *, check: bool) -> None:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    expected = render_status(state)
    if check:
        actual = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
        if actual != expected:
            raise RuntimeError(f"{output_path} is out of date")
        return
    output_path.write_text(expected, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, default=Path(".research/execution_state.json"))
    parser.add_argument("--output", type=Path, default=Path("STATUS.md"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    render_to_path(args.state, args.output, check=args.check)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 验证渲染器单元测试，不改机器状态**

```powershell
py -3.11 -m pytest tests/project/test_render_status.py -v
```

Expected: all three tests PASS。此任务不得修改 `.research/execution_state.json`，也不得提前生成 `STATUS.md`；机器状态、revision、journal 和最终状态页统一在 Task 10 只迁移一次。

- [ ] **Step 5: 创建稳定 ROADMAP**

Create `ROADMAP.md` with exactly these top-level sections:

```markdown
# 强化学习项目路线图

## MATLAB/Simulink圆周抗扰

环境模型 → 多控制器比较 → Residual RL-v1 → RL-v2/MPC imitation

## PyBullet圆周跟踪

基础环境与PID → Bootstrap Preflight → Stage A 20k → Stage B 50k → 可选Stage C 100k → 最终评估

## 停止规则

任何前置阶段NO-GO时，后续阶段保持未开始；不得通过换种子、修改阈值或扩大预算绕过。
```

- [ ] **Step 6: 提交状态入口**

```powershell
git add ROADMAP.md tools/project tests/project/test_render_status.py
git diff --cached --check
git commit -m "feat: add status renderer and project roadmap"
```

## Task 3: 迁移根目录长文档并锁定文档职责

**Files:**
- Copy in this task; delete in Task 10: `PROJECT_STRUCTURE.md` → `docs/project/repository_structure.md`
- Replace: `PROJECT_LAYOUT.json` → `docs/project/public_snapshot_policy.md`
- Copy in this task; delete in Task 10: `RL_PAPER_EXECUTION_PLAN.md` → `docs/projects/pybullet_td3/research_plan.md`
- Copy in this task; delete in Task 10: `docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-paper-rebuild.md` → `docs/projects/pybullet_td3/implementation_plan.md`
- Copy in this task; delete in Task 10: `docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-parallel-runbook.md` → `docs/projects/pybullet_td3/parallel_runbook.md`
- Create: `docs/project/research_history.md`
- Create: `docs/project/decisions/README.md`
- Create: `docs/projects/pybullet_td3/protocol_history.md`

- [ ] **Step 1: 建立目标目录并复制状态仍引用的活动文档**

```powershell
New-Item -ItemType Directory -Force docs/project/decisions, docs/projects/pybullet_td3 | Out-Null
Copy-Item -LiteralPath PROJECT_STRUCTURE.md -Destination docs/project/repository_structure.md
Copy-Item -LiteralPath RL_PAPER_EXECUTION_PLAN.md -Destination docs/projects/pybullet_td3/research_plan.md
Copy-Item -LiteralPath docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-paper-rebuild.md -Destination docs/projects/pybullet_td3/implementation_plan.md
Copy-Item -LiteralPath docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-parallel-runbook.md -Destination docs/projects/pybullet_td3/parallel_runbook.md
```

Do not remove the four source files in this task. Keeping them until Task 10 preserves every active `.research/execution_state.json` path between local checkpoints.

- [ ] **Step 2: 将错误的公开快照 JSON 改写为政策文档**

Use `apply_patch` to create `docs/project/public_snapshot_policy.md` with sections:

```markdown
# 公开仓库与本地产物政策

## 仓库根目录
GitHub根目录与唯一正式worktree一一对应。

## Git跟踪
源码、配置、小型证据、README、模型身份清单和九个Simulink源模型。

## 本地保留
Replay、checkpoint、原始MAT、日志、视频、缓存和临时worktree。

## 文件上限
单个Git blob不得超过50 MiB；禁止伪造占位模型。
```

Then remove the obsolete JSON:

```powershell
git rm PROJECT_LAYOUT.json
```

- [ ] **Step 3: 拆出研究历史和协议历史**

Use `apply_patch` to create:

- `docs/project/research_history.md`: move the terminal reward bug, half-circle training, oracle leakage, PID-FF imitation, test leakage and statistical lessons from the old handoff/plan without changing historical claims.
- `docs/projects/pybullet_td3/protocol_history.md`: list v1.0.2, v2.0.0 and v2.1.0, their result namespaces and final decisions.
- `docs/project/decisions/README.md`: explain that future durable method-changing decisions receive dated Markdown records here.

- [ ] **Step 4: 更新已移动文档内部相对链接**

Run first:

```powershell
rg -n "RL_PAPER_EXECUTION_PLAN|PROJECT_STRUCTURE|2026-07-10-hidden-disturbance-td3-(paper-rebuild|parallel-runbook)" docs/project docs/projects/pybullet_td3
```

Use `apply_patch` to replace active navigation links with the new paths. Historical quoted commands remain unchanged only inside `docs/project/research_history.md` and protocol history.

- [ ] **Step 5: 提交文档迁移**

```powershell
git add -A PROJECT_STRUCTURE.md PROJECT_LAYOUT.json RL_PAPER_EXECUTION_PLAN.md docs/project docs/projects/pybullet_td3 docs/superpowers/plans
git diff --cached --check
git commit -m "docs: organize project and protocol documentation"
```

## Task 4: 创建两条研究线和 PyBullet 阶段骨架

**Files:**
- Create: `experiments/circular_tracking/matlab_simulink/README.md`
- Create: `experiments/circular_tracking/pybullet_td3/**/__init__.py`
- Create: `experiments/circular_tracking/pybullet_td3/README.md`
- Create: `experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/README.md`
- Create: stage `README.md`, `config/stage.json`, `manifests/README.md`, `evidence/README.md`, `runs/README.md`
- Create: `tests/project/test_repository_layout.py`

- [ ] **Step 1: 写骨架失败测试**

Create `tests/project/test_repository_layout.py`:

```python
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

STAGE_CONFIGS = {
    "00_foundation_and_pid": {
        "stage_id": "00_foundation_and_pid",
        "status": "GO",
        "protocol_path": "../../../protocol/current.json",
        "budget_steps": 0,
        "training_seeds": [],
        "evaluation_seed_partition": "none",
        "controllers": ["pid"],
        "scenarios": ["standard", "random_wind", "actuator_loss", "compound"],
        "prerequisites": [],
        "go_rule": "Archived frozen-PID raw SHA-256 and inherited runtime-contract payload hash both match the registered identities.",
        "stop_rule": "Any frozen-PID identity mismatch blocks every later stage.",
    },
    "10_bootstrap_preflight": {
        "stage_id": "10_bootstrap_preflight",
        "status": "NO-GO",
        "protocol_path": "../../../protocol/current.json",
        "budget_steps": 5000,
        "training_seeds": [0, 1],
        "evaluation_seed_partition": "validation_100_109",
        "controllers": ["pid", "direct_td3", "residual_td3"],
        "scenarios": ["standard", "random_wind", "actuator_loss", "compound"],
        "prerequisites": ["00_foundation_and_pid:GO"],
        "go_rule": "The archived v2.1 Gate 3 decision must be GO.",
        "stop_rule": "The archived v2.1 Gate 3 NO-GO blocks Stage A and requires a separately approved method revision.",
    },
    "20_stage_a_20k": {
        "stage_id": "20_stage_a_20k",
        "status": "blocked",
        "protocol_path": "../../../protocol/current.json",
        "budget_steps": 20000,
        "training_seeds": [0],
        "evaluation_seed_partition": "validation_100_109",
        "controllers": ["pid", "residual_td3"],
        "scenarios": ["standard", "random_wind", "actuator_loss", "compound"],
        "prerequisites": ["00_foundation_and_pid:GO", "10_bootstrap_preflight:GO"],
        "go_rule": "Not evaluable while protocol/current.json has training_authorized=false; a replacement protocol must define and freeze the GO rule before training.",
        "stop_rule": "10_bootstrap_preflight:NO-GO blocks execution.",
    },
    "30_stage_b_50k": {
        "stage_id": "30_stage_b_50k",
        "status": "not_started",
        "protocol_path": "../../../protocol/current.json",
        "budget_steps": 50000,
        "training_seeds": [0, 1, 2],
        "evaluation_seed_partition": "validation_100_109",
        "controllers": ["pid", "residual_td3"],
        "scenarios": ["standard", "random_wind", "actuator_loss", "compound"],
        "prerequisites": ["20_stage_a_20k:GO"],
        "go_rule": "Not evaluable until an authorized replacement protocol freezes a Stage B rule before training.",
        "stop_rule": "Any Stage A result other than GO blocks execution.",
    },
    "40_stage_c_100k": {
        "stage_id": "40_stage_c_100k",
        "status": "not_started",
        "protocol_path": "../../../protocol/current.json",
        "budget_steps": 100000,
        "training_seeds": [0, 1, 2, 3, 4],
        "evaluation_seed_partition": "validation_100_109",
        "controllers": ["pid", "residual_td3"],
        "scenarios": ["standard", "random_wind", "actuator_loss", "compound"],
        "prerequisites": ["30_stage_b_50k:GO"],
        "go_rule": "Not evaluable until an authorized replacement protocol freezes a Stage C rule before training.",
        "stop_rule": "Any Stage B result other than GO blocks execution.",
    },
    "50_final_evaluation": {
        "stage_id": "50_final_evaluation",
        "status": "not_started",
        "protocol_path": "../../../protocol/current.json",
        "budget_steps": 0,
        "training_seeds": [0, 1, 2, 3, 4],
        "evaluation_seed_partition": "test_200_219_and_unseen_300_319",
        "controllers": ["pid", "residual_td3"],
        "scenarios": ["standard", "random_wind", "actuator_loss", "compound"],
        "prerequisites": ["40_stage_c_100k:GO"],
        "go_rule": "No optimization or checkpoint selection is permitted; report every paired held-out and unseen result.",
        "stop_rule": "Do not open test or unseen partitions before Stage C GO and protocol freeze.",
    },
}


def test_two_research_lines_exist():
    circular = ROOT / "experiments" / "circular_tracking"
    assert (circular / "matlab_simulink").is_dir()
    assert (circular / "pybullet_td3").is_dir()


def test_current_stage_skeleton_is_complete():
    stages = (
        ROOT
        / "experiments"
        / "circular_tracking"
        / "pybullet_td3"
        / "studies"
        / "pid_residual_td3"
        / "stages"
    )
    expected = set(STAGE_CONFIGS)
    assert {path.name for path in stages.iterdir() if path.is_dir()} == expected
    for stage in expected:
        root = stages / stage
        assert (root / "README.md").is_file()
        assert (root / "config" / "stage.json").is_file()
        assert (root / "manifests" / "README.md").is_file()
        assert (root / "evidence" / "README.md").is_file()
        assert (root / "runs" / "README.md").is_file()
        assert json.loads((root / "config" / "stage.json").read_text(encoding="utf-8")) == STAGE_CONFIGS[stage]
```

- [ ] **Step 2: 运行并确认失败**

```powershell
py -3.11 -m pytest tests/project/test_repository_layout.py -v
```

Expected: FAIL because the new research-line directories do not exist.

- [ ] **Step 3: 创建包骨架和阶段模板**

Create empty `__init__.py` files at:

```text
experiments/circular_tracking/pybullet_td3/__init__.py
experiments/circular_tracking/pybullet_td3/common/__init__.py
experiments/circular_tracking/pybullet_td3/studies/__init__.py
experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/__init__.py
experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/code/__init__.py
experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/code/environments/__init__.py
experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/code/training/__init__.py
experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/code/evaluation/__init__.py
experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/code/analysis/__init__.py
```

Create each `config/stage.json` with the exact object under the same stage key in `STAGE_CONFIGS` from Step 1. Keep key names, array order and strings unchanged. The relative protocol path is `../../../protocol/current.json` because every file lives under `stages/<stage>/config/`.

Create these tracked placeholders with literal explanatory text, not fabricated experiment data:

```text
manifests/README.md: "Run manifests are created only after an authorized real run; this directory is intentionally empty."
evidence/README.md:  "Metrics, summaries and decisions are created only from real evidence; this directory is intentionally empty unless the stage already has a recorded decision."
runs/README.md:      "Local runs use runs/<controller>/seed_<NNN>/budget_<steps>/attempt_<NN>/ and are ignored by Git."
```

Each stage `README.md` must quote its exact `status`, `budget_steps`, `training_seeds`, `prerequisites`, `go_rule` and `stop_rule` from `stage.json`. Do not create `experiment_manifest.json`, `seed_manifest.json`, `model_registry.json`, metrics files or model-shaped placeholders for a run that has not occurred.

- [ ] **Step 4: 运行骨架测试**

```powershell
py -3.11 -m pytest tests/project/test_repository_layout.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: 提交骨架**

```powershell
git add experiments/circular_tracking/matlab_simulink experiments/circular_tracking/pybullet_td3 tests/project/test_repository_layout.py
git diff --cached --check
git commit -m "feat: scaffold reinforcement learning research lines"
```

## Task 5: 原子迁移 MATLAB/Simulink 源码、模型和小型证据

**Files:**
- Move: `experiments/circular_tracking/simulink_residual_rl/**`
- Populate: `experiments/circular_tracking/matlab_simulink/**`
- Create: `experiments/circular_tracking/matlab_simulink/common/matlab_simulink_root.m`
- Create: `experiments/circular_tracking/matlab_simulink/evidence/provenance/source_inventory.csv`
- Create: `experiments/circular_tracking/matlab_simulink/evidence/provenance/model_registry.json`
- Modify: `.gitignore`
- Create: `.gitattributes`

This task is one atomic local commit. Do not commit a state in which moved MATLAB scripts cannot resolve their dependencies.

- [ ] **Step 1: 先更新二进制和本地产物规则**

Create `.gitattributes`:

```gitattributes
*.slx binary
*.mat binary
*.png binary
*.pdf binary
*.docx binary
```

Append these exact rules to `.gitignore`:

```gitignore
# MATLAB/Simulink local artifacts
experiments/circular_tracking/matlab_simulink/artifacts/*
!experiments/circular_tracking/matlab_simulink/artifacts/README.md
experiments/circular_tracking/matlab_simulink/reports/**/*.docx
experiments/circular_tracking/matlab_simulink/reports/**/*.pdf
experiments/circular_tracking/matlab_simulink/reports/assets/**/*.png
**/slprj/
**/sccprj/
**/*.slxc
**/*.autosave
**/*.asv
**/~$*
```

Do not add a global `*.mat` ignore rule because three tiny frozen policy files are tracked evidence.

- [ ] **Step 2: Git-move the 46 authoritative tracked files by responsibility**

Use `git mv` according to this exact map:

```text
simulink_residual_rl/README.md
  -> matlab_simulink/README.md
simulink_residual_rl/setup_simulink_residual_rl_paths.m
  -> matlab_simulink/setup_matlab_simulink_paths.m

scripts/init_quadrotor_params.m
scripts/parse_quad_log.m
scripts/quadrotor_environment_core.m
scripts/quadrotor_pack_log_core.m
scripts/quadrotor_reference_core.m
scripts/quadrotor_rhs_core.m
  -> matlab_simulink/common/

scripts/quadrotor_controller_core.m
  -> matlab_simulink/methods/pid/
scripts/quadrotor_disturbance_compensation_core.m
  -> matlab_simulink/methods/pid_feedforward/
scripts/quadrotor_mpc_outer_core.m
  -> matlab_simulink/methods/mpc/
scripts/quadrotor_adrc_eso_derivative_core.m
scripts/quadrotor_adrc_outer_core.m
  -> matlab_simulink/methods/adrc/
scripts/enable_quadrotor_rl_policy.m
scripts/quadrotor_rl_policy_core.m
scripts/train_quadrotor_rl_policy.m
  -> matlab_simulink/methods/residual_rl_v1/
scripts/create_quadrotor_rl_v2_imitation_dataset.m
scripts/enable_quadrotor_rl_v2_policy.m
scripts/fit_quadrotor_rl_v2_readout.m
scripts/quadrotor_rl_v2_features_core.m
scripts/quadrotor_rl_v2_policy_core.m
scripts/train_quadrotor_rl_v2_policy.m
  -> matlab_simulink/methods/residual_rl_v2/

scripts/build_quadrotor_models.m
scripts/plot_circle_rotor_steady_periodic_zoom.m
  -> matlab_simulink/studies/00_environment_models/
scripts/build_controller_strategy_models.m
scripts/run_strategy_model_smoke_tests.m
scripts/run_strategy_circle_comparison.m
  -> matlab_simulink/studies/10_controller_comparison/
scripts/run_rl_circle_comparison.m
  -> matlab_simulink/studies/20_residual_rl_v1/
scripts/run_rl_v2_mpc_benchmark.m
  -> matlab_simulink/studies/30_rl_v2_mpc_imitation/

tests/test_quadrotor_rl_v2_imitation.m
  -> matlab_simulink/tests/test_quadrotor_rl_v2_imitation.m
docs/design/2026-07-04-mpc-imitation-readout-design.md
  -> matlab_simulink/studies/30_rl_v2_mpc_imitation/docs/design.md
docs/plans/2026-07-04-mpc-imitation-readout-implementation.md
  -> matlab_simulink/studies/30_rl_v2_mpc_imitation/docs/implementation_plan.md
scripts/reporting/*
  -> matlab_simulink/reports/generators/
docs/source_delivery_README.md
  -> matlab_simulink/reports/legacy/source_delivery_README.md
audit/*
  -> matlab_simulink/evidence/provenance/legacy_delivery/
reports/assets/beginner_control_strategies/formula_sources.md
  -> matlab_simulink/reports/assets/beginner_control_strategies/formula_sources.md
reports/rl_v1/强化学习圆周抗扰控制对比报告.md
  -> matlab_simulink/reports/rl_v1/强化学习圆周抗扰控制对比报告.md
reports/rl_v2/RL-v2超越MPC控制策略报告.md
  -> matlab_simulink/reports/rl_v2/RL-v2超越MPC控制策略报告.md
reports/strategy_comparison/多控制策略圆周抗扰对比报告.md
  -> matlab_simulink/reports/strategy_comparison/多控制策略圆周抗扰对比报告.md
reports/strategy_comparison/五种控制策略小白说明报告.md
  -> matlab_simulink/reports/strategy_comparison/五种控制策略小白说明报告.md
```

Create destination directories before each `git mv`; do not use a recursive copy from the 275-file external project.

- [ ] **Step 3: 建立唯一 MATLAB 根路径函数**

Create `experiments/circular_tracking/matlab_simulink/common/matlab_simulink_root.m`:

```matlab
function rootDir = matlab_simulink_root()
%MATLAB_SIMULINK_ROOT Return the canonical MATLAB/Simulink study root.
rootDir = fileparts(fileparts(mfilename('fullpath')));
end
```

Replace `setup_matlab_simulink_paths.m` with:

```matlab
function setup_matlab_simulink_paths()
%SETUP_MATLAB_SIMULINK_PATHS Add only active source folders to MATLAB path.
rootDir = fileparts(mfilename('fullpath'));
folders = {
    rootDir
    fullfile(rootDir, 'common')
    fullfile(rootDir, 'methods', 'pid')
    fullfile(rootDir, 'methods', 'pid_feedforward')
    fullfile(rootDir, 'methods', 'mpc')
    fullfile(rootDir, 'methods', 'adrc')
    fullfile(rootDir, 'methods', 'residual_rl_v1')
    fullfile(rootDir, 'methods', 'residual_rl_v2')
    fullfile(rootDir, 'studies', '00_environment_models')
    fullfile(rootDir, 'studies', '10_controller_comparison')
    fullfile(rootDir, 'studies', '20_residual_rl_v1')
    fullfile(rootDir, 'studies', '30_rl_v2_mpc_imitation')
    };
for idx = 1:numel(folders)
    addpath(folders{idx});
end
fprintf('MATLAB/Simulink study paths added: %s\n', rootDir);
end
```

- [ ] **Step 4: 更新13个活动 MATLAB 入口的路径解析**

Update these files in one pass:

```text
setup_matlab_simulink_paths.m
tests/test_quadrotor_rl_v2_imitation.m
studies/00_environment_models/build_quadrotor_models.m
studies/10_controller_comparison/build_controller_strategy_models.m
methods/residual_rl_v1/enable_quadrotor_rl_policy.m
methods/residual_rl_v2/enable_quadrotor_rl_v2_policy.m
methods/residual_rl_v1/train_quadrotor_rl_policy.m
methods/residual_rl_v2/train_quadrotor_rl_v2_policy.m
studies/10_controller_comparison/run_strategy_circle_comparison.m
studies/10_controller_comparison/run_strategy_model_smoke_tests.m
studies/20_residual_rl_v1/run_rl_circle_comparison.m
studies/30_rl_v2_mpc_imitation/run_rl_v2_mpc_benchmark.m
studies/00_environment_models/plot_circle_rotor_steady_periodic_zoom.m
```

Each file obtains `rootDir` from `matlab_simulink_root()` and uses the new `models/`, `evidence/`, `artifacts/` and `reports/` paths. Do not retain fixed-depth `fileparts(fileparts(...))` chains. Update the four Python report generators under `reports/generators/` so they read tracked CSV/policies from `evidence/` and write generated DOCX/PDF only to `artifacts/report_exports/`.

- [ ] **Step 5: 恢复并验证九个 Simulink 源模型**

```powershell
$sourceA = 'E:\1-AI辅助工作\科研项目\强化学习\gym-pybullet-drones\experiments\circular_tracking\simulink_residual_rl\models'
$sourceB = 'E:\1-AI辅助工作\科研项目\干扰环境仿真\quadrotor_env_comparison\models'
$target = (Resolve-Path experiments/circular_tracking/matlab_simulink).Path + '\models'
New-Item -ItemType Directory -Force $target | Out-Null
$names = @(
  'quadrotor_dust.slx','quadrotor_standard.slx','quadrotor_strategy_adrc.slx',
  'quadrotor_strategy_mpc.slx','quadrotor_strategy_pid_ff.slx','quadrotor_strategy_pid.slx',
  'quadrotor_strategy_rl_v2.slx','quadrotor_strategy_rl.slx','quadrotor_temperature.slx'
)
foreach ($name in $names) {
    $a = Join-Path $sourceA $name
    $b = Join-Path $sourceB $name
    if ((Get-FileHash $a -Algorithm SHA256).Hash -ne (Get-FileHash $b -Algorithm SHA256).Hash) {
        throw "模型来源冲突：$name"
    }
    Copy-Item -LiteralPath $a -Destination (Join-Path $target $name)
}
```

Create `evidence/provenance/model_registry.json` with this exact content:

```json
{
  "schema_version": 1,
  "models": [
    {"name": "quadrotor_dust.slx", "size_bytes": 115894, "sha256": "60456557b48376b1af9efaea3d65f751e27d53bd1e922fc8064719572c51f6b8"},
    {"name": "quadrotor_standard.slx", "size_bytes": 115611, "sha256": "e78267d2cf58cc103555301bbe235c7210f49b189a27e1512b6db1fcb7a7d174"},
    {"name": "quadrotor_strategy_adrc.slx", "size_bytes": 128432, "sha256": "297c9241d8bf03f30af4d88f17bdeff6d989b9c272935a86b51c08c953c560d5"},
    {"name": "quadrotor_strategy_mpc.slx", "size_bytes": 128499, "sha256": "85fcc40fd13d8b6ef6f294ec2fa686d13c0f958d99d2ff77d2a811256917f3da"},
    {"name": "quadrotor_strategy_pid_ff.slx", "size_bytes": 128438, "sha256": "d15a0f0622449a4d00b017f1457de7d904fcffb37f6a2623a3aa1479a144dee1"},
    {"name": "quadrotor_strategy_pid.slx", "size_bytes": 128486, "sha256": "46d14fd0c62fc9eaacf2e285582f4a1898fc99933d6904f8d035d1ce56eaa866"},
    {"name": "quadrotor_strategy_rl_v2.slx", "size_bytes": 131867, "sha256": "bc57817e82d89b5adf1249ec2e65385f44a6f5571586ae47cc0e51de8c713c52"},
    {"name": "quadrotor_strategy_rl.slx", "size_bytes": 128546, "sha256": "068d1b7647ddb7a053a7d099989ba0ff608eedfca049a948cd95cc994d562241"},
    {"name": "quadrotor_temperature.slx", "size_bytes": 115803, "sha256": "2a2c12ea323c10e7f0bca04cbd982159f1143f171a5dee7de17830e170a5c2ed"}
  ]
}
```

Recompute every target file's size and SHA-256 and compare it with this registry before staging.

- [ ] **Step 6: 迁入小型证据，分离本地 MAT 和报告导出物**

From the complete main-worktree copy, copy and Git-track exactly these files:

```text
results/data/quadrotor_strategy_model_smoke_tests.csv
  -> evidence/10_controller_comparison/quadrotor_strategy_model_smoke_tests.csv
results/data/quadrotor_strategy_circle_comparison_metrics.csv
  -> evidence/10_controller_comparison/quadrotor_strategy_circle_comparison_metrics.csv
results/data/quadrotor_strategy_circle_comparison_metrics.md
  -> evidence/10_controller_comparison/quadrotor_strategy_circle_comparison_metrics.md
results/figures/strategy_circle_trajectory_3d.png
results/figures/strategy_circle_position_error.png
results/figures/strategy_circle_metric_bars.png
results/figures/strategy_circle_effort_altitude.png
  -> evidence/10_controller_comparison/figures/

results/data/quadrotor_rl_training_log.csv
  -> evidence/20_residual_rl_v1/quadrotor_rl_training_log.csv
results/data/quadrotor_rl_circle_comparison_metrics.csv
  -> evidence/20_residual_rl_v1/quadrotor_rl_circle_comparison_metrics.csv
results/data/quadrotor_rl_circle_comparison_metrics.md
  -> evidence/20_residual_rl_v1/quadrotor_rl_circle_comparison_metrics.md
results/policies/rl_v1/quadrotor_rl_policy.mat
results/policies/rl_v1/quadrotor_rl_policy_summary.md
  -> evidence/20_residual_rl_v1/policy/
results/figures/rl_circle_trajectory_3d.png
results/figures/rl_circle_position_error.png
results/figures/rl_circle_metric_improvement.png
  -> evidence/20_residual_rl_v1/figures/

results/data/quadrotor_rl_v2_training_log.csv
  -> evidence/30_rl_v2_mpc_imitation/quadrotor_rl_v2_training_log.csv
results/data/quadrotor_rl_v2_mpc_benchmark_metrics.csv
  -> evidence/30_rl_v2_mpc_imitation/quadrotor_rl_v2_mpc_benchmark_metrics.csv
results/data/quadrotor_rl_v2_mpc_benchmark_metrics.md
  -> evidence/30_rl_v2_mpc_imitation/quadrotor_rl_v2_mpc_benchmark_metrics.md
results/policies/rl_v2/quadrotor_rl_v2_policy_before_imitation.mat
results/policies/rl_v2/quadrotor_rl_v2_policy.mat
results/policies/rl_v2/quadrotor_rl_v2_policy_summary.md
  -> evidence/30_rl_v2_mpc_imitation/policy/
results/figures/rl_v2_benchmark_trajectory_3d.png
results/figures/rl_v2_benchmark_position_error.png
results/figures/rl_v2_benchmark_metric_bars.png
results/figures/rl_v2_benchmark_effort_feasibility.png
  -> evidence/30_rl_v2_mpc_imitation/figures/
```

Copy but do not stage these local artifacts from the complete main-worktree copy:

```text
results/data/quadrotor_strategy_circle_comparison_results.mat
results/data/quadrotor_strategy_model_smoke_tests.mat
  -> artifacts/10_controller_comparison/data/
results/data/quadrotor_rl_circle_comparison_results.mat
  -> artifacts/20_residual_rl_v1/data/
results/data/quadrotor_rl_v2_mpc_benchmark_results.mat
results/data/quadrotor_rl_v2_mpc_imitation_data.mat
  -> artifacts/30_rl_v2_mpc_imitation/data/
reports/rl_v1/强化学习圆周抗扰控制对比报告.docx
reports/rl_v1/强化学习圆周抗扰控制对比报告.pdf
  -> artifacts/report_exports/rl_v1/
reports/rl_v2/RL-v2超越MPC控制策略报告.docx
reports/rl_v2/RL-v2超越MPC控制策略报告.pdf
  -> artifacts/report_exports/rl_v2/
reports/strategy_comparison/多控制策略圆周抗扰对比报告.docx
reports/strategy_comparison/多控制策略圆周抗扰对比报告.pdf
reports/strategy_comparison/五种控制策略小白说明报告.docx
reports/strategy_comparison/五种控制策略小白说明报告.pdf
  -> artifacts/report_exports/strategy_comparison/
reports/assets/beginner_control_strategies/eq01.png through eq15.png
  -> artifacts/report_exports/assets/beginner_control_strategies/
```

Also restore this one dependency from the external original project, without staging it:

```text
E:/1-AI辅助工作/科研项目/干扰环境仿真/quadrotor_env_comparison/results/data/quadrotor_environment_comparison_results.mat
  -> matlab_simulink/artifacts/00_environment_models/data/quadrotor_environment_comparison_results.mat
```

Store them below `matlab_simulink/artifacts/` and confirm `git check-ignore -v` reports the intended rule. Create and track only `artifacts/README.md`.

- [ ] **Step 7: 写无绝对路径的来源清单**

Create `evidence/provenance/source_inventory.csv` with columns:

```text
source_id,old_relative_path,new_relative_path,size_bytes,sha256,role,tracking_decision
```

Use source IDs `integration_head`, `main_worktree_complete_copy` and `external_original`; never write the user's absolute drive paths into the public CSV.

- [ ] **Step 8: 执行最小 MATLAB 验证，不运行训练**

```powershell
rg -n "simulink_residual_rl|results[/\\](data|figures|policies)|fullfile\(rootDir,\s*'scripts'\)" experiments/circular_tracking/matlab_simulink
matlab -batch "root=fullfile(pwd,'experiments','circular_tracking','matlab_simulink'); addpath(root); setup_matlab_simulink_paths; r=runtests(fullfile(root,'tests','test_quadrotor_rl_v2_imitation.m')); assertSuccess(r)"
matlab -batch "root=fullfile(pwd,'experiments','circular_tracking','matlab_simulink'); addpath(root); setup_matlab_simulink_paths; f=dir(fullfile(root,'models','*.slx')); assert(numel(f)==9); for k=1:numel(f), load_system(fullfile(f(k).folder,f(k).name)); [~,n]=fileparts(f(k).name); close_system(n,0); end"
```

Expected:

- active source has no old result paths; legacy delivery README may retain historical paths;
- four MATLAB tests pass;
- nine models load and close without simulation.

- [ ] **Step 9: 验证 Git 边界并提交 MATLAB 原子迁移**

```powershell
git add -A experiments/circular_tracking/simulink_residual_rl experiments/circular_tracking/matlab_simulink .gitignore .gitattributes
$trackedModels = @(git ls-files 'experiments/circular_tracking/matlab_simulink/models/*.slx')
if ($trackedModels.Count -ne 9) { throw '九个SLX未全部跟踪' }
$unexpected = git diff --cached --name-only | Select-String 'matlab_simulink/artifacts/.*\.(mat|pdf|docx|png)$'
if ($unexpected) { $unexpected; throw '本地产物进入暂存区' }
git diff --cached --check
git commit -m "refactor: organize matlab simulink research line"
```

## Task 6: 归档冻结 PID 身份并建立派生运行契约

**Files:**
- Copy byte-for-byte: `experiments/circular_tracking/config/hidden_pid_frozen.json`
- Create: `experiments/circular_tracking/pybullet_td3/archive/20_hidden_disturbance_v1/provenance/hidden_pid_frozen.schema4.json`
- Create: `experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/protocol/frozen_pid.json`
- Create: `experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/study_paths.py`
- Create: `experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/code/training/pid_contract.py`
- Create: `tests/circular_tracking/pybullet_td3/test_pid_runtime_contract.py`

- [ ] **Step 1: 写派生契约失败测试**

Create `tests/circular_tracking/pybullet_td3/test_pid_runtime_contract.py`:

```python
import hashlib
import json
from pathlib import Path

import pytest

from experiments.circular_tracking.pybullet_td3.studies.pid_residual_td3.code.training.pid_contract import (
    load_pid_runtime_contract,
)


ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / "experiments/circular_tracking/pybullet_td3/archive/20_hidden_disturbance_v1/provenance/hidden_pid_frozen.schema4.json"
RUNTIME = ROOT / "experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/protocol/frozen_pid.json"


def test_archived_pid_bytes_are_immutable():
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == (
        "c7530d2725d4c55b31252f89c1ed126ae140a35789b3c653b86e955165e48ef3"
    )


def test_runtime_contract_is_derived_without_retuning():
    contract = load_pid_runtime_contract(RUNTIME)
    assert contract["parameters"] == {
        "pid_target_step_limit": 0.0,
        "pid_xy_d_scale": 1.25,
        "pid_xy_p_scale": 1.0,
        "reference_velocity_gain": 1.0,
    }
    assert contract["pid_payload_hash"] == (
        "624e86cf7452410e15608774d5630512bd8a7f48f5d4e8d30fd5a8dcca37b99a"
    )


def test_runtime_contract_rejects_changed_parameters(tmp_path: Path):
    payload = json.loads(RUNTIME.read_text(encoding="utf-8"))
    payload["parameters"]["pid_xy_d_scale"] = 1.0
    candidate = tmp_path / "frozen_pid.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="parameter values"):
        load_pid_runtime_contract(candidate)


def test_runtime_contract_rejects_extra_fields(tmp_path: Path):
    payload = json.loads(RUNTIME.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    candidate = tmp_path / "frozen_pid.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="top-level fields"):
        load_pid_runtime_contract(candidate)
```

- [ ] **Step 2: 运行并确认失败**

```powershell
py -3.11 -m pytest tests/circular_tracking/pybullet_td3/test_pid_runtime_contract.py -v
```

Expected: FAIL because archive/contract/loader do not exist.

- [ ] **Step 3: 逐字复制原冻结证据并验证 raw hash**

Use `Copy-Item -LiteralPath` from the old config path to the archive path. Do not read and rewrite JSON through a serializer.

```powershell
$source = 'experiments/circular_tracking/config/hidden_pid_frozen.json'
$target = 'experiments/circular_tracking/pybullet_td3/archive/20_hidden_disturbance_v1/provenance/hidden_pid_frozen.schema4.json'
New-Item -ItemType Directory -Force (Split-Path -Parent $target) | Out-Null
Copy-Item -LiteralPath $source -Destination $target
$hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne 'c7530d2725d4c55b31252f89c1ed126ae140a35789b3c653b86e955165e48ef3') { throw '冻结PID字节身份改变' }
```

- [ ] **Step 4: 创建当前派生运行契约**

Create `protocol/frozen_pid.json` with the exact JSON object below:

```json
{
  "schema_version": 1,
  "contract": "inherited_frozen_pid_runtime_contract",
  "parameters": {
    "pid_target_step_limit": 0.0,
    "pid_xy_d_scale": 1.25,
    "pid_xy_p_scale": 1.0,
    "reference_velocity_gain": 1.0
  },
  "pid_payload_hash": "624e86cf7452410e15608774d5630512bd8a7f48f5d4e8d30fd5a8dcca37b99a",
  "derived_from": {
    "path": "../../../archive/20_hidden_disturbance_v1/provenance/hidden_pid_frozen.schema4.json",
    "raw_sha256": "c7530d2725d4c55b31252f89c1ed126ae140a35789b3c653b86e955165e48ef3",
    "evaluation_git_sha": "f19e99103d2700b3a9bd5cb4baf9ec2e31b7385d",
    "source_protocol_hash": "e6edc37f6f89ec6684917f71f20444dd45b6e745f299b8ea6bf165d71e294359",
    "evidence_index_content_sha256": "c94b41c77eed7f10dcb1d319f347458dec00c2d9c4334ee22def536383f7b851"
  }
}
```

- [ ] **Step 5: 实现严格的运行契约加载器和集中路径模块**

Create `experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/code/training/pid_contract.py` exactly as follows. This loader validates only the inherited runtime contract and immutable archive bytes; it never calls the old external evidence graph and never claims a new PID tune.

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_RAW_SHA256 = "c7530d2725d4c55b31252f89c1ed126ae140a35789b3c653b86e955165e48ef3"
EXPECTED_PAYLOAD_HASH = "624e86cf7452410e15608774d5630512bd8a7f48f5d4e8d30fd5a8dcca37b99a"
EXPECTED_PARAMETERS = {
    "pid_target_step_limit": 0.0,
    "pid_xy_d_scale": 1.25,
    "pid_xy_p_scale": 1.0,
    "reference_velocity_gain": 1.0,
}
EXPECTED_DERIVED_FROM = {
    "path": "../../../archive/20_hidden_disturbance_v1/provenance/hidden_pid_frozen.schema4.json",
    "raw_sha256": EXPECTED_RAW_SHA256,
    "evaluation_git_sha": "f19e99103d2700b3a9bd5cb4baf9ec2e31b7385d",
    "source_protocol_hash": "e6edc37f6f89ec6684917f71f20444dd45b6e745f299b8ea6bf165d71e294359",
    "evidence_index_content_sha256": "c94b41c77eed7f10dcb1d319f347458dec00c2d9c4334ee22def536383f7b851",
}


def _canonical_json_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_exact_keys(payload: dict[str, Any], expected: set[str], label: str) -> None:
    if set(payload) != expected:
        raise ValueError(f"PID runtime contract {label} fields are invalid")


def load_pid_runtime_contract(path: Path | str) -> dict[str, Any]:
    resolved_contract = Path(path).resolve()
    payload = json.loads(resolved_contract.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("PID runtime contract must be an object")
    _require_exact_keys(
        payload,
        {"schema_version", "contract", "parameters", "pid_payload_hash", "derived_from"},
        "top-level",
    )
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ValueError("PID runtime contract schema is invalid")
    if payload["contract"] != "inherited_frozen_pid_runtime_contract":
        raise ValueError("PID runtime contract kind is invalid")

    parameters = payload["parameters"]
    if not isinstance(parameters, dict):
        raise ValueError("PID runtime parameters must be an object")
    _require_exact_keys(parameters, set(EXPECTED_PARAMETERS), "parameter")
    if any(type(value) not in (int, float) for value in parameters.values()):
        raise ValueError("PID runtime parameter types are invalid")
    if parameters != EXPECTED_PARAMETERS:
        raise ValueError("PID runtime parameter values are invalid")
    if payload["pid_payload_hash"] != EXPECTED_PAYLOAD_HASH:
        raise ValueError("PID runtime parameter identity is invalid")
    if _canonical_json_hash(parameters) != EXPECTED_PAYLOAD_HASH:
        raise ValueError("PID runtime parameter hash is invalid")

    derived = payload["derived_from"]
    if not isinstance(derived, dict):
        raise ValueError("PID runtime provenance is invalid")
    _require_exact_keys(derived, set(EXPECTED_DERIVED_FROM), "provenance")
    if not all(isinstance(value, str) for value in derived.values()):
        raise ValueError("PID runtime provenance types are invalid")
    if derived != EXPECTED_DERIVED_FROM:
        raise ValueError("PID runtime provenance identity is invalid")

    if len(resolved_contract.parents) < 4:
        raise ValueError("PID runtime contract path is outside the study layout")
    pybullet_root = resolved_contract.parents[3]
    archive_root = (pybullet_root / "archive").resolve()
    relative_archive = Path(derived["path"])
    if relative_archive.is_absolute():
        raise ValueError("PID runtime archive path must be relative")
    archive_path = (resolved_contract.parent / relative_archive).resolve()
    try:
        archive_path.relative_to(archive_root)
    except ValueError as exc:
        raise ValueError("PID runtime archive path escapes the archive root") from exc
    expected_archive = (
        archive_root
        / "20_hidden_disturbance_v1"
        / "provenance"
        / "hidden_pid_frozen.schema4.json"
    ).resolve()
    if archive_path != expected_archive:
        raise ValueError("PID runtime archive path is not canonical")
    if not archive_path.is_file():
        raise ValueError("archived PID evidence is missing")
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != EXPECTED_RAW_SHA256:
        raise ValueError("archived PID evidence hash is invalid")
    return payload
```

Create `experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/study_paths.py` exactly as follows:

```python
from __future__ import annotations

from pathlib import Path


def find_repository_root(start: Path | None = None) -> Path:
    cursor = (start or Path(__file__)).resolve()
    if cursor.is_file():
        cursor = cursor.parent
    for candidate in (cursor, *cursor.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "experiments").is_dir():
            return candidate
    raise RuntimeError("repository root containing pyproject.toml and experiments/ was not found")


REPO_ROOT = find_repository_root()
PYBULLET_TD3_ROOT = REPO_ROOT / "experiments" / "circular_tracking" / "pybullet_td3"
STUDY_ROOT = PYBULLET_TD3_ROOT / "studies" / "pid_residual_td3"
PROTOCOL_PATH = STUDY_ROOT / "protocol" / "current.json"
FROZEN_PID_PATH = STUDY_ROOT / "protocol" / "frozen_pid.json"
ACTIVE_STAGES_ROOT = STUDY_ROOT / "stages"
ENVIRONMENT_SOURCE_PATH = STUDY_ROOT / "code" / "environments" / "hidden_disturbance_td3_env.py"
```

- [ ] **Step 6: 运行测试并提交契约**

```powershell
py -3.11 -m pytest tests/circular_tracking/pybullet_td3/test_pid_runtime_contract.py -v
git add experiments/circular_tracking/pybullet_td3/archive/20_hidden_disturbance_v1/provenance experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3 tests/circular_tracking/pybullet_td3/test_pid_runtime_contract.py
git diff --cached --check
git commit -m "feat: preserve frozen pid provenance across layout migration"
```

## Task 7: 原子迁移 PyBullet 当前代码、测试和旧 Oracle 源码

**Files:**
- Move current: `experiments/circular_tracking/rl_envs/{disturbance_processes,hidden_disturbance_td3_env}.py`
- Move current: `experiments/circular_tracking/scripts/td3/{tune_hidden_pid,train_hidden_td3,evaluate_hidden_td3,summarize_hidden_td3}.py`
- Archive legacy: `circular_residual_td3_env.py` and nine legacy TD3 scripts
- Move tests: four active hidden-TD3 tests to `tests/circular_tracking/pybullet_td3/`
- Archive byte-for-byte: `tests/circular_tracking/test_hidden_pid_acceptance.py`
- Modify: `gym_pybullet_drones/examples/{pid,pid_velocity,downwash}.py`

- [ ] **Step 1: 从结果提交提取 v2.1 协议原件并建立阻塞的当前协议**

Extract the exact Git blob used by the v2.1 Gate 3 run, without passing it through a text serializer:

```powershell
$commit = '0079879968992042b62a6e8e85f3474d7655ca11'
$sourcePath = 'experiments/circular_tracking/config/hidden_td3_protocol.json'
$targetPath = 'experiments/circular_tracking/pybullet_td3/archive/31_hidden_disturbance_v2_1/protocol/hidden_td3_protocol.v2_1.json'
$zip = 'tmp/layout-migration/protocol-v2_1.zip'
$extract = 'tmp/layout-migration/protocol-v2_1'
New-Item -ItemType Directory -Force (Split-Path -Parent $zip), $extract, (Split-Path -Parent $targetPath) | Out-Null
git archive --format=zip --output=$zip $commit -- $sourcePath
if ($LASTEXITCODE -ne 0) { throw '无法导出v2.1协议Git blob' }
Expand-Archive -LiteralPath $zip -DestinationPath $extract
Copy-Item -LiteralPath (Join-Path $extract $sourcePath) -Destination $targetPath
$hash = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne '16781e621b316b2d8b3c9811cefd775b2e4ee2c931b275bcc059edc803d9f259') {
    throw "v2.1协议身份异常：$hash"
}
```

Create `studies/pid_residual_td3/protocol/current.json`:

```json
{
  "schema_version": 1,
  "protocol_name": "pid_residual_td3_follow_up",
  "status": "blocked_pending_method_revision",
  "training_authorized": false,
  "controllers": ["pid", "residual_td3"],
  "derived_from": {
    "protocol": "../../../archive/31_hidden_disturbance_v2_1/protocol/hidden_td3_protocol.v2_1.json",
    "final_gate": "Gate 3 v2.1",
    "decision": "NO-GO"
  }
}
```

Its LF-normalized SHA-256 is `213c95cea1e7557319c3943946191c236b9eb84a7540ae9749d3d3b4306263bb`. Verify that hash after creation. No training CLI may treat this file as a frozen training authorization.

- [ ] **Step 2: Git-move active Python modules**

```text
rl_envs/disturbance_processes.py
  -> pybullet_td3/studies/pid_residual_td3/code/environments/disturbance_processes.py
rl_envs/hidden_disturbance_td3_env.py
  -> pybullet_td3/studies/pid_residual_td3/code/environments/hidden_disturbance_td3_env.py
scripts/td3/tune_hidden_pid.py
  -> pybullet_td3/studies/pid_residual_td3/code/training/tune_hidden_pid.py
scripts/td3/train_hidden_td3.py
  -> pybullet_td3/studies/pid_residual_td3/code/training/train_hidden_td3.py
scripts/td3/evaluate_hidden_td3.py
  -> pybullet_td3/studies/pid_residual_td3/code/evaluation/evaluate_hidden_td3.py
scripts/td3/summarize_hidden_td3.py
  -> pybullet_td3/studies/pid_residual_td3/code/analysis/summarize_hidden_td3.py
analysis/hidden_td3_metric_schema.md
  -> pybullet_td3/studies/pid_residual_td3/protocol/metric_schema.md
```

- [ ] **Step 3: 按字节归档 Oracle/PID-FF 旧源码**

Move these without editing their imports, commands or default paths:

```text
rl_envs/circular_residual_td3_env.py
scripts/td3/train_direct_td3.py
scripts/td3/train_residual_td3.py
scripts/td3/evaluate_td3_controllers.py
scripts/td3/run_td3_paper_pipeline.py
scripts/td3/select_td3_models.py
scripts/td3/plot_td3_results.py
scripts/td3/summarize_td3_results.py
scripts/td3/analyze_td3_diagnostics.py
  -> pybullet_td3/archive/10_oracle_pid_ff_pilot/source/

analysis/claim_evidence_ledger.csv
analysis/td3_metric_schema.md
analysis/plan_completion_audit.md
  -> pybullet_td3/archive/10_oracle_pid_ff_pilot/evidence/
```

Add an archive README stating that executable reproduction requires checkout of the recorded original Git commit; the moved files are preserved evidence, not an active package.

- [ ] **Step 4: Move common classical examples and update wrappers**

```text
scripts/position_pid/
  -> pybullet_td3/common/baselines/position_pid/
scripts/downwash_periodic/
  -> pybullet_td3/common/examples/downwash_periodic/
scripts/velocity_input/
  -> pybullet_td3/common/examples/velocity_input/
```

Update module strings/imports in:

```text
gym_pybullet_drones/examples/pid.py
gym_pybullet_drones/examples/pid_velocity.py
gym_pybullet_drones/examples/downwash.py
```

Keep their public `run` behavior unchanged.

- [ ] **Step 5: Update active imports and centralize study paths**

Update every active import to the new package. `code/environments/__init__.py` exports only `HiddenDisturbanceCircularTD3Env`; it must not export the archived `CircularResidualTD3Env`.

Modify the four active entry points to import path constants from `study_paths.py` and the PID parameters from `pid_contract.py` rather than `tune_hidden_pid.py` globals. Replace:

```text
experiments.circular_tracking.rl_envs...
experiments.circular_tracking.scripts.td3...
experiments/circular_tracking/config/...
experiments/circular_tracking/results/hidden_disturbance_td3_paper
```

with the canonical study package and stage `runs/` paths. Training output validation must reject every path outside:

```text
experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/stages/*/runs/
```

The training CLI must fail before environment creation when `current.json` has `training_authorized: false`.

- [ ] **Step 6: Split active and archival tests**

Move and update imports in:

```text
test_hidden_disturbance_td3_env.py
test_hidden_td3_metrics.py
test_hidden_td3_training_config.py
test_hidden_td3_v2_safety.py
  -> tests/circular_tracking/pybullet_td3/
```

Move `test_hidden_pid_acceptance.py` byte-for-byte to:

```text
experiments/circular_tracking/pybullet_td3/archive/20_hidden_disturbance_v1/tests/test_hidden_pid_acceptance.py
```

Do not reinterpret that test against new paths; Task 1 already validated its evidence at the old anchor. The new runtime-contract test replaces only the current-path identity check, not the archived scientific evidence.

In `test_hidden_disturbance_td3_env.py`, replace the old assertion that one package exports both legacy and current environments with an assertion that the active environment package exports only `HiddenDisturbanceCircularTD3Env`.

- [ ] **Step 7: Remove empty old packages and old configs**

After `rg` proves no active imports remain:

```powershell
git rm experiments/circular_tracking/rl_envs/__init__.py
git rm experiments/circular_tracking/scripts/td3/__init__.py
git rm experiments/circular_tracking/config/hidden_td3_protocol.json
git rm experiments/circular_tracking/config/hidden_pid_frozen.json
```

Remove now-empty `config`, `rl_envs`, `scripts/td3`, `analysis` directories only if they contain no unrelated tracked files.

- [ ] **Step 8: Run the one focused PyBullet path verification**

```powershell
py -3.11 -m pytest tests/circular_tracking/pybullet_td3 -q
py -3.11 -m compileall experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/code
py -3.11 -m experiments.circular_tracking.pybullet_td3.studies.pid_residual_td3.code.training.tune_hidden_pid --help
py -3.11 -m experiments.circular_tracking.pybullet_td3.studies.pid_residual_td3.code.training.train_hidden_td3 --help
py -3.11 -m experiments.circular_tracking.pybullet_td3.studies.pid_residual_td3.code.evaluation.evaluate_hidden_td3 --help
py -3.11 -m experiments.circular_tracking.pybullet_td3.studies.pid_residual_td3.code.analysis.summarize_hidden_td3 --help
```

Expected: focused tests and compileall pass; all four CLIs parse help without creating an environment or run directory.

- [ ] **Step 9: Scan active source for obsolete paths and commit**

```powershell
$hits = git grep -n -I -E 'experiments\.circular_tracking\.(rl_envs|scripts\.td3)|experiments/circular_tracking/(config|rl_envs|scripts/td3)' -- `
  experiments/circular_tracking/pybullet_td3/studies tests/circular_tracking/pybullet_td3 gym_pybullet_drones/examples
if ($LASTEXITCODE -eq 0) { $hits; throw '活动源码仍引用旧路径' }
if ($LASTEXITCODE -ne 1) { throw "git grep失败：$LASTEXITCODE" }
git add -A experiments/circular_tracking tests/circular_tracking gym_pybullet_drones/examples
git diff --cached --check
git commit -m "refactor: organize pybullet td3 code and provenance"
```

## Task 8: 归档历史运行并建立当前阶段结论

**Files:**
- Move local and tracked: `results/hidden_disturbance_td3_paper/{smoke,stage_A,stage_B,protocol_v2,protocol_v2_1}`
- Archive: `stage_status.md`
- Create: archive README files
- Create: `stages/10_bootstrap_preflight/evidence/decision.json`
- Modify: `.gitignore`

- [ ] **Step 1: 记录原目录清单并增加 runs 忽略规则**

Append:

```gitignore
# PyBullet stage and archive local runs
experiments/circular_tracking/pybullet_td3/**/runs/*
!experiments/circular_tracking/pybullet_td3/**/runs/README.md
experiments/circular_tracking/pybullet_td3/**/runs/**/*.zip
experiments/circular_tracking/pybullet_td3/**/runs/**/*.pkl
experiments/circular_tracking/pybullet_td3/**/runs/**/*.npz
experiments/circular_tracking/pybullet_td3/**/runs/**/logs/
experiments/circular_tracking/pybullet_td3/**/runs/**/checkpoints/
experiments/circular_tracking/pybullet_td3/**/runs/**/trajectories/
```

Capture `git ls-files` for each old subtree and record count/total bytes before moving. Keep the list in ignored `tmp/layout-migration/` only.

- [ ] **Step 2: 从实际运行提交提取 v1.0.2 和 v2.0.0 协议快照**

Use Git archives so line endings and bytes come from the recorded commits rather than the current checkout:

```powershell
$sourcePath = 'experiments/circular_tracking/config/hidden_td3_protocol.json'
$snapshots = @(
    @{
        Label = 'v1_0_2'
        Commit = '3006bcce8dd944382305c42d0d37da26a366e48e'
        Target = 'experiments/circular_tracking/pybullet_td3/archive/20_hidden_disturbance_v1/protocol/hidden_td3_protocol.v1_0_2.json'
        Sha256 = 'e6edc37f6f89ec6684917f71f20444dd45b6e745f299b8ea6bf165d71e294359'
    },
    @{
        Label = 'v2_0_0'
        Commit = '1d77a30254c86b44c9706e9d4b38b66ca51c8d65'
        Target = 'experiments/circular_tracking/pybullet_td3/archive/30_hidden_disturbance_v2/protocol/hidden_td3_protocol.v2_0.json'
        Sha256 = '4b8bd9dc4031c3e682e4a78f137a9339c0f28201bd08a7d97b5f0b47bef1a796'
    }
)
foreach ($snapshot in $snapshots) {
    $zip = "tmp/layout-migration/protocol-$($snapshot.Label).zip"
    $extract = "tmp/layout-migration/protocol-$($snapshot.Label)"
    New-Item -ItemType Directory -Force (Split-Path -Parent $zip), $extract, (Split-Path -Parent $snapshot.Target) | Out-Null
    git archive --format=zip --output=$zip $snapshot.Commit -- $sourcePath
    if ($LASTEXITCODE -ne 0) { throw "无法导出协议：$($snapshot.Label)" }
    Expand-Archive -LiteralPath $zip -DestinationPath $extract
    Copy-Item -LiteralPath (Join-Path $extract $sourcePath) -Destination $snapshot.Target
    $actual = (Get-FileHash -LiteralPath $snapshot.Target -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $snapshot.Sha256) {
        throw "协议身份异常：$($snapshot.Label) expected=$($snapshot.Sha256) actual=$actual"
    }
}
```

The v2.1.0 snapshot extracted in Task 7 must still hash to `16781e621b316b2d8b3c9811cefd775b2e4ee2c931b275bcc059edc803d9f259`.

- [ ] **Step 3: Move each entire legacy directory with safe absolute-path checks**

Use this mapping:

```text
smoke/      -> archive/20_hidden_disturbance_v1/runs/legacy_layout/smoke/
stage_A/    -> archive/20_hidden_disturbance_v1/runs/legacy_layout/stage_A/
stage_B/    -> archive/20_hidden_disturbance_v1/runs/legacy_layout/stage_B/
protocol_v2/   -> archive/30_hidden_disturbance_v2/runs/legacy_layout/
protocol_v2_1/ -> archive/31_hidden_disturbance_v2_1/runs/legacy_layout/
```

Before each `Move-Item`, resolve source and target and require both to begin with the current worktree root. Create the target parent first; never build a deletion command from unverified strings.

- [ ] **Step 4: Copy old tracked small files into evidence and verify hashes**

For each path recorded by `git ls-files` before the move:

1. derive its relative path below the old subtree;
2. copy the moved file from `runs/legacy_layout/` to `evidence/legacy_layout/`;
3. compare source and evidence SHA-256;
4. stage only the evidence copy.

Do not alter JSON fields containing old paths, module names, commands, Git SHA or protocol versions.

- [ ] **Step 5: Archive old status and write protocol summaries**

Move the original `stage_status.md` unchanged to:

```text
experiments/circular_tracking/pybullet_td3/archive/historical_stage_status_2026-07-11.md
```

Create one README in each archive with:

- protocol identity;
- controller set;
- actual final decision;
- original Git SHA;
- `evidence/legacy_layout/` and local `runs/legacy_layout/` locations;
- a warning that archived JSON is not current status.

Record exactly these protocol identities:

```text
v1.0.2: smoke + Stage A + Stage B
v2.0.0: protocol_v2
v2.1.0: protocol_v2_1, Gate 3 NO-GO
```

- [ ] **Step 6: Record the current preflight NO-GO without copying results**

Create `stages/10_bootstrap_preflight/evidence/decision.json`:

```json
{
  "schema_version": 1,
  "stage_id": "10_bootstrap_preflight",
  "decision": "NO-GO",
  "source_protocol": "v2.1.0",
  "source_evidence": "../../../../../archive/31_hidden_disturbance_v2_1/evidence/legacy_layout/gate_3/gate_3_summary.json",
  "reason": "Direct TD3 post-update episode length collapsed in both training seeds; Stage A remains unauthorized."
}
```

Verify that the stage JSON statuses created in Task 4 still equal:

```text
00_foundation_and_pid: GO
10_bootstrap_preflight: NO-GO
20_stage_a_20k: blocked
30_stage_b_50k: not_started
40_stage_c_100k: not_started
50_final_evaluation: not_started
```

If any value differs, stop and inspect the migration diff; do not silently rewrite a scientific stage decision during evidence archiving.

- [ ] **Step 7: Verify all eight Replay Buffers survived and remain ignored**

```powershell
$replays = @(Get-ChildItem experiments/circular_tracking/pybullet_td3 -Recurse -File -Filter replay_buffer.pkl)
$bytes = ($replays | Measure-Object Length -Sum).Sum
if ($replays.Count -ne 8) { throw "Replay数量异常：$($replays.Count)" }
if ($bytes -ne 16864079016) { throw "Replay字节异常：$bytes" }
$trackedReplay = git ls-files | Select-String 'replay_buffer\.pkl$'
if ($trackedReplay) { throw 'Replay被意外跟踪' }
```

- [ ] **Step 8: Record the external 1.8 GiB Oracle result location without copying it**

Create `archive/10_oracle_pid_ff_pilot/runs/README.md` with the local source label, file count, total bytes and a note that the external main-worktree copy remains untouched. Do not put the machine absolute path in a public JSON; the local absolute path may be recorded only in the ignored migration inventory.

- [ ] **Step 9: Stage only compact evidence and commit**

```powershell
git add -A experiments/circular_tracking/results/hidden_disturbance_td3_paper experiments/circular_tracking/pybullet_td3 .gitignore
$bad = git diff --cached --name-only | Select-String '\.(pkl|zip|npz|pt|pth)$'
if ($bad) { $bad; throw '大训练产物进入暂存区' }
git diff --cached --check
git commit -m "refactor: archive pybullet protocol evidence by stage"
```

## Task 9: 完整退役悬停复现和定点控制研究

**Files:**
- Delete: the 24 tracked files named in Step 2
- Modify: `tests/test_examples.py`
- Preserve: `gym_pybullet_drones/tasks/hover/`, `HoverAviary.py`, `MultiHoverAviary.py`

- [ ] **Step 1: 写退役失败测试**

Extend `tests/project/test_repository_layout.py`:

```python
def test_retired_research_paths_are_absent():
    retired = (
        "experiments/hover_rl_reproduction",
        "experiments/hover_fixed_point",
        "gym_pybullet_drones/examples/learn.py",
        "gym_pybullet_drones/examples/play.py",
        "gym_pybullet_drones/examples/mrac.py",
    )
    for relative in retired:
        assert not (ROOT / relative).exists(), relative
```

Run and expect FAIL while the directories still exist:

```powershell
py -3.11 -m pytest tests/project/test_repository_layout.py::test_retired_research_paths_are_absent -v
```

- [ ] **Step 2: Delete the retired research and dedicated dependents**

Run these explicit removals; do not use wildcards and do not run `git clean`:

```powershell
git rm -r -- experiments/hover_rl_reproduction experiments/hover_fixed_point
git rm -- `
  gym_pybullet_drones/examples/learn.py `
  gym_pybullet_drones/examples/play.py `
  gym_pybullet_drones/examples/mrac.py `
  reproducibility/docker/Dockerfile.repro `
  tools/visualization/live_progress_viewer.py `
  tools/visualization/render_policy_scene.py `
  'docs/guides/PPO悬停复现说明_零基础.md' `
  docs/report_generators/create_visit_docx.py `
  docs/report_generators/create_training_workflow_materials.py `
  docs/report_generators/create_compact_training_ppt.py `
  'docs/reports/visit_overview/强化学习控制项目参观说明.md' `
  gym_pybullet_drones/assets/rl.gif `
  gym_pybullet_drones/assets/marl.gif
```

Delete the `test_learn()` function from `tests/test_examples.py`; retain `test_pid`, `test_pid_velocity` and `test_downwash` unchanged.

- [ ] **Step 3: Remove only the two known ignored caches after boundary verification**

```powershell
$root = (Resolve-Path .).Path
$cachePaths = @(
  'experiments/hover_rl_reproduction/__pycache__',
  'experiments/hover_rl_reproduction/scripts/__pycache__'
)
foreach ($relative in $cachePaths) {
    $absolute = [IO.Path]::GetFullPath((Join-Path $root $relative))
    if (-not $absolute.StartsWith($root + [IO.Path]::DirectorySeparatorChar)) { throw '缓存路径越界' }
    if (Test-Path -LiteralPath $absolute) { Remove-Item -LiteralPath $absolute -Recurse }
}
```

- [ ] **Step 4: Prove no active references remain**

```powershell
$hits = git grep -n -I -E '(hover_rl_reproduction|hover_fixed_point|Dockerfile\.repro|live_progress_viewer|render_policy_scene)' -- . `
  ':(exclude)docs/superpowers/specs/**' `
  ':(exclude)docs/superpowers/plans/**' `
  ':(exclude).research/execution_journal.jsonl' `
  ':(exclude)docs/project/research_history.md'
if ($LASTEXITCODE -eq 0) { $hits; throw '仍存在退役研究运行时引用' }
if ($LASTEXITCODE -ne 1) { throw "git grep失败：$LASTEXITCODE" }
```

- [ ] **Step 5: Verify generic hover capability remains**

```powershell
py -3.11 -m pytest tests/test_examples.py -v
py -3.11 -c "from gym_pybullet_drones.tasks.hover.envs.HoverAviary import HoverAviary; print(HoverAviary.__name__)"
```

Expected: remaining example tests pass and generic `HoverAviary` imports.

- [ ] **Step 6: Commit retirement**

```powershell
git add -A experiments/hover_rl_reproduction experiments/hover_fixed_point gym_pybullet_drones docs reproducibility tools tests/test_examples.py tests/project/test_repository_layout.py
git diff --cached --check
git commit -m "chore: retire hover-only research lines"
```

## Task 10: 重写根入口并一次性迁移执行状态

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `PROJECT_HANDOFF.md`
- Modify: `experiments/README.md`
- Modify: `experiments/circular_tracking/README.md`
- Modify: `docs/paper/README.md`
- Delete: `docs/paper/MORNING_STATUS.md`
- Delete atomically with state-path update: `PROJECT_STRUCTURE.md`, `RL_PAPER_EXECUTION_PLAN.md`, and the two copied 2026-07-10 plan/runbook sources
- Modify once: `.research/execution_state.json`
- Append once: `.research/execution_journal.jsonl`
- Create from state: `STATUS.md`

- [ ] **Step 1: Rewrite README as the human entry point**

The first screen of `README.md` must be:

```markdown
# 强化学习

本仓库集中保存四旋翼圆周跟踪中的两条正式研究线：MATLAB/Simulink圆周抗扰与残差强化学习，以及PyBullet中的PID-based Residual TD3。

| 研究线 | 平台 | 入口 | 当前状态 |
|---|---|---|---|
| MATLAB/Simulink圆周抗扰 | MATLAB/Simulink | `experiments/circular_tracking/matlab_simulink/` | 已完成多控制器、RL-v1和RL-v2/MPC研究 |
| PyBullet圆周跟踪 | Python/PyBullet | `experiments/circular_tracking/pybullet_td3/` | Bootstrap NO-GO，等待方法修订 |

当前进展见 [STATUS.md](STATUS.md)，稳定路线见 [ROADMAP.md](ROADMAP.md)，智能体规则见 [AGENTS.md](AGENTS.md)。
```

Keep package installation, PyBullet prerequisites and citation sections below this project navigation. Remove hover-reproduction and MRAC research promotion.

- [ ] **Step 2: Reduce AGENTS and HANDOFF to their confirmed roles**

`AGENTS.md` must preserve:

- durable recovery protocol;
- hidden-information and scientific-fairness rules;
- minimal-review/no-repeat-testing constraint;
- `.research/execution_state.json` as sole machine state;
- new read-first paths;
- archive immutability and no-training-during-layout rules.

Remove stale “not implemented” statements and retired-study sections. Move long failure explanations to `docs/project/research_history.md` and link them.

`PROJECT_HANDOFF.md` must contain only:

```text
project identity
two research lines
latest PyBullet NO-GO
MATLAB asset location
read-first order
single next action
links to history and protocol archive
```

- [ ] **Step 3: Rewrite experiment navigation**

`experiments/README.md` lists only `circular_tracking/`. `experiments/circular_tracking/README.md` presents the two sibling platforms and explicitly prohibits cross-platform numeric pooling. `docs/paper/README.md` links current status and labels old manuscripts as historical.

Delete `docs/paper/MORNING_STATUS.md` after moving any unique historical note to `docs/project/research_history.md`.

Now remove the four temporary source copies in the same uncommitted change set as the state-path update in Step 4:

```powershell
git rm -- PROJECT_STRUCTURE.md RL_PAPER_EXECUTION_PLAN.md `
  docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-paper-rebuild.md `
  docs/superpowers/plans/2026-07-10-hidden-disturbance-td3-parallel-runbook.md
```

- [ ] **Step 4: Update execution_state exactly once**

Use `apply_patch`, preserving all task decisions and historical verification payloads. Perform these exact active-field changes:

```text
project_name = 强化学习
active_research_line = PyBullet 圆周跟踪 / PID-based Residual TD3
plan_path = docs/projects/pybullet_td3/implementation_plan.md
runbook_path = docs/projects/pybullet_td3/parallel_runbook.md
protocol_path = experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/protocol/current.json
protocol_hash = 213c95cea1e7557319c3943946191c236b9eb84a7540ae9749d3d3b4306263bb
status_evidence = [experiments/circular_tracking/pybullet_td3/archive/31_hidden_disturbance_v2_1/evidence/legacy_layout/gate_3/gate_3_summary.json, .research/task_reports/task_6.md]
next_action.allowed_files = [experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/code/training/train_hidden_td3.py, experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/code/evaluation/evaluate_hidden_td3.py, tests/circular_tracking/pybullet_td3/test_hidden_td3_v2_safety.py, experiments/circular_tracking/pybullet_td3/studies/pid_residual_td3/protocol/current.json]
state_revision = previous value + 1
updated_at = current Asia/Shanghai ISO-8601 timestamp
```

Do not replace paths inside `last_verification`, task history, task reports or old journal records.

- [ ] **Step 5: Append one layout event to the journal**

Append one JSON line with these keys:

```json
{
  "event": "repository_layout_migrated",
  "state_revision": 250,
  "project_name": "强化学习",
  "old_layout_anchor": "layout-pre-migration-20260712",
  "current_protocol_status": "blocked_pending_method_revision",
  "training_started": false
}
```

Use the actual incremented revision if it is not 250, and add the execution timestamp. Do not rewrite prior journal lines.

- [ ] **Step 6: Generate and check STATUS**

```powershell
py -3.11 tools/project/render_status.py
py -3.11 tools/project/render_status.py --check
py -3.11 -m pytest tests/project/test_render_status.py -v
```

Expected: STATUS shows Gate 3 v2.1 NO-GO, Stage A unauthorized, the new evidence path and exactly one next action.

- [ ] **Step 7: Scan active docs for stale navigation**

```powershell
$hits = git grep -n -I -E '(RL_PAPER_EXECUTION_PLAN\.md|PROJECT_STRUCTURE\.md|PROJECT_LAYOUT\.json|MORNING_STATUS\.md|results/hidden_disturbance_td3_paper/stage_status\.md)' -- `
  README.md AGENTS.md PROJECT_HANDOFF.md STATUS.md ROADMAP.md experiments docs/project docs/projects docs/paper
if ($LASTEXITCODE -eq 0) { $hits; throw '活动文档仍引用旧入口' }
if ($LASTEXITCODE -ne 1) { throw "git grep失败：$LASTEXITCODE" }
```

- [ ] **Step 8: Commit root navigation and state**

```powershell
git add README.md AGENTS.md PROJECT_HANDOFF.md STATUS.md ROADMAP.md experiments/README.md experiments/circular_tracking/README.md docs/paper .research/execution_state.json .research/execution_journal.jsonl
git diff --cached --check
git commit -m "docs: align project entry points with canonical state"
```

## Task 11: Enforce repository layout, CI and file-size policy

**Files:**
- Modify: `tests/project/test_repository_layout.py`
- Modify: `.github/workflows/test.yml`
- Modify: `.gitignore`
- Modify: `pyproject.toml`
- Create: `reproducibility/README.md`
- Create: `tools/README.md`

- [ ] **Step 1: Extend the permanent layout contract tests**

Add to `tests/project/test_repository_layout.py`:

```python
import subprocess


def tracked_files():
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [Path(item.decode("utf-8")) for item in output.split(b"\0") if item]


def test_required_root_entries_are_visible():
    required = {
        ".github", ".research", "docs", "experiments", "gym_pybullet_drones",
        "reproducibility", "tests", "tools", "README.md", "AGENTS.md",
        "PROJECT_HANDOFF.md", "STATUS.md", "ROADMAP.md", "pyproject.toml",
    }
    assert required <= {path.name for path in ROOT.iterdir()}


def test_workspace_mirror_entries_are_absent():
    for name in ("gym-pybullet-drones", "research_papers", "wt-gpd"):
        assert not (ROOT / name).exists()


def test_nine_simulink_models_are_tracked():
    models = [
        path for path in tracked_files()
        if path.parts[:4] == ("experiments", "circular_tracking", "matlab_simulink", "models")
        and path.suffix == ".slx"
    ]
    assert len(models) == 9


def test_no_tracked_file_exceeds_50_mib():
    oversized = []
    for relative in tracked_files():
        path = ROOT / relative
        if path.is_file() and path.stat().st_size > 50 * 1024 * 1024:
            oversized.append((relative.as_posix(), path.stat().st_size))
    assert oversized == []
```

- [ ] **Step 2: Run layout tests**

```powershell
py -3.11 -m pytest tests/project -v
```

Expected: render-status and all layout tests PASS.

- [ ] **Step 3: Update CI for the canonical root**

Keep checkout/setup-python/install steps. Replace the test step with:

```yaml
    - name: Verify generated status
      run: python tools/project/render_status.py --check
    - name: Repository layout contract
      run: python -m pytest tests/project -v
    - name: Unit tests
      run: |
        python -m pytest tests/ -q
        rm -rf tmp/
```

The old machine-local frozen-PID test no longer requires a CI ignore because its exact source was archived outside `tests/` and validated at the migration anchor.

- [ ] **Step 4: Update package metadata without renaming the Python distribution**

Keep:

```toml
name = "gym-pybullet-drones"
packages = [{ include = "gym_pybullet_drones" }]
```

Update only the description and repository URL to explain that this distribution supports the broader《强化学习》research repository. Do not rename the import package.

- [ ] **Step 5: Normalize ignore rules and delete obsolete result exceptions**

Remove old exceptions for `results/hidden_disturbance_td3_paper`. Retain the new MATLAB artifacts and PyBullet `runs/` rules. Add a short `reproducibility/README.md` explaining reproducibility files after removal of the hover-only Dockerfile, and `tools/README.md` explaining remaining visualization/project utilities.

- [ ] **Step 6: Commit CI and policy enforcement**

```powershell
git add .github/workflows/test.yml .gitignore pyproject.toml tests/project reproducibility/README.md tools/README.md
git diff --cached --check
git commit -m "ci: enforce canonical reinforcement learning layout"
```

## Task 12: Run the single final local verification

**Files:**
- Verify only; no expected source edits

- [ ] **Step 1: Verify status and references**

```powershell
py -3.11 tools/project/render_status.py --check
py -3.11 -m pytest tests/project -q
```

Run the two active-reference scans from Tasks 7 and 9. Historical design, plan, archive, journal and task-report matches are allowed; active-code matches are not.

- [ ] **Step 2: Verify PyBullet once**

```powershell
py -3.11 -m pytest tests/circular_tracking/pybullet_td3 -q
py -3.11 -m compileall gym_pybullet_drones experiments/circular_tracking/pybullet_td3 tools/project
```

- [ ] **Step 3: Verify MATLAB assets without training**

```powershell
matlab -batch "root=fullfile(pwd,'experiments','circular_tracking','matlab_simulink'); addpath(root); setup_matlab_simulink_paths; f=dir(fullfile(root,'models','*.slx')); assert(numel(f)==9); for k=1:numel(f), load_system(fullfile(f(k).folder,f(k).name)); [~,n]=fileparts(f(k).name); close_system(n,0); end"
```

Do not rerun RL-v1/RL-v2 training or controller comparison.

- [ ] **Step 4: Run the final full Python suite once**

```powershell
py -3.11 -m pytest tests -q
```

Expected: all current tests pass. Do not start another review/fix loop for warnings unrelated to the layout migration.

- [ ] **Step 5: Verify large files, Git objects and clean status**

```powershell
$replays = @(Get-ChildItem experiments/circular_tracking/pybullet_td3 -Recurse -File -Filter replay_buffer.pkl)
$bytes = ($replays | Measure-Object Length -Sum).Sum
if ($replays.Count -ne 8 -or $bytes -ne 16864079016) { throw 'Replay基线不匹配' }

$oversized = git ls-tree -r -l HEAD | Where-Object {
    $_ -match '^\d+\s+blob\s+\S+\s+(\d+)\t' -and [int64]$Matches[1] -gt 50MB
}
if ($oversized) { $oversized; throw 'Git历史中新增超过50MiB的blob' }

git diff --check
git status --short --branch
```

Expected: eight Replay Buffers remain local/ignored, no oversized tracked file, no diff errors, worktree clean.

- [ ] **Step 6: 折叠本地检查点为一个公开迁移提交**

Preserve the granular local commits on a backup branch, then make one public migration commit on top of the pre-migration tag. `--soft` changes only commit/index state; it does not rewrite working-tree files. Prove the verified tree is unchanged:

```powershell
$granularHead = (git rev-parse HEAD).Trim()
$verifiedTree = (git rev-parse 'HEAD^{tree}').Trim()
git branch archive/layout-migration-checkpoints-20260712 $granularHead
git reset --soft layout-pre-migration-20260712
git diff --cached --check
git commit -m "refactor: organize reinforcement learning research repository"
$publicationTree = (git rev-parse 'HEAD^{tree}').Trim()
if ($publicationTree -ne $verifiedTree) { throw '折叠提交改变了已验证文件树' }
if (git status --porcelain) { throw '折叠提交后工作区不干净' }
```

Expected: the backup branch points to the granular checkpoint history; current HEAD contains one migration commit after `layout-pre-migration-20260712`; its tree SHA equals the already verified tree SHA.

- [ ] **Step 7: Tag the verified publication commit**

```powershell
git tag -a layout-migration-verified-20260712 -m "Verified reinforcement learning repository layout"
```

## Task 13: Publish the canonical root to GitHub and verify Actions

**Files:**
- Remote-only operation after all local verification passes

Run Steps 1–5 in one PowerShell session so the credential header, lease SHA and published SHA remain in memory. Never print `$pass`, `$pair` or `$headers`.

- [ ] **Step 1: Preserve the current three-folder remote snapshot**

Read the current remote `main` SHA and create `archive/workspace-mirror-20260712` through the GitHub API. Obtain credentials from Git Credential Manager without printing the secret:

```powershell
$repo = 'magictierwheel/TD3'
$lines = "protocol=https`nhost=github.com`npath=magictierwheel/TD3.git`n`n" | git credential fill
$user = ($lines | Where-Object { $_ -like 'username=*' }).Substring(9)
$pass = ($lines | Where-Object { $_ -like 'password=*' }).Substring(9)
$pair = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$user`:$pass"))
$headers = @{ Authorization="Basic $pair"; Accept='application/vnd.github+json'; 'X-GitHub-Api-Version'='2022-11-28' }
$ref = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$repo/git/ref/heads/main"
$remoteBefore = $ref.object.sha
$body = @{ ref='refs/heads/archive/workspace-mirror-20260712'; sha=$remoteBefore } | ConvertTo-Json
try {
    Invoke-RestMethod -Method Post -Headers $headers -Uri "https://api.github.com/repos/$repo/git/refs" -Body $body -ContentType 'application/json'
} catch {
    $existing = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$repo/git/ref/heads/archive/workspace-mirror-20260712"
    if ($existing.object.sha -ne $remoteBefore) { throw }
}
```

- [ ] **Step 2: Attempt a lease-protected Git push**

```powershell
$localHead = (git rev-parse HEAD).Trim()
$localTree = (git rev-parse "$localHead^{tree}").Trim()
git push td3 HEAD:refs/heads/main --force-with-lease=refs/heads/main:$remoteBefore
if ($LASTEXITCODE -eq 0) {
    $publishedSha = $localHead
    $publishMode = 'git-force-with-lease'
} else {
    $publishedSha = $null
    $publishMode = 'git-data-api-required'
}
```

Expected: the lease-protected push succeeds and never uses bare `--force`. If HTTPS transport is reset, leave `$publishedSha` null and run Step 3 once instead of retrying indefinitely.

- [ ] **Step 3: Git Data API fallback for a transport reset**

Run this only when Step 2 left `$publishedSha` null. It uploads the exact indexed Git blobs, verifies every returned blob SHA, builds a complete tree without `base_tree`, proves that the API tree SHA equals the local HEAD tree SHA, creates a commit whose parent is `$remoteBefore`, rechecks the lease, and advances `main` with `force=false`.

```powershell
if (-not $publishedSha) {
    $current = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$repo/git/ref/heads/main"
    if ($current.object.sha -ne $remoteBefore) {
        throw "远端main已并发变化：expected=$remoteBefore actual=$($current.object.sha)"
    }
    if (git status --porcelain) { throw 'API发布要求干净工作区' }

    function Get-GitBlobBytes {
        param(
            [Parameter(Mandatory=$true)][string]$Sha,
            [Parameter(Mandatory=$true)][string]$WorkingDirectory
        )
        $start = [Diagnostics.ProcessStartInfo]::new()
        $start.FileName = 'git'
        $start.WorkingDirectory = $WorkingDirectory
        $start.UseShellExecute = $false
        $start.RedirectStandardOutput = $true
        $start.RedirectStandardError = $true
        [void]$start.ArgumentList.Add('cat-file')
        [void]$start.ArgumentList.Add('blob')
        [void]$start.ArgumentList.Add($Sha)
        $process = [Diagnostics.Process]::new()
        $process.StartInfo = $start
        [void]$process.Start()
        $memory = [IO.MemoryStream]::new()
        $process.StandardOutput.BaseStream.CopyTo($memory)
        $errorText = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) {
            $memory.Dispose()
            $process.Dispose()
            throw "git cat-file failed for $Sha`: $errorText"
        }
        $bytes = $memory.ToArray()
        $memory.Dispose()
        $process.Dispose()
        return ,$bytes
    }

    $worktree = (Resolve-Path .).Path
    $indexLines = @(git -c core.quotepath=false ls-files --stage)
    if ($LASTEXITCODE -ne 0 -or $indexLines.Count -eq 0) { throw '无法读取Git索引' }
    $treeEntries = [Collections.Generic.List[object]]::new()
    foreach ($line in $indexLines) {
        if ($line -notmatch '^(?<mode>\d{6}) (?<sha>[0-9a-f]{40}) (?<stage>\d)\t(?<path>.+)$') {
            throw "无法解析索引记录：$line"
        }
        $mode = $Matches.mode
        $blobSha = $Matches.sha
        $stage = $Matches.stage
        $trackedPath = $Matches.path
        if ($stage -ne '0') { throw "索引存在未合并条目：$trackedPath" }
        if ($mode -notin @('100644', '100755', '120000')) {
            throw "API发布不支持Git mode $mode：$trackedPath"
        }
        $sizeText = git cat-file -s $blobSha
        if ($LASTEXITCODE -ne 0) { throw "无法读取blob大小：$trackedPath" }
        $size = [int64]$sizeText
        if ($size -gt 50MB) { throw "blob超过50MiB：$trackedPath ($size bytes)" }
        [byte[]]$bytes = Get-GitBlobBytes -Sha $blobSha -WorkingDirectory $worktree
        if ($bytes.LongLength -ne $size) { throw "blob读取长度不匹配：$trackedPath" }
        $blobBody = @{
            content = [Convert]::ToBase64String($bytes)
            encoding = 'base64'
        } | ConvertTo-Json -Compress
        $apiBlob = Invoke-RestMethod -Method Post -Headers $headers `
            -Uri "https://api.github.com/repos/$repo/git/blobs" `
            -Body $blobBody -ContentType 'application/json'
        if ($apiBlob.sha -ne $blobSha) {
            throw "GitHub blob SHA不匹配：$trackedPath local=$blobSha remote=$($apiBlob.sha)"
        }
        $treeEntries.Add([ordered]@{
            path = $trackedPath
            mode = $mode
            type = 'blob'
            sha = $apiBlob.sha
        })
    }

    $treeBody = @{ tree = @($treeEntries) } | ConvertTo-Json -Depth 5 -Compress
    $apiTree = Invoke-RestMethod -Method Post -Headers $headers `
        -Uri "https://api.github.com/repos/$repo/git/trees" `
        -Body $treeBody -ContentType 'application/json'
    if ($apiTree.sha -ne $localTree) {
        throw "完整树SHA不匹配：local=$localTree api=$($apiTree.sha)"
    }

    $commitBody = @{
        message = 'Publish canonical reinforcement learning repository layout'
        tree = $apiTree.sha
        parents = @($remoteBefore)
    } | ConvertTo-Json -Depth 4 -Compress
    $apiCommit = Invoke-RestMethod -Method Post -Headers $headers `
        -Uri "https://api.github.com/repos/$repo/git/commits" `
        -Body $commitBody -ContentType 'application/json'

    $beforePatch = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$repo/git/ref/heads/main"
    if ($beforePatch.object.sha -ne $remoteBefore) {
        throw "PATCH前远端main已变化：expected=$remoteBefore actual=$($beforePatch.object.sha)"
    }
    $patchBody = @{ sha = $apiCommit.sha; force = $false } | ConvertTo-Json -Compress
    $patched = Invoke-RestMethod -Method Patch -Headers $headers `
        -Uri "https://api.github.com/repos/$repo/git/refs/heads/main" `
        -Body $patchBody -ContentType 'application/json'
    if ($patched.object.sha -ne $apiCommit.sha) { throw 'GitHub main引用未指向API提交' }
    $publishedSha = $apiCommit.sha
    $publishMode = 'git-data-api'
}
```

- [ ] **Step 4: Verify the remote root and size policy**

```powershell
$branch = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$repo/branches/main"
$sha = $branch.commit.sha
if ($sha -ne $publishedSha) { throw "远端main SHA异常：expected=$publishedSha actual=$sha" }
$archiveRef = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$repo/git/ref/heads/archive/workspace-mirror-20260712"
if ($archiveRef.object.sha -ne $remoteBefore) { throw '远端archive分支未保留原main' }
$root = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$repo/contents?ref=main"
$names = @($root.name)
$required = @('.github','.research','docs','experiments','gym_pybullet_drones','reproducibility','tests','tools','README.md','AGENTS.md','PROJECT_HANDOFF.md','STATUS.md','ROADMAP.md','pyproject.toml')
foreach ($name in $required) { if ($name -notin $names) { throw "远端根缺少：$name" } }
foreach ($name in @('gym-pybullet-drones','research_papers','wt-gpd','PROJECT_LAYOUT.json','PROJECT_STRUCTURE.md','RL_PAPER_EXECUTION_PLAN.md')) {
    if ($name -in $names) { throw "远端仍有旧根条目：$name" }
}
$commit = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$repo/git/commits/$sha"
if ($commit.tree.sha -ne $localTree) { throw "远端树与本地HEAD树不同：$($commit.tree.sha)" }
$tree = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$repo/git/trees/$($commit.tree.sha)?recursive=1"
if ($tree.truncated) { throw 'GitHub递归树响应被截断，无法完成验收' }
$large = @($tree.tree | Where-Object { $_.type -eq 'blob' -and $_.size -gt 50MB })
if ($large) { $large; throw 'GitHub存在超过50MiB的文件' }
```

- [ ] **Step 5: Verify the new commit's GitHub Actions run**

Poll the Actions API at intervals no longer than 20 seconds, for at most five minutes. Require a workflow run whose `head_sha` equals the new remote `main` SHA and whose conclusion is `success`. A historical green run does not count.

```powershell
$deadline = (Get-Date).AddMinutes(5)
$run = $null
do {
    $runs = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$repo/actions/runs?branch=main&per_page=20"
    $run = $runs.workflow_runs | Where-Object head_sha -eq $sha | Select-Object -First 1
    if ($run -and $run.status -eq 'completed') { break }
    Start-Sleep -Seconds 20
} while ((Get-Date) -lt $deadline)
if (-not $run) { throw '五分钟内未发现新main的Actions运行' }
if ($run.status -ne 'completed' -or $run.conclusion -ne 'success') {
    throw "Actions未通过：status=$($run.status) conclusion=$($run.conclusion)"
}
$actionsUrl = $run.html_url
```

## Completion report

Report:

- local verified tag and HEAD;
- remote `main` SHA and archive branch SHA;
- root entries;
- MATLAB model count and hashes verified;
- Replay count/bytes preserved and ignored;
- Python/MATLAB test results;
- GitHub Actions URL and conclusion;
- confirmation that no training was run.
