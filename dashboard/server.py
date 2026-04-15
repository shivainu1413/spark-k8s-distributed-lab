"""
Dashboard Backend — Real-time Monitoring of K8s Pod Events + Spark API

Two data sources:
  1. kubectl get pods --watch: Real-time Pod creation/deletion detection
  2. Spark REST API (port 4040): Real-time Stage/Shuffle/Task status

Uses Server-Sent Events (SSE) to push updates to frontend, no frontend polling needed
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
import json
import urllib.request
import subprocess
import threading
import time
import os
import re

# ============================================================
# Global State
# ============================================================
state = {
    "pods": {},          # pod_name -> {name, status, role, age, ready}
    "spark": {           # Spark API data
        "connected": False,
        "app_id": None,
        "jobs": [],
        "stages": [],
        "executors": [],
    },
    "events": [],        # Recent events list [{time, type, message}]
}
state_lock = threading.Lock()

NAMESPACE = os.environ.get("NAMESPACE", "spark-demo")
SPARK_DRIVER_HOST = os.environ.get("SPARK_DRIVER_HOST", "localhost")
SPARK_DRIVER_PORT = os.environ.get("SPARK_DRIVER_PORT", "4040")

# ============================================================
# K8s Pod Watcher — Use kubectl to monitor Pod changes in real-time
# ============================================================
def watch_pods():
    """Background thread: Poll pod status every second (more reliable than --watch, detects pod deletion)"""
    while True:
        try:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", NAMESPACE, "-o", "json"],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                current_pods = {}

                for obj in data.get("items", []):
                    process_pod_event(obj)
                    name = obj.get("metadata", {}).get("name", "")
                    current_pods[name] = True

                # Detect deleted pods — mark as removing, keep for a few seconds for frontend fade-out
                with state_lock:
                    deleted = [name for name in state["pods"]
                               if name not in current_pods
                               and state["pods"][name].get("status") != "removing"]
                    for name in deleted:
                        old_pod = state["pods"][name]
                        role = old_pod.get("role", "unknown")
                        if role in ("executor", "driver"):
                            add_event("pod", f"[OK] {role.capitalize()} Pod [{name}] destroyed")
                        state["pods"][name]["status"] = "removing"
                        state["pods"][name]["removeAt"] = time.time() + 5  # Remove after 5 seconds

                    # Clean up expired removing pods
                    expired = [name for name in state["pods"]
                               if state["pods"][name].get("status") == "removing"
                               and time.time() > state["pods"][name].get("removeAt", 0)]
                    for name in expired:
                        del state["pods"][name]

        except Exception as e:
            pass

        time.sleep(0.8)


def process_pod_event(obj):
    """Process a pod event"""
    metadata = obj.get("metadata", {})
    status_obj = obj.get("status", {})
    name = metadata.get("name", "unknown")
    labels = metadata.get("labels", {})

    # Determine role
    role = "unknown"
    if "spark-role" in labels:
        role = labels["spark-role"]  # driver or executor
    elif "app" in labels and labels["app"] == "minio":
        role = "minio"
    elif "app" in labels and labels["app"] == "spark-history":
        role = "history"
    elif "app" in labels and labels["app"] == "jupyter-spark":
        role = "jupyter"
    elif name.startswith("spark-operator"):
        role = "operator"

    # Pod status
    phase = status_obj.get("phase", "Unknown")
    container_statuses = status_obj.get("containerStatuses", [])
    ready = all(c.get("ready", False) for c in container_statuses) if container_statuses else False

    # Get creation time
    creation = metadata.get("creationTimestamp", "")

    with state_lock:
        old_status = state["pods"].get(name, {}).get("status")

        state["pods"][name] = {
            "name": name,
            "status": phase,
            "role": role,
            "ready": ready,
            "created": creation,
            "labels": labels,
        }

        # Generate events
        if old_status != phase:
            if phase == "Running" and role == "driver":
                add_event("pod", f"[DRIVER] Driver Pod [{name}] started")
            elif phase == "Running" and role == "executor":
                add_event("pod", f"[EXECUTOR] Executor Pod [{name}] started")
            elif phase == "Succeeded" and role == "driver":
                add_event("pod", f"[OK] Driver Pod [{name}] completed")
            elif phase == "Succeeded" and role == "executor":
                add_event("pod", f"[OK] Executor Pod [{name}] destroyed")
            elif phase == "Pending" and role in ("driver", "executor"):
                add_event("pod", f"[PENDING] {role.capitalize()} Pod [{name}] creating...")
            elif phase == "Failed":
                add_event("pod", f"[ERROR] Pod [{name}] failed")


# ============================================================
# Spark API Poller — Poll Driver's REST API
# ============================================================
def poll_spark_api():
    """Background thread: Continuously poll Spark Driver API"""
    while True:
        try:
            # Find the running driver pod first
            driver_host = find_driver_host()

            if driver_host:
                base_url = f"http://{driver_host}:{SPARK_DRIVER_PORT}"
                apps = fetch_json(f"{base_url}/api/v1/applications")

                if apps and len(apps) > 0:
                    app_id = apps[0]["id"]

                    with state_lock:
                        was_connected = state["spark"]["connected"]
                        state["spark"]["connected"] = True
                        state["spark"]["app_id"] = app_id

                        if not was_connected:
                            add_event("spark", "[OK] Connected to Spark Driver API")

                    # Fetch jobs
                    jobs = fetch_json(f"{base_url}/api/v1/applications/{app_id}/jobs") or []
                    # Fetch stages
                    stages = fetch_json(f"{base_url}/api/v1/applications/{app_id}/stages") or []
                    # Fetch executors
                    executors = fetch_json(f"{base_url}/api/v1/applications/{app_id}/executors") or []

                    with state_lock:
                        old_stages = {s["stageId"]: s for s in state["spark"]["stages"]}

                        state["spark"]["jobs"] = [
                            {"jobId": j["jobId"], "status": j["status"],
                             "numTasks": j.get("numTasks", 0),
                             "numCompletedTasks": j.get("numCompletedTasks", 0),
                             "stageIds": j.get("stageIds", [])}
                            for j in jobs[:20]
                        ]

                        new_stages = []
                        for s in stages[:20]:
                            stage = {
                                "stageId": s["stageId"],
                                "name": s.get("name", ""),
                                "status": s["status"],
                                "numTasks": s.get("numTasks", 0),
                                "numCompleteTasks": s.get("numCompleteTasks", 0),
                                "inputBytes": s.get("inputBytes", 0),
                                "outputBytes": s.get("outputBytes", 0),
                                "shuffleReadBytes": s.get("shuffleReadBytes", 0),
                                "shuffleWriteBytes": s.get("shuffleWriteBytes", 0),
                            }
                            new_stages.append(stage)

                            # Detect shuffle events
                            old = old_stages.get(s["stageId"])
                            if old:
                                if s.get("shuffleWriteBytes", 0) > 0 and old.get("shuffleWriteBytes", 0) == 0:
                                    add_event("shuffle", f"[SHUFFLE] Stage {s['stageId']} triggered — data exchange between executors")

                            # Detect stage completion
                            if s["status"] == "COMPLETE" and (not old or old["status"] != "COMPLETE"):
                                desc = s.get("name", f"Stage {s['stageId']}")
                                add_event("stage", f"[OK] Stage {s['stageId']} completed ({desc})")

                        state["spark"]["stages"] = new_stages

                        state["spark"]["executors"] = [
                            {"id": e["id"],
                             "isActive": e.get("isActive", False),
                             "totalTasks": e.get("totalTasks", 0),
                             "activeTasks": e.get("activeTasks", 0),
                             "completedTasks": e.get("completedTasks", 0),
                             "totalShuffleRead": e.get("totalShuffleRead", 0),
                             "totalShuffleWrite": e.get("totalShuffleWrite", 0),
                             "totalInputBytes": e.get("totalInputBytes", 0),
                             "totalOutputBytes": e.get("totalOutputBytes", 0),
                             "memoryUsed": e.get("memoryUsed", 0),
                             "maxMemory": e.get("maxMemory", 0)}
                            for e in executors
                        ]

                else:
                    with state_lock:
                        if state["spark"]["connected"]:
                            add_event("spark", "[DISCONNECT] Spark Driver disconnected")
                        state["spark"]["connected"] = False
            else:
                with state_lock:
                    if state["spark"]["connected"]:
                        add_event("spark", "[DISCONNECT] Spark Driver disconnected")
                    state["spark"]["connected"] = False

        except Exception as e:
            pass

        time.sleep(1)  # Poll every second


port_forward_proc = None

def find_driver_host():
    """Find the running Spark Driver and use port-forward to connect"""
    global port_forward_proc

    try:
        # First, find Jupyter Pod (Client Mode Driver)
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", NAMESPACE,
             "-l", "app=jupyter-spark",
             "--field-selector", "status.phase=Running",
             "-o", "jsonpath={.items[0].metadata.name}"],
            capture_output=True, text=True, timeout=5
        )
        pod_name = result.stdout.strip()

        # If no Jupyter, find Cluster Mode Driver
        if not pod_name:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", NAMESPACE,
                 "-l", "spark-role=driver",
                 "--field-selector", "status.phase=Running",
                 "-o", "jsonpath={.items[0].metadata.name}"],
                capture_output=True, text=True, timeout=5
            )
            pod_name = result.stdout.strip()

        if not pod_name:
            # Driver not running, clean up port-forward
            if port_forward_proc:
                port_forward_proc.kill()
                port_forward_proc = None
            return None

        # If no port-forward yet, create one
        if port_forward_proc is None or port_forward_proc.poll() is not None:
            # Kill old one first
            if port_forward_proc:
                try: port_forward_proc.kill()
                except: pass

            port_forward_proc = subprocess.Popen(
                ["kubectl", "port-forward", pod_name,
                 f"{SPARK_DRIVER_PORT}:4040", "-n", NAMESPACE],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(3)

            test = fetch_json(f"http://localhost:{SPARK_DRIVER_PORT}/api/v1/applications")
            if not test:
                return None
            add_event("spark", f"[OK] Connected to Spark Driver API")

        return "localhost"

    except Exception as e:
        return None


def fetch_json(url, timeout=3):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except:
        return None


def add_event(type, message):
    """Add event to event list"""
    event = {
        "time": time.strftime("%H:%M:%S"),
        "timestamp": time.time(),
        "type": type,
        "message": message,
    }
    state["events"].append(event)
    # Keep only the last 50 events
    if len(state["events"]) > 50:
        state["events"] = state["events"][-50:]
    print(f"  [{event['time']}] {message}")


# ============================================================
# HTTP Handler
# ============================================================
class DashboardHandler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)

    def do_GET(self):
        if self.path == "/api/state":
            with state_lock:
                data = json.dumps(state)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data.encode())

        elif self.path == "/api/events":
            # SSE endpoint
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            last_event_count = 0
            try:
                while True:
                    with state_lock:
                        if len(state["events"]) > last_event_count:
                            new_events = state["events"][last_event_count:]
                            last_event_count = len(state["events"])
                            for evt in new_events:
                                data = json.dumps(evt)
                                self.wfile.write(f"data: {data}\n\n".encode())
                            self.wfile.flush()
                    time.sleep(0.5)
            except (BrokenPipeError, ConnectionResetError):
                pass

        else:
            if self.path == "/":
                self.path = "/index.html"
            super().do_GET()

    def log_message(self, format, *args):
        if "/api/" not in str(args):
            super().log_message(format, *args)


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))

    add_event("system", "Dashboard started")
    add_event("system", f"Watching namespace: {NAMESPACE}")

    # Start Pod watcher
    t1 = threading.Thread(target=watch_pods, daemon=True)
    t1.start()
    print("[INFO] Pod watcher started")

    # Start Spark API poller
    t2 = threading.Thread(target=poll_spark_api, daemon=True)
    t2.start()
    print("[INFO] Spark API poller started")

    # Start HTTP server
    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    server = ThreadedHTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"[INFO] Dashboard: http://localhost:{port}")
    server.serve_forever()
