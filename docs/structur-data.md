# Модель данных MVP для AI Agent SMM-системы

## 1. Цель модели данных

Модель должна поддерживать:

```text
Telegram-пользователь
→ проект
→ вводное описание компании
→ запуск агентного пайплайна
→ результаты агентов
→ идеи
→ оценки идей
→ сценарии
→ оценки сценариев
→ финальный контент-пак
→ логи моделей / стоимости / ошибок
```

Для MVP достаточно **PostgreSQL + JSONB**. Отдельный S3, Qdrant, аналитическое хранилище и сложный observability-слой не нужны.

---

# 2. Сущности MVP

## Базовая структура

```text
users
projects
project_inputs
pipeline_runs
agent_runs
ideas
idea_reviews
scripts
script_reviews
final_content_packs
model_usage_logs
pipeline_errors
```

Этого достаточно, чтобы хранить весь жизненный цикл генерации.

---

# 3. ER-схема

```text
users
  ↓
projects
  ↓
project_inputs
  ↓
pipeline_runs
  ↓
agent_runs
  ↓
ideas
  ↓
idea_reviews
  ↓
scripts
  ↓
script_reviews
  ↓
final_content_packs

pipeline_runs
  ↓
model_usage_logs

pipeline_runs
  ↓
pipeline_errors
```

---

# 4. Основные таблицы

## 4.1. `users`

Хранит пользователей Telegram.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    telegram_user_id BIGINT UNIQUE NOT NULL,
    telegram_username TEXT,
    first_name TEXT,
    last_name TEXT,

    language_code TEXT DEFAULT 'ru',
    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### Зачем нужна

Чтобы связать пользователя Telegram с проектами и запусками.

---

## 4.2. `projects`

Проект = один бренд / компания / блог / клиент.

```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    title TEXT NOT NULL,
    project_type TEXT,
    niche TEXT,
    brand_name TEXT,

    status TEXT NOT NULL DEFAULT 'draft',
    -- draft / active / archived

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### Пример

```json
{
  "title": "Бренд натуральной косметики",
  "project_type": "brand",
  "niche": "уходовая косметика",
  "brand_name": "Vita Cavcasea"
}
```

---

## 4.3. `project_inputs`

Хранит исходные вводные от пользователя.

```sql
CREATE TABLE project_inputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    input_type TEXT NOT NULL DEFAULT 'company_description',
    -- company_description / brief / manual_form

    raw_text TEXT NOT NULL,

    platform TEXT,
    content_goal TEXT,
    ideas_count INT DEFAULT 30,
    scripts_count INT DEFAULT 10,

    metadata JSONB DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Что хранить в `raw_text`

Полное описание компании, которое пользователь прислал в Telegram.

### Что хранить в `metadata`

```json
{
  "source": "telegram",
  "message_id": 12345,
  "user_selected_platform": "instagram_reels",
  "quality_mode": "balanced"
}
```

---

# 5. Таблицы пайплайна

## 5.1. `pipeline_runs`

Один запуск всей цепочки агентов.

```sql
CREATE TABLE pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    project_input_id UUID REFERENCES project_inputs(id) ON DELETE SET NULL,

    status TEXT NOT NULL DEFAULT 'pending',
    -- pending / running / completed / failed / cancelled

    quality_mode TEXT DEFAULT 'balanced',
    -- economy / balanced / high_quality

    current_agent TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,

    total_input_tokens INT DEFAULT 0,
    total_output_tokens INT DEFAULT 0,
    total_estimated_cost NUMERIC(12, 6) DEFAULT 0,

    error_message TEXT,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### Зачем нужна

Чтобы бот мог показывать статус:

```text
Проект обрабатывается.
Сейчас работает: Idea Critic Agent.
```

---

## 5.2. `agent_runs`

Главная таблица для хранения результатов каждого агента.

```sql
CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    agent_name TEXT NOT NULL,
    agent_order INT,

    status TEXT NOT NULL DEFAULT 'pending',
    -- pending / running / completed / failed / skipped

    input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_json JSONB NOT NULL DEFAULT '{}'::jsonb,

    model_id TEXT,
    temperature NUMERIC(3, 2),

    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    latency_ms INT,

    validation_status TEXT DEFAULT 'not_checked',
    -- not_checked / valid / invalid

    validation_error TEXT,
    error_message TEXT,

    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Зачем нужна

