"""Render a trained HoverAviary policy into screenshot and video assets.

The script runs headless in PyBullet DIRECT mode, steps a saved PPO policy, and
uses PyBullet's virtual camera to capture frames. It also writes a compact GIF
when Pillow is available.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pybullet as p
from PIL import Image, ImageDraw, ImageFont
from stable_baselines3 import PPO

from gym_pybullet_drones.tasks.hover.envs.HoverAviary import HoverAviary
from gym_pybullet_drones.utils.enums import ActionType, ObservationType


def _as_rgb(width: int, height: int, rgba) -> Image.Image:
    array = np.reshape(np.asarray(rgba, dtype=np.uint8), (height, width, 4))
    return Image.fromarray(array[:, :, :3], mode="RGB")


def _draw_overlay(frame: Image.Image, step: int, z: float, reward: float) -> Image.Image:
    canvas = frame.copy()
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rectangle((18, 18, 430, 104), fill=(255, 255, 255, 205), outline=(30, 64, 100, 200), width=2)
    font = ImageFont.load_default()
    lines = [
        "gym-pybullet-drones | PPO hover policy",
        f"step: {step:03d}    z: {z:.3f} m    target z: 1.000 m",
        f"reward: {reward:.3f}    action: one_d_rpm",
    ]
    y = 28
    for line in lines:
        draw.text((30, y), line, fill=(10, 28, 45), font=font)
        y += 24
    return canvas


def _capture_frame(env: HoverAviary, width: int, height: int, step: int, z: float, reward: float) -> Image.Image:
    # Track the drone from an oblique camera angle so the floor grid and height
    # change remain visible even without an interactive GUI.
    target = [0.0, 0.0, max(0.45, min(1.0, z + 0.2))]
    view = p.computeViewMatrixFromYawPitchRoll(
        cameraTargetPosition=target,
        distance=1.05,
        yaw=38,
        pitch=-20,
        roll=0,
        upAxisIndex=2,
        physicsClientId=env.CLIENT,
    )
    projection = p.computeProjectionMatrixFOV(
        fov=34,
        aspect=float(width) / float(height),
        nearVal=0.05,
        farVal=20.0,
    )
    _, _, rgba, _, _ = p.getCameraImage(
        width=width,
        height=height,
        viewMatrix=view,
        projectionMatrix=projection,
        renderer=p.ER_BULLET_HARDWARE_OPENGL,
        physicsClientId=env.CLIENT,
    )
    return _draw_overlay(_as_rgb(width, height, rgba), step, z, reward)


def render_policy(
    model_path: Path,
    output_dir: Path,
    steps: int,
    fps: int,
    width: int,
    height: int,
    stride: int,
    seed: int,
) -> dict[str, str | int | float]:
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    model = PPO.load(str(model_path))
    env = HoverAviary(gui=False, obs=ObservationType.KIN, act=ActionType.ONE_D_RPM)
    obs, _ = env.reset(seed=seed, options={})

    frames: list[Image.Image] = []
    rows: list[dict[str, float | int | bool]] = []
    screenshot_path = output_dir / "policy_scene_screenshot.png"

    for step in range(steps):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, _ = env.step(action)
        obs_flat = np.asarray(obs, dtype=float).reshape(-1)
        reward_value = float(np.asarray(reward).reshape(-1)[0])
        z = float(obs_flat[2])

        rows.append(
            {
                "step": step,
                "x": float(obs_flat[0]),
                "y": float(obs_flat[1]),
                "z": z,
                "reward": reward_value,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
            }
        )

        if step % stride == 0:
            frame = _capture_frame(env, width, height, step, z, reward_value)
            frame_path = frames_dir / f"frame_{len(frames):04d}.png"
            frame.save(frame_path)
            frames.append(frame)
            # Keep updating the representative screenshot so the final file
            # shows the learned policy after it has had time to act.
            if step >= int(steps * 0.65):
                frame.save(screenshot_path)

        if terminated or truncated:
            break

    env.close()

    if frames and not screenshot_path.exists():
        frames[min(len(frames) // 2, len(frames) - 1)].save(screenshot_path)

    gif_path = output_dir / "policy_scene_animation.gif"
    if frames:
        frame_duration_ms = int(1000 / fps)
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            duration=frame_duration_ms,
            loop=0,
            optimize=False,
        )

    summary = {
        "model_path": str(model_path),
        "steps_run": len(rows),
        "frames": len(frames),
        "fps": fps,
        "screenshot": str(screenshot_path),
        "gif": str(gif_path),
        "final_z": rows[-1]["z"] if rows else float("nan"),
        "final_reward": rows[-1]["reward"] if rows else float("nan"),
    }
    (output_dir / "policy_scene_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/visualizations/hover_policy_scene_short"),
    )
    parser.add_argument("--steps", type=int, default=240)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--stride", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    summary = render_policy(**vars(args))
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
