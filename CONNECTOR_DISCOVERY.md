# Alloy Connector — Connector Discovery

**Дата discovery:** 2026-08-23
**Статус:** Ярусы 1-3 пройдены (чтение официальной документации
developer.alloy.com + полной публичной OpenAPI-схемы Alloy API,
опубликованной на GitHub api-evangelist/alloy-com, 2026-08-23). §7 (решение
по объёму) НЕ требует отдельного вопроса Владу — Влад заявил объём с первого
сообщения по этому коннектору ("разработай это приложение в максимальной
форме со всеми доступными функциями с их стороны и всеми возможными
функциями внутри нашего приложения для повышения эффективности"), что по
`CONNECTOR_DISCOVERY_STANDARD.md` Шаг 5 действует как уже данный ответ.
Берём Ярус 1 + Ярус 2 + Ярус 3.

---

## 1. Целевой сервис и источники

Alloy (Alloy.com, юридически Alloy Technologies) — identity decisioning
платформа для банков, кредитных союзов и финтех-компаний: KYC (Know Your
Customer), KYB (Know Your Business), AML (антиотмывочный скрининг), борьба
с фродом, кредитный скоринг и непрерывный мониторинг клиентов (ongoing
monitoring) — всё через настраиваемые no-code/API-管理ные workflow
("Journeys"), которые оркестрируют десятки сторонних data-провайдеров
(бюро кредитных историй, sanctions/watchlist-провайдеры, document
verification вендоры и т.д.) за одним API-вызовом. В портфеле Imperal нет
ни одного специализированного identity-decisioning/compliance-коннектора
такого профиля — ближайшие по духу (Ironclad, DocuSign, PandaDoc) относятся
к контрактному/подписному документообороту, а не к автоматизированному
скринингу клиентов при онбординге.

Источники (прочитаны 2026-08-23):
- `developer.alloy.com` — точка входа документации (Products: Events API,
  SDK, Entities, Journeys, Webhooks)
- `developer.alloy.com/public/docs/authentication-guide` — HTTP Basic Auth
  и OAuth 2.0, миграция `workflow_token`/`workflow_secret` →
  account-level `token`/`secret`
- `developer.alloy.com/public/docs/integrating-with-events` /
  `event-types` — Events API (непрерывный мониторинг клиентов)
- `developer.alloy.com/public/docs/intro-to-entities`,
  `using-external-entity-ids`, `entity-merging`,
  `creating-entities-and-bank-accounts-events`,
  `multiple-external-entity-ids` — модель Entities (Person/Business)
- `developer.alloy.com/public/reference/*` — Reference-страницы конкретных
  эндпоинтов (Entities, Journeys, Reviews, Manual Review)
- `developer.alloy.com/public/docs/webhook-events`, `webhooks`,
  `webhooks-and-notifications`, `journey-events`, `application-statuses`,
  `retry-logic-and-webhook-logs`, `best-practices`,
  `authentication-types`, `integration` — Webhooks/Journeys operational
  docs
- Полная публичная OpenAPI 3.0.3-реконструкция API Alloy, зеркалированная
  на `github.com/api-evangelist/alloy-com/openapi/` (19 файлов, по одному
  на ресурсный домен) — использована как основной источник точных путей
  и `operationId` для каждого домена: oauth, evaluations, entities,
  journeys, batches, bank-accounts, transactions, documents, events,
  cases, investigations, custom-lists, lists, published-attributes,
  portfolio-evaluations, groups, entity-groups, reviews, parameters.

## 2. Критично по этому приложению

1. **НАЗВАНИЕ-ЛОВУШКА: под именем "Alloy" на рынке существуют ДВА совершенно
   разных продукта.** **Alloy Automation** (`runalloy.com`,
   `docs.runalloy.com`) — embedded iPaaS/интеграционная платформа для
   e-commerce (категория ближе к Make.com/Workato в нашем портфеле).
   **Alloy.com** (`developer.alloy.com`, он же Alloy Technologies) —
   identity decisioning для банков/финтеха (KYC/KYB/AML/фрод/кредит).
   Задача явно нацелена на максимальный, самодостаточный функциональный
   охват в духе уже выстроенного enterprise/compliance-направления
   портфеля — коннектор строится строго на **Alloy.com**
   (`developer.alloy.com` / `api.alloy.co`), Alloy Automation
   (`runalloy.com`) НЕ используется нигде и не упоминается в схемах, чтобы
   не создавать путаницу для пользователя. Если в будущем понадобится
   Alloy Automation как отдельная iPaaS-интеграция — это отдельный
   коннектор с отдельным discovery.
2. **Авторизация двойная: HTTP Basic ИЛИ OAuth 2.0 Client Credentials.**
   Basic Auth — `token` (username) + `secret` (password) в заголовке
   `Authorization: Basic base64(token:secret)`, самый простой и
   рекомендованный путь для server-to-server интеграций (BYOK-паттерн,
   уже применённый в портфеле — Cin7 Core, MuleSoft). OAuth 2.0 — через
   `POST /oauth/bearer` (обмен credentials на bearer-токен) и
   `POST /oauth/validate` (проверка токена). Историческое именование:
   `workflow_token`/`workflow_secret` (per-workflow ключи) мигрирует в
   `token`/`secret` (account-level ключи, из новой страницы API Key
   Settings в дашборде Alloy) — коннектор поддерживает оба именования
   как синонимы в форме подключения, с явной подсказкой пользователю,
   откуда взять актуальную пару в его дашборде.
3. **Два базовых URL, оба должны быть явно выбираемы пользователем.**
   `https://sandbox.alloy.co/v1` — тестовая песочница с фейковыми данными
   (для разработки/отладки Journey без реальных запросов к бюро/сервисам
   верификации, которые часто платные). `https://api.alloy.co/v1` —
   боевой продакшн. Коннектор ОБЯЗАН давать пользователю переключатель
   sandbox/production при подключении (аналогично `set_sandbox_mode` в
   DataForSEO Connector портфеля) — путать их означает либо тратить
   реальные деньги на тестовые вызовы, либо принимать боевые решения по
   фейковым sandbox-данным.
4. **Центральная концепция — Journeys, не отдельные "оценки" по каждому
   провайдеру.** Journey — визуально сконструированный (в дашборде Alloy)
   decisioning-флоу, который принимает один payload (данные персоны или
   бизнеса) и внутри себя вызывает множество сторонних data source
   (сверка личности, sanctions screening, credit bureau pull, document
   verification и т.д.), а на выходе даёт единый вердикт-статус
   (`Approved`/`Denied`/`Manual Review`/`Pending`) плюс подробный `Journey
   Application` со всеми узлами решения. Коннектор НЕ конструирует сами
   Journey (это делается только в UI Alloy) — он запускает существующие
   Journey Applications, читает их результат и управляет их жизненным
   циклом (rerun, manual review, батчи). Это тот же принцип, что у
   PagerDuty/PandaDoc: конфигурация процесса — в UI сервиса, API — только
   исполнение и данные.
5. **Entities — фундаментальная сущность, отделённая от Journey
   Applications.** Person Entity и Business Entity создаются один раз
   (или неявно при первом Journey Application) и переиспользуются между
   несколькими Journey (напр. один и тот же клиент проходит KYC при
   открытии счёта и повторный AML-скрининг раз в квартал — оба раза это
   один Entity). Entities поддерживают внешние ID (`external_entity_id`,
   причём МНОЖЕСТВЕННЫЕ на одну сущность — см. Multiple External Entity
   IDs) для увязки с ID клиента в системе банка, и merging (объединение
   дублей сущностей, обнаруженных на разных каналах).
6. **Events API — основной канал непрерывного (ongoing) мониторинга,
   отдельный от вебхуков.** Events — это то, что банк САМ отправляет В
   Alloy по мере жизни клиента (логин, транзакция, смена адреса, попытка
   вывода средств) для непрерывного риск-скоринга ПОСЛЕ первоначального
   онбординга — открытый набор `event_type` (см. `event-types`).
   Webhooks — противоположное направление: то, что Alloy отправляет
   ПОЛЬЗОВАТЕЛЮ при изменении статуса Journey Application/Review/Case.
   Обе стороны обязательны для полноты: `create_event` (egress в Alloy) и
   `list_webhooks`/`create_webhook` (получение уведомлений из Alloy).
7. **Cases и Investigations — два разных уровня операционного
   compliance-воркфлоу для комплаенс-аналитиков.** Case — контейнер вокруг
   одного Entity/Journey Application, требующего внимания человека
   (алерт), с evidences (доказательства/вложения) и works (заметки/шаги
   работы). Investigation — более формальный, юридически значимый процесс
   (например SAR/подозрительная активность), с собственным
   жизненным циклом (assignment, review, archival) и типами
   расследований. Оба домена — value-add для банков с реальными
   compliance-командами, не просто автоматизацией онбординга.
8. **Custom Lists — версионируемые списки-исключения/белые-чёрные списки.**
   Позволяют банку/финтеху поддерживать собственные списки (например,
   внутренний watchlist сотрудников-инсайдеров, список одобренных
   бизнес-партнёров) с версионированием изменений — Journey может
   сверяться с Custom List как с одним из узлов решения. Отдельный домен
   `Lists` (вероятно системные списки/watchlists самого Alloy, отличные от
   custom) фиксируется отдельно на этапе Дизайна по фактическому
   содержимому OpenAPI-файла `lists`.
9. **Published Attributes — экспортируемые вычисленные атрибуты Journey.**
   Каждый узел решения внутри Journey может публиковать вычисленный
   атрибут (например скоринговый балл конкретного провайдера,
   булев-флаг совпадения по санкционному списку) — Published Attributes
   API позволяет читать эти значения по отдельности, не парся весь
   вложенный `outcome`-объект Journey Application. Важно для отчётности и
   интеграции с внутренними BI/риск-системами банка.
10. **Portfolio Evaluations — агрегированная оценка риска на уровне
    портфеля клиентов, а не одной сделки.** Отдельный домен для
    периодической переоценки риска по всей клиентской базе (или её
    сегменту) сразу — типичный для AML-мониторинга сценарий "просканировать
    весь портфель клиентов на новые санкционные списки".
11. **Bank Accounts и Transactions — привязаны к Entity, отдельные от
    основного decisioning-цикла.** Используются в first-party
    banking/lending продуктах, где Alloy также хранит связанные банковские
    счета и историю транзакций клиента как часть его риск-профиля
    (например для fraud-детекции на основе паттернов транзакций).
12. **Reviews / Manual Review — human-in-the-loop гейт, аналогичный
    Workflow Approvals в других коннекторах портфеля (Ansible AAP,
    PagerDuty).** Когда Journey Application получает вердикт "Manual
    Review", комплаенс-аналитик обязан явно одобрить/отклонить его через
    `POST /journeys/{journey_token}/applications/{token}/review` — коннектор
    должен поддерживать это как явное человеческое решение, не
    автоматизировать вердикт.
13. **Documents — загрузка identity/address/supporting-документов,
    `multipart/form-data`.** Верификация документов (паспорт, счёт за
    коммунальные услуги, W-9 и т.д.) — отдельный upload-эндпоинт
    (`POST /documents`), документ затем привязывается к Entity/Journey
    Application и может использоваться как узел решения (document
    verification plugins, "Step Up Plugins" в терминологии Alloy).
14. **Rate limiting и retry — Alloy официально документирует Retry Logic
    для вебхуков** (`retry-logic-and-webhook-logs`) с экспоненциальным
    backoff — коннектор должен читать эти логи доставки (если API их
    предоставляет) и явно репортить пользователю невалидные/недоставленные
    вебхуки, а не молчать (тот же принцип уже применён к Cin7 Core
    webhook health check).
15. **Compliance-домен = данные крайне чувствительны (PII/PCI/финансовые
    данные).** Ни один хэндлер не должен логировать сырые персональные
    данные (SSN, номера счетов, паспортные данные) за пределами прямого
    прохождения через API-запрос — то же правило самодисциплины, что уже
    применяется к Stripe/DocuSign/Ironclad в этом портфеле.
