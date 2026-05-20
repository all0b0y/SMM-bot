# Документ: архитектура AI-агентной SMM-системы

## 1. Назначение системы

Система должна принимать на вход **описание компании / бренда / продукта / блога** в свободной форме и автоматически строить SMM-логику:

```text
описание компании
→ структурированный бриф
→ сегменты ЦА
→ подсегменты
→ портреты потребителей
→ боли / желания / триггеры
→ позиционирование
→ конкурентные инсайты
→ стратегия контента
→ рубрикатор
→ идеи видео
→ фильтрация мусора
→ сценарии
→ проверка сценариев
→ финальный контент-пак
```

Базовая методология опирается на логику из ваших материалов: сначала выделяются сегменты, затем подсегменты, по ним строится портрет потребителя с возрастом, доходом, сегментом и болью, после чего боли превращаются в идеи и сценарии. Для сценария используется простая базовая формула: **проблема / боль + польза + призыв к действию**. 

Второй важный источник — структура полноценной SMM-стратегии: описание компании, позиционирование, УТП, цели соцсетей, ЦА, триггеры, анализ конкурентов, контент-план, tone of voice, рубрикатор, Stories, визуальная стилистика и методы продвижения. 

---

# 2. Общая архитектура

## 2.1. Верхнеуровневая схема

```text
INPUT
  ↓
Brief Agent
  ↓
Audience Segmentation Agent
  ↓
Persona Builder Agent
  ↓
Pain & Trigger Agent
  ↓
Positioning Agent
  ↓
Competitor Insight Agent
  ↓
Content Strategy Agent
  ↓
Rubricator Agent
  ↓
Parallel Idea Generators
  ↓
Deduplication Agent
  ↓
Idea Critic Agent
  ↓
Garbage Filter Agent
  ↓
Idea Improvement Agent
  ↓
Second Critic Agent
  ↓
Script Writer Agent
  ↓
Script Critic Agent
  ↓
CTA Critic Agent
  ↓
Platform Adaptation Agent
  ↓
Final Content Pack Agent
```

## 2.2. Ключевой принцип

Генераторы идей **не имеют права напрямую передавать результат сценаристу**.

Правильная цепочка:

```text
генерация идей
→ дедупликация
→ критика
→ анти-мусорный фильтр
→ улучшение
→ повторная критика
→ только затем сценарии
```

Это обязательное условие, потому что в SMM слабые идеи часто выглядят “нормально” на уровне текста, но проваливаются по конкретике, связи с ЦА, связи с продуктом и удержанию.

---

# 3. Слои системы

## Слой 1. Input & Brief Normalization

**Агенты:**

* Brief Agent

**Назначение слоя:**
Принять большое неструктурированное описание компании и превратить его в машинно-читаемый бриф.

**Что делает слой:**

* извлекает нишу;
* определяет тип проекта: бизнес, блог, эксперт, бренд, продукт;
* вытаскивает УТП;
* фиксирует цели;
* фиксирует tone of voice;
* определяет ограничения;
* отделяет факты от предположений;
* помечает недостающие данные.

**Выход слоя:**

```json
{
  "brief": {
    "project_type": "",
    "niche": "",
    "brand_name": "",
    "product_or_service": "",
    "geo": "",
    "platforms": [],
    "goals": [],
    "usp": "",
    "positioning_raw": "",
    "tone_of_voice": "",
    "constraints": [],
    "forbidden_topics": []
  },
  "missing_data": [],
  "assumptions": []
}
```

**Рекомендуемая LLM:** `qwen/qwen3.6-flash`

**Почему:**
Этот агент делает структурирование, извлечение и нормализацию. Для этого не нужна дорогая frontier-модель. Nvidia Nemotron-Lite на OpenRouter имеет 1M контекст и стоит $0.10 / 1M input tokens и $0.40 / 1M output tokens, что делает ее хорошей базовой моделью для дешевого парсинга длинных описаний. ([OpenRouter][1])

---

## Слой 2. Audience Intelligence

**Агенты:**

* Audience Segmentation Agent
* Persona Builder Agent
* Pain & Trigger Agent

**Назначение слоя:**
Построить стратегическое понимание аудитории.

**Что делает слой:**

1. Делит аудиторию на сегменты.
2. Делит сегменты на подсегменты.
3. Строит портреты потребителей.
4. Извлекает боли, желания, возражения, триггеры.
5. Формирует контентные возможности.