Это универсальное хранилище для всех агентов:

```text
Brief Agent
Audience Segmentation Agent
Persona Builder Agent
Pain & Trigger Agent
Positioning Agent
...
Final Content Pack Agent
```

На MVP не нужно создавать отдельную таблицу под каждый агент. Достаточно хранить результат в `output_json`.

---

# 6. Таблицы идей

## 6.1. `ideas`

Хранит все идеи, которые сгенерировали агенты.

```sql
CREATE TABLE ideas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    source_agent TEXT NOT NULL,
    external_idea_id TEXT,

    title TEXT NOT NULL,

    target_persona TEXT,
    segment TEXT,
    pain TEXT,
    trigger TEXT,
    content_angle TEXT,
    video_format TEXT,
    funnel_stage TEXT,
    rubric TEXT,

    rough_hook TEXT,
    why_it_can_work TEXT,

    status TEXT NOT NULL DEFAULT 'generated',
    -- generated / duplicate_removed / approved / revise / rejected / improved

    parent_idea_id UUID REFERENCES ideas(id) ON DELETE SET NULL,

    raw_json JSONB DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### Важные поля

| Поле             | Зачем                                 |
| ---------------- | ------------------------------------- |
| `source_agent`   | понимать, какой генератор создал идею |
| `parent_idea_id` | связывать улучшенную идею с исходной  |
| `status`         | отслеживать прохождение через фильтры |
| `raw_json`       | хранить полный JSON от генератора     |

---

## 6.2. `idea_reviews`

Хранит оценки идей от критиков.

```sql
CREATE TABLE idea_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    idea_id UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,

    reviewer_agent TEXT NOT NULL,
    -- Idea Critic Agent / Garbage Filter Agent / Second Critic Agent

    audience_fit INT,
    pain_specificity INT,
    product_fit INT,
    retention_potential INT,
    novelty INT,
    production_simplicity INT,
    safety INT,

    total_score NUMERIC(5, 2),

    decision TEXT NOT NULL,
    -- approve / revise / reject / duplicate / garbage

    main_issue TEXT,
    comment TEXT,

    raw_json JSONB DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Зачем отдельная таблица

Одна идея может пройти несколько проверок:

```text
Idea Critic Agent
→ Garbage Filter Agent
→ Second Critic Agent
```

Поэтому оценки лучше хранить отдельно, а не внутри `ideas`.

---

# 7. Таблицы сценариев

## 7.1. `scripts`

Хранит сценарии по одобренным идеям.

