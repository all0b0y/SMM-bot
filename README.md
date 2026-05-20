# AI SMM Telegram Bot MVP

MVP по документам проекта: Telegram-бот принимает описание бизнеса, прогоняет его через AI agent pipeline, использует OpenRouter как LLM gateway и PostgreSQL как хранилище запусков, результатов агентов, идей, сценариев и финального content pack.

В текущем состоянии репозитория есть проектные документы, запусковой/тестовый контур, backend/DB MVP-скелет и агентный MVP pipeline: FastAPI app, async SQLAlchemy models, Alembic schema migration, Postgres/Redis docker-compose, Celery worker entrypoint, Pydantic-схемы агентов, OpenRouter client skeleton и fake LLM для тестов.

## Быстрый старт

```bash
cp .env.example .env
make install-dev
make health
make smoke
make test
```

Заполните `.env` локальными значениями:

```text
TELEGRAM_BOT_TOKEN=...
OPEN_ROUTER_KEY=...
DATABASE_URL=postgresql+asyncpg://smm:smm@localhost:5432/smm
REDIS_URL=redis://localhost:6379/0
```

Не коммитьте реальные токены и ключи. `.env.example` содержит только безопасные placeholders.

## Команды

```bash
make install-dev  # создать .venv и поставить pytest
make health       # проверить Python, обязательные файлы и env-контракт
make smoke        # выполнить deterministic fake pipeline без сети и LLM
make test         # запустить pytest
make clean        # убрать pytest/python cache
```

## Backend / DB

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d postgres redis
alembic upgrade head
uvicorn smm_bot.main:app --reload
```

Full Docker stack:

```bash
docker compose up -d --build
```

Services:

```text
postgres
redis
app
worker
bot
```

API health endpoint:

```bash
curl http://localhost:8000/health
```

Fake pipeline endpoint без внешних LLM:

```bash
curl -X POST http://localhost:8000/pipeline/fake-run \
  -H 'Content-Type: application/json' \
  -d '{"company_description":"SMM-агентство для малого бизнеса. Нужно генерировать Reels идеи от болей клиентов."}'
```

## MVP pipeline contract

Ожидаемая цепочка из документов:

```text
Brief Agent
Audience Segmentation Agent
Persona Builder Agent
Pain & Trigger Agent
Positioning Agent
Competitor Insight Agent
Content Strategy Agent
Rubricator Agent
Parallel Idea Generators
Deduplication Agent
Idea Critic Agent
Garbage Filter Agent
Idea Improvement Agent
Second Critic Agent
Script Writer Agent
Script Critic Agent
CTA Critic Agent
Platform Adaptation Agent
Final Content Pack Agent
```

Ключевое правило MVP: генераторы идей не передают результат напрямую сценаристу. Перед сценариями обязательны дедупликация, критика, anti-garbage gate, улучшение и повторная критика.

## Smoke без реального LLM

`scripts/smoke_fake_pipeline.py` имитирует полный контур на deterministic fake LLM:

```bash
python3 scripts/smoke_fake_pipeline.py
```

Скрипт возвращает JSON content pack со структурой:

```text
brand_summary
audience_summary
content_strategy_summary
approved_content
rejected_content
publishing_recommendations
risk_notes
next_steps_for_human
```

Это дополняет core implementation и дает стабильный smoke для CI и локальной проверки пайплайн-контракта до подключения реальных LLM-вызовов.

## Health check

```bash
python3 scripts/healthcheck.py
python3 scripts/healthcheck.py --json
```

Проверка не печатает значения секретов. Она показывает только наличие обязательных переменных окружения и файлов.

## Pytest

Тесты покрывают:

- наличие и базовый контракт проектных документов;
- безопасный `.env.example`;
- импортируемость health/smoke scripts;
- deterministic fake pipeline и правило quality gate перед сценариями.

Запуск:

```bash
python3 -m pytest
```