В ваших материалах отдельно указано, что сегменты нужно дробить на подсегменты, а затем строить конкретный портрет потребителя с именем, возрастом, сегментом, семейным положением, доходом и болью. 

**Рекомендуемые LLM:**

| Агент                       | Основная модель          | Резерв                    |
| --------------------------- | ------------------------ | ------------------------- |
| Audience Segmentation Agent | `deepseek/deepseek-chat` | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` |
| Persona Builder Agent       | `deepseek/deepseek-chat` | `qwen/qwen3.6-plus`       |
| Pain & Trigger Agent        | `qwen/qwen3.6-plus`      | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` |

**Почему:**
`deepseek/deepseek-chat` стоит $0.32 / 1M input и $0.89 / 1M output tokens, при этом OpenRouter описывает DeepSeek-V3 как сильную модель для instruction following и coding, конкурирующую с ведущими open-source моделями. Она подходит для массовых аналитических и генеративных шагов без высокой стоимости. ([OpenRouter][2])

`qwen/qwen3.6-plus` стоит $0.325 / 1M input и $1.95 / 1M output tokens, имеет 1M контекст и позиционируется как модель с сильным reasoning и agentic coding. Ее лучше использовать там, где нужна более сложная смысловая сборка: боли, скрытые мотивации, связка триггеров с продуктом. ([OpenRouter][3])

---

## Слой 3. Brand & Market Strategy

**Агенты:**

* Positioning Agent
* Competitor Insight Agent
* Content Strategy Agent
* Rubricator Agent

**Назначение слоя:**
Перевести аналитику ЦА в SMM-стратегию.

**Что делает слой:**

* формирует позиционирование;
* выделяет УТП;
* определяет допустимые и запрещенные обещания;
* ищет конкурентные паттерны;
* определяет возможности для отстройки;
* собирает контентные столпы;
* создает рубрикатор.

В SMM-стратегии Vita Cavcasea есть именно такая логика: позиционирование, УТП, цели соцсетей, аудитория, триггеры, анализ конкурентов, tone of voice, рубрикатор и методы продвижения. 

**Рекомендуемые LLM:**

| Агент                    | Основная модель           | Резерв                    |
| ------------------------ | ------------------------- | ------------------------- |
| Positioning Agent        | `qwen/qwen3.6-plus`       | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` |
| Competitor Insight Agent | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | `qwen/qwen3.6-plus`       |
| Content Strategy Agent   | `qwen/qwen3.6-plus`       | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` |
| Rubricator Agent         | `deepseek/deepseek-chat`  | `qwen/qwen3.6-plus`       |

**Почему:**
Здесь уже не просто извлечение, а стратегическая сборка. Нужны модели уровня “хороший баланс reasoning + цена”. Для этого оптимальны Qwen3.6 Plus и Nvidia Nemotron. Nvidia Nemotron на OpenRouter имеет 1M контекст и стоит $0.30 / 1M input и $2.50 / 1M output tokens; он подходит для reasoning, coding, математики и научных задач, а также имеет встроенные thinking-возможности. ([OpenRouter][4])

---

## Слой 4. Idea Generation

**Агенты:**

* Pain-Based Generator
* Trigger-Based Generator
* Competitor Gap Generator
* Funnel-Based Generator
* Platform Format Generator

**Назначение слоя:**
Создать большой пул идей из разных логик, а не из одного генератора.

**Почему несколько генераторов:**
Если использовать одного агента, идеи будут однотипными. Параллельные генераторы создают разные классы идей:

| Генератор                 | Что производит                                            |
| ------------------------- | --------------------------------------------------------- |
| Pain-Based Generator      | идеи от болей ЦА                                          |
| Trigger-Based Generator   | идеи от триггеров: простота, время, натуральность, выгода |
| Competitor Gap Generator  | идеи от слабых мест конкурентов                           |
| Funnel-Based Generator    | идеи под охват, доверие, продажу, удержание               |
| Platform Format Generator | идеи под Reels, Shorts, TikTok, VK Клипы                  |

**Рекомендуемые LLM:**

