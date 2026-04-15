#!/bin/bash
# ============================================================
# Step 4: Run First Spark Job - SparkPi
#
# SparkPi is Spark's Hello World
# It uses Monte Carlo method to calculate pi, distributing computation to 2 Executors
#
# This script will:
#   1. Submit SparkPi job
#   2. Show Pod creation process in real-time (you will see Driver → Executors appear)
#   3. Display results after job completes
#
# Usage: ./scripts/04-run-sparkpi.sh
# ============================================================

set -e

echo "=========================================="
echo "  [INFO] Running First Spark Job: SparkPi"
echo "=========================================="
echo ""

# --- Submit SparkApplication ---
echo "[INFO] Submitting SparkPi job..."
kubectl apply -f jobs/spark-pi/spark-pi.yaml

echo ""
echo "[INFO] Observing Pod lifecycle (you will see Driver and Executors appear dynamically)"
echo "   Press Ctrl+C to stop observing (job will continue running)"
echo ""

# Wait a bit to let K8s start creating Pods
sleep 3

# Display Pod status
echo "--- Pod Status ---"
kubectl get pods -n spark-demo -l app=spark-pi --watch &
WATCH_PID=$!

# Wait for Driver Pod to complete
echo ""
echo "Waiting for job to complete..."
kubectl wait --for=condition=complete sparkapplication/spark-pi \
    -n spark-demo \
    --timeout=300s 2>/dev/null || true

# Stop watch
kill $WATCH_PID 2>/dev/null || true
wait $WATCH_PID 2>/dev/null || true

echo ""
echo "=========================================="
echo "  [INFO] SparkPi Results"
echo "=========================================="

# Get Driver Pod name
DRIVER_POD=$(kubectl get pods -n spark-demo -l app=spark-pi,role=driver -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -n "$DRIVER_POD" ]; then
    echo ""
    echo "Driver Pod: $DRIVER_POD"
    echo ""
    # Display calculation result
    kubectl logs "$DRIVER_POD" -n spark-demo | grep -i "pi is roughly" || echo "(check log after job completes)"
    echo ""
fi

echo "[INFO] Manual commands to view results:"
echo "   kubectl get sparkapplication spark-pi -n spark-demo     # View job status"
echo "   kubectl logs $DRIVER_POD -n spark-demo                  # View full log"
echo "   kubectl get pods -n spark-demo                          # View all Pods"
echo ""
echo "[INFO] Cleanup: kubectl delete sparkapplication spark-pi -n spark-demo"
