"""Run a traceable TD3 training/evaluation batch for the circular-tracking paper."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

from experiments.circular_tracking.scripts.td3.evaluate_td3_controllers import (
    SUMMARY_COLUMNS,
    run_rollout,
    write_csv,
)


RL_CONTROLLERS = {
    "direct_td3",
    "residual_td3",
    "disturbance_aware_residual_td3",
    "disturbance_aware_residual_td3_no_gate",
}


def train_controller(
    controller: str,
    seed: int,
    args: argparse.Namespace,
    run_dir: Path,
) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    if controller == "direct_td3":
        command = [
            sys.executable,
            "-m",
            "experiments.circular_tracking.scripts.td3.train_direct_td3",
        ]
    else:
        command = [
            sys.executable,
            "-m",
            "experiments.circular_tracking.scripts.td3.train_residual_td3",
            "--mode",
            controller,
        ]
    command.extend(
        [
            "--scenario",
            args.training_scenario,
            "--scenario-set",
            args.training_scenario_set,
            "--total-timesteps",
            str(args.train_timesteps),
            "--seed",
            str(seed),
            "--duration-sec",
            str(args.train_duration_sec),
            "--radius",
            str(args.radius),
            "--period",
            str(args.period),
            "--height",
            str(args.height),
            "--residual-gate-min",
            str(args.residual_gate_min),
            "--output-folder",
            str(run_dir),
        ]
    )
    if args.checkpoint_freq > 0:
        command.extend(["--checkpoint-freq", str(args.checkpoint_freq)])
    if controller != "direct_td3" and args.warm_start_samples > 0 and args.warm_start_epochs > 0:
        command.extend(
            [
                "--warm-start-samples",
                str(args.warm_start_samples),
                "--warm-start-epochs",
                str(args.warm_start_epochs),
                "--warm-start-batch-size",
                str(args.warm_start_batch_size),
                "--warm-start-scenario-set",
                args.warm_start_scenario_set,
            ]
        )
        if args.warm_start_retain_freq > 0:
            command.extend(
                [
                    "--warm-start-retain-freq",
                    str(args.warm_start_retain_freq),
                    "--warm-start-retain-updates",
                    str(args.warm_start_retain_updates),
                    "--warm-start-retain-batch-size",
                    str(args.warm_start_retain_batch_size),
                    "--warm-start-retain-start",
                    str(args.warm_start_retain_start),
                ]
            )
    subprocess.run(command, check=True)
    model_path = run_dir / "model.zip"
    if not model_path.exists():
        raise FileNotFoundError(f"Training did not produce {model_path}")
    return model_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", default="pilot_multiseed")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("experiments/circular_tracking/results/td3_residual_paper"),
    )
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument(
        "--train-controllers",
        nargs="+",
        default=[
            "direct_td3",
            "residual_td3",
            "disturbance_aware_residual_td3",
            "disturbance_aware_residual_td3_no_gate",
        ],
    )
    parser.add_argument(
        "--eval-controllers",
        nargs="+",
        default=[
            "pid",
            "pid_ff",
            "direct_td3",
            "residual_td3",
            "disturbance_aware_residual_td3",
            "disturbance_aware_residual_td3_no_gate",
        ],
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=["standard", "wind", "thermal", "dust", "compound"],
    )
    parser.add_argument("--training-scenario", default="standard")
    parser.add_argument(
        "--training-scenario-set",
        choices=["train", "validation", "test", "unseen"],
        default="train",
    )
    parser.add_argument("--train-timesteps", type=int, default=1000)
    parser.add_argument("--train-duration-sec", type=float, default=5.0)
    parser.add_argument("--eval-duration-sec", type=float, default=30.0)
    parser.add_argument(
        "--checkpoint-freq",
        type=int,
        default=0,
        help="Save TD3 checkpoints every N environment steps during training. Disabled when 0.",
    )
    parser.add_argument("--warm-start-samples", type=int, default=0)
    parser.add_argument("--warm-start-epochs", type=int, default=0)
    parser.add_argument("--warm-start-batch-size", type=int, default=256)
    parser.add_argument("--warm-start-retain-freq", type=int, default=0)
    parser.add_argument("--warm-start-retain-updates", type=int, default=1)
    parser.add_argument("--warm-start-retain-batch-size", type=int, default=256)
    parser.add_argument("--warm-start-retain-start", type=int, default=0)
    parser.add_argument(
        "--warm-start-scenario-set",
        choices=["train", "validation", "test", "unseen"],
        default="train",
    )
    parser.add_argument("--radius", type=float, default=0.3)
    parser.add_argument("--period", type=float, default=10.0)
    parser.add_argument("--height", type=float, default=1.0)
    parser.add_argument("--residual-gate-min", type=float, default=0.0)
    parser.add_argument("--skip-training", action="store_true")
    parser.add_argument(
        "--model-runs-root",
        type=Path,
        default=None,
        help="Existing runs directory to reuse when --skip-training is set.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    batch_root = args.output_root / args.run_name
    runs_root = batch_root / "runs"
    eval_root = batch_root / "eval"
    model_runs_root = args.model_runs_root or runs_root
    runs_root.mkdir(parents=True, exist_ok=True)
    eval_root.mkdir(parents=True, exist_ok=True)

    config = vars(args).copy()
    config["output_root"] = str(args.output_root)
    config["model_runs_root"] = str(args.model_runs_root) if args.model_runs_root else None
    (batch_root / "config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    model_paths: Dict[tuple[str, int], Path] = {}
    for controller in args.train_controllers:
        if controller not in RL_CONTROLLERS:
            raise ValueError(f"Unsupported train controller: {controller}")
        for seed in args.seeds:
            run_dir = (model_runs_root if args.skip_training else runs_root) / f"{controller}_seed{seed}"
            model_path = run_dir / "model.zip"
            if args.skip_training:
                if not model_path.exists():
                    raise FileNotFoundError(f"--skip-training requested but missing {model_path}")
            else:
                model_path = train_controller(controller, seed, args, run_dir)
            model_paths[(controller, seed)] = model_path

    summary_rows: List[Dict[str, object]] = []
    for controller in args.eval_controllers:
        for scenario in args.scenarios:
            for seed in args.seeds:
                model_path = model_paths.get((controller, seed))
                summary_rows.append(
                    run_rollout(
                        controller=controller,
                        scenario=scenario,
                        seed=seed,
                        duration_sec=args.eval_duration_sec,
                        output_folder=eval_root,
                        model_path=model_path,
                        radius=args.radius,
                        period=args.period,
                        height=args.height,
                        residual_gate_min=args.residual_gate_min,
                    )
                )

    summary_path = eval_root / "summary_metrics.csv"
    write_csv(summary_path, SUMMARY_COLUMNS, summary_rows)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "experiments.circular_tracking.scripts.td3.summarize_td3_results",
            "--summary-metrics",
            str(summary_path),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