| Агент                     | Основная модель          | Резерв                         |
| ------------------------- | ------------------------ | ------------------------------ |
| Pain-Based Generator      | `deepseek/deepseek-chat` | `qwen/qwen3.6-plus`            |
| Trigger-Based Generator   | `deepseek/deepseek-chat` | `qwen/qwen3.6-plus`            |
| Competitor Gap Generator  | `qwen/qwen3.6-plus`      | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`      |
| Funnel-Based Generator    | `deepseek/deepseek-chat` | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`      |
| Platform Format Generator | `deepseek/deepseek-chat` | `qwen/qwen3.6-flash` |

**Почему:**
Генерация идей требует объема. Здесь нельзя ставить дорогую модель на каждый вызов, потому что генераторов несколько и они будут давать десятки идей. `deepseek/deepseek-chat` — хороший default для массовой генерации по цене / качеству. Для конкурентной отстройки лучше использовать `qwen/qwen3.6-plus`, потому что там больше стратегического reasoning.

---

## Слой 5. Quality Control

**Агенты:**

* Deduplication Agent
* Idea Critic Agent
* Garbage Filter Agent
* Idea Improvement Agent
* Second Critic Agent

**Назначение слоя:**
Исключить мусорные идеи, повторы, банальности и рискованные формулировки.

**Что считается браком:**

* идея подходит любой нише;
* нет конкретного сегмента ЦА;
* нет боли / желания / ситуации;
* нет связи с продуктом;
* идея звучит как шаблон;
* нет конфликта или пользы;
* невозможно снять как короткое видео;
* есть ложные обещания;
* CTA не связан с видео;
* идея повторяет уже принятую.

**Рекомендуемые LLM:**

