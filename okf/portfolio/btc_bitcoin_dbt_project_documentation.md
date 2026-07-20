---
title: BTC - Bitcoin - dbt Project Documentation
description: dbt pipeline processing Bitcoin transaction data in Snowflake, flattening nested structures and building whale-detection analytical models with versioned schemas.
technologies: dbt, Snowflake, Snowpipe, AWS SQS, AWS S3, Python, SQL, Git, Looker Studio
keywords:
- dbt
- snowflake
- snowpipe
- aws sqs
- auto-ingest
- s3
- incremental loading
- data marts
- whale detection
- blockchain analytics
- data modeling
- version control
- ci/cd
- data quality
- looker studio
archetypes:
- Analytics Engineering
- Data Engineering
repo_url: https://github.com/SagarMarthandan/BTC
---

# BTC - Bitcoin - dbt Project Documentation

This project is designed to process Bitcoin transaction data within a Snowflake environment using dbt. It handles data ingestion from raw sources, flattens complex nested structures, and produces analytical models to identify "Whale" activities.

---

## ✨ Tech Stack

<p align="center">
  <img src="https://img.shields.io/badge/dbt-FF694B?style=for-the-badge&logo=dbt&logoColor=white" alt="dbt" />
  <img src="https://img.shields.io/badge/Snowflake-2C9CCA?style=for-the-badge&logo=Snowflake&logoColor=white" alt="Snowflake" />
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/SQL-025E8C?style=for-the-badge&logo=postgresql&logoColor=white" alt="SQL" />
  <img src="https://img.shields.io/badge/YAML-CB171E?style=for-the-badge&logo=yaml&logoColor=white" alt="YAML" />
  <img src="https://img.shields.io/badge/GIT-E44C30?style=for-the-badge&logo=git&logoColor=white" alt="Git" />
  <img src="https://img.shields.io/badge/Looker-4285F4?style=for-the-badge&logo=Looker&logoColor=white" alt="Looker Studio" />
</p>

---

## 📂 Project Structure

```text
.
├── .github/workflows/
│   └── dbt-ci.yml           # CI/CD pipeline definition
├── analyses/                # SQL analytical queries (not materialized)
├── macros/                  # Reusable Jinja/SQL functions
│   ├── btc_utils.sql        # USD conversion logic
│   ├── hooks.sql            # Custom post-hooks for versioning
│   └── logging.sql          # Event logging macros
├── models/
│   ├── marts/               # Final analytical tables
│   │   ├── whale_alerts_v1.sql
│   │   ├── whale_alerts_v2.sql
│   │   └── whale_top_10.sql # Top addresses by volume
│   ├── stg/                 # Staging & cleaning layer
│   │   ├── stg_btc.sql
│   │   ├── stg_btc_outputs.sql
│   │   ├── stg_btc_outputs_py.py # Python-based flattening logic
│   │   └── stg_btc_transactions.sql
│   ├── schema.yml           # Documentation & tests
│   └── sources.yml          # Source data configurations
├── seeds/                   # Static CSV data
│   └── btc_usd_max.csv      # BTC/USD exchange rates
├── snapshots/               # SCD Type 2 tracking
├── tests/                   # Custom data tests
├── dbt_project.yml          # Main project configuration
└── packages.yml             # External dbt dependencies
```

---

## 🗺️ Project Lineage

This graph illustrates the flow of data from raw sources to the final analytical models and exposures.

```mermaid
graph TD
    subgraph "Raw Data"
        A[source: btc.btc]
        F[seed: btc_usd_max.csv]
    end

    subgraph "Staging Layer"
        B(stg_btc)
        C(stg_btc_outputs)
        C_PY(stg_btc_outputs_py)
        D{{stg_btc_transactions}}
    end

    subgraph "Marts Layer"
        E(whale_alerts)
        E_TOP(whale_top_10)
    end

    subgraph "Macros"
        G((convert_to_usd))
    end

    subgraph "Downstream"
        H{{Looker Studio Dashboard}}
    end

    subgraph "Data Quality"
        T1[not_null & unique tests]
        T2[equal_rowcount test]
        T3[custom data test]
    end

    A --> B
    B --> C
    B --> C_PY
    C --> D
    D --> E
    E --> E_TOP
    F --> G
    G --> E
    E --> H

    B --> T1
    C --> T2
    E --> T3

    style A fill:#e6f3ff,stroke:#333,stroke-width:2px
    style F fill:#fff2e6,stroke:#333,stroke-width:2px
    style B fill:#e6ffed,stroke:#333,stroke-width:2px
    style C fill:#e6ffed,stroke:#333,stroke-width:2px
    style C_PY fill:#e6ffed,stroke:#333,stroke-width:2px
    style D fill:#e6ffed,stroke:#333,stroke-width:2px
    style E fill:#e6ffed,stroke:#333,stroke-width:2px
    style E_TOP fill:#e6ffed,stroke:#333,stroke-width:2px
    style G fill:#f2e6ff,stroke:#333,stroke-width:2px
    style H fill:#ffe6e6,stroke:#333,stroke-width:2px
    style T1 fill:#fff8e6,stroke:#333,stroke-width:2px
    style T2 fill:#fff8e6,stroke:#333,stroke-width:2px
    style T3 fill:#fff8e6,stroke:#333,stroke-width:2px
```

