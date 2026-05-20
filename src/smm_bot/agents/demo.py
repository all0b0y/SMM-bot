from __future__ import annotations

from smm_bot.agents.llm import FakeLLMClient


def build_demo_fake_llm() -> FakeLLMClient:
    return FakeLLMClient(
        {
            "brief": {
                "brief": {
                    "project_type": "brand",
                    "niche": "SMM",
                    "company_or_brand_name": "Demo",
                    "tone_of_voice_raw": "спокойный экспертный",
                }
            },
            "audience_segmentation": {
                "audience_segments": [
                    {
                        "segment_id": "seg_001",
                        "segment_name": "малый бизнес",
                        "subsegments": [{"subsegment_id": "sub_001", "name": "основатели"}],
                    }
                ]
            },
            "persona_builder": {
                "personas": [
                    {
                        "persona_id": "persona_001",
                        "name": "Анна",
                        "age": 34,
                        "segment_id": "seg_001",
                        "subsegment_id": "sub_001",
                        "main_pain": "контент не приводит заявки",
                    }
                ]
            },
            "pain_trigger": {
                "pain_trigger_map": [
                    {
                        "persona_id": "persona_001",
                        "explicit_pains": ["нет связи между роликами и заявками"],
                        "triggers": ["понятная система"],
                    }
                ]
            },
            "positioning": {
                "positioning": {
                    "short_positioning": "AI SMM-система для стратегичных коротких видео"
                }
            },
            "content_strategy": {
                "content_strategy": {
                    "main_content_goal": "доверие и заявки",
                    "content_pillars": [{"pillar_id": "pillar_001", "name": "контент от боли"}],
                }
            },
            "rubricator": {
                "rubricator": [{"rubric_id": "rubric_001", "rubric_name": "разбор ошибок"}]
            },
            "pain_based_generator": {
                "ideas": [
                    {
                        "idea_id": "pain_001",
                        "idea_title": "Почему контент не приводит заявки",
                        "target_persona": "persona_001",
                        "pain": "ролики не связаны с болью клиента",
                        "rough_hook": "Контент есть, а заявок нет?",
                    }
                ]
            },
            "trigger_based_generator": {"ideas": []},
            "funnel_based_generator": {"ideas": []},
            "deduplication": {
                "unique_ideas": [
                    {
                        "idea_id": "pain_001",
                        "idea_title": "Почему контент не приводит заявки",
                        "source_agent": "pain_based_generator",
                        "reason_kept": "конкретная боль и понятная связь с продуктом",
                    }
                ],
                "kept_count": 1,
            },
            "idea_critic": {
                "evaluated_ideas": [
                    {
                        "idea_id": "pain_001",
                        "idea_title": "Почему контент не приводит заявки",
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
                        "idea_title": "Почему контент не приводит заявки",
                        "reason_passed": "есть ЦА, боль и связь с продуктом",
                    }
                ]
            },
            "script_writer": {
                "scripts": [
                    {
                        "script_id": "script_001",
                        "idea_id": "pain_001",
                        "title": "Контент есть, заявок нет",
                        "hook": "Контент есть, а заявок нет?",
                        "core_message": "Проблема часто в слабой связке: боль клиента, оффер и CTA.",
                        "cta": "Сохраните и проверьте следующий ролик по этой структуре.",
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
                    "brand_summary": {
                        "niche": "SMM",
                        "positioning": "AI SMM-система для стратегичных коротких видео",
                    },
                    "approved_content": [{"content_id": "content_001", "idea_id": "pain_001"}],
                }
            },
        }
    )
