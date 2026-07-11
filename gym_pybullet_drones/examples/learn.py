"""Compatibility wrapper for the PPO hover training example."""

if __name__ == "__main__":
    import runpy

    runpy.run_module(
        "experiments.hover_rl_reproduction.scripts.learn_hover_ppo",
        run_name="__main__",
    )
else:
    from experiments.hover_rl_reproduction.scripts.learn_hover_ppo import *  # noqa: F401,F403