---

## ⚙️ 1. Project Configuration & Security

### `dbt_project.yml`

The core configuration file for the dbt project.

- **Project Name:** `BTC`
- **Profile:** Uses the `BTC` profile for connection settings.
- **Model Paths:** Defines where dbt looks for models, seeds, macros, and tests.
- **Marts Configuration:** Specifically configures models in the `marts` folder to materialize as tables and includes post-hooks for table commenting and versioned view creation.

### Access Keys & `profiles.yml`

- **Why separate keys?** 🔐 Git is a version control system for code, not a secret manager. Committing database passwords or private keys to Git is a major security risk.
- **How it works:** dbt uses a file called `profiles.yml` (typically stored in your local `~/.dbt/` directory, outside the project folder) to manage connection details (account, user, password, warehouse).
- **Local vs. Git:** The `dbt_project.yml` references a profile name (e.g., `BTC`). When you run dbt locally, it looks up `BTC` in your local `profiles.yml`. In production (like GitHub Actions), secrets are injected via environment variables into a generated `profiles.yml`.

---

## 📚 2. Data Sources & Schema Definition

### `models/sources.yml`

- **Purpose:** Defines the raw data loaded into Snowflake (e.g., `btc.btc_schema.btc`).
- **Function:** Maps raw database tables to dbt "sources". This allows you to refer to them dynamically using `{{ source('btc', 'btc') }}` in your SQL, enabling lineage tracking and freshness checks.

### `models/schema.yml`

- **Purpose:** The "contract" and documentation registry for your models.
- **Key Components:**
  - **Model Properties:** Defines descriptions and data types for columns.
  - **Tests:** Applies constraints like `unique` and `not_null` to ensure data integrity.
  - **Versioning:** Defines model versions (e.g., `whale_alerts` v1 vs v2), allowing you to introduce breaking changes (like removing a column) without immediately breaking downstream consumers.
  - **Exposures:** Documents downstream dependencies (e.g., the "BTC Whale Alerts" Looker Studio dashboard), so you know what breaks if a model changes.

---

## 🏗️ 3. Models (`/models`)

The models are organized into layers following dbt best practices: Staging and Marts.

### Staging Layer (`/models/stg`)

This layer handles the initial cleaning and transformation of raw source data.

- **`stg_btc.sql`**

  - **Materialization:** Incremental (Merge strategy).
  - **Purpose:** Acts as the entry point for raw Bitcoin data from the `btc.btc_schema.btc` source.
  - **Logic:** It uses a `HASH_KEY` as a unique identifier and incrementally loads new data based on the `BLOCK_TIMESTAMP`.

- **`stg_btc_outputs.sql`**

  - **Materialization:** Incremental (Append strategy).
  - **Purpose:** Bitcoin transactions often contain multiple outputs in a nested format. This model flattens that data.
  - **Logic:** It uses Snowflake's `LATERAL FLATTEN` on the `outputs` column to create a row for every unique address/value pair in a transaction.

- **`stg_btc_outputs_py.py`**

  - **Materialization:** Table (Python).
  - **Purpose:** Demonstrates the use of **dbt Python Models** to perform idempotent flattening and transformation logic using DataFrames, providing an alternative to standard SQL flattening.

- **`stg_btc_transactions.sql`**
  - **Materialization:** Ephemeral (CTE-based, not created in the DB).
  - **Purpose:** Filters the flattened outputs to focus on standard transactions.
  - **Logic:** It excludes "Coinbase" transactions (newly minted coins) to focus on peer-to-peer transfers.

### Marts Layer (`/models/marts`)

The analytical layer where business logic is applied.

- **`whale_alerts.sql` (v1 & v2)**

  - **Materialization:** Table.
  - **Purpose:** Identifies "Whales"—addresses involved in high-value transactions.
  - **Logic:**
    - Filters for transactions where the output value is greater than 10 BTC.
    - Aggregates data by `output_address` to show total sent and transaction counts.
    - Uses a custom macro to calculate the USD value of the BTC sent.
  - **Versioning:** This model supports multiple versions (v1 and v2) as defined in `schema.yml`.

