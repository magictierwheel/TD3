> [!NOTE]
> 这些文献笔记来自旧路线，可继续作为检索起点，但 revised paper 必须围绕 unknown disturbance、sample efficiency、safe residual learning 和公平信息边界重新组织，并补充传统鲁棒控制基线文献。

# Related Work Notes

This file records the starting related-work set for the PyBullet circular-tracking residual TD3 paper. Publication metadata was checked on 2026-07-10. arXiv items are marked as preprints and should not be presented as peer-reviewed publications unless their status changes.

## Core References

### PID-DRL Wind Disturbance Rejection

- Citation key: `Ma2024DronesWindDRL`
- Status: journal article
- Source: Drones, 2024, 8(11), 632
- DOI: `10.3390/drones8110632`
- URL: https://www.mdpi.com/2504-446X/8/11/632
- Authors: Qun Ma, Yibo Wu, Muhammad Usman Shoukat, Yukai Yan, Jun Wang, Long Yang, Fuwu Yan, Lirong Yan
- Method keywords: PID-DRL, DDPG, wind field model, wind disturbance rejection, trajectory tracking
- Relation to this paper: Supports the motivation that wind-disturbed UAV control benefits from combining classical control and learning-based compensation. Our difference is residual TD3 for circular tracking under compound wind/thermal/dust disturbances, with explicit ablations for disturbance observations and safety gating.

BibTeX draft:

```bibtex
@article{Ma2024DronesWindDRL,
  title = {Deep Reinforcement Learning-Based Wind Disturbance Rejection Control Strategy for UAV},
  author = {Ma, Qun and Wu, Yibo and Shoukat, Muhammad Usman and Yan, Yukai and Wang, Jun and Yang, Long and Yan, Fuwu and Yan, Lirong},
  journal = {Drones},
  volume = {8},
  number = {11},
  pages = {632},
  year = {2024},
  doi = {10.3390/drones8110632}
}
```

### Continual RL For Wind-Disturbed Quadrotor Tracking

- Citation key: `Liu2025SensorsContinualQuadrotor`
- Status: journal article
- Source: Sensors, 2025, 25(16), 4895
- DOI: `10.3390/s25164895`
- URL: https://www.mdpi.com/1424-8220/25/16/4895
- Authors: Yanhui Liu, Lina Hao, Shuopeng Wang, Xu Wang
- Method keywords: continual reinforcement learning, PPO, wind disturbance, trajectory tracking, catastrophic forgetting
- Relation to this paper: Useful for framing adaptability under time-varying wind. Our work focuses less on continual adaptation and more on residual structure, compound disturbances, and traceable ablation metrics.

BibTeX draft:

```bibtex
@article{Liu2025SensorsContinualQuadrotor,
  title = {Trajectory Tracking Controller for Quadrotor by Continual Reinforcement Learning in Wind-Disturbed Environment},
  author = {Liu, Yanhui and Hao, Lina and Wang, Shuopeng and Wang, Xu},
  journal = {Sensors},
  volume = {25},
  number = {16},
  pages = {4895},
  year = {2025},
  doi = {10.3390/s25164895}
}
```

### Residual RL For Cascaded PID Quadcopters

- Citation key: `Ishihara2023ResidualWind`
- Status: arXiv preprint
- arXiv: `2308.01648`
- DOI: `10.48550/arXiv.2308.01648`
- URL: https://arxiv.org/abs/2308.01648
- Authors: Yu Ishihara, Yuichi Hazama, Kousuke Suzuki, Jerry Jun Yokono, Kohtaro Sabe, Kenta Kawamoto
- Method keywords: residual reinforcement learning, cascaded PID, wind resistance, sim-to-real
- Relation to this paper: Closest conceptual reference for preserving a conventional controller and learning a residual correction. Our contribution should emphasize circular tracking, compound disturbance design, TD3-specific training/evaluation, and safety-gate ablation.

BibTeX draft:

