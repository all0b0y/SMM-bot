from fastapi import FastAPI

from smm_bot.agents.demo import build_demo_fake_llm
from smm_bot.agents.pipeline import PipelineExecutor
from smm_bot.agents.schemas import CompanyInput, PipelineResult
from smm_bot.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
    }


@app.post("/pipeline/fake-run", response_model=PipelineResult)
async def fake_pipeline_run(payload: CompanyInput) -> PipelineResult:
    return PipelineExecutor(build_demo_fake_llm()).run(payload)