| Агент                  | Основная модель                | Резерв                   | Температура |
| ---------------------- | ------------------------------ | ------------------------ | ----------: |
| Deduplication Agent    | `qwen/qwen3.6-flash` | `deepseek/deepseek-chat` |         0.1 |
| Idea Critic Agent      | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`      | `qwen/qwen3.6-plus`      |         0.1 |
| Garbage Filter Agent   | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`      | `qwen/qwen3.6-plus`      |     0.0–0.1 |
| Idea Improvement Agent | `deepseek/deepseek-chat`       | `qwen/qwen3.6-plus`      |     0.5–0.7 |
| Second Critic Agent    | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`      | `qwen/qwen3.6-plus`      |     0.0–0.1 |

**Почему:**
Критики должны быть строже генераторов. Лучше использовать более надежную reasoning-модель с низкой температурой. На критических этапах можно подключать `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`, а не Flash-Lite, потому что качество отбора важнее экономии.

---

## Слой 6. Script Production

**Агенты:**

* Script Writer Agent
* Script Critic Agent
* CTA Critic Agent
* Platform Adaptation Agent

**Назначение слоя:**
Превратить одобренные идеи в сценарии и адаптировать их под площадку.

**Базовая структура сценария:**

```text
1. Хук
2. Узнаваемая боль
3. Причина проблемы
4. Бесплатная польза
5. CTA
```

Эта структура расширяет вашу базовую формулу “проблема / боль + польза + call to action”. 

**Рекомендуемые LLM:**

| Агент                     | Основная модель                | Резерв                    | Температура |
| ------------------------- | ------------------------------ | ------------------------- | ----------: |
| Script Writer Agent       | `qwen/qwen3.6-plus`            | `deepseek/deepseek-chat`  |         0.6 |
| Script Critic Agent       | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`      | `qwen/qwen3.6-plus`       |         0.1 |
| CTA Critic Agent          | `qwen/qwen3.6-flash` | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` |         0.1 |
| Platform Adaptation Agent | `deepseek/deepseek-chat`       | `qwen/qwen3.6-plus`       |     0.4–0.6 |

**Почему:**
Сценарии требуют хорошего языка, структуры, удержания и адаптации под короткий формат. `qwen/qwen3.6-plus` лучше поставить основным сценаристом, а `deepseek/deepseek-chat` использовать как более дешевый fallback или для массовых черновиков.

---

## Слой 7. Final Packaging

**Агент:**

* Final Content Pack Agent

**Назначение слоя:**
Собрать финальный результат в формат, который можно отдавать пользователю.

**Выход:**

```json
{
  "brand_summary": {},
  "audience_summary": {},
  "content_strategy_summary": {},
  "approved_content": [],
  "rejected_content": [],
  "publishing_recommendations": [],
  "risk_notes": [],
  "next_steps_for_human": []
}
```

**Рекомендуемая LLM:** `qwen/qwen3.6-flash`
**Резерв:** `qwen/qwen3.6-plus`

**Почему:**
Финальная сборка — это не самая сложная reasoning-задача, если все предыдущие агенты вернули валидный JSON. Дорогая модель нужна только если нужно переписать результат в презентационный, коммерческий или стратегический стиль.

---

# 4. Модельная политика OpenRouter

## 4.1. Почему OpenRouter подходит

OpenRouter дает доступ к сотням моделей через единый API и автоматически работает с fallback и выбором cost-effective вариантов. ([OpenRouter][5])

Также OpenRouter позволяет настраивать routing через `provider` object и по умолчанию балансирует запросы между лучшими провайдерами для повышения uptime. ([OpenRouter][6])

Для вашей системы это важно по трем причинам:

1. можно использовать дешевые модели на массовых задачах;
2. можно ставить более сильные модели на критические quality gates;
3. можно делать fallback при сбоях или деградации качества.

---

## 4.2. Рекомендуемые модельные tiers

### Tier A — дешевые структурные задачи

**Модель:** `qwen/qwen3.6-flash`

Использовать для:

* извлечения данных;
* нормализации брифа;
* JSON-сборки;
* CTA-проверки;
* дедупликации;
* финальной упаковки;
* коротких служебных проверок.

**Почему:** Быстрая и дешевая модель от Qwen для структурных задач. Хорошо следует JSON-инструкциям, поддерживает structured output.

---

### Tier B — массовая генерация и SMM-текст

**Модель:** `deepseek/deepseek-chat`

Использовать для:

* генерации идей;
* черновых сценариев;
* рубрикатора;
* улучшения идей;
* адаптации под платформы.

**Цена:** $0.32 / 1M input, $0.89 / 1M output. ([OpenRouter][2])

---

### Tier C — стратегия, позиционирование, сложное reasoning

**Модель:** `qwen/qwen3.6-plus`

Использовать для:

* позиционирования;
* болей и скрытых мотиваций;
* сложной стратегии;
* сценариев финального качества;
* конкурентной отстройки.

**Цена:** $0.325 / 1M input, $1.95 / 1M output. ([OpenRouter][3])

---

### Tier D — строгая критика и reasoning-контроль

**Модель:** `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`

Использовать для:

* Idea Critic Agent;
* Garbage Filter Agent;
* Second Critic Agent;
* Script Critic Agent;
* сложной проверки соответствия стратегии.

**Почему:** Nvidia Nemotron — reasoning-модель с бесплатным доступом через OpenRouter. Быстрее большинства frontier-моделей, хорошо справляется с аналитическими и критическими задачами. Используется на всех quality gates.

---

### Tier E — премиум-резерв, не default

**Модель:** `qwen/qwen3.6-plus`

Использовать только для:

* сложных enterprise-клиентов;
* финальной проверки большого стратегического документа;
* спорных сценариев;
* cases, где стоимость менее важна, чем качество.

`qwen/qwen3.6-plus` — самая сильная модель в нашем стеке: глубокий reasoning, 1M контекст, хороший русский язык. Стоит использовать как escalation там, где остальные модели не справились.

---

# 5. Таблица: агент → задача → модель

| Агент                       | Задача                                  | Основная LLM         | Fallback             | Причина выбора                        |
| --------------------------- | --------------------------------------- | -------------------- | -------------------- | ------------------------------------- |
| Brief Agent                 | Извлечение и структурирование брифа     | `qwen3.6-flash`      | `deepseek-chat`      | Быстро, дёшево, JSON-задача           |
| Audience Segmentation Agent | Сегменты и подсегменты                  | `deepseek-chat`      | `qwen3.6-plus`       | Хороший баланс цены и качества        |
| Persona Builder Agent       | Портреты ЦА                             | `deepseek-chat`      | `qwen3.6-plus`       | Нужна генерация реалистичных персон   |
| Pain & Trigger Agent        | Боли, желания, триггеры                 | `qwen3.6-plus`       | `nemotron:free`      | Нужна смысловая глубина               |
| Positioning Agent           | УТП, позиционирование, границы обещаний | `qwen3.6-plus`       | `nemotron:free`      | Стратегическая задача                 |
| Competitor Insight Agent    | Паттерны конкурентов и отстройка        | `nemotron:free`      | `qwen3.6-plus`       | Нужен reasoning и анализ              |
| Content Strategy Agent      | Контентные столпы и воронка             | `qwen3.6-plus`       | `nemotron:free`      | Сложная SMM-сборка                    |
| Rubricator Agent            | Рубрики и темы                          | `deepseek-chat`      | `qwen3.6-plus`       | Генеративная задача средней сложности |
| Pain-Based Generator        | Идеи от болей                           | `deepseek-chat`      | `qwen3.6-plus`       | Массовая генерация                    |
| Trigger-Based Generator     | Идеи от триггеров                       | `deepseek-chat`      | `qwen3.6-plus`       | Массовая генерация                    |
| Competitor Gap Generator    | Идеи от слабостей конкурентов           | `qwen3.6-plus`       | `nemotron:free`      | Нужна отстройка                       |
| Funnel-Based Generator      | Идеи под воронку                        | `deepseek-chat`      | `nemotron:free`      | Генерация + структура                 |
| Platform Format Generator   | Идеи под Reels / Shorts / TikTok / VK   | `deepseek-chat`      | `qwen3.6-flash`      | Форматная генерация                   |
| Deduplication Agent         | Удаление дублей                         | `qwen3.6-flash`      | `deepseek-chat`      | Быстрая логическая проверка           |
| Idea Critic Agent           | Скоринг идей                            | `nemotron:free`      | `qwen3.6-plus`       | Строгий reasoning                     |
| Garbage Filter Agent        | Анти-мусорный фильтр                    | `nemotron:free`      | `qwen3.6-plus`       | Критический gate                      |
| Idea Improvement Agent      | Улучшение слабых идей                   | `deepseek-chat`      | `qwen3.6-plus`       | Креативная переработка                |
| Second Critic Agent         | Повторная проверка                      | `nemotron:free`      | `qwen3.6-plus`       | Независимый контроль                  |
| Script Writer Agent         | Сценарии видео                          | `qwen3.6-plus`       | `deepseek-chat`      | Лучше качество текста                 |
| Script Critic Agent         | Проверка сценариев                      | `nemotron:free`      | `qwen3.6-plus`       | Строгая оценка                        |
| CTA Critic Agent            | Проверка CTA                            | `qwen3.6-flash`      | `nemotron:free`      | Простая, но важная проверка           |
| Platform Adaptation Agent   | Адаптация под площадку                  | `deepseek-chat`      | `qwen3.6-plus`       | Текстовая адаптация                   |
| Final Content Pack Agent    | Финальная сборка                        | `qwen3.6-flash`      | `qwen3.6-plus`       | Сборка JSON и итогового пакета        |

---

# 6. Настройки генерации

## 6.1. Температура

| Тип агента        | Temperature |
| ----------------- | ----------: |
| Извлечение данных |     0.0–0.2 |
| Сегментация       |     0.2–0.4 |
| Персоны           |     0.4–0.6 |
| Стратегия         |     0.2–0.4 |
| Генерация идей    |     0.7–0.9 |
| Критика           |     0.0–0.2 |
| Улучшение идей    |     0.5–0.7 |
| Сценарии          |     0.5–0.7 |
| Финальная сборка  |     0.1–0.3 |

## 6.2. Structured Outputs

Все агенты должны возвращать JSON по схеме. OpenRouter поддерживает structured outputs для совместимых моделей, что позволяет требовать ответ по JSON Schema и надежно парсить результат приложением. ([OpenRouter][9])

**Рекомендация:**
Для каждого агента создать Pydantic-схему и прокидывать ее в `response_format`.

---

# 7. Технический стек

## 7.1. Backend

**Рекомендация:** Python 3.12 + FastAPI.

FastAPI — современный высокопроизводительный Python framework для API, основанный на стандартных type hints. ([FastAPI][10])

**Почему подходит:**

* удобно строить API;
* хорошо работает с Pydantic;
* удобно валидировать JSON;
* легко интегрируется с OpenAI-compatible SDK;
* подходит для MVP и production.

---

## 7.2. Agent Orchestration

**Рекомендация:** LangGraph.

LangGraph — низкоуровневый orchestration framework для long-running, stateful agents; он поддерживает durable execution, streaming, human-in-the-loop, memory и debugging. ([docs.langchain.com][11])

**Почему подходит именно вам:**

* архитектура у вас графовая, а не линейная;
* есть параллельные генераторы идей;
* есть циклы `revise → improve → second review`;
* нужны quality gates;
* нужен state между агентами;
* позже можно добавить human-in-the-loop.

---

## 7.3. LLM Gateway

**Рекомендация:** OpenRouter API через OpenAI-compatible client.

**Использовать:**

* `openai` Python SDK с `base_url="https://openrouter.ai/api/v1"`;
* свой `ModelRouter` внутри приложения;
* конфиг моделей в YAML / PostgreSQL;
* fallback-массивы моделей;
* cost logging по каждому вызову.

OpenRouter предоставляет единый API к моделям и умеет выбирать cost-effective варианты и fallback. ([OpenRouter][5])

---

## 7.4. Data Validation

**Рекомендация:** Pydantic v2.

Pydantic использует типы для валидации и сериализации данных; это подходит для строгих схем каждого агента. ([Pydantic Docs][12])

**Использование:**

* `BriefSchema`;
* `AudienceSegmentsSchema`;
* `PersonasSchema`;
* `IdeasSchema`;
* `CriticReviewSchema`;
* `ScriptsSchema`;
* `FinalContentPackSchema`.

---

## 7.5. Database

**Рекомендация для MVP и production:** PostgreSQL + pgvector.

pgvector позволяет хранить вектора прямо в PostgreSQL, поддерживает exact / approximate nearest neighbor search и метрики L2, inner product, cosine, L1, Hamming, Jaccard. ([GitHub][13])

**Что хранить:**

* проекты;
* брифы;
* результаты агентов;
* идеи;
* оценки;
* сценарии;
* rejected ideas;
* брендовые ограничения;
* embeddings для дедупликации;
* историю успешных и слабых идей.

---

## 7.6. Vector Search / Memory

**Рекомендация:** PostgreSQL + pgvector.

Для проекта достаточно хранить embeddings и делать semantic search внутри PostgreSQL. Это упрощает инфраструктуру: одна база закрывает и основные данные, и векторный поиск для дедупликации идей, memory и поиска по прошлым результатам.

---

## 7.7. Queue & Background Jobs

**Рекомендация:** Celery + Redis.

Celery — distributed task queue для Python, поддерживает real-time processing и task scheduling. ([docs.celeryq.dev][14])

**Почему нужно:**

* генерация контент-пака может занимать десятки LLM-вызовов;
* нельзя держать HTTP-запрос открытым слишком долго;
* нужны retry;
* нужны очереди по приоритетам;
* нужен контроль стоимости.

**Очереди:**

```text
brief_queue
audience_queue
strategy_queue
idea_generation_queue
quality_queue
script_queue
final_pack_queue
```

---

## 7.8. Cache

**Рекомендация:** Redis.

**Что кэшировать:**

* результаты одинаковых брифов;
* промежуточные JSON;
* expensive prompts;
* embeddings;
* результаты competitor analysis;
* результаты rubricator.

Также стоит использовать prompt caching OpenRouter, где поддерживается моделью. OpenRouter описывает prompt caching как способ снизить inference cost, а sticky routing помогает удерживать запросы на том же provider endpoint для максимизации cache hit rate. ([OpenRouter][15])

---

## 7.9. Логи и мониторинг

**Рекомендация:** встроенные application logs + таблица `model_usage_logs` + Sentry.

Отдельный стек аналитики и мониторинга на MVP не нужен. Достаточно логировать ключевые события приложения, ошибки и стоимость LLM-вызовов в PostgreSQL.

**Что логировать:**

* agent name;
* model;
* prompt tokens;
* completion tokens;
* cost;
* latency;
* retries;
* validation errors;
* score каждого critic agent;
* причины reject;
* human override.

---

## 7.10. Bot

**Рекомендация для MVP:**

* Telegram Bot API;
* Python-бот на `aiogram`;
* webhook через FastAPI;
* фоновые задачи через Celery.


**Основные сценарии в Telegram:**

1. Создание проекта через команду или кнопку.
2. Отправка описания компании текстом или файлом.
3. Запуск генерации SMM-стратегии.
4. Получение статуса обработки.
5. Просмотр брифа, ЦА, идей и сценариев сообщениями.
6. Выбор и доработка идей через inline-кнопки.
7. Экспорт финального контент-пака файлом.

---

# 8. Production-архитектура

```