```bibtex
@misc{Ishihara2023ResidualWind,
  title = {Improving Wind Resistance Performance of Cascaded PID Controlled Quadcopters using Residual Reinforcement Learning},
  author = {Ishihara, Yu and Hazama, Yuichi and Suzuki, Kousuke and Yokono, Jerry Jun and Sabe, Kohtaro and Kawamoto, Kenta},
  year = {2023},
  eprint = {2308.01648},
  archivePrefix = {arXiv},
  primaryClass = {cs.RO},
  doi = {10.48550/arXiv.2308.01648}
}
```

### Cascaded TD3-PID Hybrid Quadrotor Controller

- Citation key: `Zhang2026CascadedTD3PID`
- Status: arXiv preprint, version 2 as of 2026-05-13
- arXiv: `2604.13505`
- DOI: `10.48550/arXiv.2604.13505`
- URL: https://arxiv.org/abs/2604.13505
- Authors: Yukang Zhang, Shuqi Chai, Yuhang Zhang, Danlan Huang, Quanbo Ge
- Method keywords: TD3-PID, cascaded hybrid control, disturbance observer, wind disturbance, ablation
- Relation to this paper: Important comparator for TD3/PID hybrid framing. Our planned method differs by using a residual TD3 correction with explicit disturbance observations and a safety gate, evaluated on compound disturbance scenarios rather than wind alone.

BibTeX draft:

```bibtex
@misc{Zhang2026CascadedTD3PID,
  title = {Cascaded TD3-PID Hybrid Controller for Quadrotor Trajectory Tracking in Wind Disturbance Environments},
  author = {Zhang, Yukang and Chai, Shuqi and Zhang, Yuhang and Huang, Danlan and Ge, Quanbo},
  year = {2026},
  eprint = {2604.13505},
  archivePrefix = {arXiv},
  primaryClass = {eess.SY},
  doi = {10.48550/arXiv.2604.13505}
}
```

### Wind-Aware RL With Learned Wind Estimation

- Citation key: `AlTasim2026WindAwareRL`
- Status: arXiv preprint, DOI registration pending on the arXiv page as of 2026-07-10
- arXiv: `2607.01528`
- DOI: `10.48550/arXiv.2607.01528`
- URL: https://arxiv.org/abs/2607.01528
- Authors: Abdullah Al Tasim, Wei Sun
- Method keywords: wind-aware RL, learned onboard wind estimation, PPO, atmospheric turbulence, out-of-distribution wind
- Relation to this paper: Supports the value of explicit wind/disturbance information. It also highlights a limitation for our first version: disturbance observations in PyBullet are oracle-like unless we add an estimator. This must be discussed clearly.

BibTeX draft:

```bibtex
@misc{AlTasim2026WindAwareRL,
  title = {Wind-Aware Reinforcement Learning Control of a Small Quadrotor Using Learned Onboard Wind Estimation in Simulated Atmospheric Turbulence},
  author = {Al Tasim, Abdullah and Sun, Wei},
  year = {2026},
  eprint = {2607.01528},
  archivePrefix = {arXiv},
  primaryClass = {cs.LG},
  doi = {10.48550/arXiv.2607.01528}
}
```

## Positioning Summary

The literature already contains several strong wind-focused UAV RL and hybrid PID/RL studies. The paper should not claim that residual TD3 is new in isolation. The defensible novelty is the combination of:

- a PyBullet circular-tracking benchmark,
- compound disturbances beyond wind alone,
- a PID-stabilized residual TD3 policy,
- explicit disturbance observations,
- safety gating,
- and claim-by-claim ablation evidence with traceable CSV/JSON outputs.

## Open Literature Tasks

- Add 2 to 4 model-based baselines papers on MPC, ADRC, robust control, or disturbance observers for quadrotor trajectory tracking.
- Add one reproducibility reference for continuous-control RL evaluation.
- Re-check arXiv preprints before submission for journal/conference versions.
- Decide whether Simulink RL-v1/RL-v2 should be cited as internal prior work, appendix material, or omitted from related work.
