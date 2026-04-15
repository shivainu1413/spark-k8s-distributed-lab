#!/bin/bash
# ============================================================
# Step 1: Install Local Development Tools (macOS)
#
# This script will help you install:
#   - minikube   : Local K8s cluster
#   - kubectl    : K8s CLI tool (for communicating with cluster)
#   - helm       : K8s package manager (similar to pip/npm)
#
# Usage: chmod +x scripts/01-install-tools.sh && ./scripts/01-install-tools.sh
# ============================================================

set -e  # Stop if any command fails

echo "=========================================="
echo "  Spark on K8s Project - Tool Installation"
echo "=========================================="

# --- Check Homebrew ---
if ! command -v brew &> /dev/null; then
    echo "[ERROR] Please install Homebrew first: https://brew.sh"
    exit 1
fi
echo "[OK] Homebrew installed"

# --- Check Docker ---
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "[ERROR] Docker Desktop is not running, please start it"
    exit 1
fi
echo "[OK] Docker installed and running"

# --- Install minikube ---
if command -v minikube &> /dev/null; then
    echo "[OK] minikube installed ($(minikube version --short))"
else
    echo "[INFO] Installing minikube..."
    brew install minikube
    echo "[OK] minikube installation complete ($(minikube version --short))"
fi

# --- Install kubectl ---
if command -v kubectl &> /dev/null; then
    echo "[OK] kubectl installed ($(kubectl version --client --short 2>/dev/null || kubectl version --client -o yaml | grep gitVersion | head -1))"
else
    echo "[INFO] Installing kubectl..."
    brew install kubectl
    echo "[OK] kubectl installation complete"
fi

# --- Install helm ---
if command -v helm &> /dev/null; then
    echo "[OK] Helm installed ($(helm version --short))"
else
    echo "[INFO] Installing Helm..."
    brew install helm
    echo "[OK] Helm installation complete ($(helm version --short))"
fi

echo ""
echo "=========================================="
echo "  [OK] All tools installed successfully!"
echo "=========================================="
echo ""
echo "Next step: Execute ./scripts/02-start-cluster.sh to start K8s cluster"
