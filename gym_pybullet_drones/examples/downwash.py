"""Compatibility wrapper for the downwash periodic tracking example."""

if __name__ == "__main__":
    import runpy

    runpy.run_module(
        "experiments.circular_tracking.pybullet_td3.common.examples.downwash_periodic.run_downwash_periodic",
        run_name="__main__",
    )
else:
    from experiments.circular_tracking.pybullet_td3.common.examples.downwash_periodic.run_downwash_periodic import *  # noqa: F401,F403
