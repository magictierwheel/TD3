"""Compatibility wrapper for the MRAC fixed-point hover example."""

if __name__ == "__main__":
    import runpy

    runpy.run_module(
        "experiments.hover_fixed_point.scripts.adaptive_mrac.run_mrac_fixed_point",
        run_name="__main__",
    )
else:
    from experiments.hover_fixed_point.scripts.adaptive_mrac.run_mrac_fixed_point import *  # noqa: F401,F403