---

# 9. База данных: основные сущности

## Таблицы

```text
users
projects
brand_briefs
agent_runs
audience_segments
personas
pain_trigger_maps
positioning_documents
competitor_insights
content_strategies
rubricators
ideas
idea_scores
idea_duplicates
rejected_ideas
scripts
script_scores
final_content_packs
model_usage_logs
prompt_versions
quality_rules
```

## Важная таблица: `model_usage_logs`

```sql
model_usage_logs
- id
- project_id
- agent_name
- model_id
- provider
- input_tokens
- output_tokens
- estimated_cost
- latency_ms
- status
- error_message
- created_at
```

Эта таблица нужна, чтобы вы реально контролировали связку **цена → качество → надежность**.

---

# 10. Quality gates

## Gate 1. Audience Fit

Идея проходит, только если:

```text
audience_fit >= 4/5
```

## Gate 2. Pain Specificity

Идея проходит, только если:

```text
pain_specificity >= 4/5
```

## Gate 3. Product Fit

Идея проходит, только если:

```text
product_fit >= 3/5
```

## Gate 4. Safety

Идея проходит, только если:

```text
safety = 5/5
```

## Gate 5. Garbage Filter

Идея отклоняется, если:

```text
- подходит любой нише;
- звучит шаблонно;
- нет конкретной ситуации;
- нет причины досмотреть;
- нет связи с продуктом;
- есть ложное обещание;
- неясно, кому это видео.
```

