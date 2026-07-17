---
title: 'Kafka FX Rates: Batch vs Stream Processing Walkthrough'
description: Kafka-driven pipeline processing FX rates from batch CSV files to real-time stream consumers for analytics and monitoring.
technologies: Apache Kafka, Python, Pandas, Jupyter
keywords:
- real-time analytics
- message queue
- producer consumer
- data pipeline
- currency exchange
- latency benchmark
- python producer
- csv ingestion
- throughput optimization
- changes
- context
- data
- apache
- batch
- driven
archetypes:
- Data Engineering
repo_url: https://github.com/SagarMarthandan
---

# Kafka FX Rates: Batch vs Stream Processing Walkthrough

[![Kafka](https://img.shields.io/badge/Apache_Kafka-231F20?style=for-the-badge&logo=apache-kafka&logoColor=white)](https://kafka.apache.org/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Jupyter](https://img.shields.io/badge/Jupyter-F37626?style=for-the-badge&logo=jupyter&logoColor=white)](https://jupyter.org/)
[![Pandas](https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)](https://pandas.pydata.org/)

This project demonstrates a **Kafka-driven data pipeline** designed to process Foreign Exchange (FX) rates. It highlights how Kafka can be leveraged to move data from static batch files to real-time consumers for analytics and monitoring.

---

## 🏗️ System Architecture

The following diagram illustrates the flow of currency data from a CSV source to a live analytics "billboard" via Kafka.

```mermaid
graph LR
    subgraph "Data Source"
        CSV[rates_sample.csv]
    end

    subgraph "Kafka Cluster"
        P[Producer Notebook] --> T((Topic: currency_fx_rates))
    end

    subgraph "Analytics Layer"
        T --> C[Consumer Notebook]
        C --> B[Analytics Billboard]
    end

    style T fill:#f9f,stroke:#333,stroke-width:2px
    style B fill:#bbf,stroke:#333,stroke-width:2px
```

---

## 🚀 How to Run

Follow these steps to set up the Kafka environment and run the processing tool.

### 1. Start Services

Open your terminal in the Kafka installation directory (e.g., `C:\kafka\bin\windows`) and run:

| Step             | Command                                                        |
| :--------------- | :------------------------------------------------------------- |
| **Zookeeper**    | `zookeeper-server-start.bat ..\..\config\zookeeper.properties` |
| **Kafka Server** | `kafka-server-start.bat ..\..\config\server.properties`        |

### 2. Configure Topics

Create the necessary topic for FX rates:

```bash
kafka-topics.bat --create --topic currency_fx_rates --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
```

### 3. Run the Pipeline

1.  **Start the Producer**: Run `producer_360T.ipynb`. This reads `rates_sample.csv` and streams the data to Kafka.
2.  **Start the Consumer**: Run `consumer_360T.ipynb`. This consumes the data and calculates percentage changes against "Yesterday's 5 PM Rate".

---

## 🧠 Project Logic

### 📤 Producer (`producer_360T.ipynb`)

- **Function**: Ingests `rates_sample.csv`.
- **Logic**: Iterates through each FX event, serializes it to JSON, and publishes it to the `currency_fx_rates` topic.
- **Mechanism**: Uses a `KafkaProducer` with a 1-second delay between messages to simulate a steady stream of data.

### 📥 Consumer (`consumer_360T.ipynb`)

- **Function**: Real-time Analytics Engine.
- **Logic**:
  - Listens to the Kafka topic.
  - Compares the current rate against a hardcoded `previous_day_rates` dictionary.
  - Calculates the **Percentage Change**.
- **Output**: Renders a "Billboard" in the terminal showing the pair, current rate, and trend.

---

## 🔄 Kafka: Stream vs Batch Processing

This project sits at the intersection of Batch and Stream processing. Here is how they differ in the context of Kafka:

| Feature          | 📦 Batch Processing                                  | 🌊 Stream Processing (Used Here)                      |
| :--------------- | :--------------------------------------------------- | :---------------------------------------------------- |
| **Data Arrival** | Collected over a period, then processed all at once. | Processed immediately as individual events occur.     |
| **Latency**      | High (Minutes to Hours).                             | Ultra-Low (Milliseconds to Seconds).                  |
| **Source**       | Large files (CSV, Parquet) or Databases.             | Real-time events, sensors, or app logs.               |
| **Kafka Role**   | Storing historical logs for later analysis.          | Acting as the "central nervous system" for live data. |

> [!TIP]
> **Why Kafka?** Kafka allows us to turn static files into a high-throughput stream, making it easy to scale the analytics layer without modifying the data source.

---

## 📂 Structure

- `producer_360T.ipynb`: Logic to push data to Kafka.
- `consumer_360T.ipynb`: Logic to process data and show analytics.
- `rates_sample.csv`: Sample FX data source.
- `kafka commands.txt`: Cheat sheet for Kafka operations.





-------------------------------------------------------------------------------------