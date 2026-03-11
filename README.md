# Ringostat RevOps Dashboard

An interactive Streamlit dashboard for analyzing deal pipeline performance, identifying data quality issues, and surfacing actionable RevOps insights. Built as a test assignment for the Middle Revenue Operations Specialist position at Ringostat.

## Live Demo

> Link to deployed dashboard will be added here.

## Features

### Filters
- **Date range** — filter by AQL date (start/end)
- **Client country** — single selectbox with "All" option
- **Client CRM** — single selectbox with "All" option
- **Show 0% win rate segments** — toggle to reveal segments with zero conversions
- Live counter: "Showing X of Y deals"

### Metrics & Charts
- **Top metrics row** — Total Deals, Win Rate %, Closed Won, Closed Lost
- **Win Rate by Country** — horizontal bar chart with sample size `(n=X)`, long names auto-truncated
- **Win Rate by CRM** — horizontal bar chart with sample size `(n=X)`, shared height with Country chart
- **Deal Distribution by Stage** — pie chart with consistent color mapping and fallback palette
- **Deals by Source** — stacked horizontal bar (Won / Lost / Open) with total count annotations
- **Win Rate by PPC Budget** — vertical bar chart with `(n=X)` labels, 0% segments shown as text caption

### Data Quality Checks
Runs on the **full unfiltered dataset**. Only flags objectively verifiable errors:
- Missing values in key columns (Stage, Country, Source, CRM)
- Closing Date before AQL date (impossible chronology)
- Closed deal without Closing Date
- Non-closed deal with Closing Date
- Closed Lost without loss reason

### RevOps Insights Summary
5-8 auto-generated one-line insights with bold key facts:
- Overall win rate with W/L breakdown
- Pipeline bottleneck (where open deals accumulate)
- Best and worst markets by win rate
- CRM impact (conversion with CRM vs without)
- Source efficiency (volume vs conversion leader)
- Top loss reason with documentation coverage
- Win rate trend (earlier vs recent months)
- Data quality summary with most common issue

## Setup & Run

**Requirements:** Python 3.10+

```bash
git clone https://github.com/Galaganus/ringostat-revops-dashboard.git
cd ringostat-revops-dashboard

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Place your `deals.xlsx` file into the `data/` folder (expected sheet name: `база угод`).

## Project Structure

```
ringostat-revops-dashboard/
├── app.py                  # Main dashboard (single-file application)
├── requirements.txt        # Python dependencies
├── data/
│   └── deals.xlsx          # Source data (test dataset from Ringostat)
└── README.md
```

## Використання AI

### Інструменти

- **Claude** (claude.ai) — основний AI-асистент для архітектури дашборду, логіки data quality checks, побудови RevOps insights, код-рев'ю
- **Cursor** — IDE з AI-автокомплітом для написання та рефакторингу коду

### Які промпти спрацювали найкраще

- **Структурні промпти з контекстом** — "ось поточний код, ось проблема, ось що я хочу". Давали найточніший результат з першої ітерації
- **Ітеративний код-рев'ю** — "зроби фінальний чек всього коду і логік". Допомагало знаходити дублювання змінних, приховані фільтри та неконсистентності
- **Конкретні візуальні фікси** — "ось скріншот, що викликало такий візуальний результат і як виправити". Ефективно для роботи з Plotly-специфічними проблемами

### Що генерувалось AI, а що робилось вручну

**AI:**
- Архітектура дашборду та структура коду
- Логіка data quality checks
- RevOps insights (формули, агрегації, текстові шаблони)

**Вручну:**
- Фінальні рішення по UX (чекбокс для 0% win rate, сортування графіків, вибір між annotation та caption)
- Верифікація даних та перевірка коректності метрик
- Деплой

### Де були складнощі

- **Візуалізація нульових значень у Plotly** — бари з 0% win rate мають нульову висоту і невидимі, лейбли обрізаються. Annotation поверх нульового бара створював дублювання тексту. Рішення: не рисувати нульові бари, показувати їх окремим caption під графіком
- **Сортування stacked bars у Plotly** — ігнорує `pd.Categorical`, довелось використовувати `category_orders`
- **Нормалізація бюджетних діапазонів** — числа vs рядки у вихідних даних. Числовий `0` — це не діапазон "0-500", а відсутність PPC-бюджету ("No PPC")
- **Баланс між повнотою та читабельністю** — 38 CRM в одному графіку нечитабельні, але приховувати дані теж неправильно. Рішення: динамічна висота з обмеженням + тогл для 0% сегментів