---

# 11. API-структура

## Основные endpoints

```text
POST /projects
POST /projects/{id}/input
POST /projects/{id}/run
GET  /projects/{id}/status
GET  /projects/{id}/brief
GET  /projects/{id}/audience
GET  /projects/{id}/ideas
GET  /projects/{id}/scripts
GET  /projects/{id}/final-pack
POST /projects/{id}/human-review
POST /projects/{id}/export
```

## Endpoint запуска

```json
{
  "project_id": "uuid",
  "input_type": "company_description",
  "platform": "instagram_reels",
  "ideas_count": 50,
  "scripts_count": 10,
  "quality_mode": "balanced",
  "model_policy": "cost_quality_balanced"
}
```

---

# 12. Режимы качества

## 12.1. Economy Mode

Использовать, если пользователь тестирует систему.

```text
Brief:    qwen/qwen3.6-flash
Analysis: deepseek/deepseek-chat
Strategy: deepseek/deepseek-chat
Ideas:    deepseek/deepseek-chat
Critics:  qwen/qwen3.6-flash
Scripts:  deepseek/deepseek-chat
```

## 12.2. Balanced Mode

Основной режим.

```text
Brief:         qwen/qwen3.6-flash
Audience:      deepseek/deepseek-chat
Pain/Trigger:  qwen/qwen3.6-plus
Strategy:      qwen/qwen3.6-plus
Ideas:         deepseek/deepseek-chat
Critics:       nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free
Scripts:       qwen/qwen3.6-plus
Final:         qwen/qwen3.6-flash
```

