# Alloy Connector — идеальный первый запуск

Источник: `ONBOARDING_FIRST_LAUNCH_STANDARD.md`. Целевой пользователь: Compliance/Risk
менеджер fintech-компании/банка (KYC/KYB онбординг, мониторинг мошенничества).

## 1. Credential type
API key-пара (token + secret) + environment (sandbox/production) — трёхполевая форма,
похожая по структуре на Plaid, но без multi-secret-per-env усложнения.

## 2. Идеальный флоу
1. **Первое открытие** — `Empty` со ссылкой "Dashboard > API Key Settings" + явное
   объяснение разницы sandbox/production ДО ввода данных (тестовые заявки vs реальные
   решения по реальным клиентам — ошибиться здесь стоит дорого, это compliance-домен).
2. **Форма** — token + secret (оба password-type) + environment select, все с лейблами.
3. **После успеха** — сводка очереди evaluations (сколько на ручном review) сразу.
4. **Production warning** — идеально: при первом переключении на production —
   обязательное предупреждение "решения здесь влияют на реальных клиентов", не просто
   цветовой индикатор, а явный `Alert` при входе в этот режим.
5. **Ошибка "invalid credentials pair"** — Alloy требует ОБА поля правильными
   одновременно — конкретное "проверьте, что token и secret из одной пары API-ключа",
   не общее "неверные данные".
6. **Webhook events** — если приложение поддерживает real-time решения по evaluations
   через вебхуки — идеально показать webhook URL для копирования сразу после коннекта,
   а не прятать в отдельном "Settings".

## 3. Разница с реализацией сейчас
См. `UI_COMPONENT_PLAN.md` §0.
