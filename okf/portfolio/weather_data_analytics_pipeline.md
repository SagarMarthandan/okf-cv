---
title: Weather Data Analytics Pipeline
description: End-to-end ELT pipeline ingesting real-time weather data from Weatherstack API, transforming with dbt, and visualizing via Apache Superset.
technologies: Airflow, Docker, PostgreSQL, Python, Redis, dbt, Apache Superset
keywords:
- airflow
- dbt
- postgresql
- docker
- real-time ingestion
- apache superset
- containerized environment
- dood connection
- system staging
- access
- bash
- data
- warehouse
- acts
- analytics
archetypes:
- Data Engineering
- Analytics Engineering
repo_url: https://github.com/SagarMarthandan
---

# Weather Data Analytics Pipeline

An end-to-end data engineering pipeline designed to ingest real-time weather data from the Weatherstack API, transform it using dbt, and visualize insights through Apache Superset.

---

## 🛠️ Tech Stack

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![PostgreSQL](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Airflow](https://img.shields.io/badge/Airflow-017CEE?style=for-the-badge&logo=Apache%20Airflow&logoColor=white)
![dbt](https://img.shields.io/badge/dbt-FF694B?style=for-the-badge&logo=dbt&logoColor=white)
![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)

*   **Languages:** Python, SQL
*   **Orchestration:** Apache Airflow
*   **Transformation:** dbt (Data Build Tool)
*   **Database:** PostgreSQL
*   **Containerization:** Docker & Docker Compose
*   **Messaging/Broker:** Redis
*   **Visualization:** Apache Superset

---

## 🏗️ System Architecture

The following diagram illustrates the data flow from the external API to the final visualization layer:

```mermaid
graph TD
    subgraph External_Source [External Source]
        API[Weatherstack API]
    end

    subgraph Orchestration_Messaging [Orchestration & Messaging]
        AF[Apache Airflow]
        REDIS[(Redis Broker)]
        AF <--> REDIS
    end

    subgraph Ingestion_Layer [Ingestion Layer - Python]
        REQ[api_request.py] -->|Fetch JSON| INS[insert_records.py]
    end

    subgraph Storage_Layer [Storage Layer - PostgreSQL Warehouse]
        DB[(Postgres DB)]
        RAW[[dev.raw_weather_data]]
    end

    subgraph Transformation_Layer [Transformation Layer - dbt]
        STG[stg_weather_data.sql] -->|Deduplicate & Localize| MART[daily_average.sql]
    end

    subgraph Visualization_Layer [Visualization Layer]
        SUPER[Apache Superset]
    end

    %% Data Flow
    API --> REQ
    INS --> RAW
    RAW --> STG
    MART --> SUPER

    %% Orchestration Flow
    AF -->|Trigger Ingestion| REQ
    AF -->|Trigger dbt run| Transformation_Layer
```

---

## 🌉 The WSL 2 & Docker Desktop Bridge

This pipeline leverages the high-performance integration between **Windows**, **WSL 2**, and **Docker Desktop**:

1.  **The Socket Bridge:** Docker Desktop creates a symbolic link for the Docker Unix socket (`/var/run/docker.sock`) inside the WSL 2 environment.
2.  **DooD (Docker-out-of-Docker):** The Airflow container mounts this socket from WSL. When the `DockerOperator` triggers a task, it doesn't run Docker *inside* Airflow; instead, it sends a command through the socket to the Docker Engine on the Windows host.
3.  **Sibling Containers:** This allows Airflow to spin up "sibling" containers (like the `dbt` container) that run alongside it on the same network, sharing the same Docker resources.

---

## 🧠 In-Depth Component Breakdown

### 1. The Ingestion Engine (Python & API)
The ingestion layer is built using Python's `requests` library. 
*   **Logic:** It performs a synchronous GET request to Weatherstack. 
*   **Database Interaction:** Instead of just dumping JSON, `insert_records.py` uses `psycopg2` to ensure the `dev` schema exists and creates the `raw_weather_data` table if it's missing. It appends a `utc_offset` and a `NOW()` timestamp to every record to handle time-series analysis later.

### 2. The Orchestrator (Airflow & Redis)
**Apache Airflow** acts as the brain of the pipeline.
*   **Redis's Role:** Redis serves as the **Message Broker**. When Airflow schedules a task, it pushes a message to Redis. An Airflow Worker then pulls that message to execute the task. This ensures that even if the web server goes down, the task queue remains intact.
*   **Task Dependencies:** The DAG enforces a strict "Ingest-then-Transform" policy. If the Python ingestion fails, the dbt transformation will not trigger, preventing stale or null data processing.

### 3. Transformation Layer (dbt & Docker)
We use an **ELT (Extract, Load, Transform)** approach. Data is loaded raw into Postgres and then transformed using dbt.
*   **Docker-out-of-Docker (DooD):** The Airflow DAG uses the `DockerOperator`. By mounting `/var/run/docker.sock`, the Airflow container can spin up a *sibling* container running `dbt-postgres`.
*   **Staging (`stg_weather_data`)**: This model handles the "dirty" work. It uses a Window Function (`row_number()`) to deduplicate records based on the API's `time` field. It also converts the system insertion time to the city's local time using the `utc_offset`.
*   **Mart (`daily_average`)**: This is the final "Gold" layer. It aggregates the cleaned data to provide high-level metrics (average temp/wind) used by the business layer.

### 4. Storage & Visualization (Postgres & Superset)
*   **PostgreSQL:** Serves as the single source of truth. It stores the raw JSON-like rows, the staged views, and the final aggregated tables.
*   **Apache Superset:** Connects directly to the `daily_average` table. Because dbt materializes this as a **Table** (not a view), Superset queries are lightning-fast as they don't require re-calculating averages on every dashboard refresh.

---

## 🛠️ Advanced Configuration: Docker Mounting
To keep the dbt logic separate from the orchestration logic, we bind-mount the dbt project into the Docker container at runtime:
```python
Mount(
    source='/home/sagar/repos/weather-data-project/dbt/my_project', 
    target='/usr/app/', 
    type='bind'
)
```
This allows you to update your SQL models without needing to rebuild your Docker images.

## 📂 Project Structure

*   **`api-request/`**: Contains Python scripts for interacting with the Weatherstack API and handling initial database inserts.
*   **`airflow/`**: Contains the DAG definitions to schedule and monitor the pipeline.
*   **`dbt/`**: Contains the dbt project, including staging models, data marts, and source configurations.
*   **`docker-compose.yml`**: Orchestrates the various services (Postgres, Airflow, Superset).

---

## 🚀 Pipeline Workflow

### 1. Data Ingestion
The pipeline starts with a Python-based ingestion process:
*   **`api_request.py`**: Authenticates with the Weatherstack API and retrieves current weather data for New York.
*   **`insert_records.py`**: Establishes a connection to the PostgreSQL instance, ensures the `dev.raw_weather_data` table exists, and appends the new JSON record with an insertion timestamp.

### 2. Orchestration
**Apache Airflow** manages the workflow via the `weather-api-dbt-orchestrator` DAG:
*   **Schedule:** Runs every minute (`timedelta(minutes=1)`).
*   **Task 1 (`ingest_data_task_1`):** Executes the Python ingestion script.
*   **Task 2 (`transform_data_task`):** Uses a `DockerOperator` to spin up a dbt container and execute `dbt run`, ensuring transformations happen immediately after data lands.

### 3. Data Transformation (dbt)
Data is transformed in two stages within the Postgres `dev` schema:
*   **Staging (`stg_weather_data`)**: 
    *   Deduplicates records based on the API's observation time.
    *   Calculates `inserted_at_local` by applying the `utc_offset` to the system timestamp.
*   **Mart (`daily_average`)**: 
    *   Aggregates data to a daily grain.
    *   Calculates the average temperature and wind speed per city per day.

### 4. Visualization
The final `daily_average` table is connected to **Apache Superset**, where dashboards track:
*   Temperature trends over time.
*   Average wind speed comparisons.
*   Real-time weather status updates.

---

##  How to Run (Step-by-Step)

### 1. API Setup
Sign up at Weatherstack and obtain your free API Access Key.

### 2. Environment Configuration
In the project root, create a file named `.env`:
```bash
WEATHERSTACK_API_KEY=your_api_key_here
POSTGRES_USER=airflow
POSTGRES_PASSWORD=airflow
POSTGRES_DB=weather_db
```

### 3. Launch the Infrastructure
Open your WSL terminal and run:
```bash
docker-compose up -d
```

### 4. Initialize Apache Superset
Superset requires a one-time setup to create the admin user and initialize the metadata database:
```bash
docker-compose exec superset superset db upgrade
docker-compose exec superset superset fab create-admin --username admin --firstname Admin --lastname User --email admin@fab.org --password admin
docker-compose exec superset superset init
```

### 5. Trigger the Pipeline
1. Access the Airflow UI at `http://localhost:8080` (Login: `airflow` / `key-generated-in-airflow-logs`).
2. Locate the `weather-api-dbt-orchestrator` DAG.
3. Toggle the DAG to **Unpause** and click **Trigger DAG**.

### 6. Visualize Data
1. Access Superset at `http://localhost:8088` (Login: `admin` / `admin`).
2. Connect to the Postgres database using the connection string:
    ```bash
    postgresql://airflow:airflow@postgres:5432/weather_db
    ```
3. Query the `dev.daily_average` table to build your charts and dashboards.


-----------------------------------------------------------------------------------