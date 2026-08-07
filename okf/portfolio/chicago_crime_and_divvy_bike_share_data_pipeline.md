---
title: Chicago Crime & Divvy Bike-Share Data Engineering Pipeline
description: End-to-end data pipeline (Spark, Kafka, Airflow, BigQuery, dbt, Terraform) correlating Chicago crime patterns with bike-share ridership, developed with parallel AI agents.
technologies: Python, Apache Spark, Apache Airflow, Apache Kafka, dbt, Google BigQuery, BigQuery ML, Terraform, GitHub Actions, Grafana, PostgreSQL, Docker, dlt, SQL
keywords:
  - ai data engineering
  - ai agents
  - apache airflow
  - apache spark
  - apache kafka
  - bigquery
  - bigquery ml
  - ci/cd
  - data engineering
  - machine learning
  - analytics
  - dbt core
  - docker compose
  - github actions
  - terraform iac
archetypes:
  - Data Engineering
  - Analytics Engineering
  - Backend/Platform Engineering
  - AI Engineer
transferable_skills:
  - etl
  - elt
  - data warehousing
  - data pipeline
  - data modeling
  - orchestration
  - data quality
  - streaming
  - batch processing
  - cloud data warehouse
  - data architecture
  - data ingestion
  - data transformation
  - analytics
  - machine learning
repo_url: https://github.com/SagarMarthandan/chicago-data-pipeline
---

# Chicago Crime & Divvy Bike-Share Data Engineering Pipeline

