#!/bin/bash
# ============================================================
# Step 3: Deploy Spark Operator + MinIO
#
# This script will:
#   1. Install Spark Operator with Helm (persistent Pod, manages Spark jobs)
#   2. Deploy MinIO (S3-compatible storage)
#   3. Create MinIO buckets for Spark to use
#   4. Configure ServiceAccount and RBAC for Spark
#
# Usage: ./scripts/03-deploy-spark.sh
# Prerequisites: Cluster started (02-start-cluster.sh)
# ============================================================

set -e

echo "=========================================="
echo "  Deploying Spark Operator + MinIO"
echo "=========================================="

# --- Check if cluster is running ---
if ! minikube status --format='{{.Host}}' 2>/dev/null | grep -q "Running"; then
    echo "[ERROR] Minikube cluster is not running, please first run ./scripts/02-start-cluster.sh"
    exit 1
fi
echo "[OK] Minikube cluster is running"
echo ""

# --- Ensure namespace exists ---
kubectl create namespace spark-demo --dry-run=client -o yaml | kubectl apply -f -

# ============================================================
# 1. Install Spark Operator (with Helm)
# ============================================================
echo "[INFO] [1/4] Installing Spark Operator..."

# Add Helm repo
helm repo add spark-operator https://kubeflow.github.io/spark-operator
helm repo update

# Install (or upgrade) Spark Operator
helm upgrade --install spark-operator spark-operator/spark-operator \
    --namespace spark-operator \
    --create-namespace \
    --values k8s/spark-operator/values.yaml \
    --wait \
    --timeout 3m

echo "   [OK] Spark Operator installed"
echo ""

# ============================================================
# 2. Configure RBAC (allow Spark to create Executor Pods)
# ============================================================
echo "[INFO] [2/4] Configuring Spark RBAC permissions..."

# Create ServiceAccount for Spark
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: ServiceAccount
metadata:
  name: spark
  namespace: spark-demo
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: spark-role
  namespace: spark-demo
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "services", "configmaps", "persistentvolumeclaims"]
    verbs: ["*"]
  - apiGroups: [""]
    resources: ["events"]
    verbs: ["create", "update", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: spark-role-binding
  namespace: spark-demo
subjects:
  - kind: ServiceAccount
    name: spark
    namespace: spark-demo
roleRef:
  kind: Role
  name: spark-role
  apiGroup: rbac.authorization.k8s.io
EOF

echo "   [OK] ServiceAccount 'spark' created (Driver uses this identity to create Executors)"
echo ""

# ============================================================
# 3. Deploy MinIO
# ============================================================
echo "[INFO] [3/4] Deploying MinIO..."

kubectl apply -f k8s/minio/deployment.yaml
kubectl apply -f k8s/minio/service.yaml

# Wait for MinIO Pod to be ready
echo "   Waiting for MinIO to start..."
kubectl wait --for=condition=ready pod -l app=minio -n spark-demo --timeout=120s

echo "   [OK] MinIO deployed"
echo ""

# ============================================================
# 4. Create MinIO buckets
# ============================================================
echo "[INFO] [4/4] Creating MinIO buckets..."
echo "   Waiting for MinIO to fully start..."
sleep 10

# Use temporary Pod to run mc (MinIO Client) to create buckets
kubectl run minio-setup --rm -i --restart=Never \
    --namespace spark-demo \
    --image=minio/mc:latest \
    --command -- sh -c '
    mc alias set myminio http://minio-svc:9000 minioadmin minioadmin &&
    mc mb --ignore-existing myminio/spark-data &&
    mc mb --ignore-existing myminio/spark-logs &&
    echo "Buckets created successfully"
    '

echo "   [OK] buckets 'spark-data' and 'spark-logs' created"
echo ""

echo "=========================================="
echo "  [OK] Spark environment deployed successfully!"
echo "=========================================="
echo ""
echo "[INFO] Current cluster status:"
kubectl get pods -n spark-operator
echo ""
kubectl get pods -n spark-demo
echo ""
echo "[INFO] Common commands:"
echo "   kubectl get pods -n spark-demo                # View Pods"
echo "   kubectl port-forward svc/minio-svc 9001:9001 -n spark-demo  # Open MinIO UI"
echo "   # Then open http://localhost:9001 in browser (credentials: minioadmin/minioadmin)"
echo ""
echo "Next step: Run ./scripts/04-run-sparkpi.sh to execute the first Spark job!"
