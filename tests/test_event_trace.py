import json
import uuid

from smm_bot.agents.schemas import CompanyInput
from smm_bot.services.event_trace import PipelineEventLogger


def test_pipeline_event_logger_writes_jsonl_report(tmp_path) -> None:
    run_id = uuid.uuid4()
    trace = PipelineEventLogger(run_id=run_id, trace_dir=tmp_path)

    trace.record("pipeline_input", input=CompanyInput(company_description="Demo brand"))
    trace.record("agent_response", agent_name="brief", output={"ok": True})

    lines = trace.path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]

    assert [event["event_type"] for event in events] == ["pipeline_input", "agent_response"]
    assert events[0]["run_id"] == str(run_id)
    assert events[0]["input"]["company_description"] == "Demo brand"
    assert events[1]["output"] == {"ok": True}
