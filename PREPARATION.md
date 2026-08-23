# Alloy Connector — Preparation

**Статус:** Фаза 1 (Discovery + архитектурные решения) завершена. Влад
подтвердил объём релиза с первого сообщения по этому коннектору —
«разработай это приложение в максимальной форме со всеми доступными
функциями с их стороны и всеми возможными функциями внутри нашего
приложения для повышения эффективности» (Ярус 1+2+3), без отдельного
запроса подтверждения (см. `CONNECTOR_DISCOVERY.md` шапка).

**Владелец продукта:** vlad@bluebeeweb.com
**Дата подготовки:** 2026-08-23, v0.1
**Vikunja task:** #2311 (BBW Imperal Apps), [App Development] Alloy Connector.

**Почему сейчас:** Alloy.com — устоявшаяся identity decisioning платформа
для банков/кредитных союзов/финтеха (KYC/KYB/AML/фрод/кредит через
конфигурируемые Journeys). В портфеле Imperal есть контрактно-подписной
compliance-слой (Ironclad, DocuSign, PandaDoc), но нет ни одного
специализированного identity-decisioning коннектора — скрининг клиентов
при онбординге и непрерывный мониторинг это отдельный, самостоятельный
операционный домен.

---

## 1. Паспорт приложения

**Название в Marketplace (display_name): «Alloy»**. Внутренний
app_id/папка: `alloy-connector`.

**Alloy Connector** — коннектор к Alloy.com API (REST, `api.alloy.co/v1`
prod / `sandbox.alloy.co/v1` sandbox) для identity decisioning: сущности
(персоны/бизнесы), запуск/чтение evaluations и journey applications,
работа с батчами, документами (upload/verification), непрерывным
мониторингом через Events API, кейсами и расследованиями (investigations),
custom lists (внутренние watchlists), опубликованными атрибутами
(published attributes), ручными ревью (manual review gate), банковскими
счетами/транзакциями клиента, портфельными evaluations и группами
сущностей. BYOK: пользователь подключает свой собственный Alloy аккаунт
через пару `token`+`secret` (HTTP Basic) ИЛИ через OAuth 2.0 Client
Credentials (`POST /oauth/bearer`), созданные в самом Alloy Dashboard.
Imperal ничего не хостит и не проксирует, кроме самого запроса.

---

## 2. Ключевые архитектурные решения (см. `CONNECTOR_DISCOVERY.md` §2)

### 2.1 Жёсткая фиксация на Alloy.com, НЕ Alloy Automation

Под именем «Alloy» существуют два разных продукта (`runalloy.com` —
embedded iPaaS для e-commerce, и `developer.alloy.com` — identity
decisioning для финансового сектора). Задача явно нацелена на
максимальный, самодостаточный функциональный охват в духе
enterprise/compliance-направления портфеля — весь код, все
docstrings и именование (app_id, UI) явно говорят «Alloy» с явной
ссылкой на identity decisioning/KYC/KYB/AML в описании, чтобы у
пользователя не было иллюзии, что это коннектор автоматизации/iPaaS.

### 2.2 Авторизация — двойная (HTTP Basic ИЛИ OAuth 2.0 Client Credentials)

Alloy поддерживает оба метода на одних и тех же `token`+`secret`:
- **HTTP Basic** — `token` как username, `secret` как password на
  КАЖДЫЙ запрос (проще, без дополнительного шага)
- **OAuth 2.0** — `POST /oauth/bearer` с `token`+`secret` в теле,
  получаем bearer-токен, используем `Authorization: Bearer <token>`
  (плюс `POST /oauth/validate` для явной проверки токена)

Коннектор реализует HTTP Basic как основной путь подключения (проще,
без лишнего шага, тот же паттерн BYOK, что у Cin7 Core/MuleSoft) —
`connect_alloy` просит **token** + **secret** + опциональный
**environment** (`sandbox`/`production`) + опциональный **label**,
проверяет пару лёгким GET-запросом. OAuth оставлен как внутренняя
опция клиента (можно переключить позже без изменения контракта
handlers), но не выставляется отдельным полем формы — избегаем
раздувания UI на редко нужный кейс.

### 2.3 Два окружения — sandbox и production, явный выбор при подключении

В отличие от большинства коннекторов портфеля (один base_url), Alloy
жёстко разделяет `sandbox.alloy.co/v1` (тестовые данные, безопасно для
экспериментов) и `api.alloy.co/v1` (реальные решения о реальных
клиентах, с реальными последствиями для комплаенса). `connect_alloy`
требует явного выбора `environment`, никогда не строит предположение
по умолчанию — ошибочный вызов на боевом окружении в KYC/AML-домене
недопустим молча.

