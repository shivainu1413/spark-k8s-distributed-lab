#!/bin/bash
# ============================================================
# Step 2: Start Minikube K8s Cluster
#
# This will create a virtual K8s cluster (single Node) on your Mac
# All Spark Pods will run in this cluster
#
# Usage: ./scripts/02-start-cluster.sh
# ============================================================

set -e

echo "=========================================="
echo "  Starting Minikube K8s Cluster"
echo "=========================================="

# --- Set cluster specifications ---
# Your Mac has 8GB RAM, macOS itself needs ~3-4GB
# So allocate 4GB to cluster, leaving rest for system
CPUS=2          # Allocate 2 cores to cluster (save some for macOS)
MEMORY=4096     # Allocate 4GB memory (first set Docker Desktop Memory to 6GB)
DISK="20g"      # Allocate 20GB disk space

echo ""
echo "[INFO] Cluster specifications:"
echo "   CPU:    ${CPUS} cores"
echo "   Memory: $((MEMORY / 1024)) GB"
echo "   Disk:   ${DISK}"
echo ""

# --- Check if cluster is already running ---
if minikube status --format='{{.Host}}' 2>/dev/null | grep -q "Running"; then
    echo "[WARN] Minikube cluster is already running"
    echo "   To rebuild, first run: minikube delete"
    echo ""
    minikube status
    exit 0
fi

# --- Start cluster ---
echo "[INFO] Starting Minikube cluster (may take 2-5 minutes)..."
echo ""

minikube start \
    --cpus=${CPUS} \
    --memory=${MEMORY} \
    --disk-size=${DISK} \
    --driver=docker \
    --kubernetes-version=stable

echo ""

# --- Enable common addons ---
echo "[INFO] Enabling K8s addons..."

# storage-provisioner: automatically creates PersistentVolume, MinIO needs it
# (Minikube enables it by default, this ensures it)
minikube addons enable storage-provisioner
echo "   [OK] storage-provisioner (storage management)"

# metrics-server and dashboard not enabled to save memory
# Enable later if needed:
#   minikube addons enable metrics-server
#   minikube addons enable dashboard
echo "   [INFO] metrics-server / dashboard disabled (save 8GB RAM resources)"
echo "         To enable: minikube addons enable dashboard"

echo ""

# --- Create project namespace ---
# namespace is like a folder, separates our resources from system resources
echo "[INFO] Creating spark-demo namespace..."
kubectl create namespace spark-demo --dry-run=client -o yaml | kubectl apply -f -
echo "   [OK] namespace 'spark-demo' created"

echo ""
echo "=========================================="
echo "  [OK] K8s cluster started successfully!"
echo "=========================================="
echo ""
echo "[INFO] Common commands:"
echo "   kubectl get nodes              # View Nodes (your Minikube VM)"
echo "   kubectl get pods -A            # View all Pods (-A = all namespaces)"
echo "   kubectl get pods -n spark-demo # View Pods in our namespace"
echo "   minikube dashboard             # Open K8s web management interface"
echo "   minikube stop                  # Stop cluster (keep data)"
echo "   minikube delete                # Delete cluster (start fresh)"
echo ""
echo "Next step: Try the commands above to learn kubectl!"
echo "           Then run ./scripts/03-deploy-spark.sh to deploy Spark"
