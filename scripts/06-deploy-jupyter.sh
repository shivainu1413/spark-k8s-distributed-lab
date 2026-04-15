#!/bin/bash
# ============================================================
# Step 6: Deploy JupyterLab + Dashboard
#
# This script will:
#   1. Build JupyterLab Docker image
#   2. Deploy JupyterLab Pod to K8s
#   3. Configure port-forward
#   4. Tell you how to open it
# ============================================================

set -e

echo "=========================================="
echo "  [INFO] Deploying JupyterLab + Dashboard"
echo "=========================================="
echo ""

# --- Ensure cluster is running ---
if ! minikube status --format='{{.Host}}' 2>/dev/null | grep -q "Running"; then
    echo "[ERROR] Minikube is not running"
    exit 1
fi

# ============================================================
# 1. Build JupyterLab image
# ============================================================
echo "[INFO] [1/3] Creating JupyterLab image..."
eval $(minikube docker-env)

docker build \
    -t jupyter-spark:latest \
    -f docker/Dockerfile.jupyter \
    .

echo "   [OK] jupyter-spark:latest created"
echo ""

# ============================================================
# 2. Ensure spark-etl image is present (Executors will use it)
# ============================================================
echo "[INFO] [2/3] Verifying Spark ETL image..."
docker build \
    -t spark-etl:latest \
    -f docker/Dockerfile.spark \
    .
echo "   [OK] spark-etl:latest verified"
echo ""

# ============================================================
# 3. Deploy JupyterLab
# ============================================================
echo "[INFO] [3/3] Deploying JupyterLab Pod..."

kubectl apply -f k8s/jupyter/deployment.yaml

echo "   Waiting for JupyterLab to start..."
kubectl wait --for=condition=ready pod -l app=jupyter-spark -n spark-demo --timeout=300s

echo "   [OK] JupyterLab deployed"
echo ""

echo "=========================================="
echo "  [OK] Deployment complete!"
echo "=========================================="
echo ""
echo "[INFO] Startup method (requires 3 terminals):"
echo ""
echo "Terminal 1 - JupyterLab:"
echo "  kubectl port-forward svc/jupyter-spark-svc 8888:8888 -n spark-demo"
echo "  → Open http://localhost:8888 in browser"
echo ""
echo "Terminal 2 - Dashboard:"
echo "  cd dashboard && python3 server.py"
echo "  → Open http://localhost:8080 in browser"
echo ""
echo "Terminal 3 - Spark History Server (optional):"
echo "  kubectl port-forward svc/spark-history-svc 18080:18080 -n spark-demo"
echo "  → Open http://localhost:18080 in browser"
echo ""
echo "Then open 01_spark_etl_demo.ipynb in JupyterLab"
echo "Run cell by cell and watch Dashboard changes in real-time!"