### 2.4 Journeys как основной decisioning-конвейер, Evaluations как более простой прямой путь

Alloy предлагает два уровня работы с decisioning:
- **Evaluations API** — более старый, прямой одношаговый вызов
  (`POST /evaluations`) для простых случаев
- **Journeys API** — современный, гибкий многошаговый workflow,
  настраиваемый в самом Alloy Dashboard (визуальный конструктор),
  запускается через `POST /journeys/{journey_token}/applications`

Коннектор реализует ОБА пути как равноправные — `run_evaluation` для
простого прямого сценария и `create_journey_application` +
`get_journey_application` + `rerun_journey_application` +
`review_journey_application` для полного Journey-цикла, т.к. новые и
существующие клиенты Alloy могут использовать любой из них в
зависимости от того, когда был настроен их аккаунт.

### 2.5 Entities с явным разделением Person / Business

Alloy строго разделяет два типа сущностей на уровне пути
(`/entities/persons` vs `/entities/businesses`), а не единый `/entities`
с полем `type`. Схемы и хэндлеры коннектора зеркалируют это разделение
(`create_person_entity`/`create_business_entity`, а не один
универсальный `create_entity` с discriminator) — точнее отражает
реальный API-контракт и снижает риск отправки не тех полей не в тот
эндпоинт.

### 2.6 Reviews / Manual Review — человек в цикле, не автоматизируется

Когда Journey Application получает вердикт "Manual Review", коннектор
предоставляет `list_manual_reviews`/`get_manual_review` для чтения
очереди и `submit_manual_review` для явного решения комплаенс-аналитика
(approve/deny) — сам вердикт никогда не выставляется автоматически
внутри коннектора, только по explicit вызову пользователя/аналитика.
Тот же принцип human-in-the-loop, что уже применён к Workflow Approvals
(Ansible AAP) и Incident acknowledgement (PagerDuty).

### 2.7 Multi-account, как multi-org у остальных BYOK-коннекторов портфеля

Пользователь может подключить несколько Alloy аккаунтов (агентство/банк
с несколькими юрлицами, или разделение sandbox+production как два
отдельных подключения) — хранится список подключений
(`alloy_connections` secret), каждый вызов принимает опциональный
`connection_id` (по умолчанию первый/единственный), тот же паттерн, что
уже применён во всех недавних BYOK-коннекторах портфеля (ctx-based
`_load_connections(ctx)`/`_save_connections(ctx,...)`/
`_resolve_connection(ctx, connection_id)`, по образцу Cin7 Core).

### 2.8 Чувствительность данных — PII/финансовые данные, без логирования сырых значений

Compliance-домен работает с крайне чувствительными данными (SSN,
паспортные данные, номера банковских счетов, финансовая история).
Хэндлеры пропускают эти поля напрямую через API-запрос, но ни один
хэндлер/лог/summary-строка не печатает и не эхо-репортит сырые
значения полей идентификации обратно пользователю сверх того, что сам
Alloy API возвращает как часть ответа — тот же принцип, что уже
применяется к Stripe/DocuSign/Ironclad в этом портфеле.

---

## 3. Три яруса функций (по `CONNECTOR_DISCOVERY_STANDARD.md`)

### Ярус 1 — управление подключением + базовый decisioning-цикл

- `connect_alloy` / `disconnect_alloy` / `list_connections`
- `create_person_entity`, `create_business_entity`, `get_entity`
- `run_evaluation`
- `create_journey_application`, `get_journey_application`,
  `list_journey_applications`
- `get_journey_schema`

### Ярус 2 — полнота охвата домена (19 ресурсных доменов Alloy API)

- Entities: `merge_entities`, `add_entity_note`, `list_entity_notes`,
  `submit_entity_feedback`, `list_external_entity_ids`,
  `add_external_entity_id`
- Journeys: `rerun_journey_application`, `update_journey_application_node`,
  `create_journey_batch`, `get_journey_batch`, `list_journey_batches`
- Reviews: `list_manual_reviews`, `get_manual_review`,
  `submit_manual_review`
- Evaluations: `get_evaluation`, `list_evaluations`
- Bank Accounts: `create_bank_account`, `get_bank_account`,
  `list_bank_accounts`, `update_bank_account`
