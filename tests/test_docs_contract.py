from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = [
    ROOT / "docs/main-info-about-projects.md",
    ROOT / "docs/structur-ai-agents-team.md",
    ROOT / "docs/structur-data.md",
]

EXPECTED_PIPELINE_ORDER = [
    "Brief Agent",
    "Audience Segmentation Agent",
    "Persona Builder Agent",
    "Pain & Trigger Agent",
    "Positioning Agent",
    "Competitor Insight Agent",
    "Content Strategy Agent",
    "Rubricator Agent",
    "Parallel Idea Generators",
    "Deduplication Agent",
    "Idea Critic Agent",
    "Garbage Filter Agent",
    "Idea Improvement Agent",
    "Second Critic Agent",
    "Script Writer Agent",
    "Script Critic Agent",
    "CTA Critic Agent",
    "Platform Adaptation Agent",
    "Final Content Pack Agent",
]


def test_required_project_docs_exist() -> None:
    missing = [path for path in REQUIRED_DOCS if not path.exists()]
    assert not missing


def test_agent_pipeline_order_is_documented() -> None:
    text = (ROOT / "docs/structur-ai-agents-team.md").read_text(encoding="utf-8")
    positions = [text.index(step) for step in EXPECTED_PIPELINE_ORDER]
    assert positions == sorted(positions)


def test_mvp_stack_and_data_entities_are_documented() -> None:
    main_info = (ROOT / "docs/main-info-about-projects.md").read_text(encoding="utf-8")
    data = (ROOT / "docs/structur-data.md").read_text(encoding="utf-8")

    assert "Telegram Bot" in main_info
    assert "OpenRouter API" in main_info
    assert "PostgreSQL" in main_info

    for table_name in [
        "users",
        "projects",
        "pipeline_runs",
        "agent_runs",
        "ideas",
        "scripts",
        "final_content_packs",
        "model_usage_logs",
        "pipeline_errors",
    ]:
        assert table_name in data
