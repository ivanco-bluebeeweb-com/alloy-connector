# Alloy Connector — UI component plan

Источники: `Docs/session-notes/UI_COMPONENT_VOCABULARY.md`, `UI_INTERFACE_STANDARD.md`,
`concepts/panels.md`. Основано на функционале `alloy-connector`.

## 1. Компоненты

| Экран | Примитивы | Почему именно эти |
|---|---|---|
| Sidebar (left) | `ui.Column`(align="start") + `ui.Text`(workflow/journey name) + `ui.Divider` + navigation `ui.ListItem`(Evaluations/Entities/Case Management) + `ui.Button`("App settings") | Без карточек по стандарту. |
| Evaluation List (center, `center_overlay=True`) | `ui.Stats`(Approved/Denied/Manual Review today) + `ui.Select`(outcome_filter) + `ui.DataTable`(entity name, outcome Badge Approved/Denied/Manual Review, timestamp; sortable) | `DataTable` — стандартный способ работать с потоком KYC/KYB решений Alloy. |
| Evaluation Detail | Back-button + `ui.KeyValue`(entity info/outcome/score) + `ui.List`(triggered rules/reasons — каждая как ListItem) + `ui.Timeline`(evaluation stages: submitted→data sources queried→decisioned) | `Timeline` отражает последовательность обращений к data sources до вынесения решения; `List` для человекочитаемого перечня сработавших правил. |
| Manual Review Queue | `ui.DataTable`(entity, flagged reason, submitted date; sortable) + `ui.Row`(Button "Approve", "Deny", "Escalate") | Табличная очередь ручной проверки с прямыми действиями по строке. |
| Manual Review Decision Dialog | `ui.Dialog`(title="Подтвердить решение?", content=`ui.TextArea`(param_name="review_note", placeholder="Причина решения..."), confirm_label="Подтвердить") | Ручное решение по кейсу — значимое действие, требует явного подтверждения с обоснованием. |
| Entity Detail | Back-button + `ui.KeyValue`(name/DOB/address/document status — permitted fields) + `ui.List`(document uploads: ID, proof of address) + `ui.Timeline`(entity evaluation history — все прошлые evaluations) | `Timeline` показывает историю решений по одной и той же сущности со временем. |
| Data Source Diagnostics | `ui.DataTable`(source name, status Badge ok/timeout/error, latency ms; sortable) | Диагностика используемых источников данных (KYC/AML/credit bureaus) при отладке решений. |
| Rule/Workflow Config Viewer (read-only) | `ui.Code`(language="json", workflow config, readonly) | Конфигурация journey/workflow в Alloy — сырой JSON, лучше всего смотрится в `Code`. |
| App Settings | `ui.Accordion`([Connections+Disconnect, Environment sandbox/prod, Webhook URL]) | Централизованные настройки по стандарту. |

## 2. User flow (валидно по panel lifecycle)

1. **SESSION INIT** → `__panel__alloy_sidebar` рендерит journey + разделы,
   `auto_action` открывает Evaluation List.
2. Evaluation List: DataTable с outcome Badge → клик на строку с outcome
   "Manual Review" → `ui.Call(evaluation_id=...)` → Evaluation Detail на том
   же center handler.
3. Evaluation Detail: показывает triggered rules + Timeline стадий; если
   outcome = Manual Review → доступны Approve/Deny/Escalate (через
   Manual Review Queue или прямо здесь).
4. Approve/Deny → `Dialog` с обязательным `review_note` → `ui.Call` →
   `submit_manual_decision` → `refresh_panels` (необратимое решение по
   комплаенсу — обязателен Dialog).
5. Из сайдбара → Entities → список сущностей → Entity Detail показывает
   всю историю evaluations этой сущности через `Timeline`.
6. "App settings" (нижняя кнопка сайдбара) → отдельный center handler
   `panels_settings.py`; "Disconnect" — единственное деструктивное действие,
   обёрнуто в `Dialog`.

## 3. Экраны/карточки (конкретно)

- **Screen: Evaluation List** — Stats(3) + Select(outcome) + DataTable(entity/outcome/timestamp).
- **Screen: Evaluation Detail** — KeyValue(entity/outcome/score) + List(rules) + Timeline(stages).
- **Screen: Manual Review Queue** — DataTable(entity/reason/date) + Row(Approve/Deny/Escalate).
- **Screen: Entity Detail** — KeyValue(entity fields) + List(documents) + Timeline(history).
- **Screen: Data Source Diagnostics** — DataTable(source/status/latency).
- **Screen: App Settings** — Accordion(Connections, Environment, Webhook URL).