[![Python](https://img.shields.io/badge/Python-3.13-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Apache Spark](https://img.shields.io/badge/Apache_Spark-3.5.1-E25A1C?style=for-the-badge&logo=apachespark&logoColor=white)](https://spark.apache.org/)
[![Apache Airflow](https://img.shields.io/badge/Apache_Airflow-3.0.0-017CEE?style=for-the-badge&logo=apacheairflow&logoColor=white)](https://airflow.apache.org/)
[![Apache Kafka](https://img.shields.io/badge/Apache_Kafka-7.6.0-231F20?style=for-the-badge&logo=apachekafka&logoColor=white)](https://kafka.apache.org/)
[![dbt](https://img.shields.io/badge/dbt-1.12.0-FF694B?style=for-the-badge&logo=dbt&logoColor=white)](https://www.getdbt.com/)
[![Google BigQuery](https://img.shields.io/badge/BigQuery-Cloud-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)](https://cloud.google.com/bigquery)
[![Terraform](https://img.shields.io/badge/Terraform-1.x-7B42BC?style=for-the-badge&logo=terraform&logoColor=white)](https://www.terraform.io/)
[![Grafana](https://img.shields.io/badge/Grafana-12.4-F46800?style=for-the-badge&logo=grafana&logoColor=white)](https://grafana.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-CI/CD-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)](https://github.com/features/actions)

An end-to-end, phased data engineering pipeline that investigates whether crime near a Divvy bike-share station affects ridership. The project was **built entirely through AI agents and subagents** — an AI assistant (Oh-My-Pi Harness/ Devin IDE / GLM 5.2 model as executor / Qwen 3.7 plus as advisor) acted as the primary engineer, orchestrating scoped subagents for parallel workstreams (CI/CD setup, documentation consolidation, dashboard development, data migration). The human developer provided architectural decisions, phase gates, and terminal execution, while the AI handled code generation, debugging, Docker configuration, Terraform scripting, dbt modeling, and CI/CD pipeline design.

The architecture implements a hybrid ingestion pattern: a **batch ETL path** processing 8.6M crime events and 50M+ Divvy trips through **Apache Spark** and **dlt** into **Google BigQuery**, combined with a **real-time streaming path** capturing live bike station status via **Apache Kafka** and **Spark Structured Streaming** into local **PostgreSQL**. Cloud infrastructure is provisioned with **Terraform**, transformations modeled with **dbt Core** (dbt-bigquery), orchestration via **Apache Airflow 3.0**, observability through **Grafana**, and continuously verified through **GitHub Actions** CI/CD with semantic versioning and GHCR image publishing.

**Key result: Overall Pearson correlation r = +0.20** (n = 1,463,049 station-days). A BigQuery ML linear regression controlling for station, day of week, and month yields a crime coefficient of **+1.45** with in-sample R² = 0.434 — confirming a weak positive relationship driven by urban activity level as a confounding variable.

---

## AI-Driven Development Methodology

This project was engineered through a multi-agent AI workflow:

| Role | Responsibility |
|:---|:---|
| **AI Agent (Oh-My-Pi Harness/ Devin IDE / GLM 5.2 model as executor / Qwen 3.7 plus model as advisor)** | Primary engineer: code generation, debugging, Docker/Terraform/dbt/CI-CD authoring, architecture diagrams, documentation |
| **Subagents (parallel)** | Scoped workstreams: CI/CD workflow setup, documentation consolidation (20+ phase docs → 5), dashboard SQL migration, Spark image rebuilds |
| **Human Developer** | Architectural decisions, phase gate enforcement, terminal execution, code review, error diagnosis direction |

The AI operated under a structured protocol (`AGENTS.md`): phase gates prevented skipping ahead, a changelog tracked every error and fix, and a learning protocol enforced Socratic interaction (explain causes, don't just paste fixes). Subagents were dispatched in parallel batches for independent workstreams — e.g., one consolidated Phase 1 docs while another rebuilt Spark Docker images with GCS connector JARs.

---

## Architecture Diagram

![Architecture Diagram](https://raw.githubusercontent.com/SagarMarthandan/chicago-data-pipeline/prod/docs/images/master_architecture.png)

The system flows from batch and stream sources through processing into cloud storage and analytics. Three parallel paths: batch (Spark → GCS → BigQuery), streaming (Kafka → Spark Streaming → Postgres), and transformation (dlt → BigQuery → dbt → BQML). Airflow orchestrates all paths with dashed dependency arrows. Grafana and DBT Docs serve as observability and documentation layers.

---

## Tech Stack

| Component | Technology | Purpose |
|:---|:---|:---|
| **Language** | Python 3.13 | Pipeline scripts, Spark jobs, Kafka producers, dlt ingestion |
| **Batch Processing** | Apache Spark 3.5.1 | DataFrame cleaning and transformation of crime data (Parquet → GCS) |
| **Stream Processing** | Spark Structured Streaming | Real-time Kafka consumer writing micro-batches to Postgres |
| **Message Broker** | Apache Kafka 7.6.0 | 3-partition topic for GBFS station status updates, keyed by station_id |
| **Orchestration** | Apache Airflow 3.0.0 | DAG scheduling, SqlSensor gating, retries, failure callbacks |
| **Cloud Warehouse** | Google BigQuery | Serverless analytics warehouse with partitioned/clustered marts |
| **Machine Learning** | BigQuery ML | Linear regression model (`crime_ridership_model`) via SQL |
| **Transformation** | dbt Core 1.12.0 (dbt-bigquery) | Modular SQL transforms, dimensional modeling, 84 tests |
| **Cloud Ingestion** | dlt (data load tool) | S3 → BigQuery incremental append for 50M+ Divvy trips |
| **Local Warehouse** | PostgreSQL 16 | Streaming sink + observability metadata store |
| **IaC Provisioning** | Terraform | GCS buckets + BigQuery datasets provisioning |
| **Observability** | Grafana 12.4 | Pipeline health + crime/Divvy analysis dashboards (Postgres datasource) |
| **CI/CD** | GitHub Actions | 3-workflow pipeline: CI checks, GHCR builds, semantic releases |
| **Containerization** | Docker Compose | 12-service local stack: Postgres, Spark, Airflow, Kafka, Grafana |
| **Package Manager** | uv | Reproducible Python dependency management |

---

## Data Sources

| Source | Format | Volume | Access Method |
|:---|:---|:---|:---|
| **Chicago Crime** | BigQuery public dataset | 8.6M rows (2001–present) | `bigquery-public-data.chicago_crime.crime` — referenced directly in dbt source() |
| **Divvy Trip History** | AWS S3 CSV ZIPs | ~50M+ trips (2020–present), 75 monthly files | dlt incremental append into BigQuery `raw.divvy_trips` |
| **Divvy GBFS Live** | REST JSON API | ~60s refresh, station status | Python producer → Kafka → Spark Streaming → Postgres |

---

## Pipeline Architecture

### Batch Path (Cloud — BigQuery)
1. **Crime Data**: Chicago crime data is referenced directly from `bigquery-public-data` via dbt `source()` — no ingestion needed. Filtered to 2018+ for overlap with Divvy data.
2. **Divvy Trips**: `load_divvy_trips.py` uses dlt to stream 75 monthly CSV ZIPs from `divvy-tripdata.s3.amazonaws.com` into BigQuery `raw.divvy_trips` (50M+ rows, append mode).
3. **Spark Batch**: `crime_batch.py` reads local Parquet, cleans/transforms via Spark DataFrames, writes to GCS as Parquet for BigQuery external table access.

### Streaming Path (Local — Postgres)
1. **Kafka Producer**: `divvy_producer.py` polls the GBFS API every 60 seconds, publishes station status JSON to a 3-partition Kafka topic keyed by `station_id`.
2. **Spark Structured Streaming**: `divvy_stream.py` consumes the Kafka stream, parses JSON, and writes micro-batches to Postgres `raw.station_status` with exactly-once semantics via checkpointing.

### Transformation Path (dbt → BigQuery)
1. **Staging Models**: Type casting, field renaming, deduplication on primary keys.
2. **Dimension Models**:
   - `dim_date` — unified calendar covering crime + streaming date ranges
   - `dim_community_area` — seed-backed lookup for Chicago's 77 community areas
   - `dim_crime_type` — normalized crime classification taxonomy
   - `dim_stations` — station dimension with most common coordinate per station via `ROW_NUMBER()`
3. **Fact Models**:
   - `fact_crime_events` — 8.6M geolocation-enriched crime events (partitioned by date, clustered by community_area)
   - `fact_divvy_trips` — 50M+ trip records (partitioned by started_at)
   - `fact_station_day` — 1.46M station-day aggregates: trip_count + crime_count_within_quarter_mile (ST_DISTANCE ≤ 402m)
   - `fact_station_reads` — real-time station capacity reads from streaming path
4. **Analytics Models**:
   - `crime_ridership_correlation` — `CORR()` at overall, per_station, and per_month scope (3,197 rows)
   - `crime_ridership_model` — BigQuery ML linear regression predicting ridership from crime count + temporal features

### Geospatial Join
The driving question is answered by matching station coordinates with crimes committed within a quarter-mile radius on the same day:
```sql
ST_DISTANCE(
  ST_GEOGPOINT(station_lon, station_lat),
  ST_GEOGPOINT(crime_lon, crime_lat)
) <= 402  -- quarter mile in meters
```

### Performance Optimization
- **Partitioning**: `fact_crime_events` partitioned by `date_key`, `fact_divvy_trips` by `started_at`, `fact_station_day` by `date_key` — enables partition pruning (97.8% bytes saved on filtered queries)
- **Clustering**: Tables clustered by `community_area_id` and `station_id` for geospatial filter optimization

---

## Project Structure

```
chicago-data-pipeline/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml              # PR checks: ruff, dbt parse, compose validate, build
│   │   ├── build.yml           # dev merge → build + push images to GHCR
│   │   └── release.yml         # prod merge → semantic version tag + GitHub Release
│   └── ci/profiles.yml         # CI-safe dbt profiles (dummy keyfile for dbt parse)
├── docker-compose.yml          # 12 services: Postgres, Spark, Airflow, Kafka, Grafana
├── pyproject.toml              # uv project mode + ruff config
├── init.sql                    # Postgres init: 3 schemas + airflow DB
│
├── ingestion/
│   ├── download_crime.py       # Socrata API → Parquet (legacy)
│   └── load_divvy_trips.py     # dlt S3→BigQuery (--month/--from/--to/--all/--dry-run)
│
├── spark/
│   ├── Dockerfile              # Spark 3.5.1 + JDBC + Kafka + GCS connector JARs
│   └── jobs/
│       ├── crime_batch.py      # Spark batch: Parquet → clean → GCS Parquet
│       └── divvy_stream.py     # Spark Structured Streaming: Kafka → Postgres
│
├── kafka/producers/
│   └── divvy_producer.py       # GBFS API → Kafka (60s polling, 3 partitions)
│
├── airflow/
│   ├── Dockerfile              # Airflow 3.0 + Docker CLI + gcloud SDK
│   ├── dags/
│   │   ├── crime_batch_dag.py       # dbt_build → record_results
│   │   ├── divvy_stream_dag.py      # streaming lifecycle (7 tasks)
│   │   ├── divvy_trip_history_dag.py # load_divvy_trips → dbt_build → record_results
│   │   └── callbacks.py             # on_failure_callback
│   └── scripts/
│       └── record_dbt_results.py    # dbt run_results.json → observability.dbt_test_results
│
├── dbt/
│   ├── Dockerfile              # dbt-bigquery==1.12.0
│   ├── models/
│   │   ├── staging/            # stg_crime_events, stg_divvy_trips, stg_station_status
│   │   └── marts/              # dim_date, dim_community_area, dim_crime_type, dim_stations,
│   │                           # fact_crime_events, fact_divvy_trips, fact_station_day,
│   │                           # fact_station_reads, crime_ridership_correlation,
│   │                           # crime_ridership_model_* (BQML)
│   ├── tests/                  # assert_crime_in_chicago_bounds.sql
│   └── seeds/                  # community_areas.csv
│
├── terraform/                  # GCP infra as code
│   ├── main.tf                 # 2 BigQuery datasets + 1 GCS bucket
│   ├── variables.tf            # project_id, region, location, credentials_path
│   └── providers.tf            # Google provider v7.40.0
│
├── grafana/
│   ├── provisioning/datasources/  # 2 Postgres datasources
│   └── dashboards/
│       ├── pipeline_health.json       # 11-panel pipeline health dashboard
│       └── crime_divvy_analysis.json  # 8-panel crime + Divvy analysis dashboard
│
└── docs/
    ├── phase/                  # Consolidated phase docs (1–5)
    ├── wiki/                   # Technology reference + conventions
    └── chat-history/           # Conversation logs + handoff doc
```

---

## CI/CD Pipeline

A 3-workflow GitHub Actions pipeline with branch protection on both `prod` (default) and `dev` branches:

### Workflow 1: CI Checks (PRs to `dev` / `prod`)
- **Ruff linting** on all Python files
- **dbt parse** with CI-safe profiles (dummy keyfile — parse never connects to DB)
- **Docker Compose config validation**
- **Multi-stage image build** checks

### Workflow 2: Build & Push (Merge to `dev`)
- Builds and tags development images (`airflow:dev`, `spark:dev`, `dbt:dev`)
- Pushes to GitHub Container Registry (GHCR) with lowercase repository path

### Workflow 3: Release (Merge to `prod`)
- Semantic version bumping (`v{MAJOR}.{MINOR}.{PATCH}`) from commit logs
- Auto-generated GitHub Release with release notes
- Versioned production images pushed to GHCR

---

## Data Quality & Fault Tolerance

### In-Warehouse Data Quality (dbt)
- **84 tests**: unique constraints, non-null properties, relationship integrity, accepted values
- **Singular test**: `assert_crime_in_chicago_bounds.sql` — rejects coordinates outside Chicago city limits
- **dbt-expectations**: Additional generic tests from dbt-utils package

### Airflow Pipeline Resilience
- **SqlSensor gating**: Checks for raw table existence before transformation tasks — prevents race conditions between batch and streaming
- **Retries**: 3 retries with 5-minute intervals
- **Execution timeouts**: 30-minute cap per task
- **Failure callbacks**: Structured JSON context logging via `on_failure_callback`

### Observability
- **dbt test results** parsed from `run_results.json` → Postgres `observability.dbt_test_results` (64 rows tracked)
- **Grafana dashboards**: 11-panel pipeline health (row counts, trip rate, freshness, DAG status) + 8-panel crime/Divvy analysis (crime heatmaps, trip charts, correlation scatter, Pearson r gauge)

---

## Key Findings

| Metric | Value | Interpretation |
|:---|:---|:---|
| **Pearson correlation (r)** | +0.20 | Weak positive — stations with more nearby crime also have more trips |
| **BQML crime coefficient** | +1.45 | Positive even after controlling for station, day of week, month |
| **BQML R²** | 0.434 | Model explains 43.4% of variance in daily trip count |
| **Station-days analyzed** | 1,463,049 | Each station-day pairs trip count with crime count within 402m |
| **Crime rows** | 8,600,000 | Full Chicago crime dataset (2001–present) |
| **Divvy trips** | 50,000,000+ | 75 monthly files, 2020–present |
| **dbt tests passing** | 84/84 | Schema assertions + singular bounds check + expectations |

**Conclusion**: The weak positive correlation does NOT mean crime causes ridership. Both are higher in busy, densely populated areas — the confounding variable is urban activity level. Per-month correlations trend upward from 0.08 (April 2020, COVID lockdown) to ~0.25–0.30 (2024–2025), suggesting the relationship strengthens as the city normalizes post-pandemic.

---

## Phase Completion Status

| Phase | Feature | Status | Details |
|:---|:---|:---|:---|
| **1** | Spark Batch + dbt + Airflow | 🟢 Complete | Crime Parquet → Spark → GCS, dbt staging/marts, Airflow DAG |
| **2** | Kafka + Spark Streaming | 🟢 Complete | GBFS → Kafka (3 partitions) → Spark Structured Streaming → Postgres |
| **3** | Grafana + dbt Test Logging | 🟢 Complete | 2 dashboards (19 panels), dbt results → Postgres, SqlSensor gating |
| **4** | Terraform + dlt + BigQuery + BQML | 🟢 Complete | GCP infra, 50M+ trips via dlt, partitioned marts, BQML regression |
| **5** | CI/CD + GHCR + Semantic Releases | 🟢 Complete | 3 GitHub Actions workflows, branch protection, versioned GHCR images |

---

## How to Run

### Prerequisites
- Docker Desktop with WSL2 backend
- GCP account with service account key (for BigQuery + GCS)

### First Run
```bash
git clone https://github.com/SagarMarthandan/chicago-data-pipeline && cd chicago-data-pipeline
cp .env.example .env                    # Fill in values
chmod 666 airflow/passwords.json        # Airflow SimpleAuthManager
docker compose build                    # Build Airflow + Spark + dbt images
docker compose up -d                    # Start 12 services
docker compose ps -a                    # Verify all healthy
```

### Accessing Services
| Service | URL | Login |
|:---|:---|:---|
| Airflow UI | http://localhost:8080 | admin / admin |
| Spark Master UI | http://localhost:8180 | — |
| Grafana UI | http://localhost:3000 | admin / admin |
| Postgres | localhost:5432 | chicago / (from .env) |

### Triggering the Pipeline
```bash
# Batch DAGs
docker exec chicago-data-pipeline-airflow-scheduler-1 airflow dags trigger crime_batch
docker exec chicago-data-pipeline-airflow-scheduler-1 airflow dags trigger divvy_trip_history

# Streaming DAG
docker exec chicago-data-pipeline-airflow-scheduler-1 airflow dags trigger divvy_stream

# Query correlation results
bq query --use_legacy_sql=false "SELECT * FROM \`chicago-divvy-pipeline.mart.crime_ridership_correlation\` WHERE scope='overall'"
```

---

## Author

- **Sagar Marthandan**
- **GitHub**: [github.com/SagarMarthandan](https://github.com/SagarMarthandan)
