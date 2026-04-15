# K8s Fundamentals Learning Guide

You already understand Docker (containers). Now you need to learn how K8s "manages" these containers.

## Core Concepts Reference

| K8s Concept | Familiar Equivalent | Explanation |
|----------|--------------|------|
| **Pod** | `docker run` | Minimal unit for running a container |
| **Deployment** | `docker-compose` `replicas` | Manages multiple identical Pods, auto-replaces failed ones |
| **Service** | `docker-compose` `ports` | Provides stable network entry point for Pods |
| **Namespace** | Folder | Isolates resources for different projects |
| **ConfigMap** | `.env` file | Stores configuration values injected into Pods |

## Learning Order

### Exercise 1: Pod (10 minutes)

```bash
# Create a Pod
kubectl apply -f 01-simple-pod.yaml

# Observe Pod status (STATUS will transition from ContainerCreating -> Running)
kubectl get pods -n spark-demo -w    # -w is watch mode, updates in real-time

# View Pod details (check Events section to see what K8s did)
kubectl describe pod nginx -n spark-demo

# Enter the Pod (like docker exec)
kubectl exec -it nginx -n spark-demo -- /bin/sh
# Once inside, you can curl localhost to check if nginx responds, exit to leave

# Delete the Pod
kubectl delete pod nginx -n spark-demo

# Check pods again - Pod is gone and won't automatically restart
# This is why we need Deployment
```

### Exercise 2: Deployment (15 minutes)

```bash
# Create Deployment (automatically creates 3 Pods)
kubectl apply -f 02-deployment.yaml

# View 3 Pods being created
kubectl get pods -n spark-demo

# Key experiment: Manually delete one Pod
kubectl delete pod <copy-one-pod-name> -n spark-demo

# Immediately check Pod list - K8s auto-replaces it!
kubectl get pods -n spark-demo
# You'll see a new Pod (different name, short AGE)

# Try scaling: change from 3 to 5 Pods
kubectl scale deployment nginx-deployment --replicas=5 -n spark-demo
kubectl get pods -n spark-demo    # Now 5 Pods

# Scale down to 2 Pods
kubectl scale deployment nginx-deployment --replicas=2 -n spark-demo
kubectl get pods -n spark-demo    # Extra Pods automatically terminated
```

### Exercise 3: Service (10 minutes)

```bash
# First, ensure Deployment is running
kubectl get deployment -n spark-demo

# Create Service
kubectl apply -f 03-service.yaml

# View Service
kubectl get service -n spark-demo

# Open browser with Minikube
minikube service nginx-svc -n spark-demo

# You should see nginx welcome page!
```

## After completing these three exercises you will understand

1. How K8s runs containers (Pod)
2. How K8s ensures service continuity (Deployment self-healing)
3. How K8s makes services discoverable (Service)

These three concepts map directly to Spark on K8s:
- Spark Driver = one Pod
- Spark Executors = multiple Pods managed by Deployment
- Driver connection endpoint = Service

## Cleanup

```bash
kubectl delete -f 03-service.yaml
kubectl delete -f 02-deployment.yaml
kubectl delete -f 01-simple-pod.yaml
```