- **`whale_top_10.sql`**
  - **Materialization:** Table.
  - **Purpose:** Ranks the top 10 whale addresses by total volume of BTC sent, providing a focused view of the most active network participants.

---

## 🔧 4. Macros & Jinja (`/macros`)

Macros are reusable SQL/Jinja functions.

- **`btc_utils.sql`**

  - **`convert_to_usd(column_name)`:**
    - **Function:** Accepts a column name (BTC value) as an argument.
    - **Logic:** Joins with the `btc_usd_max` seed table on the current date to calculate the USD equivalent.
    - **Jinja Usage:** `{{ convert_to_usd('w.total_sent') }}` injects the calculation logic directly into the compiled SQL.

- **`hooks.sql`**

  - **`create_latest_version_view()`**: A post-hook macro that automatically creates or updates a view pointing to the latest version of a versioned model (e.g., creating a `whale_alerts` view that points to `whale_alerts_v2`).

- **`logging.sql`**
  - **`log_dbt_run()`**: An `on-run-end` hook that logs termination status and metadata to a centralized logging table in Snowflake.

---

## 🌱 5. Seeds (`/seeds`)

Seeds are CSV files that dbt loads into your data warehouse as tables.

- **`btc_usd_max.csv`**
  - **Purpose:** Provides historical and current BTC to USD exchange rates.
  - **Usage:** Referenced by the `convert_to_usd` macro to provide financial context to transaction volumes.

---

## 🧪 6. Testing & Auditing

### Audit Schema

- **What is it?** When dbt runs tests, it generates SQL queries that look for failing records.
- **`dbt_test__audit`:** If you configure `store_failures: true`, dbt saves the failing records to a dedicated schema (e.g., `PROD_dbt_test__audit`). This allows you to inspect exactly _which_ rows failed a test (e.g., seeing the specific duplicate `HASH_KEY`s).

---

## 🚀 7. CI/CD & Production Operations

### GitHub Actions Workflow

The project uses GitHub Actions to automate data validation and distribution.

```mermaid
graph LR
    A[Pull Request] --> B{dbt CI}
    subgraph "CI Job"
        B --> C[Set up Environment]
        C --> D[Install dbt & deps]
        D --> E[dbt debug]
        E --> F[dbt run]
        F --> G[dbt test]
    end
    G --> H{Pass?}
    H -- Yes --> I[Merge to Master]
    H -- No --> J[Fix Errors]
```

### GitHub Actions (`dbt-ci.yml`)

- **Purpose:** Automates code validation on Pull Requests.
- **Workflow:**
  1.  **Trigger:** Runs on every push to a PR.
  2.  **Slim CI:** Often uses `dbt run --select state:modified+` to only run models that have changed, saving time and cost.
  3.  **Validation:** Executes `dbt test` to ensure changes don't violate data integrity rules before merging to `main`.

### Production Deployment

- **Deployment:** When code merges to `main`, a production job runs `dbt build` against the production database/schema.
- **Scheduling:** Jobs are typically scheduled (e.g., via dbt Cloud, Airflow, or Cron) to run at set intervals (e.g., every hour) to keep data fresh.

### Monitoring & Alerting

- **Monitoring:** Use the dbt Cloud dashboard or Airflow UI to visualize job success/failure and duration.
- **Alerting:**
  - **Job Failure:** Configure email or Slack notifications if the `dbt run` command exits with a non-zero status.
  - **Source Freshness:** Run `dbt source freshness` periodically. If raw data is stale (e.g., no new blocks in 2 hours), dbt can trigger an alert.

---

## 🗂️ 8. Project State (`/state`)

- **`manifest.json`**
  - A machine-generated file containing the full representation of the project's resources and their dependencies. It is used by dbt to understand the project structure and for state-based execution (e.g., `dbt build --state ...`).

---

## 💻 Local Setup & Prerequisites

To develop on this project locally, follow these steps:

1.  **Prerequisites**:
    - Python 3.12.x installed.
    - Access to a Snowflake warehouse.
2.  **Installation**:
    ```bash
    pip install dbt-snowflake
    ```
3.  **Authentication**:
    Configure your `~/.dbt/profiles.yml` with the appropriate Snowflake credentials and account details.
4.  **Dependencies**:
    ```bash
    dbt deps
    ```
5.  **Execution**:
    ```bash
    dbt build  # Runs seeds, snapshots, models, and tests in order
    ```




-------------------------------------------------------------------------------