from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from smm_bot.agents import FakeLLMClient, PipelineExecutor
from smm_bot.agents.llm import fallback_output
from smm_bot.agents.registry import MVP_AGENT_REGISTRY, MVP_GRAPH
from smm_bot.agents.schemas import (
    BlindScriptReview,
    BriefOutput,
    CompanyInput,
    ContentIdea,
    DeduplicationOutput,
    EvaluatedIdea,
    GarbageFilterOutput,
    IdeaCriticOutput,
    PassedIdea,
    VideoScript,
)


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
            "context_auditor": {
                "audit_status": "pass",
                "project_summary": "FitLab помогает занятым новичкам тренироваться дома",
                "must_use_context_terms": ["FitLab", "домашние тренировки", "занятые новички"],
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
            "reference_video_researcher": {
                "patterns": [
                    {
                        "pattern_id": "pattern_001",
                        "segment": "занятые новички",
                        "format_name": "ошибка новичка",
                        "example_description": "Видео показывает типичную ошибку резкого старта",
                        "hook_pattern": "Вы не ленитесь, проблема в старте",
                        "structure": ["ошибка", "почему происходит", "мягкое решение"],
                        "why_relevant": "Попадает в боль перегруза",
                    }
                ]
            },
            "topic_angle_generator": {
                "topic_angles": [
                    {
                        "idea_id": "pain_001",
                        "selected_angle_id": "angle_001",
                        "selected_angle_reason": "Самый узнаваемый угол для новичков",
                        "suggested_angles": [
                            {
                                "idea_id": "pain_001",
                                "angle_id": "angle_001",
                                "motivation_type": "avoid_pain",
                                "video_angle": "показать ошибку резкого старта без стыда",
                                "audience_insight": "новичок думает, что проблема в лени",
                                "emotional_job": "снять вину и дать простой выход",
                                "why_it_can_work": "узнаваемая ситуация",
                            }
                        ],
                    }
                ]
            },
            "hook_generator": {
                "hooks": [
                    {
                        "idea_id": "pain_001",
                        "angle_id": "angle_001",
                        "best_hook": "Вы не ленитесь, вы просто начали слишком резко",
                        "best_hook_reason": "Снимает вину и цепляет новичка",
                        "hooks": [
                            {
                                "hook": "Вы не ленитесь, вы просто начали слишком резко",
                                "mechanic": "узнавание",
                                "why_it_can_work": "попадает в самообвинение новичка",
                                "risk": "",
                                "score": 9,
                            }
                        ],
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
            "retention_optimizer": {
                "script_reviews": [
                    {
                        "script_id": "script_001",
                        "idea_id": "pain_001",
                        "anti_scroll_score": 86,
                        "retention_map": [
                            {
                                "time": "0-3 сек",
                                "task": "остановить скролл",
                                "tool": "снять вину с новичка",
                            }
                        ],
                        "drop_off_risk": "мало визуальной смены кадров",
                        "strongest_part": "хук",
                        "weakest_part": "середина",
                        "improvement_tip": "добавить смену плана после 7 секунды",
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
            "blind_script_checker": {
                "script_reviews": [
                    {
                        "script_id": "script_001",
                        "idea_id": "pain_001",
                        "blind_summary_before_comparison": "Сценарий про фитнес для новичков",
                        "inferred_project_type": "фитнес",
                        "inferred_product_or_service": "домашние тренировки",
                        "inferred_audience": "занятые новички",
                        "inferred_pain": "перегруз после резкого старта",
                        "similarity_score": 90,
                        "is_semantically_aligned": True,
                    }
                ],
                "passed_count": 1,
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

    call_names = [call[0] for call in fake.calls]

    assert call_names[:4] == list(MVP_GRAPH[:4])
    assert set(call_names[4:6]) == set(MVP_GRAPH[4:6])
    assert call_names[6:8] == list(MVP_GRAPH[6:8])
    assert set(call_names[8:11]) == set(MVP_GRAPH[8:11])
    assert call_names[11:] == list(MVP_GRAPH[11:])
    assert result.final_content_pack.final_content_pack.brand_summary.niche == "fitness"
    assert result.outputs["all_ideas_json"]["ideas"][0]["source_agent"] == "pain_based_generator"


def test_pipeline_emits_agent_trace_events() -> None:
    fake = FakeLLMClient()
    events = []

    PipelineExecutor(fake, graph=("brief",), on_agent_event=events.append).run(
        CompanyInput(company_description="FitLab helps busy beginners train at home.")
    )

    event_types = [event["event_type"] for event in events]

    assert event_types == ["pipeline_input", "agent_request", "agent_response"]
    assert events[1]["agent_name"] == "brief"
    assert "FitLab helps busy beginners train at home." in events[1]["user_prompt"]
    assert events[2]["output"].warnings == ["fake response missing for brief"]


def test_pipeline_repairs_empty_idea_ids_from_generators() -> None:
    fake = FakeLLMClient(
        {
            "pain_based_generator": {
                "ideas": [
                    {
                        "idea_id": "",
                        "idea_title": "Why busy beginners quit training",
                    }
                ]
            }
        }
    )

    result = PipelineExecutor(fake, graph=("pain_based_generator",)).run(
        CompanyInput(company_description="FitLab helps busy beginners train at home.")
    )

    idea = result.outputs["all_ideas_json"]["ideas"][0]

    assert idea["idea_id"] == "pain_based_generator_001"
    assert idea["source_agent"] == "pain_based_generator"


def test_agent_schemas_accept_common_llm_aliases() -> None:
    idea = ContentIdea.model_validate(
        {
            "id": "idea_001",
            "title": "Русификация Zeekr без сюрпризов",
            "persona": "owner_001",
            "pain_point": "боится потерять настройки авто",
            "hook": "Русский интерфейс без риска для системы",
            "next_step": "Записаться на диагностику",
        }
    )
    evaluated = EvaluatedIdea.model_validate(
        {
            "id": "idea_001",
            "title": "Русификация Zeekr без сюрпризов",
            "score": 4.5,
            "comment": "Конкретная идея под сервис китайских авто",
        }
    )
    passed = PassedIdea.model_validate(
        {
            "id": "idea_001",
            "title": "Русификация Zeekr без сюрпризов",
            "reason": "Есть ниша, боль и услуга",
        }
    )
    script = VideoScript.model_validate(
        {
            "id": "script_001",
            "ideaId": "idea_001",
            "title": "Русификация Zeekr без сюрпризов",
            "scenes": [{"visual": "Экран авто до русификации"}],
            "message": "Показываем безопасный процесс",
        }
    )
    blind_review = BlindScriptReview.model_validate(
        {
            "id": "script_001",
            "score": 82,
            "passed": True,
        }
    )

    assert idea.idea_id == "idea_001"
    assert idea.idea_title == "Русификация Zeekr без сюрпризов"
    assert idea.target_persona == "owner_001"
    assert idea.pain == "боится потерять настройки авто"
    assert idea.rough_hook == "Русский интерфейс без риска для системы"
    assert idea.viewer_next_step == "Записаться на диагностику"
    assert evaluated.weighted_score == 4.5
    assert evaluated.critic_comment == "Конкретная идея под сервис китайских авто"
    assert passed.reason_passed == "Есть ниша, боль и услуга"
    assert script.script_id == "script_001"
    assert script.idea_id == "idea_001"
    assert len(script.scene_by_scene) == 1
    assert script.core_message == "Показываем безопасный процесс"
    assert blind_review.script_id == "script_001"
    assert blind_review.similarity_score == 82
    assert blind_review.is_semantically_aligned is True


def test_pipeline_falls_back_when_idea_gates_return_empty_lists() -> None:
    executor = PipelineExecutor(FakeLLMClient())
    context = {
        "input": CompanyInput(
            company_description="FitLab helps busy beginners train at home.",
            scripts_count=1,
        ),
        "all_ideas_json": {
            "ideas": [
                {
                    "idea_id": "idea_001",
                    "idea_title": "Why busy beginners quit training",
                    "source_agent": "pain_based_generator",
                    "pain": "starting too hard",
                    "rough_hook": "You are not lazy; the plan is too aggressive.",
                }
            ]
        },
        "deduplication": DeduplicationOutput(
            unique_ideas=[
                {
                    "idea_id": "",
                    "idea_title": "Why busy beginners quit training",
                    "reason_kept": "Specific pain",
                }
            ],
        ),
        "idea_critic": IdeaCriticOutput(),
        "garbage_filter": GarbageFilterOutput(),
    }

    approved = executor._approved_ideas(context)["ideas"]

    assert approved == [
        {
            "idea_id": "idea_001",
            "idea_title": "Why busy beginners quit training",
            "source_agent": "pain_based_generator",
            "target_persona": "",
            "pain": "starting too hard",
            "hidden_pain": "",
            "pain_or_desire": "",
            "pain_or_trigger": "",
            "main_trigger": "",
            "content_angle": "",
            "video_format": "",
            "funnel_stage": "awareness",
            "rubric_id": "",
            "rough_hook": "You are not lazy; the plan is too aggressive.",
            "why_it_can_work": "",
            "viewer_next_step": "",
            "suggested_cta_type": "",
            "shooting_complexity": "medium",
            "risk_notes": [],
            "reason_passed": "Fallback: upstream critic/filter returned empty lists",
        }
    ]


def test_pipeline_quality_loop_improves_and_rechecks_top_ideas() -> None:
    idea_ids = [f"idea_{i:03d}" for i in range(1, 6)]
    fake = FakeLLMClient(
        {
            "idea_improver": {
                "improved_ideas": [
                    {
                        "idea_id": idea_id,
                        "idea_title": f"Improved idea {index}",
                        "improvement_made": "Made the pain and product fit specific",
                        "target_persona": "persona_001",
                        "pain": "unclear training plan",
                        "content_angle": "show the before/after of a simple plan",
                        "video_format": "reels",
                        "rough_hook": "You do not need more discipline; you need a clearer plan.",
                        "why_now_it_works": "Specific pain, hook and product fit",
                        "quality_check": True,
                    }
                    for index, idea_id in enumerate(idea_ids, start=1)
                ]
            },
            "idea_critic": {
                "evaluated_ideas": [
                    {
                        "idea_id": idea_id,
                        "idea_title": f"Improved idea {index}",
                        "scores": {
                            "audience_fit": 5,
                            "pain_specificity": 4,
                            "product_fit": 4,
                            "retention_potential": 4,
                            "novelty": 4,
                            "production_simplicity": 5,
                            "safety": 5,
                        },
                        "weighted_score": 4.4,
                        "decision": "approve",
                    }
                    for index, idea_id in enumerate(idea_ids, start=1)
                ],
                "summary": {"approved_count": 5},
            },
            "garbage_filter": {
                "passed": [
                    {
                        "idea_id": idea_id,
                        "idea_title": f"Improved idea {index}",
                        "reason_passed": "Meets target quality",
                    }
                    for index, idea_id in enumerate(idea_ids, start=1)
                ]
            },
        }
    )
    executor = PipelineExecutor(fake)
    context = {
        "input": CompanyInput(
            company_description="FitLab helps busy beginners train at home.",
            scripts_count=5,
        ),
        "all_ideas_json": {
            "ideas": [
                {
                    "idea_id": idea_id,
                    "idea_title": f"Draft idea {index}",
                    "source_agent": "pain_based_generator",
                }
                for index, idea_id in enumerate(idea_ids, start=1)
            ]
        },
        "idea_critic": IdeaCriticOutput(),
        "garbage_filter": GarbageFilterOutput(),
    }

    executor._ensure_minimum_quality_ideas(context)

    assert [call[0] for call in fake.calls] == [
        "idea_improver",
        "idea_critic",
        "garbage_filter",
    ]
    approved = context["quality_loop_approved_ideas_json"]["ideas"]

    assert len(approved) == 5
    assert {item["idea_id"] for item in approved} == set(idea_ids)
    assert all(item["reason_passed"] == "Meets target quality" for item in approved)


def test_blind_script_check_filters_semantic_mismatches() -> None:
    executor = PipelineExecutor(FakeLLMClient())
    accepted = VideoScript(
        script_id="script_001",
        idea_id="idea_001",
        title="Домашняя тренировка без перегруза",
    )
    mismatch = VideoScript(
        script_id="script_002",
        idea_id="idea_002",
        title="Как стать продуктивнее",
    )
    scripts = type("ScriptsStub", (), {"scripts": [accepted, mismatch]})()
    checker = type(
        "CheckerStub",
        (),
        {
            "script_reviews": [
                BlindScriptReview(
                    script_id="script_001",
                    idea_id="idea_001",
                    inferred_project_type="фитнес",
                    inferred_product_or_service="домашние тренировки",
                    similarity_score=88,
                    is_semantically_aligned=True,
                ),
                BlindScriptReview(
                    script_id="script_002",
                    idea_id="idea_002",
                    inferred_project_type="саморазвитие",
                    inferred_product_or_service="продуктивность",
                    similarity_score=30,
                    is_semantically_aligned=False,
                    mismatch_notes=["Не похоже на фитнес-проект"],
                ),
            ]
        },
    )()
    context = {
        "script_writer": scripts,
        "blind_script_checker": checker,
    }

    executor._apply_blind_script_check(context)

    assert scripts.scripts == [accepted]
    assert context["polished_scripts_json"]["scripts"][0]["script_id"] == "script_001"
    assert context["blind_script_rejections_json"]["rejected_scripts"][0]["script_id"] == "script_002"
