from scripts.smoke_fake_pipeline import (
    PIPELINE_STEPS,
    QUALITY_GATE_STEPS,
    run_fake_pipeline,
)


def test_fake_pipeline_returns_final_content_pack_shape() -> None:
    state = run_fake_pipeline()
    pack = state["final_content_pack"]

    assert state["executed_steps"] == PIPELINE_STEPS
    assert pack["brand_summary"]["project_type"] == "brand"
    assert pack["approved_content"]
    assert pack["rejected_content"]
    assert pack["risk_notes"]


def test_quality_gates_run_before_script_writer() -> None:
    state = run_fake_pipeline()
    script_writer_index = state["executed_steps"].index("Script Writer Agent")

    for step in QUALITY_GATE_STEPS:
        assert state["executed_steps"].index(step) < script_writer_index


def test_fake_pipeline_rejects_generic_ideas_before_scripts() -> None:
    state = run_fake_pipeline()
    rejected_titles = {item["title"] for item in state["rejected_ideas"]}
    script_titles = {item["title"] for item in state["scripts"]}

    assert "Buy our cream today" in rejected_titles
    assert "Buy our cream today" not in script_titles
