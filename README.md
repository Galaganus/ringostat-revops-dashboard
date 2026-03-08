# Ringostat RevOps Dashboard

Streamlit dashboard for deal analytics and data quality checks.

## Requirements

- Python 3.10+
- Place your `deals.xlsx` file into the `data/` folder (sheet name: `база угод`)

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Features

- Sidebar filters: country, CRM, date range
- Top metrics: Total Deals, Win Rate, Closed Won/Lost
- Charts: Win Rate by Country, Win Rate by CRM, Stage Distribution, Deals by Source, Win Rate by PPC Budget
- Data Quality Issues table
- RevOps Insights Summary (dynamic, calculated from data)
