from rl.marl.multi_agent_env import CareGridMAEnv


def test_critical_arrival_returns_control_before_bed_decision():
    env = CareGridMAEnv()
    env.reset(seed=42)
    for patient in env.env._patients.values():
        patient.acuity = 5
    for bed in env.env.state.beds_by_type("ICU"):
        bed.status = "OCCUPIED"
    _, _, done, _, info = env.step((0, 0))
    assert not done
    assert info["macro_interrupt"]
    assert info["decisions_in_macro_step"] == 1
    assert env.env.current_patient.status == "WAITING"
