from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from smm_bot.agents import FakeLLMClient, PipelineExecutor
from smm_bot.agents.llm import fallback_output
from smm_bot.agents.registry import MVP_AGENT_REGISTRY, MVP_GRAPH
from smm_bot.agents.schemas import BriefOutput, CompanyInput


def test_registry_contains_mvp_graph_with_models_and_temperatures() -> None:
    assert set(MVP_GRAPH).issubset(MVP_AGENT_REGISTRY)
    for agent_name in MVP_GRAPH:
        spec = MVP_AGENT_REGISTRY[agent_name]
        assert spec.primary_model
        assert 0 <= spec.temperature <= 1
        assert spec.output_schema is not None


def test_fallback_output_returns_valid_schema_with_warning() -> None:
    output = fallback_output(BriefOutput, "bad json")

    assert isinstance(output, BriefOutput)
    assert output.warnings == ["bad json"]
    assert output.brief.project_type == ""


def test_pipeline_runs_mvp_graph_with_fake_client() -> None:
    fake = FakeLLMClient(
        {
            "brief": {
                "brief": {
                    "project_type": "expert",
                    "niche": "fitness",
                    "company_or_brand_name": "FitLab",
                    "tone_of_voice_raw": "спокойный экспертный",
                }
            },
            "audience_segmentation": {
                "audience_segments": [
                    {
                        "segment_id": "seg_001",
                        "segment_name": "новички",
                        "subsegments": [{"subsegment_id": "sub_001", "name": "занятые специалисты"}],
                    }
                ]
            },
            "persona_builder": {
                "personas": [
                    {
                        "persona_id": "persona_001",
                        "name": "Анна",
                        "age": 32,
                        "segment_id": "seg_001",
                        "subsegment_id": "sub_001",
                        "main_pain": "не понимает, как тренироваться без перегруза",
                    }
                ]
            },
            "pain_trigger": {
                "pain_trigger_map": [
                    {
                        "persona_id": "persona_001",
                        "explicit_pains": ["нет понятного плана тренировок"],
                        "triggers": ["простота"],
                    }
                ]
            },
            "positioning": {"positioning": {"short_positioning": "понятный фитнес без перегруза"}},
            "content_strategy": {
                "content_strategy": {
                    "main_content_goal": "доверие",
                    "content_pillars": [{"pillar_id": "pillar_001", "name": "простые тренировки"}],
                }
            },
            "rubricator": {
                "rubricator": [{"rubric_id": "rubric_001", "rubric_name": "тренировки для занятых"}]
            },
            "pain_based_generator": {
                "ideas": [
                    {
                        "idea_id": "pain_001",
                        "idea_title": "Почему тренировки на максимум срывают режим",
                        "target_persona": "persona_001",
                        "pain": "перегруз после первой недели",
                        "rough_hook": "Вы не ленитесь, вы начали слишком резко",
                    }
                ]
            },
            "trigger_based_generator": {"ideas": []},
            "funnel_based_generator": {"ideas": []},
            "deduplication": {
                "unique_ideas": [
                    {
                        "idea_id": "pain_001",
                        "idea_title": "Почему тренировки на максимум срывают режим",
                        "source_agent": "pain_based_generator",
                        "reason_kept": "конкретная боль",
                    }
                ],
                "kept_count": 1,
            },
            "idea_critic": {
                "evaluated_ideas": [
                    {
                        "idea_id": "pain_001",
                        "idea_title": "Почему тренировки на максимум срывают режим",
                        "scores": {
                            "audience_fit": 5,
                            "pain_specificity": 5,
                            "product_fit": 4,
                            "retention_potential": 4,
                            "novelty": 4,
                            "production_simplicity": 5,
                            "safety": 5,
                        },
                        "weighted_score": 4.6,
                        "decision": "approve",
                    }
                ],
                "summary": {"approved_count": 1},
            },
            "garbage_filter": {
                "passed": [
                    {
                        "idea_id": "pain_001",
                        "idea_title": "Почему тренировки на максимум срывают режим",
                        "reason_passed": "есть ЦА, боль и связь с продуктом",
                    }
                ]
            },
            "script_writer": {
                "scripts": [
                    {
                        "script_id": "script_001",
                        "idea_id": "pain_001",
                        "title": "Не начинайте с максимума",
                        "hook": "Вы не ленитесь, вы просто начали слишком резко",
                        "cta": "Сохраните, чтобы свериться перед следующей тренировкой",
                    }
                ]
            },
            "script_critic": {
                "script_reviews": [
                    {
                        "script_id": "script_001",
                        "idea_id": "pain_001",
                        "scores": {
                            "hook_strength": 4,
                            "clarity": 5,
                            "pain_relevance": 5,
                            "structure": 4,
                            "no_water": 5,
                            "retention": 4,
                            "feasibility": 5,
                            "brand_fit": 5,
                            "safety": 5,
                        },
                        "total_score": 4.7,
                        "decision": "approve",
                    }
                ]
            },
            "final_content_pack": {
                "final_content_pack": {
                    "brand_summary": {"niche": "fitness", "positioning": "понятный фитнес без перегруза"},
                    "approved_content": [{"content_id": "content_001", "idea_id": "pain_001"}],
                }
            },
        }
    )

    result = PipelineExecutor(fake).run(
        CompanyInput(company_description="FitLab помогает занятым новичкам тренироваться дома.")
    )

    assert [call[0] for call in fake.calls] == list(MVP_GRAPH)
    assert result.final_content_pack.final_content_pack.brand_summary.niche == "fitness"
    assert result.outputs["all_ideas_json"]["ideas"][0]["source_agent"] == "pain_based_generator"
