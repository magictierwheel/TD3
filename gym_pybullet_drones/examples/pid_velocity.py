"""Compatibility wrapper for the velocity-input periodic tracking example."""

if __name__ == "__main__":
    import runpy

    runpy.run_module(
        "experiments.circular_tracking.pybullet_td3.common.examples.velocity_input.run_velocity_input_periodic",
        run_name="__main__",
    )
else:
    from experiments.circular_tracking.pybullet_td3.common.examples.velocity_input.run_velocity_input_periodic import *  # noqa: F401,F403