- Transactions: `create_transaction`, `list_transactions`,
  `get_transaction`
- Documents: `upload_document`, `get_document`, `update_document`,
  `list_documents`
- Events: `create_event`, `list_events`, `get_event`
- Cases: `create_case`, `get_case`, `list_cases`, `update_case`,
  `add_case_evidence`, `list_case_evidence`, `add_case_work`
- Investigations: `create_investigation`, `get_investigation`,
  `list_investigations`, `update_investigation`,
  `list_investigation_types`, `list_investigation_alerts`
- Custom Lists: `create_custom_list`, `get_custom_list`,
  `list_custom_lists`, `add_custom_list_item`,
  `remove_custom_list_item`, `list_custom_list_items`,
  `list_custom_list_versions`
- Lists (watchlists): `list_watchlists`, `get_watchlist`
- Published Attributes: `list_published_attributes`,
  `get_published_attribute`
- Portfolio Evaluations: `run_portfolio_evaluation`,
  `get_portfolio_evaluation`, `list_portfolio_evaluations`
- Groups / Entity Groups: `create_group`, `list_groups`,
  `create_entity_group`, `list_entity_groups`,
  `add_entity_to_group`
- Webhooks: `list_webhook_configs`, `create_webhook_config`,
  `update_webhook_config`, `delete_webhook_config` (Alloy webhooks —
  конфигурация делается частично через Dashboard; коннектор
  предоставляет то, что доступно через API, и явно предупреждает
  об остальном в docstring)
- Parameters: `list_journey_parameters`

### Ярус 3 — value-add поверх нативных возможностей

- `audit_entity_risk_profile` — агрегирующий отчёт по одной Entity:
  последний evaluation/journey application вердикт + открытые cases +
  открытые investigations + manual reviews в очереди, одним вызовом
  вместо ручного обхода 4+ разных эндпоинтов
- `get_manual_review_queue_report` — сводка очереди ручных ревью по
  всем Journeys: сколько заявок ждёт, средний возраст ожидания,
  разбивка по причине (Fraud/AML/Credit) — по аналогии с
  `get_pipeline_health`/`get_dunning_report` в других коннекторах
- `bulk_submit_manual_reviews` — explicit батч approve/deny по списку
  review-токенов одним вызовом (тот же паттерн `apply_bulk_*`)
- `find_expiring_documents` — value-add скан документов с истекающим
  сроком действия (паспорт/ID с датой истечения), по аналогии с
  `find_expiring_contracts` (Ironclad)/`get_lease_expiration_report`
  (AppFolio/Buildium)
- rate-limit aware retry в HTTP-клиенте (Alloy документирует retry
  logic для вебхуков; применяем тот же принцип backoff к основным
  API-вызовам при 429/5xx)

---

## 4. Что решено НЕ включать в этот заход (явный вырез, не забывчивость)

- **Alloy Automation функции** — другой продукт, другой API, вне
  охвата (см. `CONNECTOR_DISCOVERY.md` §2.1) — специально исключено,
  чтобы не создавать путаницу.
- **Полная конфигурация Journey-логики (визуальный конструктор узлов
  внутри Alloy Dashboard)** — Journeys подключаются и запускаются через
  API, но их внутренняя decisioning-логика (какие узлы/провайдеры
  использует конкретный Journey) настраивается в самом Alloy UI, не
  через внешний API — вне охвата коннектора, тот же принцип, что
  «производственная BOM-логика Cin7 Core» была вырезом там, где нет
  предмета для функции.
- **White-label Step Up Plugins UI** (документ-верификационные виджеты,
  встраиваемые в чужой фронтенд через Alloy SDK) — это клиентский
  JS SDK для конечных пользователей банка, не серверный REST API —
  вне охвата серверного коннектора.

---

## 5. Секреты и подключение

- `alloy_connections` — список подключений (ctx-based secret, тот же
  паттерн, что Cin7 Core): каждый элемент —
  `{connection_id, label, token, secret, environment}`.
- `connect_alloy(token, secret, environment, label=None)` — проверяет
  пару лёгким GET-запросом (например `GET /entities/persons/{fake}` c
  ожидаемым 404, или использованием `/oauth/validate` при наличии
  bearer-режима), сохраняет подключение, возвращает `connection_id`.
- `_resolve_connection(ctx, connection_id)` — как у Cin7 Core: без
  `connection_id` берёт единственное/первое подключение, при
  нескольких — требует явного выбора.
