# Команда параллельной разработки MVP

## Цель

Собрать MVP Telegram-бота AI SMM-системы по документации проекта:

```text
Telegram Bot
→ FastAPI webhook
→ Agent Pipeline
→ OpenRouter API
→ PostgreSQL
→ Redis/Celery for background jobs
```

Главный критерий готовности MVP: пользователь отправляет описание бизнеса в Telegram, система запускает агентный пайплайн, сохраняет промежуточные результаты и возвращает финальный контент-пак с анализом ЦА, идеями, сценариями, отклоненными идеями и причинами отказа.

## Потоки разработки

### 1. Backend & Data

**Зона владения:**

- FastAPI application shell
- настройки приложения
- PostgreSQL-модели
- Alembic-миграции
- репозитории для pipeline state
- health/readiness endpoints

**Основные файлы:**

- `src/smm_bot/core/`
- `src/smm_bot/db/`
- `src/smm_bot/api/`
- `migrations/`
- `docker-compose.yml`

**Definition of Done:**

- приложение стартует локально;
- PostgreSQL и Redis поднимаются через Docker Compose;
- все MVP-таблицы из `docs/structur-data.md` описаны в моделях и миграциях;
- есть endpoint проверки состояния.

### 2. AI Agents & Pipeline

**Зона владения:**

- Pydantic-схемы входов и выходов агентов;
- prompt templates из `docs/promts_for_ai_agent.md`;
- модельная политика из `docs/structur-ai-agents-team.md`;
- OpenRouter-compatible LLM client;
- fallback моделей;
- pipeline executor;
- fake LLM для тестов.

**Основные файлы:**

- `src/smm_bot/agents/`
- `src/smm_bot/llm/`
- `src/smm_bot/pipeline/`

**MVP-граф:**

```text
Brief Agent
→ Audience Segmentation Agent
→ Persona Builder Agent
→ Pain & Trigger Agent
→ Positioning Agent
→ Content Strategy Agent
→ Rubricator Agent
→ parallel idea generators
→ Deduplication Agent
→ Idea Critic Agent
→ Garbage Filter Agent
→ Script Writer Agent
→ Script Critic Agent
→ Final Content Pack Agent
```

**Definition of Done:**

- каждый агент имеет схему результата;
- агентный реестр содержит основную модель, fallback и температуру;
- пайплайн можно прогнать без внешнего API через fake LLM;
- невалидный JSON от LLM фиксируется как ошибка пайплайна.

### 3. Telegram Product Flow

**Зона владения:**

- команды `/start`, `/help`, `/new_project`, `/status`;
- прием описания компании;
- запуск фоновой генерации;
- пользовательские статусы обработки;
- выдача краткого результата и ссылки/файла финального пакета.

**Основные файлы:**

- `src/smm_bot/bot/`
- `src/smm_bot/api/webhooks.py`
- `src/smm_bot/tasks/`

**Definition of Done:**

- бот принимает длинное описание бизнеса;
- создает project + project_input;
- запускает pipeline_run;
- показывает текущего агента;
- возвращает финальный контент-пак после завершения.

### 4. QA & Debugging

**Зона владения:**

- pytest;
- smoke-тесты запуска;
- fake LLM fixtures;
- проверки JSON-схем;
- тесты quality gates;
- runbook отладки.

**Основные файлы:**

- `tests/`
- `README.md`
- `.env.example`
- `Makefile`

**Definition of Done:**

- тесты запускаются одной командой;
- есть тест без реального OpenRouter API;
- есть тест на reject слабой идеи;
- есть инструкция локального запуска.

## Порядок интеграции

1. Backend создает базовый app, settings, database и модели.
2. Agents подключают схемы, prompts, model registry и fake pipeline.
3. QA добавляет smoke-тесты на импорты, настройки и fake pipeline.
4. Telegram flow подключает создание проекта и запуск фоновой задачи.
5. Команда делает интеграционный прогон: `description → pipeline → final pack`.
6. После зеленых тестов подключается реальный OpenRouter API.

## Правила параллельной работы

- Каждый поток владеет своим каталогом и не переписывает чужие файлы без необходимости.
- Общие контракты меняются через Pydantic-схемы, а не через неявные словари.
- Любой LLM-output сначала валидируется схемой, затем сохраняется.
- Любой агентный сбой пишется в `pipeline_errors`.
- Реальные API-ключи не коммитятся; для примеров используется `.env.example`.
- Все проверки качества идей и сценариев должны быть воспроизводимыми в тестах.

## Минимальная команда агентов разработки

```text
Team Lead / Integrator
Backend Engineer
AI Pipeline Engineer
Telegram Bot Engineer
QA Engineer
DevOps Engineer
```

Для MVP роли могут совмещаться, но зоны владения должны оставаться отдельными.
