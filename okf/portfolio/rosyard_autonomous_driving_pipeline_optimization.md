---
title: "RACEYARD (formerly ROSYARD): Pipeline Optimization & QA Automation"
description: University Master Project (CAU Kiel) — QA framework with W&B and Sweeps automation for sensor tuning on an autonomous driving simulation (ROS/Gazebo). Team project; my work was the QA/automation.
technologies: Python, ROS, Gazebo, Weights & Biases, ruamel.yaml, matplotlib, rospy, YAML
keywords:
- ros
- gazebo
- wandb
- weights and biases
- hyperparameter tuning
- sweeps automation
- qa automation
- experiment tracking
- sensor parameter tuning
- simulation pipeline
- autonomous driving
- robotics
- python
- ruamel.yaml
- mlops
archetypes:
- Agentic/Automation
- ML Engineering
- Data Engineering
---

# RACEYARD (formerly ROSYARD): Pipeline Optimization & QA Automation

**University Master Project — Christian-Albrecht-University of Kiel, WiSe 2020/21**

RACEYARD (formerly ROSYARD) is an autonomous driving vehicle development project inspired by the AMZ Driverless platform, built by a student team at CAU Kiel. The full system comprises five sequential ROS pipelines: Perception (Camera/LiDAR cone detection), SLAM, Centerline Estimation, Driving (speed/steering control), and Low-Level actuation — running in Gazebo simulation with RViz visualization.

**My contribution was the pipeline optimization layer:** a Quality Assurance (QA) metrics framework, Weights & Biases (W&B) experiment tracking integration, and a custom Sweeps automation wrapper to tune sensor parameters automatically. I did not build the driving pipelines, SLAM, or the simulation environment — those were built by the team. I also collaborated with Lorenz on the initial Docker containerization and process flow documentation.

---

## What I Built

### 1. QA Framework Enablement
Enabled and instrumented the existing QA node in `rosyard_common` to measure cone detection accuracy against Gazebo ground truth. The QA node compares detected cones (position + color) against simulation ground truth and reports:
- Detection accuracy (% of ground truth cones detected)
- False-positive rate (cones detected with no matching GT)
- Color estimation accuracy
- Mean distance between detected and ground truth cones

Config: `enabled: True` in `src/rosyard_common/config/general_config.yaml`.

### 2. Weights & Biases Integration
Integrated W&B into the QA script (`src/rosyard_common/src/rosyard_common_scripts/quality_assurance/cone_detection.py`) to log metrics dynamically — a non-traditional use of W&B (normally an ML experiment tracker, here used for simulation parameter tuning).

- **Dynamic config ingestion:** Used `rospy` to fetch parameters from the ROS Parameter Server at runtime — no hardcoded values. W&B config is populated dynamically from the YAML config files.
- **Metric logging:** Converted console log statements to W&B log calls:
  ```python
  # Before (console only):
  self.log("%d / %d (%.2f%%) color estimations were correct" % (color, total, pct))
  # After (W&B + console):
  wandb.log({'percentage_color_estimations_correct': pct})
  ```
- **Track visualization:** Converted matplotlib cone-detection plots to `wandb.plot.scatter` format, rendering the detected track directly on the W&B dashboard.
- **Three separate reports:** Camera, LiDAR, and SLAM metrics logged as standalone W&B runs with project names + timestamps for filtering.

### 3. Custom Sweeps Automation Wrapper
W&B Sweeps normally targets a single ML training script. ROSYARD has no single entry point — `roscore`, Gazebo, and 14 ROS nodes must all launch concurrently. I built a custom wrapper to make Sweeps work across the ROS stack.

**Files created in `src/rosyard/rosyard_automationQA/`:**
- `pipeline_wanDB.yaml` — Sweep config defining the hyperparameter search space (e.g., `opening_angle: 30–40`) and Bayes optimization.
- `parser.py` — Intercepts Sweep-generated command-line arguments, casts to float.
- `roscore.py` — Spawns ROS Master.
- `simulation.py` — Spawns Gazebo simulator.
- `pipeline_wrapper.py` — Main orchestrator: receives parsed value from `parser.py`, writes it to `default_config.yaml` via `ruamel.yaml` (round-trip YAML editing), then spawns `roscore.py` + `simulation.py` with a 5-minute hard timer.

**Automation sequence:**
1. W&B Sweeps invokes `pipeline_wrapper.py` with a hyperparameter value (e.g., `opening_angle: 34`).
2. `parser.py` intercepts and casts the value to float.
3. `pipeline_wrapper.py` uses `ruamel.yaml` to write the value into `src/rosyard_common/config/default_config.yaml`.
4. Only after the config is updated, the wrapper spawns `roscore.py` (ROS Master) and `simulation.py` (Gazebo).
5. 14 ROS nodes run the simulation lap. QA runs on completion, logging metrics to W&B with the Sweep ID.
6. After a 5-minute hard timer, the wrapper forcefully kills all child processes to prevent termination limbo.
7. Sweeps recurses with the next value.

### 4. Process Flow Documentation
Collaborated with Lorenz (Docker integration) to manually trace ROS node logs and produce an abstract process flow chart documenting all nodes, topics, and values across the 5 pipelines. This diagram became the reference for the entire optimization work.

---

## Issues I Solved

### Server-Client GUI Conflict
Another team member's client-server GUI architecture loaded parameters permanently into memory on ROS server initialization, blocking dynamic config changes mid-sweep. **Fix:** Bypassed the GUI entirely, pulling variables from the raw `general_config.yaml` to preserve automated sweep capability.

### Termination Limbo
After logging metrics, child ROS nodes failed to self-terminate, blocking subsequent Sweep iterations. **Fix:** Implemented a hard 5-minute subprocess timer in `pipeline_wrapper.py` that forcefully kills the entire process tree before starting the next run.

---

## What I Did Not Build
- The 5 ROS pipelines (detection, SLAM, estimation, driving, low-level) — built by the team
- The Gazebo simulation environment and sensor models
- The cheat-based cone detection system (pre-existing)
- The CARLA integration (planned, not completed during my tenure)
- Centerline estimation, Camera Cone Detection (ML), Client-Server Architecture — parallel sub-projects by other team members

---

## Tech Stack
- **Languages:** Python, YAML
- **Middleware:** ROS (rospy, roslaunch, ROS Parameter Server)
- **Simulation:** Gazebo, RViz
- **Experiment Tracking:** Weights & Biases (wandb, Sweeps, Bayes optimization)
- **Automation:** Custom wrapper, subprocess management, ruamel.yaml round-trip editing
- **Visualization:** matplotlib → W&B plot conversion