```sql
CREATE TABLE scripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    idea_id UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    title TEXT NOT NULL,
    platform TEXT,

    target_persona TEXT,
    funnel_stage TEXT,
    duration TEXT,

    hook TEXT,
    core_message TEXT,
    cta TEXT,
    caption TEXT,
    shooting_notes TEXT,

    scene_by_scene JSONB NOT NULL DEFAULT '[]'::jsonb,
    props_needed JSONB DEFAULT '[]'::jsonb,

    status TEXT NOT NULL DEFAULT 'draft',
    -- draft / approved / revise / rejected / adapted

    raw_json JSONB DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### Пример `scene_by_scene`

```json
[
  {
    "time": "0-3 sec",
    "visual": "Крупный план полки с большим количеством средств",
    "voiceover": "Если ваш уход занимает 40 минут, проблема не в коже",
    "text_on_screen": "Уход стал слишком сложным?"
  },
  {
    "time": "4-12 sec",
    "visual": "Героиня убирает лишние средства",
    "voiceover": "Чаще всего проблема в том, что нет понятной системы",
    "text_on_screen": "Не больше средств, а понятная схема"
  }
]
```

---

## 7.2. `script_reviews`

Хранит оценки сценариев.

```sql
CREATE TABLE script_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    script_id UUID NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
    pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,

    reviewer_agent TEXT NOT NULL,
    -- Script Critic Agent / CTA Critic Agent

    hook_strength INT,
    clarity INT,
    pain_relevance INT,
    structure_score INT,
    no_water INT,
    retention INT,
    feasibility INT,
    brand_fit INT,
    safety INT,
    cta_score INT,

    total_score NUMERIC(5, 2),

    decision TEXT NOT NULL,
    -- approve / revise / reject / replace_cta

    issues JSONB DEFAULT '[]'::jsonb,
    improved_version JSONB DEFAULT '{}'::jsonb,

    comment TEXT,

    raw_json JSONB DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ DEFAULT now()
);
```

---

# 8. Финальный результат

## 8.1. `final_content_packs`

Хранит финальный пакет для выдачи пользователю.

```sql
CREATE TABLE final_content_packs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    title TEXT,

    brand_summary JSONB DEFAULT '{}'::jsonb,
    audience_summary JSONB DEFAULT '{}'::jsonb,
    content_strategy_summary JSONB DEFAULT '{}'::jsonb,

    approved_content JSONB DEFAULT '[]'::jsonb,
    rejected_content JSONB DEFAULT '[]'::jsonb,

    publishing_recommendations JSONB DEFAULT '[]'::jsonb,
    risk_notes JSONB DEFAULT '[]'::jsonb,
    next_steps_for_human JSONB DEFAULT '[]'::jsonb,

    full_pack_json JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Почему хранить `full_pack_json`

Потому что финальный пакет может меняться по структуре. Для MVP лучше не дробить его на 20 таблиц.

---

# 9. Логи моделей и стоимости

## 9.1. `model_usage_logs`

```sql
CREATE TABLE model_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,

    agent_name TEXT NOT NULL,
    model_id TEXT NOT NULL,
    provider TEXT DEFAULT 'openrouter',

    input_tokens INT DEFAULT 0,
    output_tokens INT DEFAULT 0,
    total_tokens INT GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,

    input_cost NUMERIC(12, 6) DEFAULT 0,
    output_cost NUMERIC(12, 6) DEFAULT 0,
    total_cost NUMERIC(12, 6) GENERATED ALWAYS AS (input_cost + output_cost) STORED,

    latency_ms INT,
    status TEXT DEFAULT 'success',
    -- success / failed / timeout / retry

    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Зачем нужна

Чтобы контролировать экономику:

```text
Сколько стоит один проект?
Какой агент самый дорогой?
Какая модель дает много output tokens?
Где стоит удешевлять?
```

---

## 9.2. `pipeline_errors`

```sql
CREATE TABLE pipeline_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,

    agent_name TEXT,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,

    raw_response TEXT,
    input_snapshot JSONB DEFAULT '{}'::jsonb,

    is_recoverable BOOLEAN DEFAULT TRUE,
    retry_count INT DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Типы ошибок

```text
llm_timeout
invalid_json
schema_validation_failed
openrouter_error
database_error
pipeline_interrupted
unknown_error
```

---

# 10. Дополнительные таблицы, которые стоит добавить сразу

## 10.1. `prompt_templates`

Не обязательно, но я бы добавил сразу. Это поможет версионировать промпты.

```sql
CREATE TABLE prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    agent_name TEXT NOT NULL,
    version TEXT NOT NULL,

    system_prompt TEXT NOT NULL,
    user_prompt_template TEXT NOT NULL,

    response_schema JSONB DEFAULT '{}'::jsonb,

    is_active BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(agent_name, version)
);
```

### Зачем нужна

Чтобы понимать:

```text
Какая версия промпта сгенерировала результат?
Почему после правок качество изменилось?
```

---

## 10.2. `model_policies`

Настройки моделей для агентов.

