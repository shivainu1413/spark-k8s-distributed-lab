# Spark on Kubernetes

> A distributed data processing lab with real-time visualization — deploy Apache Spark on Kubernetes, write PySpark interactively in JupyterLab, and watch Pod lifecycle, data flow, and Shuffle operations happen live on a custom dashboard.

![Cover](./cover.png)

## Overview

This project builds a complete Spark-on-Kubernetes environment from scratch using Minikube, designed as a hands-on learning tool and interview portfolio piece. It goes beyond typical tutorials by including an interactive JupyterLab notebook (Client Mode) paired with a real-time monitoring dashboard that visualizes how distributed processing actually works — Executor Pods dynamically scaling up/down, data flowing from MinIO to Executors, and Shuffle operations exchanging data between nodes.

## Tech Stack

- **Compute**: Apache Spark 3.5.3, PySpark
- **Orchestration**: Kubernetes (Minikube), Helm 3, Spark Operator (Kubeflow)
- **Storage**: MinIO (S3-compatible)
- **Notebook**: JupyterLab 4
- **Dashboard**: Python, HTML5 Canvas, Server-Sent Events
- **Containerization**: Docker
- **Monitoring**: Spark History Server, Spark REST API

## Features

- **Interactive Notebook**: Write PySpark cell-by-cell in JupyterLab — each cell triggers real distributed processing on Kubernetes
- **Real-time Dashboard**: Canvas-based visualization showing Pod creation/destruction, data flow particles, and Shuffle indicators as they happen
- **Dynamic Allocation**: Executor Pods automatically scale from 0 to 4 based on workload, with configurable idle timeout
- **ETL Pipeline**: Complete Extract (CSV from S3) → Transform (filter + groupBy with Shuffle) → Load (Parquet to S3) workflow
- **Spark History Server**: Review completed job DAGs, Stages, and Shuffle metrics after execution
- **Dark/Light Theme**: Dashboard supports theme toggle with grid background

## Architecture

```
                    K8s Cluster (Minikube)
    ┌──────────────────────────────────────────────┐
    │                                              │
    │   [K8s API Server]  ---  [Spark Operator]    │
    │          |                                   │
    │   [Driver / JupyterLab]                      │
    │       /     |      \                         │
    │  [MinIO] - [Exec 1] [Exec 2] ... [Exec N]   │
    │              --- Shuffle ---                  │
    └──────────────────────────────────────────────┘
                        |
              [Real-time Dashboard]
```

| Component | Role | Lifecycle |
|-----------|------|-----------|
| K8s API Server | Cluster control plane, pod scheduling | Persistent |
| Spark Operator | Watches SparkApplication CRDs, manages job lifecycle | Persistent |
| Driver (JupyterLab) | Spark Driver in Client Mode, interactive PySpark | Persistent |
| Executor Pods | Execute tasks, process data partitions | Dynamic (0-4) |
| MinIO | S3-compatible object storage | Persistent |
| Dashboard | Real-time pod events, data flow, shuffle visualization | External |

## Getting Started

```bash
git clone https://github.com/shivainu1413/spark-on-kubernetes.git
cd spark-on-kubernetes

# 1. Install tools (minikube, kubectl, helm)
./scripts/01-install-tools.sh

# 2. Start K8s cluster
./scripts/02-start-cluster.sh

# 3. Deploy Spark Operator + MinIO + RBAC
./scripts/03-deploy-spark.sh

# 4. Deploy JupyterLab
./scripts/06-deploy-jupyter.sh
```

### Interactive Demo

Open three terminals after deployment:

```bash
# Terminal 1 — JupyterLab
kubectl port-forward svc/jupyter-spark-svc 8888:8888 -n spark-demo

# Terminal 2 — Dashboard
cd dashboard && python3 server.py

# Terminal 3 — Spark History Server (optional)
kubectl port-forward svc/spark-history-svc 18080:18080 -n spark-demo
```

Open in browser:
- `http://localhost:8888` — JupyterLab (open `01_spark_etl_demo.ipynb`)
- `http://localhost:8080` — Real-time Dashboard
- `http://localhost:18080` — Spark History Server

Run notebook cells one by one and watch the Dashboard react in real-time.

## Screenshots

| Dashboard (Dark) | Dashboard (Light) |
|---|---|
| ![](./screenshots/dashboard-dark.png) | ![](./screenshots/dashboard-light.png) |

| Notebook + Dashboard | Spark History Server |
|---|---|
| ![](./screenshots/notebook-dashboard.png) | ![](./screenshots/history-server.png) |

## Project Structure

```
.
├── README.md
├── docker/
│   ├── Dockerfile.spark          # Custom Spark image (+ S3 connector)
│   └── Dockerfile.jupyter        # JupyterLab + PySpark image
├── k8s/
│   ├── namespace/                # Namespace definition
│   ├── minio/                    # MinIO deployment + service
│   ├── spark-operator/           # Helm values for Spark Operator
│   ├── spark-history/            # Spark History Server
│   ├── jupyter/                  # JupyterLab deployment + service
│   └── 00-learn-k8s-basics/      # K8s fundamentals exercises
├── jobs/
│   ├── spark-pi/                 # SparkPi test job (Cluster Mode)
│   └── etl-pipeline/             # ETL Pipeline (PySpark + MinIO)
├── notebooks/
│   └── 01_spark_etl_demo.ipynb   # Interactive ETL demo notebook
├── dashboard/
│   ├── server.py                 # Backend: K8s pod watcher + Spark API poller
│   └── index.html                # Frontend: Canvas-based real-time visualization
├── data/
│   └── sample-input/             # Sample CSV datasets
└── scripts/
    ├── 01-install-tools.sh       # Install minikube, kubectl, helm
    ├── 02-start-cluster.sh       # Start Minikube cluster
    ├── 03-deploy-spark.sh        # Deploy Spark Operator + MinIO
    ├── 04-run-sparkpi.sh         # Run SparkPi test job
    ├── 05-run-etl.sh             # Run ETL pipeline (Cluster Mode)
    └── 06-deploy-jupyter.sh      # Deploy JupyterLab
```

## Key Concepts Demonstrated

**Spark on Kubernetes** — Client Mode vs Cluster Mode, Dynamic Allocation, ServiceAccount/RBAC, Spark Operator CRD management

**Distributed Processing** — Narrow vs Wide Dependencies, Shuffle mechanics, Partition-level parallelism, Lazy Evaluation

**Data Engineering** — ETL pipeline design, S3-compatible storage, Parquet columnar format, data quality handling

## Prerequisites

- macOS with Homebrew
- Docker Desktop (memory set to 6GB+)
- 8GB+ RAM

## License

MIT
