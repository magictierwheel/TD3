"""Compatibility wrapper for the position-PID circular tracking example."""

if __name__ == "__main__":
    import runpy

    runpy.run_module(
        "experiments.circular_tracking.scripts.position_pid.run_position_pid_circle",
        run_name="__main__",
    )
else:
    from experiments.circular_tracking.scripts.position_pid.run_position_pid_circle import *  # noqa: F401,F403
