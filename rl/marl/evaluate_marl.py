"""
Full 50-seed benchmark comparing:
  - B1 (rule_based)
  - H1 (lowest_tier_first)
  - H3 (combined_heuristic)
  - DQN + Safety (x6_obs_v2 NumpyQPolicy + SafetyLayer)
  - 3-Agent MARL + Safety (SurgeAgent + ResourceManagerAgent + BedAgent + SafetyLayer)

Evaluates across:
  - Arrival modes: normal, moderate_surge, severe_surge
  - Shortage scenarios: icu_shortage, equipment_shortage, staff_shortage, combined_crisis

Generates:
  - experiments/results/curated/phase10_scenarios.json & docs/results/phase10_scenarios.md
  - experiments/results/curated/marl_evaluation.json & docs/results/marl_evaluation.md
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from ml.los.predictor import LOSPredictor
from rl.environment.hospital_env import CareGridHospitalEnv, WAIT_ACTION
from rl.evaluation.compare import paired_bootstrap
from rl.evaluation.evaluate import evaluate_policy, wait_group_metrics
from rl.evaluation.policies import (
    combined_heuristic_policy,
    lowest_tier_first_policy,
    masked_greedy_policy,
    rule_based_policy,
    safe_policy,
)
from rl.marl.multi_agent_env import MODE_SURGE
from rl.marl.resource_agent import (
    RESOURCE_EXPEDITE_CLEANING,
    RESOURCE_FLOAT_STAFF,
    RESOURCE_HOLD,
    RESOURCE_MOBILIZE_VENT,
    ResourceManagerAgent,
)
from rl.marl.surge_agent import SurgeAgent
from rl.serving.numpy_policy import NumpyQPolicy
from safety.layer import SafetyConfig, SafetyLayer
from simulator.metrics.collector import MetricsCollector
from simulator.metrics.summary import compute_metrics
from simulator.patients.streams import EVAL_SEEDS, generate_stream

REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_dqn_safe_policy(bed_policy: NumpyQPolicy):
    base = masked_greedy_policy(lambda o: bed_policy.q_values(o))
    base.observation_version = 2
    layer = SafetyLayer(SafetyConfig(fallback="h3", guardrails=True))
    wrapped = safe_policy(base, layer)
    wrapped.observation_version = 2
    return wrapped


def evaluate_marl_episode(
    patients: Sequence,
    bed_policy: NumpyQPolicy,
    surge_agent: SurgeAgent,
    resource_agent: ResourceManagerAgent,
    *,
    drain_days: float = 7.0,
    los_predictor: Any = None,
    shortage_scenario: Optional[str] = None,
    isolation_overflow: bool = True,
    macro_interval: int = 10,
    icu_reserve_ratio: float = 0.20,
) -> Dict[str, Any]:
    """Run one full episode of the 3-agent MARL + SafetyLayer on `patients`."""
    arrivals = [p.arrival_time for p in patients]
    start, last = min(arrivals), max(arrivals)
    horizon_days = (last - start).total_seconds() / 86400 + drain_days

    collector = MetricsCollector(window_start=start, window_end=last)
    env = CareGridHospitalEnv(
        max_episode_days=horizon_days,
        los_predictor=los_predictor,
        observation_version=2,
        isolation_overflow=isolation_overflow,
    )
    obs, _ = env.reset(
        seed=0,
        options={
            "patients": list(patients),
            "on_tick": collector.on_tick,
            "shortage_scenario": shortage_scenario,
        },
    )

    safety = SafetyLayer(SafetyConfig(fallback="h3", guardrails=True))
    total_reward = 0.0
    decisions = 0
    invalid = 0
    current_mode = 0
    surge_steps = 0

    while True:
        # Macro + Meso coordination every `macro_interval` decisions
        if decisions % macro_interval == 0 and env.state is not None:
            state = env.state
            icu_beds = state.beds_by_type("ICU")
            icu_avail = sum(b.status == "AVAILABLE" for b in icu_beds) / len(icu_beds) if icu_beds else 0.0
            sd_beds = state.beds_by_type("STEP_DOWN")
            sd_avail = sum(b.status == "AVAILABLE" for b in sd_beds) / len(sd_beds) if sd_beds else 0.0
            q_norm = min(float(np.log1p(len(state.waiting_queue))) / np.log1p(200), 1.0)
            crit_share = (
                sum(env._patients[pid].acuity >= 4 for pid in state.waiting_queue if pid in env._patients)
                / len(state.waiting_queue)
                if state.waiting_queue
                else 0.0
            )
            if state.current_time:
                hr = state.current_time.hour + state.current_time.minute / 60.0
                tod_sin = (np.sin(2.0 * np.pi * hr / 24.0) + 1.0) / 2.0
                tod_cos = (np.cos(2.0 * np.pi * hr / 24.0) + 1.0) / 2.0
            else:
                tod_sin, tod_cos = 0.5, 0.5

            surge_obs = np.asarray(
                [icu_avail, sd_avail, q_norm, crit_share, tod_sin, tod_cos], dtype=np.float32
            )
            current_mode = surge_agent.predict(surge_obs)
            if current_mode == MODE_SURGE:
                surge_steps += 1

            # Resource Manager observation & action
            icu_clean = len(state.cleaning_beds_by_type("ICU")) / len(icu_beds) if icu_beds else 0.0
            sd_clean = len(state.cleaning_beds_by_type("STEP_DOWN")) / len(sd_beds) if sd_beds else 0.0
            vents = [e for e in state.equipment.values() if e.type == "VENTILATOR"]
            vent_maint = len(state.maintenance_ventilators()) / len(vents) if vents else 0.0
            vent_avail = len(state.available_ventilators()) / len(vents) if vents else 0.0
            total_staff = len(state.staff)
            crit_staff = len(state.staff_by_skill("Critical-care")) / total_staff if total_staff else 0.0
            res_obs = np.asarray(
                [icu_clean, sd_clean, vent_maint, vent_avail, crit_staff, q_norm, crit_share, float(current_mode)],
                dtype=np.float32,
            )
            res_mask = np.array(
                [
                    True,
                    bool(state.cleaning_beds_by_type("ICU") or state.cleaning_beds_by_type("STEP_DOWN")),
                    bool(state.maintenance_ventilators()),
                    bool(state.staff_by_skill("General") or state.staff_by_skill("Step-down")),
                ],
                dtype=bool,
            )
            r_act = resource_agent.predict(res_obs, valid_mask=res_mask)
            if env.engine is not None:
                if r_act == RESOURCE_EXPEDITE_CLEANING:
                    env.engine.expedite_cleaning("ICU", minutes=10)
                    env.engine.expedite_cleaning("STEP_DOWN", minutes=12)
                elif r_act == RESOURCE_MOBILIZE_VENT:
                    env.engine.mobilize_ventilator()
                elif r_act == RESOURCE_FLOAT_STAFF:
                    moved = env.engine.float_staff("General", "Critical-care")
                    if moved is None:
                        env.engine.float_staff("Step-down", "Critical-care")

        # Micro Bed Agent decision
        patient = env.current_patient
        valid_mask = env.valid_actions()
        if current_mode == MODE_SURGE and patient is not None and patient.acuity < 5 and env.state is not None:
            icu_beds = env.state.beds_by_type("ICU")
            free_icu = sum(b.status == "AVAILABLE" for b in icu_beds)
            if free_icu <= max(1, int(len(icu_beds) * icu_reserve_ratio)):
                valid_mask[0] = False

        proposed = bed_policy.best_action(obs, valid_mask=valid_mask)
        if patient is not None and env.state is not None:
            action = safety.review(patient, env.state, proposed, env=env).final_action
        else:
            action = proposed

        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        decisions += 1
        invalid += info.get("invalid_reason") is not None
        if terminated or truncated:
            break

    as_of = start + timedelta(days=horizon_days)
    metrics = compute_metrics(env.engine, collector, as_of=as_of)
    metrics.update(wait_group_metrics(env.engine.patients.values(), as_of))
    interventions = dict(env.engine.resource_interventions) if env.engine else {}
    env.close()
    return {
        "policy": "marl_3agent_safe",
        "decisions": decisions,
        "invalid_actions": int(invalid),
        "episode_return": round(total_reward, 3),
        "metrics": metrics,
        "surge_epochs": surge_steps,
        "resource_interventions": interventions,
    }


def _agg(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    keys = [
        "acuity_weighted_avg_wait_min",
        "avg_wait_incl_unadmitted_min",
        "critical_avg_wait_min",
        "low_acuity_isolation_avg_wait_min",
        "icu_utilization",
        "patients_still_waiting",
    ]
    out: Dict[str, Any] = {"n": len(runs)}
    for k in keys:
        vals = [r["metrics"].get(k) for r in runs if r["metrics"].get(k) is not None]
        out[k] = round(float(np.mean(vals)), 2) if vals else None
    out["invalid_actions"] = round(float(np.mean([r["invalid_actions"] for r in runs])), 2)
    out["violations"] = round(
        float(np.mean([r["metrics"]["constraint_violations"]["total"] for r in runs])), 2
    )
    return out


def run_all_benchmarks(
    n_streams: int = 50,
    bed_model_path: str = "models/serving/dqn_x6_obs_v2.npz",
    surge_model_path: str = "models/serving/surge_agent.npz",
    resource_model_path: str = "models/serving/resource_agent.npz",
) -> None:
    seeds = list(EVAL_SEEDS[:n_streams])
    los = LOSPredictor.load()
    bed_policy = NumpyQPolicy(bed_model_path)
    surge_agent = SurgeAgent.load(surge_model_path) if Path(surge_model_path).exists() else SurgeAgent()
    resource_agent = (
        ResourceManagerAgent.load(resource_model_path)
        if Path(resource_model_path).exists()
        else ResourceManagerAgent()
    )
    dqn_safe = _make_dqn_safe_policy(bed_policy)

    scenarios = [
        ("normal", "normal", None),
        ("moderate_surge", "moderate_surge", None),
        ("severe_surge", "severe_surge", None),
        ("icu_shortage", "normal", "icu_shortage"),
        ("equipment_shortage", "normal", "equipment_shortage"),
        ("staff_shortage", "normal", "staff_shortage"),
        ("combined_crisis", "moderate_surge", "combined_crisis"),
    ]

    all_runs: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    summary: Dict[str, Dict[str, Any]] = {}

    for label, arrival_mode, shortage in scenarios:
        print(f"\n=== Benchmarking {label} ({n_streams} streams) ===")
        runs_by_pol: Dict[str, List[Dict[str, Any]]] = {
            "b1": [],
            "h1": [],
            "h3": [],
            "dqn_safe": [],
            "marl_3agent_safe": [],
        }
        for s in seeds:
            stream = generate_stream(int(s), days=30.0, mode=arrival_mode)
            runs_by_pol["b1"].append(
                evaluate_policy(rule_based_policy, stream, los_predictor=los, name="b1", shortage_scenario=shortage)
            )
            runs_by_pol["h1"].append(
                evaluate_policy(lowest_tier_first_policy, stream, los_predictor=los, name="h1", shortage_scenario=shortage)
            )
            runs_by_pol["h3"].append(
                evaluate_policy(combined_heuristic_policy, stream, los_predictor=los, name="h3", shortage_scenario=shortage)
            )
            runs_by_pol["dqn_safe"].append(
                evaluate_policy(dqn_safe, stream, los_predictor=los, name="dqn_safe", shortage_scenario=shortage)
            )
            runs_by_pol["marl_3agent_safe"].append(
                evaluate_marl_episode(
                    stream,
                    bed_policy,
                    surge_agent,
                    resource_agent,
                    los_predictor=los,
                    shortage_scenario=shortage,
                    isolation_overflow=True,
                )
            )

        all_runs[label] = runs_by_pol
        summary[label] = {p: _agg(r) for p, r in runs_by_pol.items()}
        # Paired bootstrap: MARL vs B1 and MARL vs dqn_safe on weighted wait
        marl_w = [r["metrics"]["acuity_weighted_avg_wait_min"] for r in runs_by_pol["marl_3agent_safe"]]
        b1_w = [r["metrics"]["acuity_weighted_avg_wait_min"] for r in runs_by_pol["b1"]]
        dqn_w = [r["metrics"]["acuity_weighted_avg_wait_min"] for r in runs_by_pol["dqn_safe"]]
        summary[label]["bootstrap_marl_vs_b1"] = paired_bootstrap([m - b for m, b in zip(marl_w, b1_w)])
        summary[label]["bootstrap_marl_vs_dqn"] = paired_bootstrap([m - d for m, d in zip(marl_w, dqn_w)])

        for p in ("b1", "h1", "h3", "dqn_safe", "marl_3agent_safe"):
            row = summary[label][p]
            print(
                f"  {p:16s} | weighted_wait={row['acuity_weighted_avg_wait_min']:7.1f} | "
                f"crit_wait={row['critical_avg_wait_min']:7.1f} | "
                f"still_wait={row['patients_still_waiting']:5.1f} | viol={row['violations']}"
            )

    # Save curated JSONs
    curated_dir = REPO_ROOT / "experiments" / "results" / "curated"
    docs_dir = REPO_ROOT / "docs" / "results"
    curated_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    shortage_labels = ["icu_shortage", "equipment_shortage", "staff_shortage", "combined_crisis"]
    p10_summary = {k: summary[k] for k in shortage_labels}
    (curated_dir / "phase10_scenarios.json").write_text(json.dumps(p10_summary, indent=2), encoding="utf-8")
    (curated_dir / "marl_evaluation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Write Markdown reports
    _write_md_report(
        docs_dir / "phase10_scenarios.md",
        f"Phase 10: Shortage Scenario Benchmark ({n_streams} Held-Out Evaluation Streams)",
        p10_summary,
    )
    _write_md_report(
        docs_dir / "marl_evaluation.md",
        f"3-Agent MARL Evaluation ({n_streams} Held-Out Evaluation Streams)",
        summary,
    )
    print("\nWrote phase10_scenarios and marl_evaluation reports to docs/results/ and experiments/results/curated/")


def _write_md_report(path: Path, title: str, data: Dict[str, Any]) -> None:
    lines = [f"# {title}", ""]
    for sc, sc_data in data.items():
        lines.append(f"## Scenario: `{sc}`")
        lines.append("")
        lines.append("| Policy | Weighted Wait (min) | Avg Wait (min) | Critical Wait (min) | Still Waiting | ICU Util | Violations |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for p in ("b1", "h1", "h3", "dqn_safe", "marl_3agent_safe"):
            r = sc_data[p]
            lines.append(
                f"| `{p}` | {r['acuity_weighted_avg_wait_min']} | {r['avg_wait_incl_unadmitted_min']} | "
                f"{r['critical_avg_wait_min']} | {r['patients_still_waiting']} | {r['icu_utilization']} | {r['violations']} |"
            )
        boot_b1 = sc_data["bootstrap_marl_vs_b1"]
        boot_dqn = sc_data["bootstrap_marl_vs_dqn"]
        lines.append("")
        lines.append(
            f"- **MARL vs B1 (`acuity_weighted_avg_wait_min`)**: diff = `{boot_b1['mean']:.2f}` min "
            f"(95% CI `[{boot_b1['ci_low']:.2f}, {boot_b1['ci_high']:.2f}]`, win rate `{boot_b1['win_rate']*100:.1f}%`)"
        )
        lines.append(
            f"- **MARL vs DQN+Safety (`acuity_weighted_avg_wait_min`)**: diff = `{boot_dqn['mean']:.2f}` min "
            f"(95% CI `[{boot_dqn['ci_low']:.2f}, {boot_dqn['ci_high']:.2f}]`, win rate `{boot_dqn['win_rate']*100:.1f}%`)"
        )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--streams", type=int, default=50)
    parser.add_argument("--bed-model", default="models/serving/dqn_x6_obs_v2.npz")
    parser.add_argument("--surge-model", default="models/serving/surge_agent.npz")
    parser.add_argument("--resource-model", default="models/serving/resource_agent.npz")
    args = parser.parse_args()
    run_all_benchmarks(args.streams, args.bed_model, args.surge_model, args.resource_model)