```sql
CREATE TABLE model_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    agent_name TEXT NOT NULL UNIQUE,

    primary_model TEXT NOT NULL,
    fallback_model TEXT,

    temperature NUMERIC(3, 2) DEFAULT 0.3,
    max_tokens INT,

    quality_mode TEXT DEFAULT 'balanced',

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### Пример

```json
{
  "agent_name": "Idea Critic Agent",
  "primary_model": "google/gemini-2.5-flash",
  "fallback_model": "qwen/qwen3.6-plus",
  "temperature": 0.1,
  "quality_mode": "balanced"
}
```

---

# 11. Индексы

Минимальные индексы для MVP:

```sql
CREATE INDEX idx_projects_user_id 
ON projects(user_id);

CREATE INDEX idx_project_inputs_project_id 
ON project_inputs(project_id);

CREATE INDEX idx_pipeline_runs_project_id 
ON pipeline_runs(project_id);

CREATE INDEX idx_pipeline_runs_status 
ON pipeline_runs(status);

CREATE INDEX idx_agent_runs_pipeline_run_id 
ON agent_runs(pipeline_run_id);

CREATE INDEX idx_agent_runs_agent_name 
ON agent_runs(agent_name);

CREATE INDEX idx_ideas_project_id 
ON ideas(project_id);

CREATE INDEX idx_ideas_pipeline_run_id 
ON ideas(pipeline_run_id);

CREATE INDEX idx_ideas_status 
ON ideas(status);

CREATE INDEX idx_idea_reviews_idea_id 
ON idea_reviews(idea_id);

CREATE INDEX idx_scripts_idea_id 
ON scripts(idea_id);

CREATE INDEX idx_scripts_project_id 
ON scripts(project_id);

CREATE INDEX idx_model_usage_pipeline_run_id 
ON model_usage_logs(pipeline_run_id);

CREATE INDEX idx_errors_pipeline_run_id 
ON pipeline_errors(pipeline_run_id);
```

Для JSONB можно добавить позже:

```sql
CREATE INDEX idx_agent_runs_output_json_gin 
ON agent_runs USING GIN (output_json);

CREATE INDEX idx_final_pack_json_gin 
ON final_content_packs USING GIN (full_pack_json);
```

---

# 12. Статусы

## `pipeline_runs.status`

```text
pending
running
completed
failed
cancelled
```

## `agent_runs.status`

```text
pending
running
completed
failed
skipped
```

## `ideas.status`

```text
generated
duplicate_removed
approved
revise
rejected
improved
```

## `scripts.status`

```text
draft
approved
revise
rejected
adapted
```

---

# 13. Минимальная версия модели данных

Если нужно еще проще, можно стартовать с 7 таблиц:

```text
users
projects
project_inputs
pipeline_runs
agent_runs
ideas
scripts
model_usage_logs
```

Но я бы не убирал `idea_reviews`, `script_reviews` и `pipeline_errors`, потому что они нужны для контроля качества.

---

# 14. Рекомендуемая MVP-модель

## Оставить обязательно

```text
users
projects
project_inputs
pipeline_runs
agent_runs
ideas
idea_reviews
scripts
script_reviews
final_content_packs
model_usage_logs
pipeline_errors
```

## Желательно добавить

```text
prompt_templates
model_policies
```

## Не нужно на MVP

```text
files
embeddings
vector_memory
competitor_profiles
content_calendar
payments
subscriptions
teams
roles
permissions
```

---

# 15. Итоговая структура БД MVP

```text
Core:
- users
- projects
- project_inputs

Pipeline:
- pipeline_runs
- agent_runs

Content:
- ideas
- idea_reviews
- scripts
- script_reviews
- final_content_packs

Operations:
- model_usage_logs
- pipeline_errors

Configuration:
- prompt_templates
- model_policies
```

Это достаточно компактная модель, но она уже покрывает:

```text
полный агентный пайплайн,
сохранение всех промежуточных результатов,
контроль качества,
историю генераций,
логи стоимости,
ошибки,
версионирование промптов,
настройки моделей.
```