## 12.3. High Quality Mode

Для дорогих клиентов или сложных ниш.

```text
Brief:      nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free
Audience:   qwen/qwen3.6-plus
Pain/Trigger: qwen/qwen3.6-plus
Strategy:   nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free + qwen/qwen3.6-plus
Ideas:      deepseek/deepseek-chat + qwen/qwen3.6-plus
Critics:    nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free
Scripts:    qwen/qwen3.6-plus
Escalation: qwen/qwen3.6-plus
```

---

# 13. Privacy и данные

Если в систему будут загружаться брендбуки, коммерческие материалы, клиентские PDF и внутренние стратегии, нужно добавить privacy controls.

OpenRouter поддерживает Zero Data Retention routing: ZDR означает, что provider не хранит данные, а OpenRouter позволяет ограничивать routing только endpoint’ами с Zero Data Retention policy. ([OpenRouter][16])

**Рекомендация:**

* для обычных клиентов: стандартный routing;
* для чувствительных клиентов: ZDR-only;
* для enterprise: отдельные API keys, caps, audit logs;
* не отправлять персональные данные без необходимости;
* хранить prompts и outputs только если пользователь дал согласие.

---

# 14. Рекомендуемый MVP

## MVP-версия без лишней сложности

```text
FastAPI
PostgreSQL
Redis
Celery
LangGraph
OpenRouter
Pydantic
Telegram Bot API
aiogram
```

