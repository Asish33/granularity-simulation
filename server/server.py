"""
=============================================================
  GRANULARITY OPTIMIZATION SERVER
  Run this on your PC. All phones connect to this.
=============================================================
  HOW TO RUN:
    1. pip install flask numpy pillow
    2. python server.py
    3. Open browser at http://localhost:5000
    4. On each phone, open the Android app and enter your PC's IP
=============================================================
"""

from flask import Flask, request, jsonify, render_template_string
import numpy as np
import time
import uuid
import threading
import json
import base64
import io
import os
from PIL import Image, ImageFilter

app = Flask(__name__)

# ── Global State ────────────────────────────────────────────
workers = {}          # phone_id -> {ip, name, status, specs}
jobs = {}             # job_id -> full job info
results = {}          # job_id -> list of subtask results
granularity_log = []  # list of {G, makespan, ccr, cluster_size}
lock = threading.Lock()

# ── HTML Dashboard (runs in browser on PC) ──────────────────
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Granularity Optimizer - Control Center</title>
  <style>
    body { font-family: monospace; background: #050810; color: #c8d8f0; padding: 20px; }
    h1 { color: #00d4ff; font-size: 1.4rem; margin-bottom: 4px; }
    h2 { color: #7fff6e; font-size: 1rem; margin: 20px 0 8px; }
    .subtitle { color: #4a6080; font-size: 0.8rem; margin-bottom: 20px; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
    th { background: #0c1120; color: #00d4ff; padding: 8px 12px; text-align: left; font-size: 0.8rem; border: 1px solid #1e2d4a; }
    td { padding: 8px 12px; border: 1px solid #1e2d4a; font-size: 0.8rem; }
    tr:nth-child(even) { background: #0a0f1a; }
    .online  { color: #7fff6e; } .idle { color: #ffcc00; } .busy { color: #ff6b35; }
    .btn { background: #00d4ff; color: #050810; border: none; padding: 10px 20px;
           font-family: monospace; font-weight: bold; cursor: pointer; margin: 4px; border-radius: 3px; font-size: 0.85rem; }
    .btn:hover { background: #7fff6e; }
    .btn-red { background: #ff6b35; }
    .card { background: #0c1120; border: 1px solid #1e2d4a; padding: 16px; margin-bottom: 16px; border-radius: 4px; }
    .metric { display: inline-block; margin-right: 30px; }
    .metric-val { font-size: 1.6rem; color: #00d4ff; font-weight: bold; }
    .metric-lbl { font-size: 0.7rem; color: #4a6080; display: block; }
    .result-ok  { color: #7fff6e; } .result-fail { color: #ff4444; }
    select, input[type=number] { background: #0c1120; color: #c8d8f0; border: 1px solid #1e2d4a; padding: 6px 10px; font-family: monospace; border-radius: 3px; }
    .log-entry { font-size: 0.75rem; color: #4a6080; border-bottom: 1px solid #0f1928; padding: 4px 0; }
    .highlight { color: #ff6b35; }
    form { display: inline; }
  </style>
</head>
<body>
<h1>🔬 Granularity Optimization – Distributed Mobile Clusters</h1>
<button onclick="location.reload()" class="btn" style="float:right;">
  🔄 Refresh
</button>
<div class="subtitle">SRM University AP &nbsp;|&nbsp; PC Control Center &nbsp;|&nbsp; Auto-refreshes every 3s</div>

<!-- Live Metrics -->
<div class="card">
  <span class="metric"><span class="metric-val">{{ workers|length }}</span><span class="metric-lbl">CONNECTED PHONES</span></span>
  <span class="metric"><span class="metric-val">{{ jobs|length }}</span><span class="metric-lbl">JOBS SUBMITTED</span></span>
  <span class="metric"><span class="metric-val">{{ optimal_g }}</span><span class="metric-lbl">OPTIMAL G RANGE</span></span>
  <span class="metric"><span class="metric-val">{{ total_tasks }}</span><span class="metric-lbl">TASKS COMPLETED</span></span>
</div>

<!-- Connected Phones -->
<h2>📱 Connected Worker Phones</h2>
{% if workers %}
<table>
  <tr><th>Phone Name</th><th>IP Address</th><th>Status</th><th>CPU (MIPS est.)</th><th>Battery %</th><th>Tasks Done</th><th>Last Seen</th></tr>
  {% for wid, w in workers.items() %}
  <tr>
    <td>{{ w.name }}</td>
    <td>{{ w.ip }}</td>
    <td class="{{ w.status }}">● {{ w.status.upper() }}</td>
    <td>{{ w.cpu_mips }}</td>
    <td>{{ w.battery }}%</td>
    <td>{{ w.tasks_done }}</td>
    <td>{{ w.last_seen }}</td>
  </tr>
  {% endfor %}
</table>
{% else %}
<p style="color:#4a6080; font-size:0.85rem">⏳ No phones connected yet. Open the Android app on each phone and enter this PC's IP address.</p>
{% endif %}

<!-- Submit Job -->
<h2>🚀 Submit a Job</h2>
<div class="card">
  <form action="/submit_job" method="POST">
    <label>Task Type: 
      <select name="task_type">
        <option value="matrix">Matrix Multiplication</option>
        <option value="image">Image Processing (Blur)</option>
        <option value="mixed">Mixed (Matrix + Image)</option>
      </select>
    </label>
    &nbsp;&nbsp;
    <label>Granularity G = 
      <select name="granularity">
        <option value="0.1">0.1 (Very Fine)</option>
        <option value="0.5">0.5 (Fine)</option>
        <option value="1.0">1.0 (Fine-Medium)</option>
        <option value="2.0" selected>2.0 (Medium)</option>
        <option value="5.0">5.0 (Medium-Coarse)</option>
        <option value="10.0">10.0 (Coarse)</option>
        <option value="50.0">50.0 (Very Coarse)</option>
        <option value="100.0">100.0 (Extremely Coarse)</option>
      </select>
    </label>
    &nbsp;&nbsp;
    <label>Matrix Size: 
      <select name="matrix_size">
        <option value="64">64×64 (Small)</option>
        <option value="128" selected>128×128 (Medium)</option>
        <option value="256">256×256 (Large)</option>
        <option value="512">512×512 (Very Large)</option>
      </select>
    </label>
    &nbsp;&nbsp;
    <button class="btn" type="submit">▶ SUBMIT JOB</button>
  </form>
  &nbsp;&nbsp;
  <form action="/auto_sweep" method="POST">
    <button class="btn" type="submit" style="background:#7fff6e">⚡ AUTO GRANULARITY SWEEP</button>
  </form>
</div>

<!-- Granularity Results -->
<h2>📊 Granularity vs Makespan Results</h2>
{% if granularity_log %}
<table>
  <tr><th>G Value</th><th>Task Type</th><th>Makespan (ms)</th><th>CCR</th><th>Phones Used</th><th>Throughput (tasks/s)</th><th>Optimal?</th></tr>
  {% for entry in granularity_log|reverse %}
  <tr>
    <td>{{ entry.G }}</td>
    <td>{{ entry.task_type }}</td>
    <td>{{ entry.makespan_ms }}</td>
    <td>{{ entry.ccr }}</td>
    <td>{{ entry.phones_used }}</td>
    <td>{{ entry.throughput }}</td>
    <td>{% if entry.is_optimal %}<span class="result-ok">✓ OPTIMAL</span>{% else %}–{% endif %}</td>
  </tr>
  {% endfor %}
</table>
{% else %}
<p style="color:#4a6080; font-size:0.85rem">No results yet. Submit a job above to see granularity analysis.</p>
{% endif %}

<!-- Job Log -->
<h2>📋 Job History</h2>
{% if jobs %}
<table>
  <tr><th>Job ID</th><th>Type</th><th>G Value</th><th>Subtasks</th><th>Completed</th><th>Status</th><th>Makespan</th></tr>
  {% for jid, j in jobs.items()|list|reverse %}
  <tr>
    <td style="font-size:0.7rem">{{ jid[:8] }}…</td>
    <td>{{ j.task_type }}</td>
    <td>{{ j.granularity }}</td>
    <td>{{ j.total_subtasks }}</td>
    <td>{{ j.completed_subtasks }}</td>
    <td class="{% if j.status == 'done' %}result-ok{% elif j.status == 'running' %}idle{% else %}result-fail{% endif %}">
      {{ j.status.upper() }}
    </td>
    <td>{{ j.makespan_ms if j.makespan_ms else '—' }} ms</td>
  </tr>
  {% endfor %}
</table>
{% else %}
<p style="color:#4a6080; font-size:0.85rem">No jobs yet.</p>
{% endif %}

<hr style="border-color:#1e2d4a; margin: 20px 0">
<p style="color:#4a6080; font-size:0.75rem">
  Your PC IP (tell this to phones): <strong style="color:#00d4ff">{{ server_ip }}</strong> &nbsp;|&nbsp; Port: 5000
</p>
</body>
</html>
"""

# ── Helpers ──────────────────────────────────────────────────
def get_server_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def compute_optimal_g_range():
    if len(granularity_log) < 2:
        return "N/A"
    min_makespan = min(e["makespan_ms"] for e in granularity_log)
    threshold = min_makespan * 1.1
    optimal = [e["G"] for e in granularity_log if e["makespan_ms"] <= threshold]
    if not optimal:
        return "N/A"
    return f"{min(optimal)}–{max(optimal)}"

def split_matrix_job(matrix_size, granularity, num_workers):
    """Split a matrix multiplication job into subtasks based on granularity G."""
    G = float(granularity)
    # G = T_comp / T_comm
    # More workers + finer G = more subtasks
    if G <= 0.5:
        k = max(num_workers * 4, 8)   # very fine
    elif G <= 1.0:
        k = max(num_workers * 2, 4)
    elif G <= 5.0:
        k = max(num_workers, 2)        # medium (optimal zone)
    elif G <= 20.0:
        k = max(num_workers // 2, 1)
    else:
        k = 1                           # very coarse: single task

    subtasks = []
    rows_per_task = max(1, matrix_size // k)
    row = 0
    idx = 0
    while row < matrix_size:
        end_row = min(row + rows_per_task, matrix_size)
        subtasks.append({
            "subtask_id": idx,
            "type": "matrix",
            "start_row": row,
            "end_row": end_row,
            "matrix_size": matrix_size,
            "granularity": G
        })
        row = end_row
        idx += 1
    return subtasks

def split_image_job(granularity, num_workers):
    """Split image blur into tiles based on granularity."""
    G = float(granularity)
    if G <= 1.0:
        grid = 4   # 4x4 = 16 tiles (fine)
    elif G <= 5.0:
        grid = 2   # 2x2 = 4 tiles (medium)
    else:
        grid = 1   # 1x1 = 1 tile (coarse)

    subtasks = []
    idx = 0
    tile_size = 256 // grid
    for r in range(grid):
        for c in range(grid):
            subtasks.append({
                "subtask_id": idx,
                "type": "image",
                "tile_x": c * tile_size,
                "tile_y": r * tile_size,
                "tile_w": tile_size,
                "tile_h": tile_size,
                "granularity": G
            })
            idx += 1
    return subtasks

def assign_subtasks_heft(subtasks, workers_dict):
    """Modified HEFT: assign subtasks to workers by earliest finish time."""
    worker_ids = list(workers_dict.keys())
    if not worker_ids:
        return {}
    assignments = {}
    worker_load = {wid: 0 for wid in worker_ids}
    # Sort subtasks (simulate upward rank = workload / cpu_speed)
    for st in subtasks:
        # Pick worker with lowest current load, weighted by CPU speed
        best_worker = min(worker_ids, key=lambda wid: worker_load[wid] / max(workers_dict[wid].get("cpu_mips", 1000), 1))
        assignments[st["subtask_id"]] = best_worker
        worker_load[best_worker] += 1
    return assignments

# ── Routes ───────────────────────────────────────────────────

@app.route("/")
def dashboard():
    total_tasks = sum(j.get("completed_subtasks", 0) for j in jobs.values())
    return render_template_string(
        DASHBOARD_HTML,
        workers=workers,
        jobs=jobs,
        granularity_log=granularity_log,
        optimal_g=compute_optimal_g_range(),
        total_tasks=total_tasks,
        server_ip=get_server_ip()
    )

@app.route("/register", methods=["POST"])
def register_worker():
    """Phone calls this to register itself as a worker."""
    data = request.json
    worker_id = data.get("worker_id", str(uuid.uuid4()))
    with lock:
        workers[worker_id] = {
            "name": data.get("name", f"Phone-{len(workers)+1}"),
            "ip": request.remote_addr,
            "status": "idle",
            "cpu_mips": data.get("cpu_mips", 1000),
            "battery": data.get("battery", 100),
            "tasks_done": 0,
            "last_seen": time.strftime("%H:%M:%S")
        }
    print(f"[+] Worker registered: {workers[worker_id]['name']} ({request.remote_addr})")
    return jsonify({"status": "ok", "worker_id": worker_id, "message": "Welcome to the cluster!"})

@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    """Phone sends heartbeat to stay alive in cluster."""
    data = request.json
    wid = data.get("worker_id")
    with lock:
        if wid in workers:
            workers[wid]["last_seen"] = time.strftime("%H:%M:%S")
            workers[wid]["battery"] = data.get("battery", workers[wid]["battery"])
            workers[wid]["status"] = data.get("status", "idle")
    return jsonify({"status": "ok"})

@app.route("/get_task/<worker_id>", methods=["GET"])
def get_task(worker_id):
    """Phone polls this endpoint to get its next assigned task."""
    with lock:
        for job_id, job in jobs.items():
            if job["status"] != "running":
                continue
            for subtask in job["subtasks"]:
                if (subtask.get("assigned_to") == worker_id and
                        subtask.get("status") == "pending"):
                    subtask["status"] = "in_progress"
                    subtask["start_time"] = time.time()
                    if worker_id in workers:
                        workers[worker_id]["status"] = "busy"
                    return jsonify({
                        "has_task": True,
                        "job_id": job_id,
                        "subtask": subtask
                    })
    return jsonify({"has_task": False})

@app.route("/submit_result", methods=["POST"])
def submit_result():
    """Phone submits completed subtask result."""
    data = request.json
    job_id = data.get("job_id")
    subtask_id = data.get("subtask_id")
    worker_id = data.get("worker_id")
    computation_time_ms = data.get("computation_time_ms", 0)

    with lock:
        if job_id not in jobs:
            return jsonify({"status": "error", "message": "Unknown job"})

        job = jobs[job_id]
        for subtask in job["subtasks"]:
            if subtask["subtask_id"] == subtask_id:
                subtask["status"] = "done"
                subtask["computation_time_ms"] = computation_time_ms
                subtask["result_size_bytes"] = data.get("result_size_bytes", 0)
                break

        job["completed_subtasks"] += 1
        if worker_id in workers:
            workers[worker_id]["tasks_done"] += 1
            workers[worker_id]["status"] = "idle"

        # Check if job complete
        done = all(s["status"] == "done" for s in job["subtasks"])
        if done and job["status"] == "running":
            job["status"] = "done"
            job["end_time"] = time.time()
            makespan_ms = round((job["end_time"] - job["start_time"]) * 1000)
            job["makespan_ms"] = makespan_ms

            # Calculate CCR = total_comm_time / total_comp_time
            total_comp = sum(s.get("computation_time_ms", 1) for s in job["subtasks"])
            total_comm = max(makespan_ms - total_comp, 0)
            ccr = round(total_comm / max(total_comp, 1), 3)
            throughput = round(len(job["subtasks"]) / max(makespan_ms / 1000, 0.001), 2)

            # Log granularity result
            min_makespan = min((e["makespan_ms"] for e in granularity_log), default=makespan_ms)
            is_optimal = makespan_ms <= min_makespan * 1.1

            granularity_log.append({
                "G": job["granularity"],
                "task_type": job["task_type"],
                "makespan_ms": makespan_ms,
                "ccr": ccr,
                "phones_used": len(set(s.get("assigned_to","") for s in job["subtasks"])),
                "throughput": throughput,
                "is_optimal": is_optimal,
                "num_subtasks": len(job["subtasks"])
            })
            print(f"[✓] Job {job_id[:8]} done | G={job['granularity']} | Makespan={makespan_ms}ms | CCR={ccr}")

    return jsonify({"status": "ok"})

@app.route("/submit_job", methods=["POST"])
def submit_job():
    """Dashboard form submits a job."""
    task_type = request.form.get("task_type", "matrix")
    granularity = float(request.form.get("granularity", 2.0))
    matrix_size = int(request.form.get("matrix_size", 128))

    active_workers = {wid: w for wid, w in workers.items() if w["battery"] > 10}
    if not active_workers:
        return "<script>alert('No phones connected! Connect phones first.');history.back();</script>"

    job_id = str(uuid.uuid4())

    # Build subtask list
    subtasks = []
    if task_type == "matrix":
        subtasks = split_matrix_job(matrix_size, granularity, len(active_workers))
    elif task_type == "image":
        subtasks = split_image_job(granularity, len(active_workers))
    else:  # mixed
        subtasks += split_matrix_job(matrix_size, granularity, len(active_workers))
        subtasks += split_image_job(granularity, len(active_workers))
        for i, st in enumerate(subtasks):
            st["subtask_id"] = i

    # HEFT assignment
    assignments = assign_subtasks_heft(subtasks, active_workers)
    for st in subtasks:
        st["assigned_to"] = assignments.get(st["subtask_id"], list(active_workers.keys())[0])
        st["status"] = "pending"

    with lock:
        jobs[job_id] = {
            "job_id": job_id,
            "task_type": task_type,
            "granularity": granularity,
            "matrix_size": matrix_size,
            "subtasks": subtasks,
            "total_subtasks": len(subtasks),
            "completed_subtasks": 0,
            "status": "running",
            "start_time": time.time(),
            "end_time": None,
            "makespan_ms": None
        }

    print(f"[+] Job submitted: {task_type} | G={granularity} | {len(subtasks)} subtasks → {len(active_workers)} phones")
    return "<script>window.location='/';</script>"

@app.route("/auto_sweep", methods=["POST"])
def auto_sweep():
    """Submit jobs at multiple granularity levels automatically."""
    active_workers = {wid: w for wid, w in workers.items() if w["battery"] > 10}
    if not active_workers:
        return "<script>alert('No phones connected!');history.back();</script>"

    def run_sweep():
        for G in [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 50.0]:
            # Submit matrix job at each G
            subtasks = split_matrix_job(128, G, len(active_workers))
            assignments = assign_subtasks_heft(subtasks, active_workers)
            for st in subtasks:
                st["assigned_to"] = assignments.get(st["subtask_id"], list(active_workers.keys())[0])
                st["status"] = "pending"

            job_id = str(uuid.uuid4())
            with lock:
                jobs[job_id] = {
                    "job_id": job_id, "task_type": "matrix", "granularity": G,
                    "matrix_size": 128, "subtasks": subtasks,
                    "total_subtasks": len(subtasks), "completed_subtasks": 0,
                    "status": "running", "start_time": time.time(),
                    "end_time": None, "makespan_ms": None
                }
            time.sleep(8)  # wait for phones to complete before next

    threading.Thread(target=run_sweep, daemon=True).start()
    return "<script>alert('Auto sweep started! Watch results appear.');window.location='/';</script>"

@app.route("/api/status")
def api_status():
    """Phone can poll this for cluster status."""
    return jsonify({
        "workers": len(workers),
        "jobs": len(jobs),
        "server_time": time.strftime("%H:%M:%S")
    })

if __name__ == "__main__":
    ip = get_server_ip()
    print("=" * 60)
    print("  GRANULARITY OPTIMIZATION SERVER")
    print("  SRM University AP – Distributed Mobile Clusters")
    print("=" * 60)
    print(f"  Dashboard : http://localhost:5000")
    print(f"  Your IP   : {ip}")
    print(f"  Tell phones to connect to: {ip}:5000")
    print("=" * 60)
    import logging

    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    app.run(host="0.0.0.0", port=5000, debug=False)
    app.run(host="0.0.0.0", port=5000, debug=False)
