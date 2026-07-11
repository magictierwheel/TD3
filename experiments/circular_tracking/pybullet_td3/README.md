# PyBullet TD3 research line

This is the numerical sibling research line for circular tracking in PyBullet. The `common/` package is reserved for shared, protocol-stable utilities; `studies/` contains isolated study implementations and their staged evidence boundaries.

The current study is `studies/pid_residual_td3/`, which scaffolds PID, direct TD3, and PID-residual TD3 comparisons without fabricating runs, metrics, manifests, or model files.