## MVP-граф агентов

```text
Brief Agent
→ Audience Segmentation Agent
→ Persona Builder Agent
→ Pain & Trigger Agent
→ Positioning Agent
→ Content Strategy Agent
→ Rubricator Agent
→ 3 Idea Generators
→ Deduplication Agent
→ Idea Critic Agent
→ Garbage Filter Agent
→ Script Writer Agent
→ Script Critic Agent
→ Final Content Pack Agent
```

На MVP можно временно убрать:

* Second Critic Agent;
* CTA Critic Agent как отдельный агент;
* Platform Adaptation Agent как отдельный агент;
* Competitor Insight Agent, если нет данных по конкурентам.

Но в production их лучше вернуть.

---

# 15. Итоговая рекомендация

## Основной стек

```text
Backend: Python 3.12 + FastAPI
Orchestration: LangGraph
LLM Gateway: OpenRouter API
Validation: Pydantic v2
Database: PostgreSQL + pgvector
Queue: Celery + Redis
Cache: Redis
Bot: Telegram Bot API + aiogram
Логи и ошибки: application logs + model_usage_logs + Sentry
Deployment MVP: Docker Compose
Deployment production: Docker Compose / managed containers
```

## Основная модельная политика

```text
Быстрые служебные задачи (бриф, дедупликация, финальная сборка):
qwen/qwen3.6-flash

Массовая генерация (идеи, рубрикатор, сценарии-черновики):
deepseek/deepseek-chat

Стратегия и сложная смысловая сборка (позиционирование, боли, сценарии):
qwen/qwen3.6-plus

Критика и контроль качества (idea critic, garbage filter, script critic):
nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free

Эскалация для сложных задач:
qwen/qwen3.6-plus
```

Главная логика: **дешевая модель на объем, сильная модель на стратегию, строгая модель на контроль качества, премиум-модель только на исключения**. Так система не будет оверпрайс, но сохранит надежность на критических участках.

[1]: https://openrouter.ai/google/gemini-2.5-flash-lite "Nvidia Nemotron Lite - API Pricing & Benchmarks | OpenRouter"
[2]: https://openrouter.ai/deepseek/deepseek-chat "DeepSeek V3 - API Pricing & Providers | OpenRouter"
[3]: https://openrouter.ai/qwen/qwen3.6-plus "Qwen3.6 Plus - API Pricing & Providers | OpenRouter"
[4]: https://openrouter.ai/google/gemini-2.5-flash "Nvidia Nemotron - API Pricing & Benchmarks | OpenRouter"
[5]: https://openrouter.ai/docs/quickstart "OpenRouter Quickstart Guide | Developer Documentation | OpenRouter | Documentation"
[6]: https://openrouter.ai/docs/guides/routing/provider-selection "Provider Routing | Intelligent Multi-Provider Request Routing | OpenRouter | Documentation"
[7]: https://openrouter.ai/google/gemini-3-flash-preview/pricing "Google: Gemini 3 Flash Preview – Effective Pricing | OpenRouter"
[8]: https://openrouter.ai/anthropic/claude-sonnet-4.6 "Qwen Plus - API Pricing & Providers | OpenRouter"
[9]: https://openrouter.ai/docs/guides/features/structured-outputs "Structured Outputs | Enforce JSON Schema in OpenRouter API Responses | OpenRouter | Documentation"
[10]: https://fastapi.tiangolo.com/ "FastAPI"
[11]: https://docs.langchain.com/oss/python/langgraph/overview "LangGraph overview - Docs by LangChain"
[12]: https://docs.pydantic.dev/latest/concepts/types/ "Types | Pydantic Docs"
[13]: https://github.com/pgvector/pgvector "GitHub - pgvector/pgvector: Open-source vector similarity search for Postgres · GitHub"
[14]: https://docs.celeryq.dev/en/latest/ "Celery - Distributed Task Queue — Celery 5.6.2 documentation"
[15]: https://openrouter.ai/docs/guides/best-practices/prompt-caching "Prompt Caching | Reduce AI Model Costs with OpenRouter | OpenRouter | Documentation"
[16]: https://openrouter.ai/docs/guides/features/zdr "Zero Data Retention | How OpenRouter gives you control over your data | OpenRouter | Documentation"
