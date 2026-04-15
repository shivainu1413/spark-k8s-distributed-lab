#!/bin/bash
# ============================================================
# Step 5: Execute ETL Pipeline
#
# This script will:
#   1. Create custom Spark Docker image (add S3 connector + ETL code)
#   2. Upload sample CSV data to MinIO
#   3. Submit ETL job
#   4. Observe execution process
#
# Usage: ./scripts/05-run-etl.sh
# ============================================================

set -e

echo "=========================================="
echo "  [INFO] Running ETL Pipeline"
echo "=========================================="
echo ""

# ============================================================
# 1. Create custom Spark Docker image
# ============================================================
echo "[INFO] [1/4] Creating custom Spark image..."
echo "   (Pointing Minikube Docker environment to our shell)"

# Let docker build store the image directly in Minikube's Docker registry
# This way K8s can use it directly, no need to push to external registry
eval $(minikube docker-env)

docker build \
    -t spark-etl:latest \
    -f docker/Dockerfile.spark \
    .

echo "   [OK] spark-etl:latest image created"
echo ""

# ============================================================
# 2. Upload sample data to MinIO
# ============================================================
echo "[INFO] [2/4] Uploading CSV data to MinIO..."

# Use port-forward to temporarily expose MinIO to local machine, then upload with curl
# First run port-forward in background
kubectl port-forward svc/minio-svc 9000:9000 -n spark-demo &
PF_PID=$!
sleep 3

# Use curl to upload through MinIO S3 API (PUT to specified path)
curl -s -X PUT \
    -T data/sample-input/sales_data.csv \
    -u minioadmin:minioadmin \
    http://localhost:9000/spark-data/raw/sales_data.csv

# Close port-forward
kill $PF_PID 2>/dev/null || true
wait $PF_PID 2>/dev/null || true

echo "   [OK] sales_data.csv uploaded to s3://spark-data/raw/"
echo ""

# ============================================================
# 3. Submit ETL Job
# ============================================================
echo "[INFO] [3/4] Submitting ETL Pipeline job..."

# Clean up previous job (if exists)
kubectl delete sparkapplication etl-pipeline -n spark-demo 2>/dev/null || true
sleep 2

kubectl apply -f jobs/etl-pipeline/spark-etl.yaml
echo ""

# ============================================================
# 4. Observe execution process
# ============================================================
echo "[INFO] [4/4] Observing Pod lifecycle..."
echo "   Press Ctrl+C to stop observing (job will continue running)"
echo ""

sleep 3

kubectl get pods -n spark-demo -l app=etl-pipeline --watch &
WATCH_PID=$!

# Wait for job to complete (max 10 minutes, because image needs to be pulled)
kubectl wait --for=jsonpath='{.status.applicationState.state}'=COMPLETED \
    sparkapplication/etl-pipeline \
    -n spark-demo \
    --timeout=600s 2>/dev/null || true

kill $WATCH_PID 2>/dev/null || true
wait $WATCH_PID 2>/dev/null || true

echo ""
echo "=========================================="
echo "  [INFO] ETL Pipeline Results"
echo "=========================================="

# Get Driver Pod name
DRIVER_POD=$(kubectl get pods -n spark-demo -l app=etl-pipeline,role=driver -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -n "$DRIVER_POD" ]; then
    echo ""
    echo "Driver Pod: $DRIVER_POD"
    echo ""
    echo "--- ETL Output ---"
    kubectl logs "$DRIVER_POD" -n spark-demo 2>/dev/null | grep -A 100 "ETL Pipeline execution started" || echo "(view full log: kubectl logs $DRIVER_POD -n spark-demo)"
fi

echo ""
echo "[INFO] Common commands:"
echo "   kubectl logs $DRIVER_POD -n spark-demo    # View full log"
echo "   kubectl get sparkapplication etl-pipeline -n spark-demo  # View job status"
echo ""
echo "[INFO] Cleanup: kubectl delete sparkapplication etl-pipeline -n spark-demo"
