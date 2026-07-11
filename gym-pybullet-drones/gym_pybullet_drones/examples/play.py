"""Compatibility wrapper for playing a trained PPO hover policy."""

if __name__ == "__main__":
    import runpy

    runpy.run_module(
        "experiments.hover_rl_reproduction.scripts.play_hover_policy",
        run_name="__main__",
    )
else:
    from experiments.hover_rl_reproduction.scripts.play_hover_policy import *  # noqa: F401,F403
