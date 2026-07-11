# Quadrotor RL Residual Policy Summary

Generated: 2026-06-22 00:50:12

Algorithm: cross-entropy direct policy search over a compact residual actor.

Best cost: 0.431139

Best weights:

| weight | value | meaning |
|---|---:|---|
| w_drag | 0.969041 | cancel drag acceleration from wind-relative motion |
| w_thermal | 1.057147 | cancel vertical thermal updraft |
| w_thrust | 1.028591 | compensate rotor thrust loss f_T |
| w_tau_xy | 0.810672 | compensate roll/pitch torque loss |
| w_tau_yaw | 0.738009 | compensate yaw torque loss f_Q |

Training evaluations: 56 candidates.
